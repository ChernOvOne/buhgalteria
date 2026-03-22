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
SCRIPT_URL="https://raw.githubusercontent.com/ChernOvOne/buhgalteria/main/install.sh"

# Если запущен через pipe и это НЕ повторный запуск — скачиваем и перезапускаем
if [ ! -t 0 ] && [ "$1" != "--tty" ]; then
    echo "Скачиваем установщик..."
    curl -fsSL "$SCRIPT_URL" -o /tmp/buh_install.sh
    chmod +x /tmp/buh_install.sh
    exec bash /tmp/buh_install.sh --tty
fi

echo ""
echo -e "${BOLD}╔══════════════════════════════════════╗${NC}"
echo -e "${BOLD}║     Установка Buhgalteria v1.0       ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════╝${NC}"
echo ""

[ "$(id -u)" -ne 0 ] && err "Запустите от root: sudo bash install.sh"

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
if [ -d "$INSTALL_DIR/.git" ]; then
    warn "Проект уже установлен, обновляем..."
    cd "$INSTALL_DIR" && git pull --rebase
else
    git clone "$REPO_URL" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"
log "Репозиторий готов"

if [ ! -f "$INSTALL_DIR/.env" ]; then
    info "Настройка окружения..."
    cp .env.example .env

    SECRET_KEY=$(openssl rand -hex 32)
    DB_PASSWORD=$(openssl rand -hex 16)
    sed -i "s/buhpass_change_me/$DB_PASSWORD/" .env
    sed -i "s/your-very-long-secret-key-change-this-in-production/$SECRET_KEY/" .env

    echo ""
    read -p "  Введите домен или IP сервера: " DOMAIN
    DOMAIN="${DOMAIN:-localhost}"
    sed -i "s/yourdomain.com/$DOMAIN/" .env

    echo ""
    read -p "  Telegram Bot Token (Enter чтобы пропустить): " TG_TOKEN
    if [ -n "$TG_TOKEN" ]; then
        sed -i "s|^TG_BOT_TOKEN=.*|TG_BOT_TOKEN=$TG_TOKEN|" .env
        read -p "  Telegram Channel ID для отчётов: " TG_CHAN
        [ -n "$TG_CHAN" ] && sed -i "s|^TG_CHANNEL_ID=.*|TG_CHANNEL_ID=$TG_CHAN|" .env
        read -p "  Ваш Telegram User ID: " TG_ADMIN
        [ -n "$TG_ADMIN" ] && sed -i "s|^TG_ADMIN_ID=.*|TG_ADMIN_ID=$TG_ADMIN|" .env
    fi
    log ".env создан"
else
    log ".env уже существует, пропускаем"
fi

info "Сборка и запуск (займёт 2-5 минут)..."
docker compose up -d --build db redis backend frontend nginx
log "Основные сервисы запущены"

TG_TOKEN_VAL=$(grep '^TG_BOT_TOKEN=' .env | cut -d'=' -f2)
if [ -n "$TG_TOKEN_VAL" ]; then
    docker compose --profile bot up -d --build bot
    log "Telegram бот запущен"
fi

info "Установка команды buh..."
cat > /usr/local/bin/buh << 'EOF'
#!/usr/bin/env bash
cd /opt/buhgalteria
exec python3 cli.py "$@"
EOF
chmod +x /usr/local/bin/buh
log "Команда buh установлена"

info "Ожидание запуска backend..."
for i in $(seq 1 40); do
    if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
        log "Backend готов"
        break
    fi
    printf "."
    sleep 3
    [ "$i" -eq 40 ] && echo "" && warn "Backend долго стартует — проверьте: docker compose logs backend"
done
echo ""

DOMAIN_VAL=$(grep '^DOMAIN=' .env | cut -d'=' -f2)
if [[ "$DOMAIN_VAL" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || [ "$DOMAIN_VAL" = "localhost" ]; then
    warn "IP/localhost — SSL пропускается"
else
    echo ""
    read -p "  Установить SSL (Let's Encrypt) для $DOMAIN_VAL? [y/N]: " INSTALL_SSL
    if [[ "$INSTALL_SSL" =~ ^[Yy]$ ]]; then
        read -p "  Email для SSL: " SSL_EMAIL
        mkdir -p /var/www/certbot
        if certbot certonly --webroot -w /var/www/certbot \
            -d "$DOMAIN_VAL" --non-interactive --agree-tos -m "$SSL_EMAIL"; then
            sed "s/DOMAIN_PLACEHOLDER/$DOMAIN_VAL/g" \
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

DOMAIN_VAL=$(grep '^DOMAIN=' .env | cut -d'=' -f2)
echo ""
echo -e "${BOLD}${GREEN}══════════════════════════════════════${NC}"
echo -e "${BOLD}${GREEN}   Установка завершена успешно!${NC}"
echo -e "${BOLD}${GREEN}══════════════════════════════════════${NC}"
echo ""
echo -e "  Адрес:   ${BLUE}http://$DOMAIN_VAL${NC}"
echo -e "  API:     ${BLUE}http://$DOMAIN_VAL:8000/api/health${NC}"
echo ""
echo -e "  Логин:   ${BOLD}admin${NC}   Пароль: ${BOLD}admin123${NC}"
echo -e "  ${YELLOW}⚠ Смените пароль после первого входа!${NC}"
echo ""
echo -e "  Управление: ${BOLD}buh${NC}"
echo ""
