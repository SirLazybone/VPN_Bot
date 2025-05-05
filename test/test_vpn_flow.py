import asyncio
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.models import Base, User, Payment
from db.database import async_session
from bot.vpn_manager import VPNManager
from bot.vpn_api import VPNClient
import json
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем тестовую базу данных
engine = create_engine('sqlite:///test.db')
Session = sessionmaker(bind=engine)
Base.metadata.create_all(engine)

async def test_vpn_flow():
    """
    Тестирует полный цикл работы VPN бота:
    1. Создание пользователя
    2. Симуляция оплаты
    3. Создание VPN конфигурации
    4. Проверка конфигурации
    """
    logger.info("Начинаем тестирование VPN бота...")
    
    # Создаем тестового пользователя
    async with async_session() as session:
        test_user = User(
            telegram_id=123456789,
            username="test_user",
            balance=0.0,
            created_at=datetime.utcnow()
        )
        session.add(test_user)
        await session.commit()
        logger.info(f"Создан тестовый пользователь: {test_user.username}")

        # Симулируем успешную оплату
        payment = Payment(
            user_id=test_user.id,
            amount=150.0,
            payment_id="test_payment_123",
            status="completed",
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        session.add(payment)
        await session.commit()
        logger.info(f"Создан тестовый платеж: {payment.id}")

        # Создаем VPN конфигурацию
        vpn_manager = VPNManager(session)
        vpn_link = await vpn_manager.create_or_update_vpn_config(
            user=test_user,
            subscription_days=30
        )

        if not vpn_link:
            logger.error("Ошибка при создании VPN конфигурации")
            return

        logger.info("VPN конфигурация успешно создана!")
        logger.info(f"Ссылка на конфигурацию: {vpn_link}")
        
        # Обновляем данные пользователя
        await session.refresh(test_user)
        
        # Проверяем, что конфигурация сохранена в базе
        assert test_user.vpn_link == vpn_link, "VPN конфигурация не сохранена в базе"
        assert test_user.is_active, "Пользователь не активирован"
        assert test_user.subscription_end is not None, "Дата окончания подписки не установлена"
        assert test_user.subscription_end > datetime.utcnow(), "Некорректная дата окончания подписки"

        # Проверяем получение существующей конфигурации
        existing_link = await vpn_manager.get_vpn_config(test_user)
        assert existing_link == vpn_link, "Получена некорректная конфигурация"

        # Симулируем продление подписки
        renewal_link = await vpn_manager.renew_subscription(
            user=test_user,
            subscription_days=30
        )
        
        if not renewal_link:
            logger.error("Ошибка при продлении подписки")
            return
            
        await session.refresh(test_user)
        assert test_user.subscription_end is not None, "Дата окончания подписки не установлена после продления"
        assert test_user.subscription_end > datetime.utcnow() + timedelta(days=29), "Некорректная дата продления"

        logger.info("Тестирование успешно завершено!")

        # Выводим итоговую информацию
        logger.info("\nИтоговая информация:")
        logger.info(f"Пользователь: {test_user.username}")
        logger.info(f"Telegram ID: {test_user.telegram_id}")
        logger.info(f"VPN конфигурация: {test_user.vpn_link}")
        logger.info(f"Подписка активна: {test_user.is_active}")
        logger.info(f"Дата окончания подписки: {test_user.subscription_end}")

if __name__ == "__main__":
    asyncio.run(test_vpn_flow()) 