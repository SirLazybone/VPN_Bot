#!/usr/bin/env python3
"""
Скрипт для запуска продакшен миграции PostgreSQL
Приводит базу данных к актуальному состоянию с серверами и новыми полями
"""

import asyncio
import sys
import os
from datetime import datetime

# Добавляем корневую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db.migrations.production_migration_postgresql import production_migration_postgresql

def print_banner():
    """Выводит информационный баннер"""
    print("=" * 60)
    print("🚀 ПРОДАКШЕН МИГРАЦИЯ VPN_BOT (PostgreSQL)")
    print("=" * 60)
    print()
    print("Эта миграция выполнит следующие действия:")
    print("📋 1. Создаст таблицу servers")
    print("👤 2. Добавит поля server_id (nullable) и trial_used в users")
    print("🖥️ 3. Заполнит 3 сервера:")
    print("    • Netherland-1 (vn.nethcloud.top:8080)")
    print("    • Netherland-2 (vn2.nethcloud.top:8080)")
    print("    • Paris-1 (paris1.nethcloud.top:8080)")
    print("🎯 4. Установит trial_used = True для всех пользователей")
    print("🎪 5. Распределит пользователей по серверам:")
    print("    • ID 1-155 → Сервер 1")
    print("    • ID 156-308 → Сервер 2")
    print("    • ID 309-542 → Сервер 3")
    print("    • ID 543+ → Сервер 1")
    print("    (только для пользователей с vpn_link)")
    print("🔗 6. Добавит внешний ключ server_id -> servers(id)")
    print()
    print("⚠️  ВАЖНО: Сделайте резервную копию базы данных!")
    print("=" * 60)

def confirm_migration():
    """Запрашивает подтверждение на выполнение миграции"""
    while True:
        response = input("\n🤔 Продолжить миграцию? (y/N): ").strip().lower()
        if response in ['y', 'yes', 'да']:
            return True
        elif response in ['n', 'no', 'нет', '']:
            return False
        else:
            print("❌ Пожалуйста, введите 'y' для подтверждения или 'n' для отмены")

def suggest_backup():
    """Предлагает создать резервную копию"""
    print("\n💾 Рекомендация по резервному копированию PostgreSQL:")
    print("   # Резервная копия всей базы")
    print("   pg_dump -h localhost -U username -d database_name > backup_$(date +%Y%m%d_%H%M%S).sql")
    print("   # или через Docker")
    print("   docker exec postgres_container pg_dump -U username database_name > backup.sql")
    
    while True:
        response = input("\n✅ Резервная копия создана? (y/N): ").strip().lower()
        if response in ['y', 'yes', 'да']:
            return True
        elif response in ['n', 'no', 'нет', '']:
            print("⚠️  Настоятельно рекомендуется создать резервную копию перед миграцией!")
            continue_anyway = input("Продолжить без резервной копии? (y/N): ").strip().lower()
            return continue_anyway in ['y', 'yes', 'да']

async def run_migration_with_checks():
    """Запускает миграцию с предварительными проверками"""
    print_banner()
    
    # Проверяем переменные окружения для PostgreSQL
    required_env_vars = ['DATABASE_URL']  # или другие переменные которые вы используете
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Отсутствуют переменные окружения: {', '.join(missing_vars)}")
        print("   Убедитесь, что настроено подключение к PostgreSQL")
        return False
    
    # Предлагаем создать резервную копию
    if not suggest_backup():
        print("❌ Миграция отменена")
        return False
    
    # Запрашиваем финальное подтверждение
    if not confirm_migration():
        print("❌ Миграция отменена пользователем")
        return False
    
    print("\n🚀 Запуск миграции PostgreSQL...")
    print("⏰ Время начала:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    try:
        await production_migration_postgresql()
        print("⏰ Время завершения:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print("\n🎉 Миграция завершена успешно!")
        print("\n📝 Что дальше:")
        print("   1. Проверьте работу бота")
        print("   2. Убедитесь, что серверы доступны")
        print("   3. Протестируйте создание новых пользователей")
        print("   4. Проверьте внешние ключи: \\d users в psql")
        return True
        
    except Exception as e:
        print(f"\n❌ Ошибка при выполнении миграции: {e}")
        print("\n🔄 Действия при ошибке:")
        print("   1. Восстановите базу из резервной копии:")
        print("      psql -h localhost -U username -d database_name < backup.sql")
        print("   2. Проверьте логи на предмет проблем")
        print("   3. Обратитесь к разработчику")
        return False

async def main():
    """Основная функция"""
    try:
        success = await run_migration_with_checks()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Миграция прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 