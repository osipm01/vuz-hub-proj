#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("build", "up", "down", "stop", "restart", "logs", "status", "clean", "local", "help")]
    [string]$Command,

    [Parameter(Position = 1)]
    [string]$Service
)

$ErrorActionPreference = "Stop"

# Список сервисов
$Services = @("monolith", "auth-service", "study-service", "finance-service", "integration-service")

# Маппинг сервис -> порт
$Ports = @{
    "monolith"          = 8000
    "auth-service"      = 8001
    "study-service"     = 8002
    "finance-service"   = 8003
    "integration-service" = 8004
}

function Show-Usage {
    Write-Host "Использование: .\run.ps1 <command> [service]" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Команды:" -ForegroundColor Yellow
    Write-Host "  build     [service]   Собрать Docker-образы"
    Write-Host "  up        [service]   Запустить сервисы (detached)"
    Write-Host "  down                  Остановить и удалить контейнеры"
    Write-Host "  stop      [service]   Остановить сервисы (без удаления)"
    Write-Host "  restart   [service]   Перезапустить сервисы"
    Write-Host "  logs      [service]   Показать логи (--follow)"
    Write-Host "  status                Статус контейнеров"
    Write-Host "  clean                 Удалить контейнеры, образы и volumes"
    Write-Host "  local     <service>   Запустить сервис локально через uvicorn"
    Write-Host "  help                  Показать эту справку"
    Write-Host ""
    Write-Host "Доступные сервисы:" -ForegroundColor Yellow
    Write-Host "  $($Services -join ', ')" -ForegroundColor Green
    Write-Host ""
    Write-Host "Примеры:" -ForegroundColor Yellow
    Write-Host "  .\run.ps1 up                       # запустить все"
    Write-Host "  .\run.ps1 up auth-service          # запустить только auth"
    Write-Host "  .\run.ps1 logs finance-service     # логи finance"
    Write-Host "  .\run.ps1 local study-service      # локально на :8002"
}

function Test-Service {
    param([string]$svc)
    if (-not $Services.Contains($svc)) {
        Write-Host "Ошибка: неизвестный сервис '$svc'" -ForegroundColor Red
        Write-Host "Доступные: $($Services -join ', ')" -ForegroundColor Green
        exit 1
    }
}

function Invoke-Build {
    param([string]$svc)
    if ($svc) {
        Test-Service $svc
        Write-Host "Сборка образа для $svc..." -ForegroundColor Blue
        docker compose build $svc
    } else {
        Write-Host "Сборка всех образов..." -ForegroundColor Blue
        docker compose build
    }
}

function Invoke-Up {
    param([string]$svc)
    if ($svc) {
        Test-Service $svc
        Write-Host "Запуск $svc..." -ForegroundColor Green
        docker compose up -d $svc
    } else {
        Write-Host "Запуск всех сервисов..." -ForegroundColor Green
        docker compose up -d
    }
    Invoke-Status
}

function Invoke-Down {
    Write-Host "Остановка и удаление контейнеров..." -ForegroundColor Yellow
    docker compose down
}

function Invoke-Stop {
    param([string]$svc)
    if ($svc) {
        Test-Service $svc
        docker compose stop $svc
    } else {
        docker compose stop
    }
}

function Invoke-Restart {
    param([string]$svc)
    if ($svc) {
        Test-Service $svc
        docker compose restart $svc
    } else {
        docker compose restart
    }
}

function Invoke-Logs {
    param([string]$svc)
    if ($svc) {
        Test-Service $svc
        docker compose logs -f $svc
    } else {
        docker compose logs -f
    }
}

function Invoke-Status {
    Write-Host "=== Статус контейнеров ===" -ForegroundColor Cyan
    docker compose ps
}

function Invoke-Clean {
    Write-Host "Полная очистка: контейнеры, образы, volumes..." -ForegroundColor Red
    docker compose down -v --rmi local --remove-orphans
    Write-Host "Готово." -ForegroundColor Green
}

function Invoke-Local {
    param([string]$svc)
    if (-not $svc) {
        Write-Host "Ошибка: укажите сервис" -ForegroundColor Red
        Show-Usage
        exit 1
    }
    Test-Service $svc

    $port = $Ports[$svc]
    Write-Host "Локальный запуск $svc на порту $port (SERVICE_NAME=$svc)" -ForegroundColor Blue
    Write-Host "Ctrl+C для остановки" -ForegroundColor Yellow

    $env:SERVICE_NAME = $svc
    $env:PORT = $port

    try {
        uvicorn main:app --host 127.0.0.1 --port $port --reload
    } finally {
        Remove-Item Env:\SERVICE_NAME -ErrorAction SilentlyContinue
        Remove-Item Env:\PORT -ErrorAction SilentlyContinue
    }
}

# ===== Основная логика =====
if (-not $Command -or $Command -eq "help") {
    Show-Usage
    exit 0
}

switch ($Command) {
    "build"   { Invoke-Build   $Service }
    "up"      { Invoke-Up      $Service }
    "down"    { Invoke-Down }
    "stop"    { Invoke-Stop    $Service }
    "restart" { Invoke-Restart $Service }
    "logs"    { Invoke-Logs    $Service }
    "status"  { Invoke-Status }
    "clean"   { Invoke-Clean }
    "local"   { Invoke-Local   $Service }
    default {
        Write-Host "Неизвестная команда: $Command" -ForegroundColor Red
        Show-Usage
        exit 1
    }
}
