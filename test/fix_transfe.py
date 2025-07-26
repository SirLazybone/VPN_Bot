import asyncio
from db.database import async_session
from db.models import User
from bot.vpn_manager import VPNManager
from sqlalchemy import and_, select
from datetime import timedelta, datetime
import logging
import time

logging.basicConfig(level=logging.INFO)

async def regenerate_vpn_links():
    """Регенерирует VPN ссылки для всех активных пользователей"""
    async with async_session() as session:
        # Получаем всех активных пользователей
        users = (await session.execute(
            select(User).where(
                User.is_active == True
            )
        )).scalars().all()

        logging.info(f"Найдено пользователей: {len(users)}")
        good = 0
        bad = 0

        for user in users:
            logging.info(f"Обрабатываем пользователя {user.username} (telegram_id={user.telegram_id})")
            vpn_manager = VPNManager(session)

            subscription_days = (user.subscription_end - datetime.utcnow()).days

            vpn_link = await vpn_manager.create_vpn_config(user=user, subscription_days=subscription_days)
            if vpn_link:
                good += 1
                user.vpn_link = vpn_link
                logging.info(f"VPN-конфиг обновлен для пользователя {user.username}")
            else:
                bad += 1
                logging.info(f"Ошибка создания VPN-конфига для пользователя {user.username}")
            await asyncio.sleep(1)
        await session.commit()
        logging.info(f"Good: {good}\nBad: {bad}\n")
        logging.info("Готово!")

if __name__ == "__main__":
    asyncio.run(regenerate_vpn_links())