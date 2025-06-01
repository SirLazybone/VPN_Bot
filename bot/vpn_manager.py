from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import User
from bot.vpn_api import VPNClient
from sheets.sheets import update_user_by_telegram_id
from config.config import VPN_PRICE
from db.service.server_service import get_server_by_id, get_default_server, get_all_servers
import asyncio


class VPNManager:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def _get_vpn_client(self, server_id: int) -> VPNClient:
        """Получает VPN клиент для конкретного сервера"""
        server = await get_server_by_id(self.db, server_id)
        if not server:
            raise ValueError(f"Сервер с ID {server_id} не найден")
        
        if not server.is_active:
            raise ValueError(f"Сервер {server.name} неактивен")
        
        return VPNClient.from_server(server)

    async def _get_default_vpn_client(self) -> tuple[VPNClient, int]:
        """Получает VPN клиент для сервера по умолчанию"""
        server = await get_default_server(self.db)
        if not server:
            # Fallback на старую конфигурацию если нет серверов в БД
            try:
                client = VPNClient.from_fallback()
                return client, 1  # Возвращаем ID 1 для fallback
            except ValueError:
                raise ValueError("Нет доступных серверов")
        
        return VPNClient.from_server(server), server.id

    async def create_vpn_config(
            self,
            user: User,
            subscription_days: int = 30,
            server_id: Optional[int] = None,
            is_trial: bool = False
    ) -> Optional[str]:
        """
        Create VPN configuration for a user and return the VPN link
        """
        # Определяем сервер для пользователя
        if server_id is not None:
            vpn_client = await self._get_vpn_client(server_id)
            assigned_server_id = server_id
        else:
            vpn_client, assigned_server_id = await self._get_default_vpn_client()
        
        # Create VPN configuration
        vpn_config = await vpn_client.create_vpn_config(
            username=user.username,
            expire_days=subscription_days
        )

        if not vpn_config or not vpn_config.get('links'):
            return None

        vpn_link = vpn_config['links'][0]

        # Обновляем данные пользователя
        user.balance -= VPN_PRICE
            
        user.vpn_link = vpn_link
        user.server_id = assigned_server_id  # Сохраняем ID сервера
        user.subscription_start = datetime.utcnow()
        user.subscription_end = datetime.utcnow() + timedelta(days=subscription_days)
        user.is_active = True
        
        # Отмечаем использование пробного периода
        if is_trial:
            user.trial_used = True

        await self.db.commit()
        await asyncio.gather(update_user_by_telegram_id(user.telegram_id, user))

        return vpn_link

    async def get_user_config(
            self,
            user: User
    ) -> Optional[Dict[str, Any]]:
        """Получает конфигурацию пользователя с правильного сервера"""
        if user.server_id is None:
            print(f"Пользователь {user.username} не имеет назначенного сервера")
            return None
            
        try:
            vpn_client = await self._get_vpn_client(user.server_id)
            vpn_config = await vpn_client.get_vpn_config(user.username)
            return vpn_config
        except ValueError as e:
            print(f"Ошибка получения конфигурации: {e}")
            return None

    async def renew_subscription(
            self,
            user: User,
            subscription_days: Optional[int] = None,
            new_expire_ts: Optional[int] = None
    ) -> bool:
        """
        Renew user's VPN subscription on their assigned server
        Если у пользователя нет VPN конфигурации, создает новую
        """
        
        # Если у пользователя нет server_id или vpn_link, создаем новую конфигурацию
        if user.server_id is None or user.vpn_link is None:
            print(f"Пользователь {user.username} не имеет VPN конфигурации, создаем новую")
            
            # Создаем новую VPN конфигурацию с сервера по умолчанию
            vpn_client, assigned_server_id = await self._get_default_vpn_client()
            
            # Определяем срок действия
            if new_expire_ts:
                expire_ts = new_expire_ts
            else:
                days = subscription_days or 30
                expire_ts = int((datetime.utcnow() + timedelta(days=days)).timestamp())
            
            # Создаем VPN конфигурацию
            vpn_config = await vpn_client.create_vpn_config(
                username=user.username,
                expire_days=subscription_days or 30
            )
            
            if not vpn_config or not vpn_config.get('links'):
                print(f"Не удалось создать VPN конфигурацию для {user.username}")
                return False
            
            # Обновляем данные пользователя
            user.vpn_link = vpn_config['links'][0]
            user.server_id = assigned_server_id
            
            await self.db.commit()
            print(f"Создана новая VPN конфигурация для {user.username} на сервере {assigned_server_id}")
            return True
        
        # Если у пользователя уже есть VPN конфигурация, обновляем её
        try:
            vpn_client = await self._get_vpn_client(user.server_id)
        except ValueError as e:
            print(f"Ошибка получения VPN клиента: {e}")
            return False

        old_vpn_config = await self.get_user_config(user=user)
        if not old_vpn_config:
            # Конфигурация потеряна на сервере, создаем новую
            print(f"Конфигурация пользователя {user.username} не найдена на сервере {user.server_id}, создаем новую")
            
            # Пытаемся создать новую конфигурацию на том же сервере
            try:
                vpn_client = await self._get_vpn_client(user.server_id)
                
                # Определяем срок действия
                if new_expire_ts:
                    expire_ts = new_expire_ts
                else:
                    days = subscription_days or 30
                    expire_ts = int((datetime.utcnow() + timedelta(days=days)).timestamp())
                
                vpn_config = await vpn_client.create_vpn_config(
                    username=user.username,
                    expire_days=subscription_days or 30
                )
                
                if vpn_config and vpn_config.get('links'):
                    user.vpn_link = vpn_config['links'][0]
                    await self.db.commit()
                    print(f"Создана новая VPN конфигурация для {user.username} на сервере {user.server_id}")
                    return True
                else:
                    print(f"Не удалось создать новую конфигурацию для {user.username}")
                    return False
                    
            except ValueError as e:
                print(f"Ошибка при создании новой конфигурации: {e}")
                return False

        # Обновляем существующую конфигурацию
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
        vpn_config = await vpn_client.update_vpn_config(
            username=user.username,
            status="active",
            expire=new_expire
        )

        if not vpn_config or not vpn_config.get('links'):
            print(f"Не удалось обновить VPN конфигурацию для {user.username}")
            return False

        print(f"Обновлена VPN конфигурация для {user.username} на сервере {user.server_id}")
        return True

    async def delete_user(self, username: str, server_id: Optional[int] = None) -> bool:
        """Удаляет пользователя с указанного сервера"""
        if server_id is not None:
            try:
                vpn_client = await self._get_vpn_client(server_id)
                response = await vpn_client.delete_user(username=username)
                return response == 200
            except ValueError as e:
                print(f"Ошибка при удалении с сервера {server_id}: {e}")
                return False
        else:
            # Если server_id не указан, пытаемся удалить со всех серверов
            success = False
            servers = await get_all_servers(self.db)
            for server in servers:
                try:
                    vpn_client = VPNClient.from_server(server)
                    response = await vpn_client.delete_user(username=username)
                    if response == 200:
                        success = True
                except Exception as e:
                    print(f"Ошибка при удалении с сервера {server.name}: {e}")
                    continue
            return success
        
