#!/usr/bin/env python3
"""
Скрипт для тестирования связей между пользователями и серверами
"""

import asyncio
import sys
import os

# Добавляем корневую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import selectinload
from sqlalchemy import select
from db.database import async_session
from db.models import User, Server
from db.service.server_service import (
    get_servers_statistics, get_server_with_users,
    get_server_users_count, get_server_active_users_count
)

async def test_relationships():
    """Тестирует связи между пользователями и серверами"""
    print("🔗 Тестирование связей между пользователями и серверами\n")
    
    async with async_session() as session:
        # Тест 1: Проверка внешнего ключа
        print("1️⃣ Проверка внешнего ключа:")
        try:
            # Попытка создать пользователя с несуществующим server_id должна завершиться ошибкой
            result = await session.execute(select(Server).limit(1))
            existing_server = result.scalar_one_or_none()
            
            if existing_server:
                print(f"   ✅ Найден сервер с ID {existing_server.id} для тестирования")
            else:
                print("   ⚠️ Серверы не найдены, создаем тестовый сервер")
                from db.service.server_service import create_server
                existing_server = await create_server(session, "Test Server", "https://test.com", "Test server for FK")
                print(f"   ✅ Создан тестовый сервер с ID {existing_server.id}")
            
        except Exception as e:
            print(f"   ❌ Ошибка при проверке FK: {e}")
        
        # Тест 2: Статистика серверов
        print("\n2️⃣ Статистика серверов:")
        try:
            stats = await get_servers_statistics(session)
            print(f"   📊 Всего серверов: {stats['total_servers']}")
            print(f"   ✅ Активных серверов: {stats['active_servers']}")
            
            for server_data in stats["servers_data"][:3]:  # Показываем первые 3
                print(f"\n   🖥️ Сервер: {server_data['name']}")
                print(f"      ID: {server_data['id']}")
                print(f"      Активен: {'✅' if server_data['is_active'] else '❌'}")
                print(f"      Всего пользователей: {server_data['total_users']}")
                print(f"      Активных пользователей: {server_data['active_users']}")
                
        except Exception as e:
            print(f"   ❌ Ошибка при получении статистики: {e}")
        
        # Тест 3: Связи ORM
        print("\n3️⃣ Тестирование ORM связей:")
        try:
            # Получаем сервер с пользователями через relationship
            result = await session.execute(select(Server).limit(1))
            server = result.scalar_one_or_none()
            
            if server:
                server_with_users = await get_server_with_users(session, server.id)
                if server_with_users:
                    print(f"   ✅ Сервер '{server_with_users.name}' загружен с пользователями")
                    print(f"   👥 Пользователей через relationship: {len(server_with_users.users)}")
                    
                    # Показываем первых 3 пользователей
                    for i, user in enumerate(server_with_users.users[:3]):
                        print(f"      {i+1}. @{user.username} (ID: {user.id})")
                        print(f"         Активен на VPN: {'✅' if user.vpn_server_active else '❌'}")
                        print(f"         Пробный период: {'🎯' if user.trial_used else '⭕'}")
                else:
                    print("   ⚠️ Не удалось загрузить сервер с пользователями")
            else:
                print("   ⚠️ Серверы не найдены")
                
        except Exception as e:
            print(f"   ❌ Ошибка при тестировании ORM связей: {e}")
        
        # Тест 4: Проверка целостности данных
        print("\n4️⃣ Проверка целостности данных:")
        try:
            # Проверяем, что все пользователи ссылаются на существующие серверы
            result = await session.execute(
                select(User)
                .outerjoin(Server, User.server_id == Server.id)
                .where(Server.id.is_(None))
            )
            orphaned_users = result.scalars().all()
            
            if orphaned_users:
                print(f"   ❌ Найдено {len(orphaned_users)} пользователей с несуществующими серверами:")
                for user in orphaned_users[:5]:
                    print(f"      @{user.username} -> server_id: {user.server_id}")
            else:
                print("   ✅ Все пользователи правильно ссылаются на существующие серверы")
            
            # Проверяем пользователей без server_id
            result = await session.execute(
                select(User).where(User.server_id.is_(None))
            )
            users_without_server = result.scalars().all()
            
            if users_without_server:
                print(f"   ❌ Найдено {len(users_without_server)} пользователей без server_id")
            else:
                print("   ✅ Все пользователи имеют назначенный сервер")
                
        except Exception as e:
            print(f"   ❌ Ошибка при проверке целостности: {e}")
        
        # Тест 5: Производительность запросов
        print("\n5️⃣ Тестирование производительности:")
        try:
            import time
            
            # Тест загрузки всех пользователей с серверами
            start_time = time.time()
            result = await session.execute(
                select(User).options(selectinload(User.server)).limit(10)
            )
            users_with_servers = result.scalars().all()
            load_time = time.time() - start_time
            
            print(f"   ⚡ Загрузка 10 пользователей с серверами: {load_time:.3f}с")
            
            if users_with_servers:
                user = users_with_servers[0]
                if hasattr(user, 'server') and user.server:
                    print(f"   ✅ Связь работает: @{user.username} -> {user.server.name}")
                else:
                    print(f"   ⚠️ Связь не загружена для @{user.username}")
            
        except Exception as e:
            print(f"   ❌ Ошибка при тестировании производительности: {e}")
        
        print("\n" + "="*50)
        print("✅ Тестирование связей завершено!")
        print("\n💡 Теперь можно использовать:")
        print("   - user.server для доступа к серверу пользователя")
        print("   - server.users для доступа к пользователям сервера")
        print("   - Улучшенную статистику в админке")

async def main():
    """Запускает тестирование связей"""
    try:
        await test_relationships()
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 