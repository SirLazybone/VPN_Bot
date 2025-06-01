#!/usr/bin/env python3
"""
Скрипт для тестирования миграции множественных серверов
"""

import asyncio
import sys
import os

# Добавляем корневую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select
from db.database import async_session
from db.models import User, Server
from db.service.server_service import get_all_servers, get_default_server

async def test_migration():
    """Тестирует результаты миграции"""
    print("🧪 Тестирование миграции множественных серверов...\n")
    
    # Тест 1: Проверка конфигурации серверов в БД
    print("1️⃣ Проверка серверов в базе данных:")
    async with async_session() as session:
        try:
            servers = await get_all_servers(session)
            default_server = await get_default_server(session)
            
            if not servers:
                print("   ⚠️ Серверы в БД не найдены, будет использоваться fallback")
                from config.config import API_URL
                if API_URL:
                    print(f"   📡 Fallback URL: {API_URL}")
                else:
                    print("   ❌ Fallback URL тоже не настроен!")
            else:
                print(f"   📊 Всего серверов в БД: {len(servers)}")
                for server in servers:
                    status = "✅ Активен" if server.is_active else "❌ Неактивен"
                    default_mark = " 🎯" if default_server and server.id == default_server.id else ""
                    print(f"      {server.name}{default_mark}: {status}")
                    print(f"         ID: {server.id} | URL: {server.url}")
                    if server.description:
                        print(f"         📝 {server.description}")
        except Exception as e:
            print(f"   ❌ Ошибка при проверке серверов: {e}")
            return
    
    print()
    
    # Тест 2: Проверка базы данных пользователей
    print("2️⃣ Проверка базы данных:")
    async with async_session() as session:
        try:
            # Проверяем наличие колонки server_id
            result = await session.execute(select(User))
            users = result.scalars().all()
            
            if not users:
                print("   ℹ️ Пользователей в базе данных нет")
            else:
                print(f"   📊 Всего пользователей: {len(users)}")
                
                # Группируем по серверам
                server_stats = {}
                for user in users:
                    server_id = getattr(user, 'server_id', 1)  # Fallback на 1 если поле отсутствует
                    if server_id not in server_stats:
                        server_stats[server_id] = 0
                    server_stats[server_id] += 1
                
                print("   📈 Распределение по серверам:")
                for server_id, count in server_stats.items():
                    # Получаем информацию о сервере
                    server = await session.execute(select(Server).where(Server.id == server_id))
                    server_obj = server.scalar_one_or_none()
                    if server_obj:
                        server_name = server_obj.name
                    else:
                        server_name = f"Неизвестный сервер"
                    print(f"      {server_name} (ID: {server_id}): {count} пользователей")
                
                # Проверяем несколько пользователей
                print("\n   👥 Примеры пользователей:")
                for i, user in enumerate(users[:3]):  # Показываем первых 3
                    server_id = getattr(user, 'server_id', 1)
                    server = await session.execute(select(Server).where(Server.id == server_id))
                    server_obj = server.scalar_one_or_none()
                    server_name = server_obj.name if server_obj else f"Сервер {server_id}"
                    print(f"      @{user.username}: {server_name} (ID: {server_id})")
                    
        except Exception as e:
            print(f"   ❌ Ошибка при проверке базы данных: {e}")
            return
    
    # Тест 3: Проверка VPN клиентов
    print("\n3️⃣ Проверка VPN клиентов:")
    async with async_session() as session:
        try:
            from bot.vpn_api import VPNClient
            servers = await get_all_servers(session)
            
            if not servers:
                print("   ⚠️ Нет серверов в БД, тестируем fallback...")
                try:
                    client = VPNClient.from_fallback()
                    print(f"   ✅ Fallback клиент создан успешно")
                    print(f"      URL: {client.base_url}")
                except Exception as e:
                    print(f"   ❌ Ошибка создания fallback клиента: {e}")
            else:
                for server in servers:
                    try:
                        client = VPNClient.from_server(server)
                        status = "✅ Готов" if server.is_active else "⏸️ Неактивен"
                        print(f"   {status} {server.name}: VPN клиент создан успешно")
                        print(f"      URL: {client.base_url}")
                    except Exception as e:
                        print(f"   ❌ {server.name}: Ошибка создания VPN клиента - {e}")
                        
        except Exception as e:
            print(f"   ❌ Ошибка при тестировании VPN клиентов: {e}")
    
    print("\n✅ Тестирование завершено!")

async def main():
    """Запускает тестирование"""
    try:
        await test_migration()
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 