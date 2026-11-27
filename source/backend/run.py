#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

# ===== Конфигурация =====
SERVICES = {
    "auth-service": 8001,
    "study-service": 8002,
    "finance-service": 8003,
    "integration-service": 8004,
    "client": 3000,
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
    "client": None,  # клиент не имеет БД
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
    if not service:
        print(f"{Fore.RED}Ошибка: укажите сервис{Style.RESET_ALL}")
        sys.exit(1)
    validate_service(service)
    db_container = DB_MAP.get(service)
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


def cmd_create_admin(_: Optional[str]) -> None:
    """Запуск скрипта создания администратора."""
    project_root = Path(__file__).resolve().parent
    admin_script = project_root / "scripts" / "create_admin.py"

    if not admin_script.exists():
        print(f"{Fore.RED}Файл {admin_script} не найден{Style.RESET_ALL}")
        sys.exit(1)

    print(f"{Fore.MAGENTA}Создание администратора...{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Укажите параметры или нажмите Enter для дефолтов (Ctrl+C для выхода){Style.RESET_ALL}\n")
    run(["python3", str(admin_script)], check=False)


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
  admin                     - создать админа

Примеры:
  python run.py up                        # запустить всё
  python run.py up auth-service           # только auth
  python run.py haproxy start             # запустить HAProxy
  python run.py db study-service          # статус БД study
  python run.py migrate-all               # миграции для всех
  python run.py                           # запустить TUI-меню
""",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["build", "up", "down", "stop", "restart", "logs", "status", "clean", "db", "migrate", "migrate-all", "shell", "haproxy", "admin"],
        help="Команда для выполнения (без аргументов — запускает TUI-меню)",
    )
    parser.add_argument(
        "service",
        nargs="?",
        default=None,
        help="Имя сервиса / действие (например: start для haproxy)",
    )
    return parser


# ===== TUI =====
def _parse_status() -> set:
    """Парсит статус контейнеров из docker compose ps."""
    try:
        result = subprocess.run(
            compose_cmd("ps", "--format", "json"),
            capture_output=True, text=True, check=False
        )
        running = set()
        if result.returncode == 0:
            import json
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if data.get("State", "").lower().startswith("running"):
                        name = data.get("Name", "").lower()
                        # Нормализация имен для надежного сопоставления независимо от префикса проекта
                        if "auth-service" in name: running.add("auth-service")
                        elif "study-service" in name: running.add("study-service")
                        elif "finance-service" in name: running.add("finance-service")
                        elif "integration-service" in name: running.add("integration-service")
                        elif "vuzhub-client" in name: running.add("client")
                        elif "auth-db" in name: running.add("auth-db")
                        elif "study-db" in name: running.add("study-db")
                        elif "finance-db" in name: running.add("finance-db")
                        elif "integration-db" in name: running.add("integration-db")
                        elif "redis" in name: running.add("redis")
                        elif "haproxy" in name: running.add("haproxy")
                except (json.JSONDecodeError, KeyError):
                    pass
        return running
    except Exception:
        return set()


def _clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def _print_tui_menu() -> bool:
    """Отрисовывает красивое TUI меню и обрабатывает ввод. Возвращает False для выхода."""
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
        from rich.prompt import Prompt
        HAS_RICH = True
    except ImportError:
        HAS_RICH = False

    console = Console() if HAS_RICH else None

    while True:
        _clear_screen()
        running = _parse_status()
        STATE["running"] = running

        if HAS_RICH:
            table = Table(show_header=False, box=None, padding=(0, 2))
            table.add_column("Service", justify="left", width=22)
            table.add_column("Port", justify="center", width=6)
            table.add_column("Status", justify="center", width=12)
            table.add_column("Service", justify="left", width=22)
            table.add_column("Port", justify="center", width=6)
            table.add_column("Status", justify="center", width=12)

            services = list(SERVICES.items())
            dbs = [
                ("auth-db", "5432"),
                ("study-db", "5433"),
                ("finance-db", "5434"),
                ("integration-db", "5435"),
                ("redis", "6379"),
            ]

            max_rows = max(len(services), len(dbs) + 2)

            for i in range(max_rows):
                # Левая колонка (Сервисы)
                if i < len(services):
                    name, port = services[i]
                    status = "[green]● Running[/green]" if name in running else "[red]○ Stopped[/red]"
                    table.add_row(f"[cyan]{name}[/cyan]", str(port), status)
                else:
                    table.add_row("", "", "", "", "", "")

                # Правая колонка (БД + админки)
                if i < len(dbs):
                    name, port = dbs[i]
                    status = "[green]● Running[/green]" if name in running else "[red]○ Stopped[/red]"
                    table.add_row(f"[yellow]{name}[/yellow]", str(port), status)
                elif i == len(dbs):
                    name, port = "haproxy", "80"
                    status = "[green]● Running[/green]" if name in running else "[red]○ Stopped[/red]"
                    table.add_row(f"[magenta]{name}[/magenta]", str(port), status)
                elif i == len(dbs) + 1:
                    name, port = "client", "3000"
                    status = "[green]● Running[/green]" if name in running else "[red]○ Stopped[/red]"
                    table.add_row(f"[green]{name}[/green]", str(port), status)
                elif i == len(dbs) + 2:
                    name, port = "adminer", "8080"
                    status = "[green]● Running[/green]" if name in running else "[red]○ Stopped[/red]"
                    table.add_row(f"[green]{name}[/green]", str(port), status)
                elif i == len(dbs) + 3:
                    name, port = "redis-commander", "8081"
                    status = "[green]● Running[/green]" if name in running else "[red]○ Stopped[/red]"
                    table.add_row(f"[green]{name}[/green]", str(port), status)
                else:
                    table.add_row("", "", "", "", "", "")

            panel = Panel(
                table,
                title="[bold cyan]VuzHub — Управление микросервисами[/bold cyan]",
                border_style="cyan",
                expand=False
            )
            console.print(panel)

            console.print("\n[bold yellow]Доступные действия:[/bold yellow]")
            console.print("  [green]1[/green]. Запустить всё")
            console.print("  [red]2[/red]. Остановить всё")
            console.print("  [yellow]3[/yellow]. Перезапустить всё")
            console.print("  [cyan]4-8[/cyan]. Управление сервисами (вкл/выкл)")
            console.print("  [cyan]9-13[/cyan]. Управление БД (вкл/выкл)")
            console.print("  [magenta]14[/magenta]. Управление HAProxy (вкл/выкл)")
            console.print("  [green]15[/green]. Управление Adminer (вкл/выкл)")
            console.print("  [green]16[/green]. Управление Redis Commander (вкл/выкл)")
            console.print("  [white]17[/white]. Логи всех сервисов")
            console.print("  [white]18[/white]. Статус контейнеров")
            console.print("  [white]19[/white]. Миграции для всех")
            console.print("  [white]20[/white]. Shell в сервисе")
            console.print("  [magenta]21[/magenta]. Создать администратора")
            console.print("  [red]22[/red]. Полная очистка (с volumes)")
            console.print("  [bold red]q[/bold red]. Выход")

            choice = Prompt.ask("\n[bold cyan]Ваш выбор[/bold cyan]", default="").strip()
        else:
            # Fallback на colorama с ASCII-графикой
            w = 64
            print(f"{Fore.CYAN}╭{'─' * w}╮{Style.RESET_ALL}")
            print(f"{Fore.CYAN}│{' VuzHub — Управление микросервисами '.center(w)}│{Style.RESET_ALL}")
            print(f"{Fore.CYAN}╰{'─' * w}╯{Style.RESET_ALL}\n")

            print(f"{Fore.YELLOW}Доступные действия:{Style.RESET_ALL}")
            print(f"  {Fore.GREEN}1{Style.RESET_ALL}. Запустить всё")
            print(f"  {Fore.RED}2{Style.RESET_ALL}. Остановить всё")
            print(f"  {Fore.YELLOW}3{Style.RESET_ALL}. Перезапустить всё")
            print(f"  {Fore.CYAN}4-8{Style.RESET_ALL}. Управление сервисами (вкл/выкл)")
            print(f"  {Fore.CYAN}9-13{Style.RESET_ALL}. Управление БД (вкл/выкл)")
            print(f"  {Fore.MAGENTA}14{Style.RESET_ALL}. Управление HAProxy (вкл/выкл)")
            print(f"  {Fore.GREEN}15{Style.RESET_ALL}. Управление Adminer (вкл/выкл)")
            print(f"  {Fore.GREEN}16{Style.RESET_ALL}. Управление Redis Commander (вкл/выкл)")
            print(f"  17. Логи всех сервисов")
            print(f"  18. Статус контейнеров")
            print(f"  19. Миграции для всех")
            print(f"  20. Shell в сервисе")
            print(f"  {Fore.MAGENTA}21{Style.RESET_ALL}. Создать администратора")
            print(f"  {Fore.RED}22{Style.RESET_ALL}. Полная очистка (с volumes)")
            print(f"  {Fore.RED}q{Style.RESET_ALL}. Выход\n")

            choice = input(f"{Fore.CYAN}Ваш выбор:{Style.RESET_ALL} ").strip()

        if choice.lower() == 'q' or choice == '':
            return False

        if choice == '1':
            if HAS_RICH: console.print("[green]Запуск всех сервисов...[/green]")
            else: print(f"{Fore.GREEN}Запуск всех сервисов...{Style.RESET_ALL}")
            run(compose_cmd("up", "-d"))
            input("\nНажмите Enter для продолжения...")

        elif choice == '2':
            if HAS_RICH: console.print("[yellow]Остановка всех сервисов...[/yellow]")
            else: print(f"{Fore.YELLOW}Остановка всех сервисов...{Style.RESET_ALL}")
            run(compose_cmd("stop"))
            input("\nНажмите Enter для продолжения...")

        elif choice == '3':
            if HAS_RICH: console.print("[yellow]Перезапуск всех сервисов...[/yellow]")
            else: print(f"{Fore.YELLOW}Перезапуск всех сервисов...{Style.RESET_ALL}")
            run(compose_cmd("restart"))
            input("\nНажмите Enter для продолжения...")

        elif choice in ['4', '5', '6', '7', '8']:
            idx = int(choice) - 4
            svc = list(SERVICES.keys())[idx]
            if svc in running:
                if HAS_RICH: console.print(f"[red]Остановка {svc}...[/red]")
                else: print(f"{Fore.RED}Остановка {svc}...{Style.RESET_ALL}")
                run(compose_cmd("stop", svc))
            else:
                if HAS_RICH: console.print(f"[green]Запуск {svc}...[/green]")
                else: print(f"{Fore.GREEN}Запуск {svc}...{Style.RESET_ALL}")
                run(compose_cmd("up", "-d", svc))
            input("\nНажмите Enter для продолжения...")

        elif choice in ['9', '10', '11', '12', '13']:
            idx = int(choice) - 9
            dbs = ["auth-db", "study-db", "finance-db", "integration-db", "redis"]
            db = dbs[idx]
            if db in running:
                if HAS_RICH: console.print(f"[red]Остановка {db}...[/red]")
                else: print(f"{Fore.RED}Остановка {db}...{Style.RESET_ALL}")
                run(compose_cmd("stop", db))
            else:
                if HAS_RICH: console.print(f"[green]Запуск {db}...[/green]")
                else: print(f"{Fore.GREEN}Запуск {db}...{Style.RESET_ALL}")
                run(compose_cmd("up", "-d", db))
            input("\nНажмите Enter для продолжения...")

        elif choice == '14':
            if "haproxy" in running:
                if HAS_RICH: console.print("[yellow]Перезапуск HAProxy...[/yellow]")
                else: print(f"{Fore.YELLOW}Перезапуск HAProxy...{Style.RESET_ALL}")
                run(compose_cmd("restart", "haproxy"))
            else:
                if HAS_RICH: console.print("[green]Запуск HAProxy...[/green]")
                else: print(f"{Fore.GREEN}Запуск HAProxy...{Style.RESET_ALL}")
                run(compose_cmd("up", "-d", "haproxy"))
            input("\nНажмите Enter для продолжения...")

        elif choice == '15':
            if "adminer" in running:
                if HAS_RICH: console.print("[yellow]Перезапуск Adminer...[/yellow]")
                else: print(f"{Fore.YELLOW}Перезапуск Adminer...{Style.RESET_ALL}")
                run(compose_cmd("restart", "adminer"))
            else:
                if HAS_RICH: console.print("[green]Запуск Adminer...[/green]")
                else: print(f"{Fore.GREEN}Запуск Adminer...{Style.RESET_ALL}")
                run(compose_cmd("up", "-d", "adminer"))
            input("\nНажмите Enter для продолжения...")

        elif choice == '16':
            if "redis-commander" in running:
                if HAS_RICH: console.print("[yellow]Перезапуск Redis Commander...[/yellow]")
                else: print(f"{Fore.YELLOW}Перезапуск Redis Commander...{Style.RESET_ALL}")
                run(compose_cmd("restart", "redis-commander"))
            else:
                if HAS_RICH: console.print("[green]Запуск Redis Commander...[/green]")
                else: print(f"{Fore.GREEN}Запуск Redis Commander...{Style.RESET_ALL}")
                run(compose_cmd("up", "-d", "redis-commander"))
            input("\nНажмите Enter для продолжения...")

        elif choice == '16':
            if HAS_RICH: console.print("[yellow]Логи всех сервисов (Ctrl+C для выхода)...[/yellow]")
            else: print(f"{Fore.YELLOW}Логи всех сервисов (Ctrl+C для выхода)...{Style.RESET_ALL}")
            run(compose_cmd("logs", "-f"), check=False)

        elif choice == '17':
            if HAS_RICH: console.print("[cyan]=== Статус контейнеров ===[/cyan]")
            else: print(f"{Fore.CYAN}=== Статус контейнеров ==={Style.RESET_ALL}")
            run(compose_cmd("ps"), check=False)
            input("\nНажмите Enter для продолжения...")

        elif choice == '18':
            if HAS_RICH: console.print("[blue]Запуск миграций для всех сервисов...[/blue]")
            else: print(f"{Fore.BLUE}Запуск миграций для всех сервисов...{Style.RESET_ALL}")
            for svc in SERVICES:
                if HAS_RICH: console.print(f"[cyan]--- {svc} ---[/cyan]")
                else: print(f"{Fore.CYAN}--- {svc} ---{Style.RESET_ALL}")
                run(compose_cmd("run", "--rm", svc, "alembic", "upgrade", "head"), check=False)
            input("\nНажмите Enter для продолжения...")

        elif choice == '19':
            for svc in SERVICES:
                run(compose_cmd("run", "--rm", svc, "alembic", "upgrade", "head"), check=False)
            input("\nНажмите Enter для продолжения...")

        elif choice == '20':
            if HAS_RICH: console.print("\n[cyan]Выберите номер сервиса для shell:[/cyan]")
            else: print(f"\n{Fore.CYAN}Выберите номер сервиса для shell:{Style.RESET_ALL}")
            for i, svc in enumerate(SERVICES, start=1):
                if HAS_RICH: console.print(f"  {i}. {svc}")
                else: print(f"  {i}. {svc}")
            if HAS_RICH: console.print("  6. Redis")
            else: print("  6. Redis")
            shell_choice = input("\nВведите номер: ").strip()
            try:
                idx = int(shell_choice)
                if 1 <= idx <= 5:
                    svc = list(SERVICES.keys())[idx - 1]
                    run(compose_cmd("exec", "-it", svc, "sh"), check=False)
                elif shell_choice == '6':
                    run(compose_cmd("exec", "-it", "redis", "sh"), check=False)
                else:
                    if HAS_RICH: console.print("[red]Неверный номер[/red]")
                    else: print(f"{Fore.RED}Неверный номер{Style.RESET_ALL}")
            except ValueError:
                if HAS_RICH: console.print("[red]Введите число[/red]")
                else: print(f"{Fore.RED}Введите число{Style.RESET_ALL}")
            input("\nНажмите Enter для продолжения...")

        elif choice == '21':
            cmd_create_admin(None)
            input("\nНажмите Enter для продолжения...")

        elif choice == '22':
            confirm = input("\nПолная очистка (удалит volumes!). Удалить? [y/N]: ").strip().lower()
            if confirm == 'y':
                if HAS_RICH: console.print("[red]Очистка...[/red]")
                else: print(f"{Fore.RED}Очистка...{Style.RESET_ALL}")
                run(compose_cmd("down", "-v", "--rmi", "local", "--remove-orphans"))
            input("\nНажмите Enter для продолжения...")

        else:
            if HAS_RICH: console.print("[red]Неверный выбор. Попробуйте снова.[/red]")
            else: print(f"{Fore.RED}Неверный выбор. Попробуйте снова.{Style.RESET_ALL}")
            input("\nНажмите Enter для продолжения...")

        return True


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Если нет аргументов — запускаем TUI
    if args.command is None:
        try:
            while _print_tui_menu():
                pass
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
        "admin": cmd_create_admin,
    }

    handler = dispatch.get(args.command)
    if handler:
        handler(args.service)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
