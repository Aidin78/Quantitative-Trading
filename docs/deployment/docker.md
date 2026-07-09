# استقرار (Deployment)

## محیط‌ها

| محیط | کاربرد | زیرساخت |
|------|--------|---------|
| **development** | توسعه لوکال | localhost |
| **staging** | تست قبل از production | VPS |
| **production** | لایو + Telegram | VPS + Docker |

## Docker Compose

### ساختار سرویس‌ها

```yaml
# docker-compose.yml
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - postgres
      - redis
    volumes:
      - ./data:/app/data
      - ./config:/app/config
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      # Browser runs on the host — must use localhost, not the docker service name.
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped

  postgres:
    image: timescale/timescaledb:latest-pg16
    environment:
      POSTGRES_USER: trading
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: trading
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    restart: unless-stopped

  # اختیاری — بک‌تست سنگین
  celery-worker:
    build: ./backend
    command: celery -A src.tasks worker -l info  # Phase 8 — اختیاری
    env_file: .env
    depends_on:
      - redis
      - postgres
    restart: unless-stopped

volumes:
  pgdata:
```

### Observability (Phase 8)

```bash
docker compose --profile observability up -d
```

| سرویس | پورت | توضیح |
|--------|------|--------|
| Prometheus | 9090 | scrape از `backend:8000/metrics` |
| Grafana | 3001 | داشبورد پیش‌فرض `QTP Overview` (admin/admin) |

متغیرهای اختیاری: `GRAFANA_USER`, `GRAFANA_PASSWORD`.

### Dockerfile — Backend

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN pip install poetry
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false && poetry install --no-dev

COPY . .
EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Dockerfile — Frontend

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

## Environment Variables (Production)

```env
# .env (هرگز در git)

# App
ENV=production
LOG_LEVEL=INFO

# Database
DATABASE_URL=postgresql+asyncpg://trading:SECRET@postgres:5432/trading
DB_PASSWORD=SECRET

# Redis
REDIS_URL=redis://redis:6379/0

# JWT
JWT_SECRET=long-random-secret
JWT_EXPIRE_MINUTES=60

# Telegram
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHANNEL_ID=...

# Exchange
EXCHANGE_API_KEY=...
EXCHANGE_API_SECRET=...

# Frontend
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
NEXT_PUBLIC_WS_URL=wss://api.yourdomain.com
```

## Reverse Proxy (Nginx)

```nginx
# /etc/nginx/sites-available/trading

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}

server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}
```

## VPS پیشنهادی

| سرویس | مشخصات | هزینه تقریبی |
|-------|--------|--------------|
| **Hetzner CX22** | 2 vCPU, 4GB RAM | ~€4/mo |
| **DigitalOcean** | 2 vCPU, 4GB RAM | ~$24/mo |

برای شروع، Hetzner CX22 کافی است.

## دستورات استقرار

```bash
# Clone
git clone <repo> && cd quantitative-trading

# Setup env
cp .env.example .env
# edit .env with real values

# Build & run
docker compose up -d --build

# Migrations
docker compose exec backend alembic upgrade head

# Logs
docker compose logs -f backend
docker compose logs -f frontend

# Stop
docker compose down
```

## Backup

### Database

```bash
# Daily cron
docker compose exec postgres pg_dump -U trading trading > backup_$(date +%Y%m%d).sql
```

### Config

```bash
tar -czf config_backup.tar.gz config/
```

## Monitoring (فاز بعد)

| ابزار | کاربرد |
|-------|--------|
| **Prometheus** | metrics |
| **Grafana** | dashboards |
| **Uptime Kuma** | uptime check |
| **Sentry** | error tracking |

## SSL

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

## Health Checks

```bash
# Backend
curl http://localhost:8000/health

# Frontend
curl http://localhost:3000

# Live status
curl http://localhost:8000/api/v1/live/status
```

## Security Checklist

- [ ] `.env` در `.gitignore`
- [ ] Firewall: فقط 80, 443, 22
- [ ] SSH key-only (بدون password)
- [ ] JWT secret قوی و random
- [ ] Exchange API: IP whitelist
- [ ] Telegram: فقط send به channel مشخص
- [ ] Database password قوی
- [ ] Regular backups
- [ ] `docker compose` بدون expose مستقیم postgres/redis به public
