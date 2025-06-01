"""
Скрипт для анализа текущего состояния продакшен базы данных PostgreSQL
Помогает понять, что нужно мигрировать
"""

from sqlalchemy import text
from db.database import async_session

async def check_production_state_postgresql():
    """Анализирует текущее состояние базы данных PostgreSQL"""
    async with async_session() as session:
        try:
            print("🔍 АНАЛИЗ ТЕКУЩЕГО СОСТОЯНИЯ БАЗЫ ДАННЫХ PostgreSQL")
            print("=" * 60)
            
            # ===== ПРОВЕРКА ТАБЛИЦ =====
            print("\n📋 Существующие таблицы:")
            result = await session.execute(text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            """))
            
            tables = [row[0] for row in result.fetchall()]
            for table in tables:
                print(f"   ✅ {table}")
            
            # ===== СТРУКТУРА ТАБЛИЦЫ USERS =====
            print(f"\n👤 Структура таблицы users:")
            result = await session.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'users' AND table_schema = 'public'
                ORDER BY ordinal_position
            """))
            user_columns = []
            
            for row in result.fetchall():
                column_name, data_type, is_nullable, column_default = row
                user_columns.append(column_name)
                nullable = "NULL" if is_nullable == 'YES' else "NOT NULL"
                default_val = f" DEFAULT {column_default}" if column_default else ""
                print(f"   {column_name}: {data_type} {nullable}{default_val}")
            
            # ===== ПРОВЕРКА ОТСУТСТВУЮЩИХ ПОЛЕЙ =====
            print(f"\n🔍 Анализ отсутствующих полей:")
            missing_fields = []
            
            if 'server_id' not in user_columns:
                missing_fields.append('server_id')
                print("   ❌ server_id - отсутствует")
            else:
                print("   ✅ server_id - присутствует")
            
            if 'trial_used' not in user_columns:
                missing_fields.append('trial_used')
                print("   ❌ trial_used - отсутствует")
            else:
                print("   ✅ trial_used - присутствует")
            
            # ===== ПРОВЕРКА ВНЕШНИХ КЛЮЧЕЙ =====
            print(f"\n🔗 Внешние ключи:")
            result = await session.execute(text("""
                SELECT 
                    tc.constraint_name,
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints AS tc 
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                  ON ccu.constraint_name = tc.constraint_name
                  AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY' 
                AND tc.table_name = 'users'
            """))
            
            foreign_keys = result.fetchall()
            if foreign_keys:
                for fk in foreign_keys:
                    constraint_name, column_name, foreign_table, foreign_column = fk
                    print(f"   ✅ {column_name} -> {foreign_table}.{foreign_column}")
            else:
                print("   ❌ Внешние ключи отсутствуют")
            
            # ===== ПРОВЕРКА ТАБЛИЦЫ СЕРВЕРОВ =====
            print(f"\n🖥️ Таблица servers:")
            if 'servers' in tables:
                print("   ✅ Таблица servers существует")
                
                result = await session.execute(text("SELECT COUNT(*) FROM servers"))
                servers_count = result.scalar()
                print(f"   📊 Количество серверов: {servers_count}")
                
                if servers_count > 0:
                    result = await session.execute(text("""
                        SELECT id, name, url, is_active, is_default 
                        FROM servers ORDER BY id
                    """))
                    print("   📝 Существующие серверы:")
                    for row in result.fetchall():
                        server_id, name, url, is_active, is_default = row
                        status = "✅" if is_active else "❌"
                        default_mark = " [DEFAULT]" if is_default else ""
                        print(f"      {server_id}: {name} ({url}) {status}{default_mark}")
            else:
                print("   ❌ Таблица servers не существует")
            
            # ===== СТАТИСТИКА ПОЛЬЗОВАТЕЛЕЙ =====
            print(f"\n👥 Статистика пользователей:")
            
            # Общее количество
            result = await session.execute(text("SELECT COUNT(*) FROM users"))
            total_users = result.scalar()
            print(f"   👥 Всего пользователей: {total_users}")
            
            # С VPN конфигами
            result = await session.execute(text("SELECT COUNT(*) FROM users WHERE vpn_link IS NOT NULL"))
            users_with_vpn = result.scalar()
            print(f"   🖥️ С VPN конфигами: {users_with_vpn}")
            
            # Активные пользователи
            result = await session.execute(text("SELECT COUNT(*) FROM users WHERE is_active = TRUE"))
            active_users = result.scalar()
            print(f"   ✅ Активные: {active_users}")
            
            # Проверяем trial_used если поле существует
            if 'trial_used' in user_columns:
                result = await session.execute(text("SELECT COUNT(*) FROM users WHERE trial_used = TRUE"))
                trial_used_count = result.scalar()
                print(f"   🎯 Использовали пробный период: {trial_used_count}")
            
            # Проверяем server_id если поле существует
            if 'server_id' in user_columns:
                result = await session.execute(text("""
                    SELECT server_id, COUNT(*) as count 
                    FROM users 
                    WHERE server_id IS NOT NULL 
                    GROUP BY server_id 
                    ORDER BY server_id
                """))
                print(f"   🖥️ Распределение по серверам:")
                for row in result.fetchall():
                    server_id, count = row
                    print(f"      Сервер {server_id}: {count} пользователей")
            
            # ===== ДИАПАЗОНЫ ID ДЛЯ РАСПРЕДЕЛЕНИЯ =====
            print(f"\n📊 Анализ для распределения пользователей с VPN:")
            
            if users_with_vpn > 0:
                # Пользователи 1-155
                result = await session.execute(text("""
                    SELECT COUNT(*) FROM users 
                    WHERE id >= 1 AND id <= 155 AND vpn_link IS NOT NULL
                """))
                range_1 = result.scalar()
                
                # Пользователи 156-308
                result = await session.execute(text("""
                    SELECT COUNT(*) FROM users 
                    WHERE id >= 156 AND id <= 308 AND vpn_link IS NOT NULL
                """))
                range_2 = result.scalar()
                
                # Пользователи 309-542
                result = await session.execute(text("""
                    SELECT COUNT(*) FROM users 
                    WHERE id >= 309 AND id <= 542 AND vpn_link IS NOT NULL
                """))
                range_3 = result.scalar()
                
                # Пользователи 543+
                result = await session.execute(text("""
                    SELECT COUNT(*) FROM users 
                    WHERE id >= 543 AND vpn_link IS NOT NULL
                """))
                range_4 = result.scalar()
                
                print(f"   ID 1-155 → Сервер 1: {range_1} пользователей")
                print(f"   ID 156-308 → Сервер 2: {range_2} пользователей")
                print(f"   ID 309-542 → Сервер 3: {range_3} пользователей")
                print(f"   ID 543+ → Сервер 1: {range_4} пользователей")
                print(f"   📈 Всего к распределению: {range_1 + range_2 + range_3 + range_4}")
            
            # ===== ПРОВЕРКА ПОСЛЕДОВАТЕЛЬНОСТЕЙ =====
            # print(f"\n🔢 Последовательности (sequences):")
            # result = await session.execute(text("""
            #     SELECT sequence_name, last_value
            #     FROM information_schema.sequences
            #     WHERE sequence_schema = 'public'
            # """))
            #
            # sequences = result.fetchall()
            # if sequences:
            #     for seq_name, last_value in sequences:
            #         print(f"   📊 {seq_name}: {last_value}")
            # else:
            #     print("   ℹ️ Последовательности не найдены")
            
            # ===== РЕКОМЕНДАЦИИ =====
            print(f"\n💡 РЕКОМЕНДАЦИИ:")
            
            if not missing_fields and 'servers' in tables:
                print("   ✅ База данных уже обновлена!")
                if not foreign_keys:
                    print("   ⚠️ Рекомендуется добавить внешние ключи")
            else:
                print("   🔄 Требуется миграция:")
                if missing_fields:
                    print(f"      • Добавить поля: {', '.join(missing_fields)}")
                if 'servers' not in tables:
                    print("      • Создать таблицу servers")
                    print("      • Заполнить серверы данными")
                print("      • Распределить пользователей по серверам")
                print("      • Установить trial_used = TRUE для всех")
                if not foreign_keys:
                    print("      • Добавить внешние ключи")
            
            print(f"\n📝 Для запуска миграции используйте:")
            print(f"   python run_production_migration_postgresql.py")
            
            print("\n" + "=" * 60)
            print("✅ Анализ завершен")
            
        except Exception as e:
            print(f"❌ Ошибка при анализе базы данных: {e}")
            raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(check_production_state_postgresql()) 