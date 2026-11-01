#!/usr/bin/env python3
"""Кроссплатформенный скрипт для управления микросервисами."""
import argparse
import os
import subprocess
import sys
from typing import Optional

# ===== Конфигурация =====
SERVICES = {
    "monolith": 8000,
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
    run(compose_cmd("down"))


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


def cmd_local(service: Optional[str]) -> None:
    if not service:
        print(f"{Fore.RED}Ошибка: укажите сервис{Style.RESET_ALL}")
        sys.exit(1)
    validate_service(service)

    port = SERVICES[service]
    print(f"{Fore.BLUE}Локальный запуск {service} на порту {port}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}SERVICE_NAME={service}, PORT={port}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Ctrl+C для остановки{Style.RESET_ALL}")

    env = os.environ.copy()
    env["SERVICE_NAME"] = service
    env["PORT"] = str(port)

    try:
        subprocess.run(
            [
                sys.executable, "-m", "uvicorn",
                "main:app",
                "--host", "127.0.0.1",
                "--port", str(port),
                "--reload",
            ],
            env=env,
        )
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Остановлено.{Style.RESET_ALL}")


# ===== CLI =====
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="Управление микросервисами VuzHub",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""Доступные сервисы:
  {', '.join(SERVICES)}

Примеры:
  python run.py up                       # запустить все
  python run.py up auth-service          # только auth
  python run.py logs finance-service     # логи finance
  python run.py local study-service      # локально на :8002
""",
    )
    parser.add_argument(
        "command",
        choices=["build", "up", "down", "stop", "restart", "logs", "status", "clean", "local"],
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
        "local": cmd_local,
    }

    handler = dispatch[args.command]
    handler(args.service)



main()
