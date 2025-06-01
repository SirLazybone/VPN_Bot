"""
Комплексная миграция для приведения продакшена к текущему состоянию (PostgreSQL)
Добавляет таблицу серверов, новые поля пользователей и заполняет данные
"""

from sqlalchemy import text
from db.database import async_session
from datetime import datetime

async def production_migration_postgresql():
    """
    Комплексная миграция для продакшена (PostgreSQL):
    1. Создает таблицу серверов
    2. Добавляет поля server_id и trial_used в users
    3. Заполняет серверы данными
    4. Распределяет пользователей по серверам
    """
    async with async_session() as session:
        try:
            print("🚀 Запуск комплексной миграции для продакшена (PostgreSQL)...")
            
            # ===== ЭТАП 1: Создание таблицы серверов =====
            print("\n📋 Этап 1: Создание таблицы серверов...")
            
            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS servers (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR NOT NULL,
                    url VARCHAR NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    is_default BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    description VARCHAR
                )
            """))
            print("   ✅ Таблица servers создана")
            
            # ===== ЭТАП 2: Добавление полей в users =====
            print("\n👤 Этап 2: Добавление новых полей в таблицу users...")
            
            # Проверяем существующие поля (PostgreSQL способ)
            result = await session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND table_schema = 'public'
            """))
            columns = [row[0] for row in result.fetchall()]
            
            # Добавляем server_id если его нет
            if 'server_id' not in columns:
                await session.execute(text(
                    "ALTER TABLE users ADD COLUMN server_id INTEGER NULL"
                ))
                print("   ✅ Добавлено поле server_id (nullable)")
            else:
                print("   ℹ️ Поле server_id уже существует")
            
            # Добавляем trial_used если его нет
            if 'trial_used' not in columns:
                await session.execute(text(
                    "ALTER TABLE users ADD COLUMN trial_used BOOLEAN DEFAULT FALSE NOT NULL"
                ))
                print("   ✅ Добавлено поле trial_used")
            else:
                print("   ℹ️ Поле trial_used уже существует")
            
            await session.commit()
            
            # ===== ЭТАП 3: Заполнение серверов =====
            print("\n🖥️ Этап 3: Заполнение данных серверов...")
            
            # Проверяем, есть ли уже серверы
            result = await session.execute(text("SELECT COUNT(*) FROM servers"))
            servers_count = result.scalar()
            
            if servers_count == 0:
                servers_data = [
                    {
                        'id': 1,
                        'name': 'Netherland-1',
                        'url': 'vn.nethcloud.top:8080',
                        'is_active': True,
                        'is_default': True,
                        'description': 'Основной сервер Нидерланды'
                    },
                    {
                        'id': 2,
                        'name': 'Netherland-2',
                        'url': 'vn2.nethcloud.top:8080',
                        'is_active': True,
                        'is_default': False,
                        'description': 'Дополнительный сервер Нидерланды'
                    },
                    {
                        'id': 3,
                        'name': 'Paris-1',
                        'url': 'paris1.nethcloud.top:8080',
                        'is_active': True,
                        'is_default': False,
                        'description': 'Сервер Париж'
                    }
                ]
                
                for server in servers_data:
                    await session.execute(text("""
                        INSERT INTO servers (id, name, url, is_active, is_default, description)
                        VALUES (:id, :name, :url, :is_active, :is_default, :description)
                    """), server)
                    print(f"   ✅ Добавлен сервер: {server['name']} -> {server['url']}")
                
                # Сбрасываем последовательность для автоинкремента
                await session.execute(text("SELECT setval('servers_id_seq', 3)"))
                
                print(f"   📊 Создано серверов: {len(servers_data)}")
            else:
                print(f"   ℹ️ В таблице уже есть {servers_count} серверов")
            
            await session.commit()
            
            # ===== ЭТАП 4: Обновление trial_used для всех пользователей =====
            print("\n🎯 Этап 4: Установка trial_used = True для всех пользователей...")
            
            result = await session.execute(text("""
                UPDATE users SET trial_used = TRUE WHERE trial_used = FALSE AND vpn_link IS NOT NULL
            """))
            
            updated_trial_count = result.rowcount
            print(f"   ✅ Обновлено пользователей: {updated_trial_count}")
            
            await session.commit()
            
            # ===== ЭТАП 5: Распределение пользователей по серверам =====
            print("\n🎪 Этап 5: Распределение пользователей по серверам...")
            
            # Получаем количество пользователей, которым нужно назначить сервер
            result = await session.execute(text("""
                SELECT COUNT(*) FROM users WHERE vpn_link IS NOT NULL AND server_id IS NULL
            """))
            users_to_assign = result.scalar()
            
            if users_to_assign > 0:
                print(f"   👥 Пользователей с VPN для распределения: {users_to_assign}")
                
                # Распределяем пользователей по логике:
                # id 1-155 -> server_id = 1
                # id 156-308 -> server_id = 2  
                # id 309-542 -> server_id = 3
                # id 543+ -> server_id = 1
                
                # Сервер 1: пользователи 1-155
                result = await session.execute(text("""
                    UPDATE users 
                    SET server_id = 1 
                    WHERE id >= 1 AND id <= 155 
                    AND vpn_link IS NOT NULL 
                    AND server_id IS NULL
                """))
                updated_1 = result.rowcount
                
                # Сервер 2: пользователи 156-308
                result = await session.execute(text("""
                    UPDATE users 
                    SET server_id = 2 
                    WHERE id >= 156 AND id <= 308 
                    AND vpn_link IS NOT NULL 
                    AND server_id IS NULL
                """))
                updated_2 = result.rowcount
                
                # Сервер 3: пользователи 309-542
                result = await session.execute(text("""
                    UPDATE users 
                    SET server_id = 3 
                    WHERE id >= 309 AND id <= 542 
                    AND vpn_link IS NOT NULL 
                    AND server_id IS NULL
                """))
                updated_3 = result.rowcount
                
                # Сервер 1: пользователи 543+
                result = await session.execute(text("""
                    UPDATE users 
                    SET server_id = 1 
                    WHERE id >= 543 
                    AND vpn_link IS NOT NULL 
                    AND server_id IS NULL
                """))
                updated_4 = result.rowcount
                
                print(f"   📊 Распределение по серверам:")
                print(f"      🖥️ Сервер 1 (Netherland-1): {updated_1 + updated_4} пользователей")
                print(f"      🖥️ Сервер 2 (Netherland-2): {updated_2} пользователей")
                print(f"      🖥️ Сервер 3 (Paris-1): {updated_3} пользователей")
                print(f"      📈 Всего назначено: {updated_1 + updated_2 + updated_3 + updated_4}")
                
            else:
                print("   ℹ️ Нет пользователей для распределения")
            
            await session.commit()
            
            # ===== ЭТАП 6: Добавление внешнего ключа =====
            print("\n🔗 Этап 6: Добавление внешнего ключа...")
            
            # Проверяем целостность данных
            result = await session.execute(text("""
                SELECT COUNT(*) FROM users u 
                WHERE u.server_id IS NOT NULL 
                AND u.server_id NOT IN (SELECT id FROM servers)
            """))
            orphaned_users = result.scalar()
            
            if orphaned_users > 0:
                print(f"   ⚠️ Найдено {orphaned_users} пользователей с некорректными server_id")
                
                # Исправляем некорректные ссылки
                await session.execute(text("""
                    UPDATE users 
                    SET server_id = 1 
                    WHERE server_id IS NOT NULL 
                    AND server_id NOT IN (SELECT id FROM servers)
                """))
                print(f"   ✅ Исправлено {orphaned_users} пользователей -> сервер 1")
            else:
                print("   ✅ Все ссылки на серверы корректны")
            
            # Проверяем существование внешнего ключа
            result = await session.execute(text("""
                SELECT COUNT(*) FROM information_schema.table_constraints 
                WHERE constraint_name = 'users_server_id_fkey' 
                AND table_name = 'users'
            """))
            fk_exists = result.scalar() > 0
            
            if not fk_exists:
                try:
                    await session.execute(text("""
                        ALTER TABLE users 
                        ADD CONSTRAINT users_server_id_fkey 
                        FOREIGN KEY (server_id) REFERENCES servers(id)
                    """))
                    print("   ✅ Добавлен внешний ключ users.server_id -> servers.id")
                except Exception as e:
                    print(f"   ⚠️ Не удалось добавить внешний ключ: {e}")
            else:
                print("   ℹ️ Внешний ключ уже существует")
            
            await session.commit()
            
            # ===== ФИНАЛЬНАЯ СТАТИСТИКА =====
            print("\n📊 Финальная статистика:")
            
            # Общая статистика пользователей
            result = await session.execute(text("SELECT COUNT(*) FROM users"))
            total_users = result.scalar()
            
            result = await session.execute(text("SELECT COUNT(*) FROM users WHERE vpn_link IS NOT NULL"))
            users_with_vpn = result.scalar()
            
            result = await session.execute(text("SELECT COUNT(*) FROM users WHERE trial_used = TRUE"))
            users_trial_used = result.scalar()
            
            print(f"   👥 Всего пользователей: {total_users}")
            print(f"   🖥️ С VPN конфигами: {users_with_vpn}")
            print(f"   🎯 Использовали пробный период: {users_trial_used}")
            
            # Статистика по серверам
            result = await session.execute(text("""
                SELECT s.id, s.name, COUNT(u.id) as user_count
                FROM servers s
                LEFT JOIN users u ON s.id = u.server_id AND u.vpn_link IS NOT NULL
                GROUP BY s.id, s.name
                ORDER BY s.id
            """))
            
            print(f"   🖥️ Распределение по серверам:")
            for row in result:
                server_id, server_name, user_count = row
                print(f"      {server_id}: {server_name} - {user_count} пользователей")
            
            await session.commit()
            print("\n✅ Комплексная миграция завершена успешно!")
            
        except Exception as e:
            print(f"❌ Ошибка при выполнении миграции: {e}")
            await session.rollback()
            raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(production_migration_postgresql()) 