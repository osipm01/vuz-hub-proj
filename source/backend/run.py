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


def cmd_shell(service: Optional[str]) -> None:
    """Открыть shell в контейнере."""
    if not service:
        print(f"{Fore.RED}Ошибка: укажите сервис{Style.RESET_ALL}")
        sys.exit(1)
    validate_service(service)
    print(f"{Fore.BLUE}Открытие shell в {service}...{Style.RESET_ALL}")
    run(compose_cmd("exec", "-it", service, "sh"))


# ===== CLI =====
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="Управление микросервисами VuzHub (Docker)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""Доступные сервисы:
  {', '.join(SERVICES)}

Примеры:
  python run.py up                       # запустить все сервисы + БД
  python run.py up auth-service          # только auth + его БД
  python run.py logs finance-service     # логи finance
  python run.py build                    # пересобрать все образы
  python run.py down                     # остановить всё
  python run.py clean                    # полная очистка (с volumes)
  python run.py migrate auth-service     # запустить миграции
  python run.py db study-service         # статус БД study
  python run.py shell integration-service# shell в контейнере
""",
    )
    parser.add_argument(
        "command",
        choices=["build", "up", "down", "stop", "restart", "logs", "status", "clean", "db", "migrate", "shell"],
        help="Команда для выполнения",
    )
    parser.add_argument(
        "service",
        nargs="?",
        default=None,
        help="Имя сервиса (опционально)",
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
        "shell": cmd_shell,
    }

    handler = dispatch[args.command]
    handler(args.service)


if __name__ == "__main__":
    main()
