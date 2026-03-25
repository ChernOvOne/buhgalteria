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
    print(f"{BOLD}║       Buhgalteria CLI v1.3.0          ║{NC}")
    print(f"{BOLD}╚══════════════════════════════════════╝{NC}\n")


def ensure_env():
    """Проверяет что .env существует и валиден, если нет — восстанавливает."""
    env_file = f"{INSTALL_DIR}/.env"
    backup_env = "/opt/buhgalteria-backups/.env.backup"

    # .env есть и не пустой
    if os.path.exists(env_file) and os.path.getsize(env_file) > 10:
        # Обновляем бэкап
        os.makedirs("/opt/buhgalteria-backups", exist_ok=True)
        shutil.copy2(env_file, backup_env)
        return True

    print(c(RED, "✗") + " .env отсутствует или пуст!")

    # Пробуем восстановить из бэкапа
    if os.path.exists(backup_env) and os.path.getsize(backup_env) > 10:
        shutil.copy2(backup_env, env_file)
        print(c(GREEN, "✓") + " .env восстановлен из бэкапа")
        return True

    # Пробуем узнать пароль из контейнера БД
    print(c(YELLOW, "!") + " Попытка определить пароль БД из контейнера...")
    try:
        r = run(f"{COMPOSE} exec -T db env", check=False, capture=True)
        db_pass = ""
        for line in (r.stdout or "").split("\n"):
            if line.startswith("POSTGRES_PASSWORD="):
                db_pass = line.split("=", 1)[1].strip()
                break
        if db_pass:
            import secrets as _secrets
            secret_key = _secrets.token_hex(32)
            with open(env_file, "w") as f:
                f.write(f"DB_PASSWORD={db_pass}\n")
                f.write(f"SECRET_KEY={secret_key}\n")
                f.write(f"DOMAIN=localhost\n")
                f.write(f"TG_BOT_TOKEN=\n")
                f.write(f"TG_CHANNEL_ID=\n")
                f.write(f"TG_ADMIN_ID=\n")
            print(c(GREEN, "✓") + " .env создан с паролем из БД (проверьте DOMAIN и TG настройки)")
            print(c(YELLOW, "!") + f" Отредактируйте: nano {env_file}")
            return True
    except Exception:
        pass

    print(c(RED, "✗") + " Не удалось восстановить .env. Создайте вручную:")
    print(f"  nano {env_file}")
    return False

def status():
    print(c(BLUE, "→") + " Статус сервисов:\n")
    result = run(f"{COMPOSE} ps --format json", check=False, capture=True)

    # Парсим JSON вывод если доступен, иначе обычный вывод
    if result.returncode == 0 and result.stdout and result.stdout.strip().startswith('{'):
        import json
        for line in result.stdout.strip().split('\n'):
            try:
                svc = json.loads(line)
                name = svc.get("Service", svc.get("Name", "?"))
                state = svc.get("State", svc.get("Status", "?"))
                health = svc.get("Health", "")
                if "running" in state.lower() or "up" in state.lower():
                    icon = c(GREEN, "●")
                    status_text = "работает"
                    if health and "healthy" in health.lower():
                        status_text += " (healthy)"
                elif "restarting" in state.lower():
                    icon = c(YELLOW, "●")
                    status_text = "перезапускается"
                else:
                    icon = c(RED, "●")
                    status_text = state
                print(f"  {icon} {name:<16} {status_text}")
            except (json.JSONDecodeError, KeyError):
                pass
    else:
        run(f"{COMPOSE} ps", check=False)

    # Проверяем health
    print()
    try:
        r = run("curl -sf http://localhost:8000/api/health", check=False, capture=True)
        if r.returncode == 0:
            print(f"  {c(GREEN, '✓')} Backend API: работает")
        else:
            print(f"  {c(RED, '✗')} Backend API: не отвечает")
    except Exception:
        print(f"  {c(RED, '✗')} Backend API: не отвечает")

def start():
    if not ensure_env(): return
    print(c(BLUE, "→") + " Запуск сервисов...")
    run(f"{COMPOSE} up -d")
    print(c(GREEN, "✓") + " Сервисы запущены")

def stop():
    print(c(YELLOW, "!") + " Остановка сервисов...")
    run(f"{COMPOSE} down")
    print(c(GREEN, "✓") + " Сервисы остановлены")

def restart():
    if not ensure_env(): return
    stop()
    start()

def update():
    if not ensure_env(): return
    print(c(BLUE, "→") + " Обновление из репозитория...")

    # 1. Автобэкап БД перед обновлением
    print(c(BLUE, "→") + " Создание резервной копии БД перед обновлением...")
    try:
        backup()
    except Exception as e:
        print(c(YELLOW, "!") + f" Бэкап не удался ({e}), продолжаем...")

    # 2. Запоминаем текущий коммит для отката
    old_commit = run("git rev-parse --short HEAD", check=False, capture=True)
    old_hash = (old_commit.stdout or "").strip()
    print(f"  Текущий коммит: {old_hash}")

    # 3. Сохраняем SSL-конфиг если он настроен
    nginx_conf = f"{INSTALL_DIR}/nginx/nginx.conf"
    ssl_backup = None
    try:
        with open(nginx_conf) as f:
            content = f.read()
        if "ssl_certificate" in content:
            ssl_backup = content
            print(c(YELLOW, "!") + " SSL-конфиг сохранён")
    except FileNotFoundError:
        pass

    # 4. Сохраняем .env
    env_backup = None
    env_file = f"{INSTALL_DIR}/.env"
    try:
        with open(env_file) as f:
            env_backup = f.read()
    except FileNotFoundError:
        pass

    # 5. Сбрасываем конфликты и забираем обновления
    run("git merge --abort", check=False)
    run("git checkout -- .", check=False)
    run("git clean -fd", check=False)

    result = run("git pull origin main", check=False)
    if result.returncode != 0:
        print(c(RED, "✗") + " Git pull не удался. Пробуем жёсткий сброс...")
        run("git fetch origin main", check=False)
        run("git reset --hard origin/main", check=False)

    # 6. Восстанавливаем SSL и .env
    if ssl_backup:
        with open(nginx_conf, "w") as f:
            f.write(ssl_backup)
        print(c(GREEN, "✓") + " SSL-конфиг восстановлен")

    if env_backup:
        with open(env_file, "w") as f:
            f.write(env_backup)

    # 7. Пересборка
    print(c(BLUE, "→") + " Пересборка backend и frontend...")
    run(f"{COMPOSE} up -d --build --no-deps backend frontend")
    run(f"{COMPOSE} restart nginx", check=False)

    token_val = _get_env("TG_BOT_TOKEN", "")
    if token_val:
        print(c(BLUE, "→") + " Пересборка Telegram бота...")
        run(f"{COMPOSE} --profile bot up -d --build --no-deps bot")
        print(c(GREEN, "✓") + " Telegram бот обновлён")

    # 8. Health-check с таймаутом 60 сек
    print(c(BLUE, "→") + " Проверка здоровья backend (до 60 сек)...")
    import time
    healthy = False
    for i in range(20):
        try:
            r = run("curl -sf http://localhost:8000/api/health", check=False, capture=True)
            if r.returncode == 0:
                healthy = True
                break
        except Exception:
            pass
        time.sleep(3)

    if healthy:
        new_commit = run("git rev-parse --short HEAD", check=False, capture=True)
        print(c(GREEN, "✓") + f" Обновление завершено ({old_hash} → {(new_commit.stdout or '').strip()})")
    else:
        print(c(RED, "✗") + " Backend не отвечает после обновления!")
        confirm = input(f"  Откатить к коммиту {old_hash}? [y/N]: ").strip()
        if confirm.lower() == "y" and old_hash:
            print(c(BLUE, "→") + f" Откат к {old_hash}...")
            run(f"git checkout {old_hash}", check=False)
            run(f"{COMPOSE} up -d --build --no-deps backend frontend")
            print(c(GREEN, "✓") + " Откат завершён")
        else:
            print(c(YELLOW, "!") + " Проверьте логи: docker compose logs backend --tail=50")

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


def versions():
    """Показывает список версий и позволяет переключиться на любую."""
    print(c(BLUE, "→") + " Получаем список версий...")

    # Получаем локальные теги (обновляем с remote)
    run("git fetch --tags", check=False)

    result = run(
        'git tag -l --sort=-version:refname',
        check=False, capture=True
    )
    tags = [t.strip() for t in (result.stdout or "").splitlines() if t.strip()]

    # Текущая версия/коммит
    cur_result = run("git describe --tags --always", check=False, capture=True)
    current = (cur_result.stdout or "").strip()
    cur_commit = run("git rev-parse --short HEAD", check=False, capture=True)
    current_commit = (cur_commit.stdout or "").strip()

    print(f"\n  Текущая версия: {c(BOLD, current)} ({current_commit})")

    if not tags:
        print(c(YELLOW, "!") + " Теги не найдены. Создайте первый тег:")
        print(f"  git tag -a v1.0.0 -m \"Первый релиз\"")
        print(f"  git push origin v1.0.0")
        return

    print(f"\n  Доступные версии:")
    options = ["latest"] + tags
    for i, tag in enumerate(options):
        marker = " ← текущая" if tag == current else ""
        is_latest = " (последняя)" if tag == "latest" else ""
        print(f"  {c(BOLD, str(i))}. {tag}{is_latest}{c(GREEN, marker)}")

    print()
    try:
        choice = input("  Выберите версию (номер) или Enter для отмены: ").strip()
    except (KeyboardInterrupt, EOFError):
        return

    if not choice:
        print("Отменено")
        return

    try:
        idx = int(choice)
        if idx < 0 or idx >= len(options):
            print(c(YELLOW, "!") + " Неверный номер")
            return
    except ValueError:
        print(c(YELLOW, "!") + " Введите номер")
        return

    selected = options[idx]
    print()

    if selected == "latest":
        print(c(BLUE, "→") + " Обновление до последней версии...")
        run("git merge --abort", check=False)
        run("git checkout -- .", check=False)
        run("git checkout main", check=False)
        result = run("git pull origin main", check=False)
        if result.returncode != 0:
            run("git fetch origin main", check=False)
            run("git reset --hard origin/main", check=False)
    else:
        confirm = input(f"  Переключиться на {c(BOLD, selected)}? [y/N]: ").strip()
        if confirm.lower() != "y":
            print("Отменено")
            return
        print(c(BLUE, "→") + f" Переключаемся на {selected}...")
        run("git merge --abort", check=False)
        run("git checkout -- .", check=False)
        run(f"git checkout {selected}", check=False)

    print(c(BLUE, "→") + " Пересборка сервисов...")
    run(f"{COMPOSE} up -d --build --no-deps backend frontend")

    token_val = _get_env("TG_BOT_TOKEN", "")
    if token_val:
        run(f"{COMPOSE} --profile bot up -d --build --no-deps bot")

    new_ver = run("git describe --tags --always", check=False, capture=True)
    print(c(GREEN, "✓") + f" Активная версия: {(new_ver.stdout or '').strip()}")


def create_tag():
    """Создаёт новый тег (релиз) из текущего состояния."""
    cur = run("git describe --tags --always", check=False, capture=True)
    print(f"  Текущая версия: {(cur.stdout or '').strip()}")

    # Предлагаем следующую версию
    tags_r = run("git tag -l --sort=-version:refname", check=False, capture=True)
    tags = [t.strip() for t in (tags_r.stdout or "").splitlines() if t.strip()]
    if tags:
        last = tags[0].lstrip("v")
        parts = last.split(".")
        try:
            parts[-1] = str(int(parts[-1]) + 1)
            suggested = "v" + ".".join(parts)
        except ValueError:
            suggested = "v1.0.0"
    else:
        suggested = "v1.0.0"

    try:
        tag = input(f"  Имя тега [{suggested}]: ").strip() or suggested
        msg = input(f"  Описание релиза: ").strip() or f"Release {tag}"
    except (KeyboardInterrupt, EOFError):
        return

    run(f'git add -A')
    # Проверяем есть ли изменения
    diff = run("git diff --cached --name-only", check=False, capture=True)
    if diff.stdout and diff.stdout.strip():
        run(f'git commit -m "Release {tag}: {msg}"', check=False)
    run(f'git tag -a {tag} -m "{msg}"')
    run(f'git push origin main --tags')
    print(c(GREEN, "✓") + f" Тег {tag} создан и отправлен на GitHub")


MENU = """
  1.  Статус сервисов
  2.  Запустить
  3.  Остановить
  4.  Перезапустить
  5.  Обновить до последней версии
  6.  Выбрать версию / откат
  7.  Создать новый релиз (тег)
  8.  Просмотр логов
  9.  Создать резервную копию БД
  10. Восстановить из резервной копии
  11. Настроить SSL (Let's Encrypt)
  12. Создать администратора
  13. Информация о сервисе
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
        elif choice == "6":  versions()
        elif choice == "7":  create_tag()
        elif choice == "8":
            svc = input("Сервис (оставьте пустым для всех): ").strip()
            logs(svc or None)
        elif choice == "9":  backup()
        elif choice == "10": restore()
        elif choice == "11": ssl_setup()
        elif choice == "12": create_admin()
        elif choice == "13": show_info()
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
            "versions": versions, "tag": create_tag,
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
