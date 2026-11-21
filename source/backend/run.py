#!/usr/bin/env python3
"""Кроссплатформенный скрипт для управления микросервисами через Docker."""
import argparse
import os
import subprocess
import sys
from typing import Optional

# ===== Конфигурация =====
SERVICES = {
    "auth-service": 8001,
    "study-service": 8002,
    "finance-service": 8003,
    "integration-service": 8004,
}

# Все контейнеры (сервисы + БД + HAProxy)
ALL_CONTAINERS = list(SERVICES.keys()) + [
    "auth-db",
    "study-db",
    "finance-db",
    "integration-db",
    "redis",
    "haproxy",
]

DB_MAP = {
    "auth-service": "auth-db",
    "study-service": "study-db",
    "finance-service": "finance-db",
    "integration-service": "integration-db",
}

# ТУИ — текущее состояние
STATE = {
    "running": set(),
    "selected": [],
    "selected_db": None,
    "selected_service": None,
    "view": "main",  # main | status | logs | services | db | haproxy
    "haproxy_status": "stopped",
    "cursor": 0,
}

# Пытаемся подключить colorama для цветного вывода в Windows
try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False

    class _Dummy:
        def __getattr__(self, _):
            return ""

    Fore = _Dummy()
    Style = _Dummy()


# ===== Утилиты =====
def run(cmd: list[str], check: bool = True) -> int:
    """Запускает команду и возвращает код возврата."""
    print(f"{Fore.BLUE}>>> {' '.join(cmd)}{Style.RESET_ALL}")
    try:
        result = subprocess.run(cmd)
        if check and result.returncode != 0:
            sys.exit(result.returncode)
        return result.returncode
    except FileNotFoundError:
        print(f"{Fore.RED}Команда не найдена: {cmd[0]}{Style.RESET_ALL}")
        sys.exit(1)
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Прервано пользователем{Style.RESET_ALL}")
        sys.exit(130)


def validate_service(name: Optional[str]) -> None:
    """Проверяет, что сервис существует."""
    if name and name not in SERVICES:
        print(f"{Fore.RED}Ошибка: неизвестный сервис '{name}'{Style.RESET_ALL}")
        print(f"{Fore.GREEN}Доступные: {', '.join(SERVICES)}{Style.RESET_ALL}")
        sys.exit(1)


def compose_cmd(*args: str) -> list[str]:
    """Возвращает команду docker compose (или docker-compose)."""
    # Пробуем новый синтаксис (плагин), иначе старый
    base = ["docker", "compose"]
    return base + list(args)


# ===== Команды =====
def cmd_build(service: Optional[str]) -> None:
    if service:
        validate_service(service)
        print(f"{Fore.BLUE}Сборка образа для {service}...{Style.RESET_ALL}")
        run(compose_cmd("build", service))
    else:
        print(f"{Fore.BLUE}Сборка всех образов...{Style.RESET_ALL}")
        run(compose_cmd("build"))


def cmd_up(service: Optional[str]) -> None:
    if service:
        validate_service(service)
        print(f"{Fore.GREEN}Запуск {service}...{Style.RESET_ALL}")
        run(compose_cmd("up", "-d", service))
    else:
        print(f"{Fore.GREEN}Запуск всех сервисов...{Style.RESET_ALL}")
        run(compose_cmd("up", "-d"))
    cmd_status(None)


def cmd_down(_: Optional[str]) -> None:
    print(f"{Fore.YELLOW}Остановка и удаление контейнеров...{Style.RESET_ALL}")
    run(compose_cmd("down", "-v"))


def cmd_stop(service: Optional[str]) -> None:
    if service:
        validate_service(service)
        run(compose_cmd("stop", service))
    else:
        run(compose_cmd("stop"))


def cmd_restart(service: Optional[str]) -> None:
    if service:
        validate_service(service)
        run(compose_cmd("restart", service))
    else:
        run(compose_cmd("restart"))


def cmd_logs(service: Optional[str]) -> None:
    if service:
        validate_service(service)
        run(compose_cmd("logs", "-f", service), check=False)
    else:
        run(compose_cmd("logs", "-f"), check=False)


def cmd_status(_: Optional[str]) -> None:
    print(f"{Fore.CYAN}=== Статус контейнеров ==={Style.RESET_ALL}")
    run(compose_cmd("ps"), check=False)


def cmd_clean(_: Optional[str]) -> None:
    print(f"{Fore.RED}Полная очистка: контейнеры, образы, volumes...{Style.RESET_ALL}")
    run(compose_cmd("down", "-v", "--rmi", "local", "--remove-orphans"))
    print(f"{Fore.GREEN}Готово.{Style.RESET_ALL}")


def cmd_db(service: Optional[str]) -> None:
    """Запуск/остановка только базы данных."""
    db_map = {
        "auth-service": "auth-db",
        "study-service": "study-db",
        "finance-service": "finance-db",
        "integration-service": "integration-db",
    }
    if not service:
        print(f"{Fore.RED}Ошибка: укажите сервис{Style.RESET_ALL}")
        sys.exit(1)
    validate_service(service)
    db_container = db_map.get(service)
    if not db_container:
        print(f"{Fore.RED}Неизвестный сервис: {service}{Style.RESET_ALL}")
        sys.exit(1)

    print(f"{Fore.BLUE}Управление БД для {service}: {db_container}{Style.RESET_ALL}")
    run(compose_cmd("ps", db_container), check=False)


def cmd_migrate(service: Optional[str]) -> None:
    """Запуск миграций Alembic для сервиса."""
    if not service:
        print(f"{Fore.RED}Ошибка: укажите сервис{Style.RESET_ALL}")
        sys.exit(1)
    validate_service(service)
    print(f"{Fore.BLUE}Запуск миграций для {service}...{Style.RESET_ALL}")
    run(compose_cmd("run", "--rm", service, "alembic", "upgrade", "head"))


def cmd_migrate_all(_: Optional[str]) -> None:
    """Запуск миграций Alembic для всех сервисов."""
    print(f"{Fore.BLUE}Запуск миграций для всех сервисов...{Style.RESET_ALL}")
    for service in SERVICES:
        print(f"{Fore.CYAN}--- {service} ---{Style.RESET_ALL}")
        rc = run(compose_cmd("run", "--rm", service, "alembic", "upgrade", "head"), check=False)
        if rc != 0:
            print(f"{Fore.RED}Миграции для {service} завершились с ошибкой (код {rc}){Style.RESET_ALL}")
            sys.exit(rc)
    print(f"{Fore.GREEN}Все миграции применены.{Style.RESET_ALL}")


def cmd_shell(service: Optional[str]) -> None:
    """Открыть shell в контейнере."""
    if not service:
        print(f"{Fore.RED}Ошибка: укажите сервис{Style.RESET_ALL}")
        sys.exit(1)
    validate_service(service)
    print(f"{Fore.BLUE}Открытие shell в {service}...{Style.RESET_ALL}")
    run(compose_cmd("exec", "-it", service, "sh"))


def cmd_haproxy(service: Optional[str]) -> None:
    """Управление HAProxy."""
    if not service:
        print(f"{Fore.RED}Ошибка: укажите действие: start, stop, restart, status, logs{Style.RESET_ALL}")
        sys.exit(1)

    action = service
    if action not in ("start", "stop", "restart", "status", "logs"):
        print(f"{Fore.RED}Ошибка: неизвестное действие '{action}'{Style.RESET_ALL}")
        print(f"{Fore.GREEN}Доступные: start, stop, restart, status, logs{Style.RESET_ALL}")
        sys.exit(1)

    cmds = {
        "start": lambda: run(compose_cmd("up", "-d", "haproxy")),
        "stop": lambda: run(compose_cmd("stop", "haproxy")),
        "restart": lambda: run(compose_cmd("restart", "haproxy")),
        "status": lambda: run(compose_cmd("ps", "haproxy"), check=False),
        "logs": lambda: run(compose_cmd("logs", "-f", "haproxy"), check=False),
    }
    print(f"{Fore.BLUE}HAProxy: {action}{Style.RESET_ALL}")
    cmds[action]()


# ===== CLI =====
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="Управление микросервисами VuzHub (Docker)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""Доступные сервисы:
  {', '.join(SERVICES)}

Доступные БД:
  auth-db, study-db, finance-db, integration-db, redis

Команды:
  build [service]           - пересобрать образ
  up [service]              - запустить сервис + его БД
  down                      - остановить всё
  stop [service]            - остановить
  restart [service]         - перезапустить
  logs [service]            - логи (-f)
  status                    - статус всех контейнеров
  clean                     - полная очистка (с volumes)
  db <service>              - статус БД для сервиса
  migrate <service>         - миграции Alembic
  migrate-all               - миграции для всех
  shell <service>           - shell в контейнере
  haproxy <action>          - start, stop, restart, status, logs

Примеры:
  python run.py up                        # запустить всё
  python run.py up auth-service           # только auth
  python run.py haproxy start             # запустить HAProxy
  python run.py haproxy status            # статус HAProxy
  python run.py db study-service          # статус БД study
  python run.py migrate-all               # миграции для всех
  python run.py                           # запустить TUI-меню
""",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["build", "up", "down", "stop", "restart", "logs", "status", "clean", "db", "migrate", "migrate-all", "shell", "haproxy"],
        help="Команда для выполнения (без аргументов — запускает TUI-меню)",
    )
    parser.add_argument(
        "service",
        nargs="?",
        default=None,
        help="Имя сервиса / действие (например: start для haproxy)",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "build": cmd_build,
        "up": cmd_up,
        "down": cmd_down,
        "stop": cmd_stop,
        "restart": cmd_restart,
        "logs": cmd_logs,
        "status": cmd_status,
        "clean": cmd_clean,
        "db": cmd_db,
        "migrate": cmd_migrate,
        "migrate-all": cmd_migrate_all,
        "shell": cmd_shell,
    }

    handler = dispatch[args.command]
    handler(args.service)


# ===== TUI =====
def _get_key() -> str:
    """Получает нажатую клавишу (кроссплатформенно)."""
    import select
    import tty
    import termios

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        if select.select([sys.stdin], [], [], 1.0)[0]:
            return sys.stdin.read(1)
        return ""
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _parse_status() -> set:
    """Парсит статус контейнеров из docker compose ps."""
    try:
        result = subprocess.run(
            compose_cmd("ps", "--format", "json"),
            capture_output=True, text=True, check=False
        )
        running = set()
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    import json
                    data = json.loads(line)
                    if data.get("State", "").startswith("running"):
                        running.add(data["Name"].split("-")[-1] if "-" in data["Name"] else data["Name"])
                        # Упрощённо: извлекаем имя сервиса
                        name = data["Name"]
                        if name == "vuzhub-auth-service": running.add("auth-service")
                        elif name == "vuzhub-study-service": running.add("study-service")
                        elif name == "vuzhub-finance-service": running.add("finance-service")
                        elif name == "vuzhub-integration-service": running.add("integration-service")
                        elif name == "vuzhub-auth-db": running.add("auth-db")
                        elif name == "vuzhub-study-db": running.add("study-db")
                        elif name == "vuzhub-finance-db": running.add("finance-db")
                        elif name == "vuzhub-integration-db": running.add("integration-db")
                        elif name == "vuzhub-redis": running.add("redis")
                        elif name == "vuzhub-haproxy": running.add("haproxy")
                except (json.JSONDecodeError, KeyError):
                    pass
        return running
    except Exception:
        return set()


def _clear_screen():
    os.system("clear" if os.name != "nt" else "cls")


def _print_header(text: str) -> None:
    w = 60
    print(f"\n{Fore.CYAN}{'═'*w}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{' ' * ((w - len(text)) // 2)}{text}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'═'*w}{Style.RESET_ALL}\n")


def _print_menu() -> None:
    """Отрисовывает главное меню."""
    _clear_screen()
    _print_header("VuzHub — Управление микросервисами")

    running = _parse_status()
    STATE["running"] = running

    print(f"{Fore.YELLOW}Доступные команды:{Style.RESET_ALL}\n")
    print(f"  {Fore.GREEN}1{Style.RESET_ALL}. Запустить всё")
    print(f"  {Fore.GREEN}2{Style.RESET_ALL}. Остановить всё")
    print(f"  {Fore.GREEN}3{Style.RESET_ALL}. Перезапустить всё")
    print()
    print(f"  {Fore.CYAN}— Сервисы —{Style.RESET_ALL}")
    for i, svc in enumerate(SERVICES, start=4):
        icon = f"{Fore.GREEN}●{Style.RESET_ALL}" if svc in running else f"{Fore.RED}○{Style.RESET_ALL}"
        port = SERVICES[svc]
        print(f"  {Fore.GREEN}{i}{Style.RESET_ALL}. {icon} {svc} :{port}")
    print()
    print(f"  {Fore.CYAN}— Базы данных —{Style.RESET_ALL}")
    dbs = [("auth-db", "5432"), ("study-db", "5433"), ("finance-db", "5434"), ("integration-db", "5435"), ("redis", "6379")]
    for i, (db, port) in enumerate(dbs, start=8):
        icon = f"{Fore.GREEN}●{Style.RESET_ALL}" if db in running else f"{Fore.RED}○{Style.RESET_ALL}"
        print(f"  {Fore.GREEN}{i}{Style.RESET_ALL}. {icon} {db} :{port}")
    print()
    print(f"  {Fore.MAGENTA}— HAProxy —{Style.RESET_ALL}")
    haproxy_icon = f"{Fore.GREEN}●{Style.RESET_ALL}" if "haproxy" in running else f"{Fore.RED}○{Style.RESET_ALL}"
    print(f"  {Fore.GREEN}14{Style.RESET_ALL}. {haproxy_icon} HAProxy :80")
    print()
    print(f"  {Fore.YELLOW}— Дополнительно —{Style.RESET_ALL}")
    print(f"  15. Логи всех сервисов")
    print(f"  16. Статус контейнеров")
    print(f"  17. Миграции для всех")
    print(f"  18. Shell в сервисе")
    print(f"  19. Полная очистка (с volumes)")
    print()
    print(f"  {Fore.YELLOW}q{Style.RESET_ALL}. Выход")


def _handle_main_menu(key: str) -> bool:
    """Возвращает False если нужно выйти."""
    running = _parse_status()
    STATE["running"] = running

    if key == "q" or key == "Q":
        return False

    if key == "1":
        print(f"{Fore.GREEN}Запуск всех сервисов...{Style.RESET_ALL}")
        run(compose_cmd("up", "-d"))
        input(f"\n{Fore.YELLOW}Нажмите Enter для продолжения...{Style.RESET_ALL}")
    elif key == "2":
        print(f"{Fore.YELLOW}Остановка всех сервисов...{Style.RESET_ALL}")
        run(compose_cmd("stop"))
        input(f"\n{Fore.YELLOW}Нажмите Enter для продолжения...{Style.RESET_ALL}")
    elif key == "3":
        print(f"{Fore.YELLOW}Перезапуск всех сервисов...{Style.RESET_ALL}")
        run(compose_cmd("restart"))
        input(f"\n{Fore.YELLOW}Нажмите Enter для продолжения...{Style.RESET_ALL}")
    elif key in "4567":
        idx = int(key) - 4
        svc = list(SERVICES.keys())[idx]
        if svc in running:
            print(f"{Fore.RED}Остановка {svc}...{Style.RESET_ALL}")
            run(compose_cmd("stop", svc))
        else:
            print(f"{Fore.GREEN}Запуск {svc}...{Style.RESET_ALL}")
            run(compose_cmd("up", "-d", svc))
        input(f"\n{Fore.YELLOW}Нажмите Enter для продолжения...{Style.RESET_ALL}")
    elif key in "8901":
        idx = int(key) - 8
        if key == "1" and idx >= 4:
            # HAProxy — key 14
            print(f"{Fore.BLUE}HAProxy{Style.RESET_ALL}")
            if "haproxy" in running:
                print(f"{Fore.YELLOW}Перезапуск HAProxy...{Style.RESET_ALL}")
                run(compose_cmd("restart", "haproxy"))
            else:
                print(f"{Fore.GREEN}Запуск HAProxy...{Style.RESET_ALL}")
                run(compose_cmd("up", "-d", "haproxy"))
            input(f"\n{Fore.YELLOW}Нажмите Enter для продолжения...{Style.RESET_ALL}")
        else:
            # БД
            dbs = ["auth-db", "study-db", "finance-db", "integration-db", "redis"]
            db = dbs[idx]
            if db in running:
                print(f"{Fore.RED}Остановка {db}...{Style.RESET_ALL}")
                run(compose_cmd("stop", db))
            else:
                print(f"{Fore.GREEN}Запуск {db}...{Style.RESET_ALL}")
                run(compose_cmd("up", "-d", db))
            input(f"\n{Fore.YELLOW}Нажмите Enter для продолжения...{Style.RESET_ALL}")
    elif key == "15":
        print(f"{Fore.YELLOW}Логи всех сервисов (Ctrl+C для выхода)...{Style.RESET_ALL}")
        run(compose_cmd("logs", "-f"), check=False)
    elif key == "16":
        print(f"{Fore.CYAN}=== Статус контейнеров ==={Style.RESET_ALL}")
        run(compose_cmd("ps"), check=False)
        input(f"\n{Fore.YELLOW}Нажмите Enter для продолжения...{Style.RESET_ALL}")
    elif key == "17":
        print(f"{Fore.BLUE}Запуск миграций для всех сервисов...{Style.RESET_ALL}")
        for svc in SERVICES:
            print(f"{Fore.CYAN}--- {svc} ---{Style.RESET_ALL}")
            run(compose_cmd("run", "--rm", svc, "alembic", "upgrade", "head"), check=False)
        input(f"\n{Fore.YELLOW}Нажмите Enter для продолжения...{Style.RESET_ALL}")
    elif key == "18":
        print(f"\n{Fore.CYAN}Выберите номер сервиса для shell:{Style.RESET_ALL}")
        for i, svc in enumerate(SERVICES, start=4):
            print(f"  {i}. {svc}")
        print(f"  9. Redis")
        choice = input(f"\n{Fore.YELLOW}Введите номер: {Style.RESET_ALL}")
        try:
            idx = int(choice)
            if idx in (4, 5, 6, 7):
                svc = list(SERVICES.keys())[idx - 4]
                run(compose_cmd("exec", "-it", svc, "sh"), check=False)
            elif choice == "9":
                run(compose_cmd("exec", "-it", "redis", "sh"), check=False)
            else:
                print(f"{Fore.RED}Неверный номер{Style.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Введите число{Style.RESET_ALL}")
        input(f"\n{Fore.YELLOW}Нажмите Enter для продолжения...{Style.RESET_ALL}")
    elif key == "19":
        confirm = input(f"\n{Fore.RED}Полная очистка (удалит volumes!). Удалить? [y/N]: {Style.RESET_ALL}")
        if confirm.lower() == "y":
            print(f"{Fore.RED}Очистка...{Style.RESET_ALL}")
            run(compose_cmd("down", "-v", "--rmi", "local", "--remove-orphans"))
        input(f"\n{Fore.YELLOW}Нажмите Enter для продолжения...{Style.RESET_ALL}")

    return True


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Если нет аргументов — запускаем TUI
    if args.command is None:
        try:
            while True:
                _print_menu()
                key = _get_key()
                if not key:
                    continue
                if not _handle_main_menu(key):
                    break
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Прервано пользователем{Style.RESET_ALL}")
        finally:
            _clear_screen()
        return

    dispatch = {
        "build": cmd_build,
        "up": cmd_up,
        "down": cmd_down,
        "stop": cmd_stop,
        "restart": cmd_restart,
        "logs": cmd_logs,
        "status": cmd_status,
        "clean": cmd_clean,
        "db": cmd_db,
        "migrate": cmd_migrate,
        "migrate-all": cmd_migrate_all,
        "shell": cmd_shell,
        "haproxy": cmd_haproxy,
    }

    handler = dispatch[args.command]
    handler(args.service)


if __name__ == "__main__":
    main()
