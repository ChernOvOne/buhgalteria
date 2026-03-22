#!/usr/bin/env bash
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
BOLD='\033[1m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }
info() { echo -e "${BLUE}[→]${NC} $1"; }
ask()  { read -p "  $1" "$2" </dev/tty; }

INSTALL_DIR="/opt/buhgalteria"
REPO_URL="https://github.com/ChernOvOne/buhgalteria.git"

echo ""
echo -e "${BOLD}╔══════════════════════════════════════╗${NC}"
echo -e "${BOLD}║     Установка Buhgalteria v1.0       ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════╝${NC}"
echo ""

[ "$(id -u)" -ne 0 ] && err "Запустите от root: sudo bash install.sh"

# ── Если уже установлено — чистим полностью ───────────────────────────────────
if [ -d "$INSTALL_DIR" ]; then
    warn "Найдена предыдущая установка — удаляем..."
    cd "$INSTALL_DIR" 2>/dev/null && docker compose down --volumes --remove-orphans 2>/dev/null || true
    rm -rf "$INSTALL_DIR"
    log "Старая установка удалена"
fi

if [ -f /etc/os-release ]; then
    . /etc/os-release
    [[ "$ID" != "ubuntu" ]] && warn "Рекомендуется Ubuntu 22.04/24.04, продолжаем..."
fi

info "Обновление пакетов..."
apt-get update -qq

info "Установка зависимостей..."
apt-get install -y -qq git curl openssl certbot 2>/dev/null || true

if ! command -v docker &>/dev/null; then
    info "Установка Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    log "Docker установлен"
else
    log "Docker уже установлен"
fi

if ! docker compose version &>/dev/null 2>&1; then
    info "Установка Docker Compose plugin..."
    mkdir -p /usr/local/lib/docker/cli-plugins
    curl -SL "https://github.com/docker/compose/releases/download/v2.27.0/docker-compose-linux-x86_64" \
        -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
    log "Docker Compose установлен"
else
    log "Docker Compose уже установлен"
fi

info "Клонирование репозитория..."
git clone "$REPO_URL" "$INSTALL_DIR"
cd "$INSTALL_DIR"
log "Репозиторий готов"

# ── Создаём .env напрямую (без .env.example) ──────────────────────────────────
info "Настройка окружения..."

SECRET_KEY=$(openssl rand -hex 32)
DB_PASSWORD=$(openssl rand -hex 16)

echo ""
ask "Введите домен или IP сервера: " DOMAIN
DOMAIN="${DOMAIN:-localhost}"

echo ""
ask "Telegram Bot Token (Enter чтобы пропустить): " TG_TOKEN
TG_CHAN=""
TG_ADMIN=""
if [ -n "$TG_TOKEN" ]; then
    ask "Telegram Channel ID для отчётов: " TG_CHAN
    ask "Ваш Telegram User ID: " TG_ADMIN
fi

cat > "$INSTALL_DIR/.env" << ENVEOF
DB_PASSWORD=$DB_PASSWORD
SECRET_KEY=$SECRET_KEY
DOMAIN=$DOMAIN
TG_BOT_TOKEN=$TG_TOKEN
TG_CHANNEL_ID=$TG_CHAN
TG_ADMIN_ID=$TG_ADMIN
ENVEOF

log ".env создан"

# ── Запуск сервисов ───────────────────────────────────────────────────────────
info "Сборка и запуск (займёт 2-5 минут)..."
docker compose up -d --build db redis backend frontend nginx
log "Основные сервисы запущены"

if [ -n "$TG_TOKEN" ]; then
    docker compose --profile bot up -d --build bot
    log "Telegram бот запущен"
fi

# ── Команда buh ───────────────────────────────────────────────────────────────
info "Установка команды buh..."
cat > /usr/local/bin/buh << 'EOF'
#!/usr/bin/env bash
cd /opt/buhgalteria
exec python3 cli.py "$@"
EOF
chmod +x /usr/local/bin/buh
log "Команда buh установлена"

# ── Ожидание backend ──────────────────────────────────────────────────────────
info "Ожидание запуска backend..."
for i in $(seq 1 40); do
    if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
        log "Backend готов"
        break
    fi
    printf "."
    sleep 3
    [ "$i" -eq 40 ] && echo "" && warn "Проверьте логи: docker compose logs backend"
done
echo ""

# ── SSL ───────────────────────────────────────────────────────────────────────
if [[ "$DOMAIN" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || [ "$DOMAIN" = "localhost" ]; then
    warn "IP/localhost — SSL пропускается"
else
    echo ""
    ask "Установить SSL (Let's Encrypt) для $DOMAIN? [y/N]: " INSTALL_SSL
    if [[ "$INSTALL_SSL" =~ ^[Yy]$ ]]; then
        ask "Email для SSL: " SSL_EMAIL
        mkdir -p /var/www/certbot
        if certbot certonly --webroot -w /var/www/certbot \
            -d "$DOMAIN" --non-interactive --agree-tos -m "$SSL_EMAIL"; then
            sed "s/DOMAIN_PLACEHOLDER/$DOMAIN/g" \
                "$INSTALL_DIR/nginx/nginx-ssl.conf.template" \
                > "$INSTALL_DIR/nginx/nginx.conf"
            docker compose restart nginx
            (crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet && docker compose -f $INSTALL_DIR/docker-compose.yml restart nginx") | crontab -
            log "SSL установлен, автообновление настроено"
        else
            warn "Не удалось получить сертификат — проверьте DNS"
        fi
    fi
fi

# ── Итог ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}══════════════════════════════════════${NC}"
echo -e "${BOLD}${GREEN}   Установка завершена успешно!${NC}"
echo -e "${BOLD}${GREEN}══════════════════════════════════════${NC}"
echo ""
echo -e "  Адрес:   ${BLUE}http://$DOMAIN${NC}"
echo -e "  API:     ${BLUE}http://$DOMAIN:8000/api/health${NC}"
echo ""
echo -e "  Логин:   ${BOLD}admin${NC}   Пароль: ${BOLD}admin123${NC}"
echo -e "  ${YELLOW}⚠ Смените пароль после первого входа!${NC}"
echo ""
echo -e "  Управление: ${BOLD}buh${NC}"
echo ""
