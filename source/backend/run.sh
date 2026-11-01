#!/usr/bin/env bash
set -euo pipefail

# ===== Цвета =====
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ===== Список сервисов =====
SERVICES=(monolith auth-service study-service finance-service integration-service)

# ===== Справка =====
usage() {
    cat <<EOF
${CYAN}Использование:${NC} $0 <command> [service]

${YELLOW}Команды:${NC}
  build     [service]   Собрать Docker-образы
  up        [service]   Запустить сервисы (detached)
  down                  Остановить и удалить контейнеры
  stop      [service]   Остановить сервисы (без удаления)
  restart   [service]   Перезапустить сервисы
  logs      [service]   Показать логи (--follow)
  status                Статус контейнеров
  clean                 Удалить контейнеры, образы и volumes
  local     <service>   Запустить сервис локально через uvicorn (без Docker)
  help                  Показать эту справку

${YELLOW}Доступные сервисы:${NC}
  ${GREEN}${SERVICES[*]}${NC}

${YELLOW}Примеры:${NC}
  $0 up                       # запустить все сервисы
  $0 up auth-service          # запустить только auth-service
  $0 logs finance-service     # логи finance-service
  $0 local study-service      # запустить study-service локально на :8002
EOF
}

# ===== Проверка сервиса =====
validate_service() {
    local svc="$1"
    for s in "${SERVICES[@]}"; do
        [[ "$s" == "$svc" ]] && return 0
    done
    echo -e "${RED}Ошибка:${NC} неизвестный сервис '$svc'"
    echo -e "Доступные: ${GREEN}${SERVICES[*]}${NC}"
    exit 1
}

# ===== Команды =====
cmd_build() {
    if [[ -n "${1:-}" ]]; then
        validate_service "$1"
        echo -e "${BLUE}Сборка образа для $1...${NC}"
        docker compose build "$1"
    else
        echo -e "${BLUE}Сборка всех образов...${NC}"
        docker compose build
    fi
}

cmd_up() {
    if [[ -n "${1:-}" ]]; then
        validate_service "$1"
        echo -e "${GREEN}Запуск $1...${NC}"
        docker compose up -d "$1"
    else
        echo -e "${GREEN}Запуск всех сервисов...${NC}"
        docker compose up -d
    fi
    cmd_status
}

cmd_down() {
    echo -e "${YELLOW}Остановка и удаление контейнеров...${NC}"
    docker compose down
}

cmd_stop() {
    if [[ -n "${1:-}" ]]; then
        validate_service "$1"
        docker compose stop "$1"
    else
        docker compose stop
    fi
}

cmd_restart() {
    if [[ -n "${1:-}" ]]; then
        validate_service "$1"
        docker compose restart "$1"
    else
        docker compose restart
    fi
}

cmd_logs() {
    if [[ -n "${1:-}" ]]; then
        validate_service "$1"
        docker compose logs -f "$1"
    else
        docker compose logs -f
    fi
}

cmd_status() {
    echo -e "${CYAN}=== Статус контейнеров ===${NC}"
    docker compose ps
}

cmd_clean() {
    echo -e "${RED}Полная очистка: контейнеры, образы, volumes...${NC}"
    docker compose down -v --rmi local --remove-orphans
    echo -e "${GREEN}Готово.${NC}"
}

cmd_local() {
    local svc="${1:-}"
    if [[ -z "$svc" ]]; then
        echo -e "${RED}Ошибка:${NC} укажите сервис"
        usage
        exit 1
    fi
    validate_service "$svc"

    # Маппинг сервис -> порт
    declare -A PORTS=(
        [monolith]=8000
        [auth-service]=8001
        [study-service]=8002
        [finance-service]=8003
        [integration-service]=8004
    )
    local port="${PORTS[$svc]}"

    echo -e "${BLUE}Локальный запуск $svc на порту $port (SERVICE_NAME=$svc)${NC}"
    echo -e "${YELLOW}Ctrl+C для остановки${NC}"

    SERVICE_NAME="$svc" PORT="$port" uvicorn main:app --host 127.0.0.1 --port "$port" --reload
}

# ===== Основная логика =====
[[ $# -lt 1 ]] && { usage; exit 1; }

COMMAND="$1"
SERVICE="${2:-}"

case "$COMMAND" in
    build)   cmd_build   "$SERVICE" ;;
    up)      cmd_up      "$SERVICE" ;;
    down)    cmd_down              ;;
    stop)    cmd_stop    "$SERVICE" ;;
    restart) cmd_restart "$SERVICE" ;;
    logs)    cmd_logs    "$SERVICE" ;;
    status)  cmd_status            ;;
    clean)   cmd_clean             ;;
    local)   cmd_local   "$SERVICE" ;;
    help|-h|--help) usage ;;
    *)
        echo -e "${RED}Неизвестная команда:${NC} $COMMAND"
        usage
        exit 1
        ;;
esac
