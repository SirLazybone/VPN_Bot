import pytest
import asyncio
from db.database import async_session
from db.models import User, Server
from db.service.server_service import (
    get_default_server, create_server, set_default_server, 
    get_server_users_count, get_active_servers
)
from db.service.user_service import get_or_create_user
from bot.vpn_manager import VPNManager
from sqlalchemy import select, delete, update
from unittest.mock import Mock, patch, AsyncMock
import tempfile
import os


class MockTelegramUser:
    """Mock класс для имитации Telegram пользователя"""
    def __init__(self, id: int, username: str):
        self.id = id
        self.username = username


async def cleanup_test_data():
    """Очистка тестовых данных"""
    async with async_session() as session:
        # Удаляем тестовых пользователей
        await session.execute(delete(User).where(User.username.like('test_auto_%')))
        
        # Удаляем тестовые серверы
        await session.execute(delete(Server).where(Server.name.like('Test Auto Server%')))
        
        await session.commit()


async def create_test_servers(count: int = 3) -> list[Server]:
    """Создает тестовые серверы"""
    servers = []
    async with async_session() as session:
        for i in range(1, count + 1):
            server = Server(
                name=f"Test Auto Server {i}",
                url=f"https://test-auto-{i}.com:8080",
                description=f"Test server {i} for automatic distribution",
                is_active=True,
                is_default=False  # Все серверы без флага по умолчанию
            )
            session.add(server)
            
        await session.commit()
        
        # Получаем созданные серверы
        result = await session.execute(
            select(Server).where(Server.name.like('Test Auto Server%')).order_by(Server.id)
        )
        servers = result.scalars().all()
        
    return servers


async def create_test_users_on_server(server_id: int, count: int) -> list[User]:
    """Создает тестовых пользователей на конкретном сервере"""
    users = []
    async with async_session() as session:
        for i in range(count):
            user = User(
                telegram_id=900000 + server_id * 1000 + i,  # Уникальные ID
                username=f"test_auto_server{server_id}_user{i}",
                balance=0.0,
                is_active=True,
                server_id=server_id,
                vpn_link=f"test://vpn-link-{server_id}-{i}"
            )
            session.add(user)
            users.append(user)
            
        await session.commit()
        
    return users


@pytest.mark.asyncio
async def test_automatic_distribution_logic():
    """
    Тестирует логику автоматического распределения серверов
    """
    print("\n🤖 Тестирование автоматического распределения серверов...")
    
    # Очищаем тестовые данные
    await cleanup_test_data()
    
    try:
        # ===== ЭТАП 1: Создаем тестовые серверы =====
        print("   📊 Создаю тестовые серверы...")
        servers = await create_test_servers(3)
        
        assert len(servers) == 3, "Должно быть создано 3 сервера"
        print(f"   ✅ Создано {len(servers)} серверов")
        
        # ===== ЭТАП 2: Тестируем выбор сервера при автоматическом распределении =====
        print("   🎯 Тестирую автоматическое распределение (без сервера по умолчанию)...")
        
        async with async_session() as session:
            # Проверяем, что нет сервера по умолчанию
            default_server = await get_default_server(session)
            
            # При автоматическом распределении должен выбираться сервер с минимумом пользователей
            # Изначально все серверы пустые, должен выбраться первый
            assert default_server is not None, "Должен быть выбран сервер для автоматического распределения"
            print(f"   ✅ Выбран сервер: {default_server.name} (ID: {default_server.id})")
        
        # ===== ЭТАП 3: Добавляем пользователей на серверы неравномерно =====
        print("   👥 Добавляю пользователей на серверы...")
        
        # Сервер 1: 5 пользователей
        await create_test_users_on_server(servers[0].id, 5)
        
        # Сервер 2: 2 пользователя  
        await create_test_users_on_server(servers[1].id, 2)
        
        # Сервер 3: 8 пользователей
        await create_test_users_on_server(servers[2].id, 8)
        
        print(f"   📈 Распределение: Сервер 1 = 5, Сервер 2 = 2, Сервер 3 = 8")
        
        # ===== ЭТАП 4: Проверяем автоматический выбор сервера с минимумом пользователей =====
        print("   🔍 Проверяю выбор сервера с минимумом пользователей...")
        
        async with async_session() as session:
            # При автоматическом распределении должен выбраться сервер 2 (меньше всего пользователей)
            auto_server = await get_default_server(session)
            
            # Проверяем количество пользователей на выбранном сервере
            selected_users_count = await get_server_users_count(session, auto_server.id)
            
            print(f"   📊 Выбранный сервер: {auto_server.name} с {selected_users_count} пользователями")
            
            # Проверяем, что выбран действительно сервер с минимумом пользователей
            all_users_counts = []
            for server in servers:
                count = await get_server_users_count(session, server.id)
                all_users_counts.append(count)
                print(f"      {server.name}: {count} пользователей")
            
            min_users = min(all_users_counts)
            assert selected_users_count == min_users, f"Должен быть выбран сервер с минимумом пользователей ({min_users})"
            print(f"   ✅ Автоматическое распределение работает корректно!")
        
        # ===== ЭТАП 5: Тестируем установку конкретного сервера по умолчанию =====
        print("   🎯 Тестирую установку сервера по умолчанию...")
        
        async with async_session() as session:
            # Устанавливаем сервер 3 (с наибольшим количеством пользователей) как по умолчанию
            success = await set_default_server(session, servers[2].id)
            assert success, "Установка сервера по умолчанию должна пройти успешно"
            
            # Проверяем, что теперь выбирается именно этот сервер
            default_server = await get_default_server(session)
            assert default_server.id == servers[2].id, "Должен быть выбран установленный сервер по умолчанию"
            
            users_count = await get_server_users_count(session, default_server.id)
            print(f"   ✅ Установлен сервер по умолчанию: {default_server.name} ({users_count} пользователей)")
        
        # ===== ЭТАП 6: Возвращаем автоматическое распределение =====
        print("   🔄 Возвращаю автоматическое распределение...")
        
        async with async_session() as session:
            # Убираем флаг is_default у всех серверов (включаем автоматическое распределение)
            await session.execute(update(Server).values(is_default=False))
            await session.commit()
            
            # Проверяем, что снова выбирается сервер с минимумом пользователей
            auto_server = await get_default_server(session)
            selected_users_count = await get_server_users_count(session, auto_server.id)
            
            # Должен снова выбраться сервер 2 (с минимумом пользователей)
            assert auto_server.id == servers[1].id, "При автоматическом распределении должен выбираться сервер с минимумом пользователей"
            print(f"   ✅ Автоматическое распределение восстановлено: {auto_server.name} ({selected_users_count} пользователей)")
        
        print("\n🎉 Все тесты автоматического распределения прошли успешно!")
        
    finally:
        # Очищаем тестовые данные
        await cleanup_test_data()


@pytest.mark.asyncio
async def test_server_load_balancing():
    """
    Тестирует балансировку нагрузки при создании пользователей
    """
    print("\n⚖️ Тестирование балансировки нагрузки...")
    
    # Очищаем тестовые данные
    await cleanup_test_data()
    
    try:
        # Создаем 2 сервера для тестирования
        servers = await create_test_servers(2)
        
        # Мокаем VPN API чтобы не делать реальные запросы
        with patch('bot.vpn_manager.VPNClient') as mock_vpn_client:
            mock_instance = AsyncMock()
            mock_instance.create_vpn_config.return_value = {
                'subscription_url': 'test://vpn-config-link'
            }
            mock_vpn_client.from_server.return_value = mock_instance
            mock_vpn_client.from_fallback.return_value = mock_instance
            
            async with async_session() as session:
                vpn_manager = VPNManager(session)
                
                # Создаем несколько пользователей и проверяем распределение
                test_users = []
                for i in range(6):  # 6 пользователей
                    mock_user = MockTelegramUser(id=800000 + i, username=f"test_balance_user{i}")
                    user = await get_or_create_user(session, mock_user)
                    
                    # Создаем VPN конфигурацию (должна использоваться автоматическая балансировка)
                    vpn_link = await vpn_manager.create_vpn_config(user, subscription_days=30)
                    assert vpn_link is not None, f"VPN конфигурация должна быть создана для пользователя {i}"
                    
                    test_users.append(user)
                
                # Проверяем распределение пользователей по серверам
                server1_users = await get_server_users_count(session, servers[0].id)
                server2_users = await get_server_users_count(session, servers[1].id)
                
                print(f"   📊 Распределение пользователей:")
                print(f"      {servers[0].name}: {server1_users} пользователей")
                print(f"      {servers[1].name}: {server2_users} пользователей")
                
                # Проверяем, что пользователи распределились
                total_distributed = server1_users + server2_users
                assert total_distributed == 6, f"Должно быть распределено 6 пользователей, распределено: {total_distributed}"
                
                # Проверяем, что распределение более-менее равномерное (разница не больше 1)
                difference = abs(server1_users - server2_users)
                assert difference <= 1, f"Распределение должно быть равномерным, разница: {difference}"
                
                print(f"   ✅ Балансировка работает корректно! Разница: {difference}")
        
        print("\n🎉 Тесты балансировки нагрузки прошли успешно!")
        
    finally:
        # Очищаем тестовые данные  
        await cleanup_test_data()


@pytest.mark.asyncio
async def test_inactive_server_handling():
    """
    Тестирует обработку неактивных серверов при автоматическом распределении
    """
    print("\n❌ Тестирование обработки неактивных серверов...")
    
    # Очищаем тестовые данные
    await cleanup_test_data()
    
    try:
        # Создаем серверы
        servers = await create_test_servers(3)
        
        async with async_session() as session:
            # Деактивируем 2 сервера, оставляем только 1 активный
            await session.execute(
                update(Server)
                .where(Server.id.in_([servers[0].id, servers[1].id]))
                .values(is_active=False)
            )
            await session.commit()
            
            # Проверяем, что выбирается только активный сервер
            default_server = await get_default_server(session)
            assert default_server is not None, "Должен быть найден активный сервер"
            assert default_server.id == servers[2].id, "Должен быть выбран единственный активный сервер"
            assert default_server.is_active == True, "Выбранный сервер должен быть активным"
            
            print(f"   ✅ Выбран единственный активный сервер: {default_server.name}")
            
            # Деактивируем все серверы
            await session.execute(update(Server).values(is_active=False))
            await session.commit()
            
            # Проверяем, что не найдется ни одного сервера
            no_server = await get_default_server(session)
            assert no_server is None, "При отсутствии активных серверов должен возвращаться None"
            
            print(f"   ✅ При отсутствии активных серверов возвращается None")
        
        print("\n🎉 Тесты обработки неактивных серверов прошли успешно!")
        
    finally:
        # Очищаем тестовые данные
        await cleanup_test_data()


@pytest.mark.asyncio 
async def test_edge_cases():
    """
    Тестирует граничные случаи автоматического распределения
    """
    print("\n🔬 Тестирование граничных случаев...")
    
    # Очищаем тестовые данные
    await cleanup_test_data()
    
    try:
        async with async_session() as session:
            # СЛУЧАЙ 1: Нет серверов вообще
            print("   🕳️ Тестирую случай без серверов...")
            no_server = await get_default_server(session)
            assert no_server is None, "При отсутствии серверов должен возвращаться None"
            print("   ✅ Без серверов возвращается None")
            
            # СЛУЧАЙ 2: Создаем один сервер, но неактивный
            print("   💤 Тестирую случай с неактивным сервером...")
            inactive_server = Server(
                name="Inactive Test Server",
                url="https://inactive.test.com",
                is_active=False,
                is_default=False
            )
            session.add(inactive_server)
            await session.commit()
            
            no_active_server = await get_default_server(session)
            assert no_active_server is None, "Неактивный сервер не должен выбираться"
            print("   ✅ Неактивный сервер не выбирается")
            
            # СЛУЧАЙ 3: Активируем сервер
            print("   🔄 Активирую сервер...")
            await session.execute(
                update(Server).where(Server.id == inactive_server.id).values(is_active=True)
            )
            await session.commit()
            
            active_server = await get_default_server(session)
            assert active_server is not None, "Активный сервер должен быть найден"
            assert active_server.id == inactive_server.id, "Должен быть выбран активированный сервер"
            print(f"   ✅ Активированный сервер выбирается: {active_server.name}")
        
        print("\n🎉 Тесты граничных случаев прошли успешно!")
        
    finally:
        # Очищаем тестовые данные
        await cleanup_test_data()


if __name__ == "__main__":
    async def run_tests():
        """Запуск всех тестов"""
        print("🚀 Запуск тестов автоматического распределения серверов\n")
        
        try:
            await test_automatic_distribution_logic()
            await test_server_load_balancing()
            await test_inactive_server_handling()
            await test_edge_cases()
            
            print("\n" + "="*60)
            print("🎉 ВСЕ ТЕСТЫ АВТОМАТИЧЕСКОГО РАСПРЕДЕЛЕНИЯ ПРОЙДЕНЫ УСПЕШНО!")
            print("="*60)
            
        except Exception as e:
            print(f"\n❌ ОШИБКА В ТЕСТАХ: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            # Финальная очистка
            await cleanup_test_data()
    
    # Запускаем тесты
    asyncio.run(run_tests()) 