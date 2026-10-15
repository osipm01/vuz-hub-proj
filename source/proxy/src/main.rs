use std::{convert::Infallible, net::SocketAddr, sync::Arc, time::Duration};

use http_body_util::{BodyExt, Full, combinators::BoxBody};
use hyper::{
    Request, Response, StatusCode, Uri, Version,
    body::{Bytes, Incoming},
    header::{self, HeaderMap, HeaderName, HeaderValue},
    http::uri::{Authority, Scheme},
    server::conn::http1,
    service::service_fn,
};
use hyper_util::{
    client::legacy::{Client, connect::HttpConnector},
    rt::{TokioExecutor, TokioIo},
};
use serde::Deserialize;
use tokio::net::TcpListener;

type Body = BoxBody<Bytes, hyper::Error>;

// ---------------------------------------------------------------- конфиг

#[derive(Debug, Deserialize)]
struct Config {
    listen: String,
    #[serde(default = "default_timeout")]
    upstream_timeout_secs: u64,
    routes: Vec<RouteConfig>,
}

fn default_timeout() -> u64 {
    30
}

#[derive(Debug, Deserialize)]
struct RouteConfig {
    prefix: String,
    upstream: String,
    #[serde(default)]
    strip_prefix: bool,
}

// ------------------------------------------------------------- состояние

struct Route {
    prefix: String,
    strip_prefix: bool,
    scheme: Scheme,
    authority: Authority,
    base_path: String, // путь из upstream без завершающего '/'
}

struct State {
    routes: Vec<Route>, // отсортированы по длине префикса (длинные первыми)
    client: Client<HttpConnector, Incoming>,
    timeout: Duration,
}

impl Route {
    fn from_config(c: RouteConfig) -> Result<Self, String> {
        if !c.prefix.starts_with('/') {
            return Err(format!("prefix '{}' должен начинаться с '/'", c.prefix));
        }
        let uri: Uri = c
            .upstream
            .parse()
            .map_err(|e| format!("неверный upstream '{}': {e}", c.upstream))?;
        let scheme = uri.scheme().cloned().ok_or("в upstream нет схемы")?;
        if scheme != Scheme::HTTP {
            return Err(format!(
                "upstream '{}': поддерживается только http://",
                c.upstream
            ));
        }
        let authority = uri
            .authority()
            .cloned()
            .ok_or("в upstream нет host[:port]")?;
        Ok(Route {
            prefix: c.prefix,
            strip_prefix: c.strip_prefix,
            scheme,
            authority,
            base_path: uri.path().trim_end_matches('/').to_owned(),
        })
    }
}

/// Самый длинный префикс, совпадающий по границе сегмента.
fn pick_route<'r, 'p>(routes: &'r [Route], path: &'p str) -> Option<(&'r Route, &'p str)> {
    routes.iter().find_map(|r| {
        let rest = path.strip_prefix(r.prefix.as_str())?;
        let on_boundary = rest.is_empty() || rest.starts_with('/') || r.prefix.ends_with('/');
        on_boundary.then_some((r, rest))
    })
}

// ----------------------------------------------------------------- ошибки

enum ProxyError {
    NoRoute,
    Timeout,
    BadGateway(String),
}

impl ProxyError {
    fn into_response(self) -> Response<Body> {
        let (status, msg) = match self {
            ProxyError::NoRoute => (StatusCode::NOT_FOUND, "no route".to_string()),
            ProxyError::Timeout => (StatusCode::GATEWAY_TIMEOUT, "upstream timeout".to_string()),
            ProxyError::BadGateway(e) => {
                eprintln!("upstream error: {e}");
                (StatusCode::BAD_GATEWAY, "bad gateway".to_string())
            }
        };
        let mut resp = Response::new(full(msg));
        *resp.status_mut() = status;
        resp
    }
}

fn full(s: impl Into<Bytes>) -> Body {
    Full::new(s.into()).map_err(|never| match never {}).boxed()
}

// ---------------------------------------------------------- hop-by-hop

const HOP_BY_HOP: [&str; 8] = [
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
];

fn strip_hop_by_hop(h: &mut HeaderMap) {
    // заголовки, перечисленные в Connection, тоже hop-by-hop
    let extra: Vec<HeaderName> = h
        .get_all(header::CONNECTION)
        .iter()
        .filter_map(|v| v.to_str().ok())
        .flat_map(|s| s.split(','))
        .filter_map(|t| HeaderName::from_bytes(t.trim().as_bytes()).ok())
        .collect();
    for n in extra {
        h.remove(n);
    }
    for n in HOP_BY_HOP {
        h.remove(n);
    }
}

// ------------------------------------------------------------- проксирование

async fn proxy(
    mut req: Request<Incoming>,
    state: &State,
    peer: SocketAddr,
) -> Result<Response<Body>, ProxyError> {
    // 1. маршрут и новый путь
    let (route, new_uri) = {
        let path = req.uri().path();
        let (route, rest) = pick_route(&state.routes, path).ok_or(ProxyError::NoRoute)?;
        let tail = if route.strip_prefix { rest } else { path };

        let mut pq = route.base_path.clone();
        if !tail.starts_with('/') {
            pq.push('/');
        }
        pq.push_str(tail);
        if let Some(q) = req.uri().query() {
            pq.push('?');
            pq.push_str(q);
        }
        let uri = Uri::builder()
            .scheme(route.scheme.clone())
            .authority(route.authority.clone())
            .path_and_query(pq)
            .build()
            .map_err(|e| ProxyError::BadGateway(e.to_string()))?;
        (route, uri)
    };

    // 2. исходный Host — для X-Forwarded-Host
    let orig_host = req.headers().get(header::HOST).cloned().or_else(|| {
        req.uri()
            .authority()
            .and_then(|a| HeaderValue::from_str(a.as_str()).ok())
    });

    // 3. заголовки
    let headers = req.headers_mut();
    strip_hop_by_hop(headers);
    if let Ok(v) = HeaderValue::from_str(route.authority.as_str()) {
        headers.insert(header::HOST, v);
    }
    let xff = HeaderName::from_static("x-forwarded-for");
    let new_xff = match headers.get(&xff).and_then(|v| v.to_str().ok()) {
        Some(prev) => format!("{prev}, {}", peer.ip()),
        None => peer.ip().to_string(),
    };
    if let Ok(v) = HeaderValue::from_str(&new_xff) {
        headers.insert(xff, v);
    }
    if let Some(h) = orig_host {
        headers.insert(HeaderName::from_static("x-forwarded-host"), h);
    }
    headers.insert(
        HeaderName::from_static("x-forwarded-proto"),
        HeaderValue::from_static("http"),
    );

    *req.uri_mut() = new_uri;
    *req.version_mut() = Version::HTTP_11;

    // 4. запрос к upstream (тело стримится без буферизации)
    let resp = match tokio::time::timeout(state.timeout, state.client.request(req)).await {
        Err(_) => return Err(ProxyError::Timeout),
        Ok(Err(e)) => return Err(ProxyError::BadGateway(e.to_string())),
        Ok(Ok(r)) => r,
    };

    let (mut parts, body) = resp.into_parts();
    strip_hop_by_hop(&mut parts.headers);
    Ok(Response::from_parts(parts, body.boxed()))
}

async fn handle(
    req: Request<Incoming>,
    state: Arc<State>,
    peer: SocketAddr,
) -> Result<Response<Body>, Infallible> {
    let method = req.method().clone();
    let path = req.uri().path().to_owned();

    let resp = proxy(req, &state, peer)
        .await
        .unwrap_or_else(ProxyError::into_response);

    eprintln!("{peer} {method} {path} -> {}", resp.status().as_u16());
    Ok(resp)
}

// --------------------------------------------------------------------- main

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let cfg_path = std::env::args()
        .nth(1)
        .unwrap_or_else(|| "config.toml".into());
    let cfg: Config = toml::from_str(&std::fs::read_to_string(&cfg_path)?)?;

    let mut routes = cfg
        .routes
        .into_iter()
        .map(Route::from_config)
        .collect::<Result<Vec<_>, _>>()?;
    routes.sort_by(|a, b| b.prefix.len().cmp(&a.prefix.len()));

    let state = Arc::new(State {
        routes,
        client: Client::builder(TokioExecutor::new()).build_http(),
        timeout: Duration::from_secs(cfg.upstream_timeout_secs),
    });

    let listener = TcpListener::bind(&cfg.listen).await?;
    eprintln!("proxy listening on http://{}", cfg.listen);

    loop {
        tokio::select! {
            _ = tokio::signal::ctrl_c() => {
                eprintln!("shutting down");
                return Ok(());
            }
            accepted = listener.accept() => {
                let (stream, peer) = match accepted {
                    Ok(x) => x,
                    Err(e) => { eprintln!("accept error: {e}"); continue; }
                };
                let state = state.clone();
                tokio::spawn(async move {
                    let svc = service_fn(move |req| handle(req, state.clone(), peer));
                    if let Err(e) = http1::Builder::new()
                        .serve_connection(TokioIo::new(stream), svc)
                        .await
                    {
                        eprintln!("connection error: {e}");
                    }
                });
            }
        }
    }
}
