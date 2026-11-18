#!/bin/bash
# deploy.sh — первоначальная установка на Hetzner Ubuntu 22.04
# Запуск: bash deploy.sh
set -e

APP_DIR="/opt/fish-agent"
REPO_URL="https://github.com/Aleksey7771/fish-agent.git"  # поменяй на свой репо

echo "=== Fish Agent Deploy ==="
echo ""

# 1. Обновление системы
echo "[1/7] Обновление системы..."
apt-get update -qq
apt-get upgrade -y -qq

# 2. Установка зависимостей
echo "[2/7] Установка Docker..."
apt-get install -y -qq curl git

# Docker
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

# Docker Compose plugin
if ! docker compose version &>/dev/null; then
    apt-get install -y -qq docker-compose-plugin
fi

echo "  Docker $(docker --version)"
echo "  Compose $(docker compose version)"

# 3. Создаём директорию приложения
echo "[3/7] Подготовка директории $APP_DIR..."
mkdir -p "$APP_DIR"
cd "$APP_DIR"

# 4. Клонируем или обновляем репозиторий
if [ -d ".git" ]; then
    echo "[4/7] Обновление кода (git pull)..."
    git pull origin main
else
    echo "[4/7] Клонирование репозитория..."
    git clone "$REPO_URL" .
fi

# 5. Создаём .env если его нет
echo "[5/7] Настройка .env..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "  ⚠️  ВАЖНО: заполни .env перед запуском:"
    echo "  nano $APP_DIR/.env"
    echo ""
    echo "  Обязательные поля:"
    echo "    BOT_TOKEN"
    echo "    OWNER_TELEGRAM_ID"
    echo "    ANTHROPIC_API_KEY"
    echo "    POSTGRES_PASSWORD"
    echo ""
    echo "  После заполнения запусти: cd $APP_DIR && make up"
    exit 0
fi

# 6. Создаём нужные директории
echo "[6/7] Создание директорий данных..."
mkdir -p data generated_pdfs pdf/assets tg_reader/session

# 7. Запускаем
echo "[7/7] Запуск Docker Compose..."
docker compose pull
docker compose up -d --build

echo ""
echo "=== Готово! ==="
echo ""
echo "Статус: docker compose ps"
echo "Логи:   docker compose logs -f bot"
echo "Стоп:   docker compose down"
echo ""
echo "Health: curl http://localhost:8080/health"
