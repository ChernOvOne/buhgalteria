#!/usr/bin/env python3
"""
buh — CLI управление системой бухгалтерии
Использование: buh [команда]
"""

import os
import sys
import subprocess
import shutil
from datetime import datetime

INSTALL_DIR = "/opt/buhgalteria"
COMPOSE = "docker compose"

RED    = "\033[0;31m"
GREEN  = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE   = "\033[0;34m"
BOLD   = "\033[1m"
NC     = "\033[0m"

def c(color, text): return f"{color}{text}{NC}"
def run(cmd, check=True, capture=False):
    kw = {"shell": True, "cwd": INSTALL_DIR}
    if capture: kw["capture_output"] = True; kw["text"] = True
    return subprocess.run(cmd, **kw, check=check)

def header():
    print(f"\n{BOLD}╔══════════════════════════════════════╗{NC}")
    print(f"{BOLD}║         Buhgalteria CLI v1.0          ║{NC}")
    print(f"{BOLD}╚══════════════════════════════════════╝{NC}\n")

def status():
    print(c(BLUE, "→") + " Статус сервисов:\n")
    run(f"{COMPOSE} ps", check=False)

    # Проверяем health
    try:
        result = run("curl -sf http://localhost:8000/api/health", check=False, capture=True)
        if result.returncode == 0:
            print(f"\n{c(GREEN, '✓')} Backend API: работает")
        else:
            print(f"\n{c(RED, '✗')} Backend API: не отвечает")
    except: pass

def start():
    print(c(BLUE, "→") + " Запуск сервисов...")
    run(f"{COMPOSE} up -d")
    print(c(GREEN, "✓") + " Сервисы запущены")

def stop():
    print(c(YELLOW, "!") + " Остановка сервисов...")
    run(f"{COMPOSE} down")
    print(c(GREEN, "✓") + " Сервисы остановлены")

def restart():
    stop()
    start()

def update():
    print(c(BLUE, "→") + " Обновление из репозитория...")
    # Сохраняем локальные изменения (например .env)
    run("git stash", check=False)
    run("git pull origin main")
    # Восстанавливаем локальные изменения
    run("git stash pop", check=False)
    print(c(BLUE, "→") + " Пересборка и перезапуск сервисов...")
    run(f"{COMPOSE} up -d --build --no-deps backend frontend")
    result = run(f"{COMPOSE} ps bot", check=False, capture=True)
    if result and "running" in (result.stdout or "").lower():
        run(f"{COMPOSE} --profile bot up -d --build --no-deps bot")
    print(c(GREEN, "✓") + " Обновление завершено")

def logs(service=None):
    svc = service or ""
    run(f"{COMPOSE} logs -f --tail=100 {svc}", check=False)

def backup():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f"/opt/buhgalteria-backups"
    os.makedirs(backup_dir, exist_ok=True)
    filename = f"{backup_dir}/buhdb_{ts}.sql.gz"

    print(c(BLUE, "→") + f" Создание резервной копии...")
    db_pass = _get_env("DB_PASSWORD", "buhpass")
    run(f'{COMPOSE} exec -T db pg_dump -U buh buhdb | gzip > {filename}')
    size = os.path.getsize(filename) // 1024
    print(c(GREEN, "✓") + f" Бэкап сохранён: {filename} ({size} KB)")

def restore():
    backup_dir = "/opt/buhgalteria-backups"
    if not os.path.exists(backup_dir):
        print(c(RED, "✗") + " Папка бэкапов не найдена")
        return

    files = sorted([f for f in os.listdir(backup_dir) if f.endswith(".sql.gz")])
    if not files:
        print(c(RED, "✗") + " Бэкапы не найдены")
        return

    print("Доступные бэкапы:")
    for i, f in enumerate(files, 1):
        size = os.path.getsize(f"{backup_dir}/{f}") // 1024
        print(f"  {i}. {f} ({size} KB)")

    try:
        choice = int(input("\nВыберите номер бэкапа: ")) - 1
        filename = f"{backup_dir}/{files[choice]}"
    except (ValueError, IndexError):
        print(c(RED, "✗") + " Неверный выбор")
        return

    confirm = input(f"\n{c(YELLOW,'!')} Восстановить из {files[choice]}? Текущие данные будут УДАЛЕНЫ. [yes/N]: ")
    if confirm.lower() != "yes":
        print("Отменено")
        return

    print(c(BLUE, "→") + " Восстановление...")
    run(f'{COMPOSE} exec -T db psql -U buh -c "DROP DATABASE IF EXISTS buhdb; CREATE DATABASE buhdb;"', check=False)
    run(f'zcat {filename} | {COMPOSE} exec -T db psql -U buh buhdb')
    print(c(GREEN, "✓") + " Восстановление завершено")

def ssl_setup():
    domain = _get_env("DOMAIN", "")
    if not domain:
        domain = input("Введите домен: ").strip()

    email = input(f"Email для Let's Encrypt: ").strip()
    print(c(BLUE, "→") + f" Получение SSL для {domain}...")

    # Временно запускаем nginx на 80 для ACME challenge
    run(f'{COMPOSE} --profile prod up -d nginx', check=False)
    import time; time.sleep(3)

    run(f'certbot certonly --webroot -w /var/www/certbot -d {domain} --non-interactive --agree-tos -m {email}')

    # Применяем SSL конфиг с подстановкой домена
    template = f"{INSTALL_DIR}/nginx/nginx-ssl.conf.template"
    target = f"{INSTALL_DIR}/nginx/nginx.conf"
    with open(template) as f:
        content = f.read().replace("DOMAIN_PLACEHOLDER", domain)
    with open(target, "w") as f:
        f.write(content)

    run(f'{COMPOSE} --profile prod restart nginx')
    print(c(GREEN, "✓") + " SSL сертификат установлен, nginx перезапущен")

def create_admin():
    username = input("Логин нового администратора: ").strip()
    password = input("Пароль: ").strip()
    if not username or not password:
        print(c(RED, "✗") + " Логин и пароль обязательны")
        return

    script = f"""
import asyncio, sys
sys.path.insert(0, '/app')
from app.database import AsyncSessionLocal, engine, Base
from app.models import User, UserRole
from app.core.security import hash_password
from sqlalchemy import select

async def create():
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(User).where(User.username == '{username}'))
        if existing.scalar_one_or_none():
            print('Пользователь уже существует')
            return
        user = User(username='{username}', hashed_password=hash_password('{password}'), role=UserRole.admin, full_name='Администратор')
        db.add(user)
        await db.commit()
        print('Администратор создан')

asyncio.run(create())
"""
    run(f'{COMPOSE} exec -T backend python3 -c "{script}"')

def _get_env(key, default=""):
    env_file = f"{INSTALL_DIR}/.env"
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1].strip()
    return os.getenv(key, default)

def show_info():
    domain = _get_env("DOMAIN", "localhost")
    print(f"\n  Веб-интерфейс:  {c(BLUE, f'http://{domain}')}")
    print(f"  API:            {c(BLUE, f'http://{domain}:8000/api')}")
    print(f"  API Docs:       {c(BLUE, f'http://{domain}:8000/docs')}")
    print(f"  Бэкапы:         /opt/buhgalteria-backups/")

MENU = """
  1.  Статус сервисов
  2.  Запустить
  3.  Остановить
  4.  Перезапустить
  5.  Обновить (git pull + rebuild)
  6.  Просмотр логов
  7.  Создать резервную копию БД
  8.  Восстановить из резервной копии
  9.  Настроить SSL (Let's Encrypt)
  10. Создать администратора
  11. Информация о сервисе
  0.  Выход
"""

def interactive_menu():
    header()
    while True:
        print(MENU)
        try:
            choice = input("Выберите действие: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nВыход")
            break

        if choice == "1":  status()
        elif choice == "2":  start()
        elif choice == "3":  stop()
        elif choice == "4":  restart()
        elif choice == "5":  update()
        elif choice == "6":
            svc = input("Сервис (оставьте пустым для всех): ").strip()
            logs(svc or None)
        elif choice == "7":  backup()
        elif choice == "8":  restore()
        elif choice == "9":  ssl_setup()
        elif choice == "10": create_admin()
        elif choice == "11": show_info()
        elif choice == "0":  break
        else: print(c(YELLOW, "!") + " Неверный выбор")
        print()

if __name__ == "__main__":
    os.chdir(INSTALL_DIR)

    # Поддержка аргументов командной строки
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        cmds = {
            "status": status, "start": start, "stop": stop,
            "restart": restart, "update": update,
            "backup": backup, "restore": restore,
            "info": show_info,
            "logs": lambda: logs(sys.argv[2] if len(sys.argv) > 2 else None),
        }
        if cmd in cmds:
            header()
            cmds[cmd]()
        else:
            print(f"Неизвестная команда: {cmd}")
            print(f"Доступные: {', '.join(cmds.keys())}")
    else:
        interactive_menu()
