# PostgreSQL + Docker Миграция VPN Bot

## Обзор

Специальная документация для использования PostgreSQL с Docker контейнерами. Включает адаптированные миграции и рекомендации по развертыванию.

## 🔄 Отличия от SQLite версии

### Основные изменения
- **Использование `information_schema`** вместо SQLite `PRAGMA`
- **SERIAL PRIMARY KEY** вместо `INTEGER PRIMARY KEY AUTOINCREMENT`
- **TRUE/FALSE** вместо `1/0` для boolean значений
- **Автоматические внешние ключи** и проверка целостности
- **Последовательности (sequences)** для автоинкремента

### Новые возможности
- ✅ Полная поддержка внешних ключей
- ✅ Проверка последовательностей
- ✅ Лучшая типизация данных
- ✅ Транзакционная безопасность

## 🐳 Docker Considerations

### Подключение к контейнеру PostgreSQL
```bash
# Если PostgreSQL в отдельном контейнере
docker exec -it postgres_container psql -U username -d database_name

# Если бот и PostgreSQL в docker-compose
docker-compose exec postgres psql -U username -d database_name
```

### Переменные окружения
```env
# Обновите .env или docker-compose.yml
DATABASE_URL=postgresql://username:password@postgres_host:5432/database_name

# Для Docker Compose
POSTGRES_HOST=postgres  # имя сервиса
POSTGRES_PORT=5432
POSTGRES_DB=vpn_bot_db
POSTGRES_USER=vpn_user
POSTGRES_PASSWORD=secure_password
```

## 📋 Специальные файлы для PostgreSQL

### 1. Миграция
- **`db/migrations/production_migration_postgresql.py`** - PostgreSQL версия миграции
- **`run_production_migration_postgresql.py`** - запуск PostgreSQL миграции

### 2. Проверка состояния
- **`db/migrations/check_production_state_postgresql.py`** - анализ PostgreSQL базы

## 🚀 Процесс миграции

### Шаг 1: Резервное копирование
```bash
# Прямое подключение
pg_dump -h localhost -U username -d database_name > backup_$(date +%Y%m%d_%H%M%S).sql

# Через Docker
docker exec postgres_container pg_dump -U username database_name > backup.sql

# Docker Compose
docker-compose exec postgres pg_dump -U username database_name > backup.sql
```

### Шаг 2: Проверка состояния
```bash
python db/migrations/check_production_state_postgresql.py
```

### Шаг 3: Выполнение миграции
```bash
python run_production_migration_postgresql.py
```

### Шаг 4: Проверка результата
```sql
-- Подключитесь к PostgreSQL и проверьте
\d users        -- структура таблицы users
\d servers      -- структура таблицы servers
SELECT COUNT(*) FROM servers;
SELECT server_id, COUNT(*) FROM users WHERE server_id IS NOT NULL GROUP BY server_id;
```

## 🐳 Docker Compose пример

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: vpn_bot_db
      POSTGRES_USER: vpn_user
      POSTGRES_PASSWORD: secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups  # для резервных копий
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U vpn_user -d vpn_bot_db"]
      interval: 30s
      timeout: 10s
      retries: 3

  bot:
    build: .
    environment:
      DATABASE_URL: postgresql://vpn_user:secure_password@postgres:5432/vpn_bot_db
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped

volumes:
  postgres_data:
```

## 📊 Особенности PostgreSQL миграции

### Проверка полей
```sql
-- PostgreSQL способ проверки колонок
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'users' AND table_schema = 'public';
```

### Последовательности
```sql
-- Проверка и сброс последовательностей
SELECT sequence_name, last_value FROM information_schema.sequences;
SELECT setval('servers_id_seq', 3);  -- устанавливаем следующий ID
```

### Внешние ключи
```sql
-- Проверка внешних ключей
SELECT 
    tc.constraint_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name = 'users';
```

## 🔧 Troubleshooting

### Проблема: Подключение к PostgreSQL
```bash
# Проверьте статус контейнера
docker ps | grep postgres

# Проверьте логи
docker logs postgres_container

# Проверьте сеть
docker network ls
docker network inspect vpn_bot_default
```

### Проблема: Права доступа
```sql
-- Предоставьте права пользователю
GRANT ALL PRIVILEGES ON DATABASE vpn_bot_db TO vpn_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO vpn_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO vpn_user;
```

### Проблема: Миграция прервана
```bash
# Восстановление из резервной копии
docker exec -i postgres_container psql -U username -d database_name < backup.sql

# Или через docker-compose
docker-compose exec -T postgres psql -U username -d database_name < backup.sql
```

## 🔄 Откат изменений

Если что-то пошло не так:

```sql
-- 1. Удалить добавленные поля
ALTER TABLE users DROP COLUMN IF EXISTS server_id;
ALTER TABLE users DROP COLUMN IF EXISTS trial_used;

-- 2. Удалить таблицу серверов
DROP TABLE IF EXISTS servers;

-- 3. Или полный откат из резервной копии
DROP DATABASE vpn_bot_db;
CREATE DATABASE vpn_bot_db;
-- Затем восстановить из backup.sql
```

## 📈 Производительность

### Индексы для больших таблиц
```sql
-- Добавьте индексы после миграции для лучшей производительности
CREATE INDEX idx_users_server_id ON users(server_id);
CREATE INDEX idx_users_is_active ON users(is_active);
CREATE INDEX idx_users_subscription_end ON users(subscription_end);
```

### Мониторинг
```sql
-- Размер таблиц
SELECT 
    schemaname,
    tablename,
    attname,
    n_distinct,
    correlation
FROM pg_stats 
WHERE tablename IN ('users', 'servers', 'payments');
```

## 🔐 Безопасность

### Переменные окружения в Docker
```bash
# Используйте Docker secrets для продакшена
echo "secure_password" | docker secret create postgres_password -

# В docker-compose.yml
secrets:
  postgres_password:
    external: true
```

### Сетевая изоляция
```yaml
# Создайте отдельную сеть для базы данных
networks:
  backend:
    driver: bridge
    internal: true  # нет доступа в интернет
```

## ✅ Checklist после миграции

- [ ] Проверить подключение к PostgreSQL
- [ ] Убедиться что все таблицы созданы
- [ ] Проверить внешние ключи
- [ ] Протестировать создание пользователя
- [ ] Проверить админ-панель
- [ ] Убедиться что бот запускается
- [ ] Проверить логи на ошибки
- [ ] Сделать финальную резервную копию

---

**🐳 Примечание**: Docker добавляет слой абстракции, но основная логика миграции остается той же. Главное - правильно настроить подключение к PostgreSQL и учесть особенности SQL синтаксиса. 