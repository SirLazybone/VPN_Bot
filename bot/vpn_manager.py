from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import User
from bot.vpn_api import VPNClient
from sheets.sheets import update_user_by_telegram_id
from config.config import VPN_PRICE
import asyncio


class VPNManager:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.vpn_client = VPNClient()

    async def create_vpn_config(
            self,
            user: User,
            subscription_days: int = 30
    ) -> Optional[str]:
        """
        Create VPN configuration for a user and return the VPN link
        """
        # Create VPN configuration
        vpn_config = await self.vpn_client.create_vpn_config(
            username=user.username,
            expire_days=subscription_days
        )

        if not vpn_config or not vpn_config.get('links'):
            return None

        vpn_link = vpn_config['links'][0]

        # Обновляем данные пользователя
        user.balance -= VPN_PRICE
        user.vpn_link = vpn_link
        user.subscription_start = datetime.utcnow()
        user.subscription_end = datetime.utcnow() + timedelta(days=subscription_days)
        user.is_active = True

        await self.db.commit()
        await asyncio.gather(update_user_by_telegram_id(user.telegram_id, user))

        return vpn_link

    async def get_user_config(
            self,
            user: User
    ) -> Optional[Dict[str, Any]]:
        vpn_config = await self.vpn_client.get_vpn_config(user.username)
        if not vpn_config:
            return None
        return vpn_config

    async def renew_subscription(
            self,
            user: User,
            subscription_days: Optional[int] = None,
            new_expire_ts: Optional[int] = None
    ) -> bool:
        """
        Renew user's VPN subscription
        """

        old_vpn_config = await self.get_user_config(user=user)
        if not old_vpn_config:
            raise Exception(f"Конфиг для пользователя с именем {user.username} не найден")

        old_expire_ts = old_vpn_config["expire"]
        now = datetime.utcnow().timestamp()
        if old_expire_ts < now:
            base_time = datetime.utcnow()
        else:
            base_time = datetime.utcfromtimestamp(old_expire_ts)

        if new_expire_ts:
            new_expire = new_expire_ts
        else:
            new_expire = int((base_time + timedelta(days=subscription_days)).timestamp())

        # Update VPN configuration
        vpn_config = await self.vpn_client.update_vpn_config(
            username=user.username,
            status="active",
            expire=new_expire
        )

        if not vpn_config or not vpn_config.get('links'):
            return False

        return True

    async def delete_user(self, username: str) -> bool:
        response = await self.vpn_client.delete_user(username=username)
        if response is not None:
            return True
        else:
            return False
