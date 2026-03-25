# PROJECT_DOCS.md — Техническая документация

## Архитектура

```
Docker Compose:
  db (PostgreSQL 15) → :5432
  redis (Redis 7) → :6379
  backend (FastAPI/Python 3.11) → :8000
  frontend (React/Vite + nginx) → :3000
  nginx (reverse proxy) → :80/:443
  bot (aiogram, опционально) → TG Bot API
```

**Стек:** FastAPI, SQLAlchemy (async), PostgreSQL, Redis, React, Tailwind CSS, Vite, Docker.

## Структура бэкенда

```
backend/app/
├── main.py              # FastAPI app, lifespan (миграции, создание admin)
├── config.py            # Pydantic Settings (env vars)
├── database.py          # AsyncEngine, AsyncSessionLocal, Base
├── models/__init__.py   # Все SQLAlchemy модели
├── schemas/__init__.py  # Все Pydantic схемы
├── api/
│   ├── auth.py          # POST /login, GET /me
│   ├── users.py         # CRUD пользователей
│   ├── transactions.py  # CRUD транзакций (доходы/расходы)
│   ├── categories.py    # Категории + авто-правила
│   ├── partners.py      # Партнёры + инкассация
│   ├── payments.py      # Webhook платежей + API ключи
│   ├── customers.py     # Клиентская база (NEW v1.3)
│   ├── utm.py           # UTM редиректы (/go/{code}) + приём лидов
│   ├── other.py         # Серверы, Реклама, Recurring, Dashboard, Milestones, Stats
│   ├── reports.py       # PDF/Excel отчёты
│   ├── settings.py      # App settings (company, TG, etc)
│   ├── compare.py       # Сравнение периодов
│   └── notification_channels.py  # TG каналы уведомлений
├── services/
│   ├── notification_service.py   # Отправка в TG
│   ├── report_service.py         # Генерация PDF/Excel
│   └── compare_pdf.py           # PDF сравнения
└── core/
    ├── security.py      # JWT, хеширование паролей
    └── dependencies.py  # get_current_user, require_admin, require_editor
```

## Модели БД (ключевые)

| Таблица | Назначение |
|---------|-----------|
| users | Админы, редакторы, партнёры |
| transactions | Доходы и расходы |
| categories | Категории расходов |
| partners | Инвесторы/партнёры |
| inkas_records | Дивиденды, возврат инвестиций |
| servers | VPN-серверы (ручной ввод) |
| ad_campaigns | Рекламные кампании + UTM |
| customers | **Клиенты VPN** (telegram_id, LTV, подписка) |
| payments | Входящие платежи через webhook |
| api_keys | Ключи для webhook |
| utm_clicks | Клики по UTM-ссылкам |
| utm_leads | Лиды из LEADTEX |
| app_settings | Глобальные настройки (key-value) |
| notification_channels | TG каналы для уведомлений |
| recurring_payments | Регулярные платежи |
| monthly_stats | Ручная статистика |
| milestones | Цели бизнеса |
| audit_logs | Журнал действий |

## Потоки данных

### Рекламная воронка
```
1. Админ создаёт кампанию → генерируется utm_code (ad_xxxx)
2. Пользователь кликает /go/ad_xxxx → utm_clicks +1, редирект на бота
3. LEADTEX ловит /start=ad_xxxx → POST /api/utm/lead → utm_leads +1, customers +1
4. Пользователь оплачивает → POST /api/payments/webhook
   → payments +1, transactions +1 (income)
   → utm_leads.converted = True
   → customers.total_paid += amount, payments_count += 1
5. Админ видит воронку: клики → лиды → оплаты → ROI
```

### Платежи
```
POST /api/payments/webhook {api_key, amount, customer_id, plan, ...}
  → Проверка API ключа
  → Проверка дублей по external_id
  → Создание Transaction (income)
  → Создание Payment
  → Поиск UTM лида по customer_id → converted=true
  → Создание/обновление Customer (LTV, payments_count)
  → Уведомление в TG
```

## Известные проблемы и решения

### .env теряется при git pull
**Причина:** `git reset --hard` или `git checkout -- .` удаляет .env если он не в .gitignore
**Решение (v1.3):**
- `.gitignore` содержит `.env`
- CLI: `ensure_env()` проверяет .env перед каждой операцией
- CLI: автобэкап .env в `/opt/buhgalteria-backups/.env.backup`
- CLI: автовосстановление из бэкапа если .env пропал
- install.sh: бэкапит .env сразу после создания

### investor_partner_id пустая строка
**Причина:** фронтенд отправляет `investor_partner_id: ""` вместо null
**Решение (v1.3):** `investor_pid = data.investor_partner_id if data.investor_partner_id else None`
**Правило:** все FK поля должны быть None, не пустая строка

### UTM API двойной /api prefix
**Причина:** axios baseURL = '/api', а utmAPI содержал пути `/api/utm/...`
**Решение (v1.2):** убран /api из путей utmAPI в frontend/src/api/index.js
**Правило:** все API пути в фронтенде без /api prefix (axios добавляет автоматически)

### nginx SSL не проксирует /go/
**Причина:** в nginx-ssl.conf.template отсутствовал location /go/
**Решение (v1.2):** добавлен location /go/ в SSL шаблон

### Backend не стартует после обновления
**Причина:** обычно .env потерян (пароль БД не совпадает)
**Диагностика:** `docker compose logs backend --tail=20` → `InvalidPasswordError`
**Решение:** `ensure_env()` или ручное восстановление .env

## Переменные окружения (.env)

| Переменная | Обязательная | Описание |
|------------|-------------|----------|
| DB_PASSWORD | Да | Пароль PostgreSQL |
| SECRET_KEY | Да | Секрет для JWT (openssl rand -hex 32) |
| DOMAIN | Нет | Домен сервера (default: localhost) |
| TG_BOT_TOKEN | Нет | Токен TG бота для уведомлений |
| TG_CHANNEL_ID | Нет | ID канала для отчётов |
| TG_ADMIN_ID | Нет | TG ID администратора |

## Роли пользователей

| Роль | Права |
|------|-------|
| admin | Всё: настройки, пользователи, удаление |
| editor | Создание/редактирование транзакций, кампаний |
| investor | Только просмотр своего дашборда |
| partner | Только просмотр своей статистики |

## API endpoints (основные)

### Без авторизации
- `GET /go/{utm_code}` — UTM редирект
- `POST /api/utm/lead` — приём лида от LEADTEX
- `POST /api/payments/webhook` — приём платежа (нужен api_key в теле)
- `POST /api/auth/login` — логин

### С авторизацией (Bearer token)
- `GET /api/dashboard/` — дашборд
- `GET /api/transactions/` — транзакции
- `GET /api/customers/` — клиенты
- `GET /api/customers/stats` — статистика клиентов
- `GET /api/ads/` — кампании
- `GET /api/ads/funnel` — воронка по кампаниям
- `GET /api/ads/summary` — сводка по рекламе
- `GET /api/utm/stats/{code}` — статистика UTM
- `GET /api/utm/summary` — сводка UTM
- `GET /api/payments/stats/summary` — статистика платежей
- `GET /api/health` — проверка здоровья (version)

## Версионирование

- v1.0.0 — первый релиз
- v1.1.0 — фиксы UTM, Payment model, nginx SSL
- v1.2.0 — клиенты, маркетинг, воронка, LEADTEX интеграция
- v1.3.0 — фикс рекламы (FK), защита .env, документация, финальная сборка
