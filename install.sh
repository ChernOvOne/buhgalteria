#!/usr/bin/env bash
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
BOLD='\033[1m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }
info() { echo -e "${BLUE}[→]${NC} $1"; }

INSTALL_DIR="/opt/buhgalteria"
REPO_URL="https://github.com/ChernOvOne/buhgalteria.git"

# Принудительно читаем ввод с терминала (а не из pipe)
exec </dev/tty

echo ""
echo -e "${BOLD}╔══════════════════════════════════════╗${NC}"
echo -e "${BOLD}║     Установка Buhgalteria v1.0       ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════╝${NC}"
echo ""

# ── Проверка root ──────────────────────────────────────────────────────────────
[ "$(id -u)" -ne 0 ] && err "Запустите скрипт от root: sudo bash install.sh"

# ── Проверка ОС ────────────────────────────────────────────────────────────────
. /etc/os-release
[[ "$ID" != "ubuntu" ]] && warn "Рекомендуется Ubuntu 22.04/24.04, продолжаем..."

# ── Установка зависимостей ────────────────────────────────────────────────────
info "Обновление пакетов..."
apt-get update -qq

info "Установка зависимостей..."
apt-get install -y -qq git curl openssl nginx-light certbot python3-certbot-nginx 2>/dev/null || true

# ── Docker ─────────────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    info "Установка Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    log "Docker установлен"
else
    log "Docker уже установлен"
fi

if ! command -v docker-compose &>/dev/null && ! docker compose version &>/dev/null 2>&1; then
    info "Установка Docker Compose..."
    curl -SL "https://github.com/docker/compose/releases/download/v2.27.0/docker-compose-linux-x86_64" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    log "Docker Compose установлен"
fi

# ── Клонирование репозитория ───────────────────────────────────────────────────
info "Клонирование репозитория..."
if [ -d "$INSTALL_DIR" ]; then
    warn "Директория $INSTALL_DIR уже существует, обновляем..."
    cd "$INSTALL_DIR" && git pull
else
    git clone "$REPO_URL" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"
log "Репозиторий готов"

# ── Генерация .env ─────────────────────────────────────────────────────────────
if [ ! -f "$INSTALL_DIR/.env" ]; then
    info "Генерация .env..."
    cp .env.example .env

    SECRET_KEY=$(openssl rand -hex 32)
    DB_PASSWORD=$(openssl rand -hex 16)
    sed -i "s/buhpass_change_me/$DB_PASSWORD/" .env
    sed -i "s/your-very-long-secret-key-change-this-in-production/$SECRET_KEY/" .env

    # Запрос домена
    echo ""
    read -p "Введите домен (или IP для тестового запуска): " DOMAIN
    sed -i "s/yourdomain.com/$DOMAIN/" .env

    # Запрос Telegram токена
    echo ""
    read -p "Telegram Bot Token (оставьте пустым чтобы пропустить): " TG_TOKEN
    if [ -n "$TG_TOKEN" ]; then
        sed -i "s/^TG_BOT_TOKEN=$/TG_BOT_TOKEN=$TG_TOKEN/" .env
        read -p "Telegram Channel ID: " TG_CHAN
        sed -i "s/^TG_CHANNEL_ID=$/TG_CHANNEL_ID=$TG_CHAN/" .env
        read -p "Ваш Telegram User ID: " TG_ADMIN
        sed -i "s/^TG_ADMIN_ID=$/TG_ADMIN_ID=$TG_ADMIN/" .env
    fi
    log ".env создан"
else
    log ".env уже существует, пропускаем"
fi

# ── Запуск сервисов ───────────────────────────────────────────────────────────
info "Сборка и запуск сервисов..."
docker compose up -d --build db redis backend frontend nginx

# Проверяем TG_BOT_TOKEN перед запуском бота
TG_TOKEN_VAL=$(grep '^TG_BOT_TOKEN=' .env | cut -d'=' -f2)
if [ -n "$TG_TOKEN_VAL" ]; then
    docker compose --profile bot up -d --build bot
    log "Telegram бот запущен"
fi

log "Все сервисы запущены"

# ── Установка CLI команды buh ─────────────────────────────────────────────────
info "Установка команды buh..."
cat > /usr/local/bin/buh << 'CLISCRIPT'
#!/usr/bin/env bash
cd /opt/buhgalteria
exec python3 cli.py "$@"
CLISCRIPT
chmod +x /usr/local/bin/buh
log "Команда buh установлена"

# ── Ожидание запуска backend ──────────────────────────────────────────────────
info "Ожидание запуска backend..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
        log "Backend готов"
        break
    fi
    sleep 2
    [ "$i" -eq 30 ] && warn "Backend не ответил за 60 сек, проверьте логи: docker compose logs backend"
done

# ── SSL (если это не IP-адрес) ────────────────────────────────────────────────
DOMAIN_VAL=$(grep '^DOMAIN=' .env | cut -d'=' -f2)
if [[ "$DOMAIN_VAL" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    warn "Домен выглядит как IP-адрес, SSL не устанавливается"
else
    echo ""
    read -p "Установить SSL сертификат Let's Encrypt для $DOMAIN_VAL? [y/N] " INSTALL_SSL
    if [[ "$INSTALL_SSL" =~ ^[Yy]$ ]]; then
        read -p "Email для Let's Encrypt: " SSL_EMAIL
        info "Получение SSL сертификата..."
        mkdir -p /var/www/certbot
        certbot certonly --webroot -w /var/www/certbot -d "$DOMAIN_VAL" \
            --non-interactive --agree-tos -m "$SSL_EMAIL" || { warn "SSL не удалось, проверьте DNS"; break; }
        # Подставляем домен в SSL конфиг
        sed "s/DOMAIN_PLACEHOLDER/$DOMAIN_VAL/g" \
            "$INSTALL_DIR/nginx/nginx-ssl.conf.template" \
            > "$INSTALL_DIR/nginx/nginx.conf"
        docker compose restart nginx
        # Автообновление сертификата через cron
        (crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet && docker compose -f $INSTALL_DIR/docker-compose.yml restart nginx") | crontab -
        log "SSL настроен. Автообновление добавлено в cron"
    fi
fi

# ── Готово ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}══════════════════════════════════════${NC}"
echo -e "${BOLD}${GREEN}  Установка завершена успешно!${NC}"
echo -e "${BOLD}${GREEN}══════════════════════════════════════${NC}"
echo ""
DOMAIN_VAL=$(grep '^DOMAIN=' .env | cut -d'=' -f2)
echo -e "  Веб-интерфейс:  ${BLUE}http://$DOMAIN_VAL${NC}"
echo -e "  API:            ${BLUE}http://$DOMAIN_VAL:8000/api${NC}"
echo -e "  Документация:   ${BLUE}http://$DOMAIN_VAL:8000/docs${NC}"
echo ""
echo -e "  Логин по умолчанию: ${BOLD}admin${NC} / ${BOLD}admin123${NC}"
echo -e "  ${YELLOW}Смените пароль после первого входа!${NC}"
echo ""
echo -e "  Управление: ${BOLD}buh${NC}"
echo ""
