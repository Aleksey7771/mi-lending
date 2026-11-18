.PHONY: up down restart logs build ps shell db-shell backup restore clean

# Запустить всё
up:
	docker compose up -d

# Остановить
down:
	docker compose down

# Перезапустить бота (после изменений кода)
restart:
	docker compose up -d --build bot

# Логи бота в реальном времени
logs:
	docker compose logs -f bot

# Логи всех сервисов
logs-all:
	docker compose logs -f

# Пересобрать образ
build:
	docker compose build bot

# Статус контейнеров
ps:
	docker compose ps

# Bash внутри бота
shell:
	docker compose exec bot bash

# Подключиться к PostgreSQL
db-shell:
	docker compose exec postgres psql -U $$(grep POSTGRES_USER .env | cut -d= -f2) -d $$(grep POSTGRES_DB .env | cut -d= -f2)

# Бэкап базы данных
backup:
	mkdir -p backups
	docker compose exec -T postgres pg_dump \
		-U $$(grep POSTGRES_USER .env | cut -d= -f2) \
		-d $$(grep POSTGRES_DB .env | cut -d= -f2) \
		> backups/backup_$$(date +%Y%m%d_%H%M%S).sql
	echo "Backup saved to backups/"

# Восстановить из бэкапа: make restore FILE=backups/backup_xxx.sql
restore:
	docker compose exec -T postgres psql \
		-U $$(grep POSTGRES_USER .env | cut -d= -f2) \
		-d $$(grep POSTGRES_DB .env | cut -d= -f2) \
		< $(FILE)

# Обновить код и перезапустить
deploy:
	git pull origin main
	docker compose up -d --build bot
	docker compose logs --tail=20 bot

# Удалить все данные (ОПАСНО!)
clean:
	docker compose down -v
	rm -rf generated_pdfs/*.pdf
