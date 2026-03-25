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

if [ -f /etc/os-release ]; then
    . /etc/os-release
    [[ "$ID" != "ubuntu" ]] && warn "Рекомендуется Ubuntu 22.04/24.04, продолжаем..."
fi

# ── Ждём освобождения apt/dpkg ────────────────────────────────────────────────
wait_apt() {
    local waited=0
    while fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 \
       || fuser /var/lib/dpkg/lock >/dev/null 2>&1 \
       || fuser /var/lib/apt/lists/lock >/dev/null 2>&1; do
        if [ "$waited" -eq 0 ]; then
            info "Ожидаем завершения системных обновлений..."
        fi
        sleep 3
        waited=$((waited + 3))
        [ "$waited" -ge 180 ] && err "apt заблокирован более 3 минут. Перезагрузите сервер и попробуйте снова."
    done
    [ "$waited" -gt 0 ] && log "apt свободен, продолжаем"
}

# Убиваем unattended-upgrades если он работает слишком долго
kill_unattended() {
    if pgrep -x unattended-upgr >/dev/null 2>&1; then
        warn "Останавливаем фоновые обновления..."
        systemctl stop unattended-upgrades 2>/dev/null || true
        # Ждём ещё раз
        sleep 3
    fi
}

kill_unattended
wait_apt

# ── Обновление пакетов ────────────────────────────────────────────────────────
info "Обновление списка пакетов..."
apt-get update -qq
log "Пакеты обновлены"

wait_apt
info "Установка зависимостей (git, curl, openssl, certbot)..."
DEBIAN_FRONTEND=noninteractive apt-get install -y git curl openssl certbot
log "Зависимости установлены"

# ── Docker ────────────────────────────────────────────────────────────────────
if command -v docker &>/dev/null; then
    log "Docker уже установлен ($(docker --version | cut -d' ' -f3 | tr -d ','))"
else
    wait_apt
    info "Установка Docker..."
    # Устанавливаем вручную без скрипта get.docker.com чтобы контролировать apt lock
    DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl gnupg
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        | tee /etc/apt/sources.list.d/docker.list > /dev/null
    wait_apt
    apt-get update -qq
    wait_apt
    DEBIAN_FRONTEND=noninteractive apt-get install -y docker-ce docker-ce-cli containerd.io
    systemctl enable docker
    systemctl start docker
    log "Docker установлен ($(docker --version | cut -d' ' -f3 | tr -d ','))"
fi

# ── Docker Compose ────────────────────────────────────────────────────────────
if docker compose version &>/dev/null 2>&1; then
    log "Docker Compose уже установлен"
else
    info "Установка Docker Compose plugin..."
    mkdir -p /usr/local/lib/docker/cli-plugins
    curl -SL "https://github.com/docker/compose/releases/download/v2.27.0/docker-compose-linux-x86_64" \
        -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
    log "Docker Compose установлен"
fi

# ── Если уже установлено — чистим ────────────────────────────────────────────
if [ -d "$INSTALL_DIR" ]; then
    warn "Найдена предыдущая установка — удаляем..."
    cd /root
    docker compose -f "$INSTALL_DIR/docker-compose.yml" down --volumes --remove-orphans 2>/dev/null || true
    rm -rf "$INSTALL_DIR"
    log "Старая установка удалена"
fi

# ── Клонирование ──────────────────────────────────────────────────────────────
info "Клонирование репозитория..."
git clone "$REPO_URL" "$INSTALL_DIR"
cd "$INSTALL_DIR"
log "Репозиторий готов"

# ── Создаём .env ──────────────────────────────────────────────────────────────
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

# ── Защита .env ──────────────────────────────────────────────────────────────
# Бэкап .env в защищённое место (за пределами git)
mkdir -p /opt/buhgalteria-backups
cp "$INSTALL_DIR/.env" /opt/buhgalteria-backups/.env.backup
log ".env сохранён в /opt/buhgalteria-backups/.env.backup"

# .gitignore уже в репозитории, но на всякий случай
if ! grep -q "^\.env$" "$INSTALL_DIR/.gitignore" 2>/dev/null; then
    echo ".env" >> "$INSTALL_DIR/.gitignore"
fi

# Запрещаем git отслеживать .env
cd "$INSTALL_DIR" && git update-index --assume-unchanged .env 2>/dev/null || true

# ── Запуск сервисов ───────────────────────────────────────────────────────────
info "Сборка Docker образов и запуск (займёт 3-7 минут)..."
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
info "Ожидание запуска backend (до 2 минут)..."
for i in $(seq 1 40); do
    if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
        log "Backend готов!"
        break
    fi
    printf "."
    sleep 3
    [ "$i" -eq 40 ] && echo "" && warn "Backend долго стартует. Проверьте: docker compose logs backend"
done
echo ""

# ── Файрвол ───────────────────────────────────────────────────────────────────
if command -v ufw &>/dev/null; then
    info "Настройка файрвола..."
    ufw allow 22/tcp  >/dev/null 2>&1
    ufw allow 80/tcp  >/dev/null 2>&1
    ufw allow 443/tcp >/dev/null 2>&1
    ufw allow 8000/tcp>/dev/null 2>&1
    echo "y" | ufw enable >/dev/null 2>&1
    log "Файрвол настроен (22, 80, 443, 8000)"
fi

# ── SSL ───────────────────────────────────────────────────────────────────────
if [[ "$DOMAIN" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || [ "$DOMAIN" = "localhost" ]; then
    warn "IP/localhost — SSL пропускается. Настройте домен и запустите 'buh' → пункт 9"
else
    echo ""
    ask "Установить SSL (Let's Encrypt) для $DOMAIN? [y/N]: " INSTALL_SSL
    if [[ "$INSTALL_SSL" =~ ^[Yy]$ ]]; then
        ask "Email для SSL уведомлений: " SSL_EMAIL
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

# ── Готово ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}══════════════════════════════════════${NC}"
echo -e "${BOLD}${GREEN}   Установка завершена успешно!${NC}"
echo -e "${BOLD}${GREEN}══════════════════════════════════════${NC}"
echo ""
echo -e "  Адрес:    ${BLUE}http://$DOMAIN${NC}"
echo -e "  API:      ${BLUE}http://$DOMAIN:8000/api/health${NC}"
echo -e "  Swagger:  ${BLUE}http://$DOMAIN:8000/docs${NC}"
echo ""
echo -e "  Логин:    ${BOLD}admin${NC}   Пароль: ${BOLD}admin123${NC}"
echo -e "  ${YELLOW}⚠ Смените пароль после первого входа!${NC}"
echo ""
echo -e "  Управление: ${BOLD}buh${NC}"
echo ""
