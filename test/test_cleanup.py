#!/usr/bin/env python3
"""
Скрипт для тестирования системы очистки пользователей
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

# Добавляем корневую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select
from db.database import async_session
from db.models import User, Server
from db.service.user_cleanup_service import (
    get_cleanup_stats, get_users_for_cleanup, cleanup_expired_users,
    mark_trial_as_used
)

async def create_test_data():
    """Создает тестовых пользователей для демонстрации очистки"""
    print("📝 Создание тестовых данных...")
    
    async with async_session() as session:
        # Проверяем, есть ли уже тестовые пользователи
        result = await session.execute(
            select(User).where(User.username.like('test_cleanup_%'))
        )
        existing_users = result.scalars().all()
        
        if existing_users:
            print(f"   ℹ️ Найдено {len(existing_users)} тестовых пользователей")
            return
        
        # Убеждаемся, что есть сервер
        result = await session.execute(select(Server).limit(1))
        server = result.scalar_one_or_none()
        if not server:
            server = Server(
                name="Test Server",
                url="https://test.com",
                is_active=True,
                is_default=True,
                description="Test server for cleanup"
            )
            session.add(server)
            await session.commit()
            await session.refresh(server)
        
        # Создаем тестовых пользователей
        test_users = [
            # Пользователь для очистки (неактивен больше недели)
            User(
                telegram_id=999001,
                username="test_cleanup_expired",
                is_active=False,
                subscription_end=datetime.utcnow() - timedelta(days=10),
                vpn_link="vless://test-expired-config",
                server_id=server.id,
                trial_used=True
            ),
            # Активный пользователь (не для очистки)
            User(
                telegram_id=999002,
                username="test_cleanup_active",
                is_active=True,
                subscription_end=datetime.utcnow() + timedelta(days=30),
                vpn_link="vless://test-active-config",
                server_id=server.id,
                trial_used=False
            ),
            # Недавно истекший (не для очистки - меньше недели)
            User(
                telegram_id=999003,
                username="test_cleanup_recent",
                is_active=False,
                subscription_end=datetime.utcnow() - timedelta(days=3),
                vpn_link="vless://test-recent-config",
                server_id=server.id,
                trial_used=True
            ),
            # Без VPN конфига (не для очистки)
            User(
                telegram_id=999004,
                username="test_cleanup_no_vpn",
                is_active=False,
                subscription_end=datetime.utcnow() - timedelta(days=20),
                vpn_link=None,
                server_id=server.id,
                trial_used=False
            )
        ]
        
        for user in test_users:
            session.add(user)
        
        await session.commit()
        print(f"   ✅ Создано {len(test_users)} тестовых пользователей")

async def test_cleanup_logic():
    """Тестирует логику очистки"""
    print("\n🧪 Тестирование логики очистки...")
    
    async with async_session() as session:
        # Получаем статистику
        stats = await get_cleanup_stats(session)
        print(f"\n📊 Общая статистика:")
        print(f"   👥 Всего пользователей: {stats['total_users']}")
        print(f"   ✅ Активных: {stats['active_users']}")
        print(f"   🖥️ С VPN конфигами: {stats['users_with_vpn']}")
        print(f"   🎯 Использовали пробный: {stats['trial_used_count']}")
        print(f"   🗑️ Кандидаты на очистку: {stats['cleanup_candidates']}")
        
        # Получаем пользователей для очистки
        cleanup_candidates = await get_users_for_cleanup(session)
        print(f"\n🗑️ Пользователи для очистки ({len(cleanup_candidates)}):")
        
        for user in cleanup_candidates:
            days_since = (datetime.utcnow() - user.subscription_end).days if user.subscription_end else 0
            trial_mark = "🎯" if user.trial_used else "⭕"
            print(f"   {trial_mark} @{user.username} - истекла {days_since} дн. назад")
        
        # Тестируем dry run
        print(f"\n👀 Тестирование предварительного просмотра...")
        dry_result = await cleanup_expired_users(session, dry_run=True)
        print(f"   Найдено для очистки: {dry_result['total_found']}")
        
        if dry_result['users']:
            print("   Детали:")
            for user_info in dry_result['users']:
                print(f"     @{user_info['username']} (сервер {user_info['server_id']}) - {user_info['days_since_expired']} дн.")

async def test_trial_logic():
    """Тестирует логику пробного периода"""
    print("\n🎯 Тестирование логики пробного периода...")
    
    async with async_session() as session:
        # Ищем тестового пользователя без использованного пробного периода
        result = await session.execute(
            select(User).where(
                User.username == "test_cleanup_no_vpn",
                User.trial_used == False
            )
        )
        test_user = result.scalar_one_or_none()
        
        if test_user:
            print(f"   📝 Пользователь @{test_user.username} не использовал пробный период")
            
            # Помечаем как использовавший пробный период
            await mark_trial_as_used(session, test_user)
            print(f"   ✅ Пробный период отмечен как использованный")
            
            # Проверяем изменение
            await session.refresh(test_user)
            print(f"   🎯 trial_used: {test_user.trial_used}")
        else:
            print("   ℹ️ Тестовый пользователь не найден или уже использовал пробный период")

async def cleanup_test_data():
    """Удаляет тестовые данные"""
    print("\n🧹 Очистка тестовых данных...")
    
    async with async_session() as session:
        # Удаляем тестовых пользователей
        result = await session.execute(
            select(User).where(User.username.like('test_cleanup_%'))
        )
        test_users = result.scalars().all()
        
        for user in test_users:
            await session.delete(user)
        
        await session.commit()
        print(f"   ✅ Удалено {len(test_users)} тестовых пользователей")

async def test_auto_cleanup():
    """Тестирует автоматическую очистку (имитация планировщика)"""
    print("\n🤖 Тестирование автоматической очистки...")
    
    try:
        from bot.scheduler import cleanup_vpn_servers
        print("   🔄 Запуск функции автоматической очистки...")
        await cleanup_vpn_servers()
        print("   ✅ Автоматическая очистка завершена")
    except Exception as e:
        print(f"   ❌ Ошибка при тестировании автоматической очистки: {e}")

async def main():
    """Основная функция тестирования"""
    try:
        print("🧪 ТЕСТИРОВАНИЕ СИСТЕМЫ ОЧИСТКИ ПОЛЬЗОВАТЕЛЕЙ")
        print("=" * 50)
        
        # Создаем тестовые данные
        await create_test_data()
        
        # Тестируем логику очистки
        await test_cleanup_logic()
        
        # Тестируем логику пробного периода
        await test_trial_logic()
        
        # Предлагаем реальную очистку
        print(f"\n❓ Выполнить реальную очистку? (y/N): ", end="")
        try:
            response = input().strip().lower()
            if response == 'y':
                print("🔄 Выполняется реальная очистка...")
                async with async_session() as session:
                    result = await cleanup_expired_users(session, dry_run=False)
                    print(f"   ✅ Очищено: {result['cleaned']}")
                    print(f"   ❌ Ошибок: {result['errors']}")
            else:
                print("   ℹ️ Реальная очистка пропущена")
        except (KeyboardInterrupt, EOFError):
            print("\n   ℹ️ Ввод прерван, реальная очистка пропущена")
        
        # Очищаем тестовые данные
        await cleanup_test_data()
        
        # Тестируем автоматическую очистку
        await test_auto_cleanup()
        
        print("\n✅ Тестирование завершено!")
        print("\n💡 Упрощенная логика очистки:")
        print("   • Автоматическая очистка запускается каждый день в 02:00")
        print("   • Удаляем с VPN серверов пользователей с is_active=False")
        print("   • И прошедшей неделей с subscription_end")
        print("   • Пользователи остаются в боте для отслеживания trial_used")
        print("   • Админы получают отчеты об очистке в Telegram")
        print("   • Поля vpn_server_active и last_vpn_activity больше не используются")
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 