from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import User
from bot.vpn_api import VPNClient
from config.config import VPN_PRICE
from db.service.server_service import get_server_by_id, get_default_server, get_all_servers
from bot.vpn_logger import vpn_manager_logger as logger
import asyncio


class VPNManager:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def _get_vpn_client(self, server_id: int) -> VPNClient:
        """Получает VPN клиент для конкретного сервера"""
        logger.info(f"🔍 Получаю VPN клиент для сервера ID: {server_id}")
        
        server = await get_server_by_id(self.db, server_id)
        if not server:
            logger.error(f"❌ Сервер с ID {server_id} не найден")
            raise ValueError(f"Сервер с ID {server_id} не найден")
        
        logger.info(f"✅ Найден сервер: {server.name} ({server.url})")
        
        if not server.is_active:
            logger.error(f"❌ Сервер {server.name} неактивен")
            raise ValueError(f"Сервер {server.name} неактивен")
        
        logger.info(f"✅ Сервер {server.name} активен, создаю VPN клиент")
        return VPNClient.from_server(server)

    async def _get_default_vpn_client(self) -> tuple[VPNClient, int]:
        """Получает VPN клиент для сервера по умолчанию"""
        logger.info("🔍 Получаю VPN клиент для сервера по умолчанию")
        
        server = await get_default_server(self.db)
        if not server:
            logger.warning("⚠️ Сервер по умолчанию не найден, пытаюсь использовать fallback")
            # Fallback на старую конфигурацию если нет серверов в БД
            try:
                client = VPNClient.from_fallback()
                logger.info("✅ Создан fallback VPN клиент")
                return client, 1  # Возвращаем ID 1 для fallback
            except ValueError as e:
                logger.error(f"❌ Ошибка создания fallback клиента: {e}")
                raise ValueError("Нет доступных серверов")
        
        logger.info(f"✅ Найден сервер по умолчанию: {server.name} (ID: {server.id})")
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
        logger.info(f"🚀 Начинаю создание VPN конфигурации для пользователя: {user.username}")
        logger.info(f"📊 Параметры: subscription_days={subscription_days}, server_id={server_id}, is_trial={is_trial}")
        
        try:
            # Определяем сервер для пользователя
            if server_id is not None:
                logger.info(f"🎯 Использую указанный сервер ID: {server_id}")
                vpn_client = await self._get_vpn_client(server_id)
                assigned_server_id = server_id
            else:
                logger.info("🎯 Использую сервер по умолчанию")
                vpn_client, assigned_server_id = await self._get_default_vpn_client()
            
            logger.info(f"✅ VPN клиент создан для сервера ID: {assigned_server_id}")
            
            # Create VPN configuration
            logger.info(f"📡 Отправляю запрос на создание VPN конфигурации...")
            vpn_config = await vpn_client.create_vpn_config(
                username=user.username,
                expire_days=subscription_days
            )

            logger.info(f"📥 Получен ответ от VPN API: {vpn_config}")

            if not vpn_config:
                logger.error("❌ VPN API вернул None")
                return None
                
            if not vpn_config.get('links'):
                logger.error(f"❌ В ответе VPN API нет поля 'links': {vpn_config}")
                return None

            vpn_link = vpn_config['links'][0]
            logger.info(f"✅ Получена VPN ссылка: {vpn_link[:50]}...")

            # Обновляем данные пользователя
            logger.info(f"💰 Списываю с баланса: {VPN_PRICE} руб. (текущий баланс: {user.balance})")
            user.balance -= VPN_PRICE
                
            user.vpn_link = vpn_link
            user.server_id = assigned_server_id  # Сохраняем ID сервера
            user.subscription_start = datetime.utcnow()
            user.subscription_end = datetime.utcnow() + timedelta(days=subscription_days)
            user.is_active = True
            
            # Отмечаем использование пробного периода
            if not is_trial:
                logger.info("🎯 Отмечаю использование пробного периода")
                user.trial_used = True

            logger.info("💾 Сохраняю изменения в базу данных...")
            await self.db.commit()

            logger.info(f"🎉 VPN конфигурация успешно создана для {user.username}")
            return vpn_link
            
        except Exception as e:
            logger.error(f"❌ Ошибка при создании VPN конфигурации: {e}")
            logger.exception("Детали ошибки:")
            return None

    async def get_user_config(
            self,
            user: User
    ) -> Optional[Dict[str, Any]]:
        """Получает конфигурацию пользователя с правильного сервера"""
        logger.info(f"🔍 Получаю конфигурацию для пользователя: {user.username}")
        
        if user.server_id is None:
            logger.warning(f"⚠️ Пользователь {user.username} не имеет назначенного сервера")
            return None
            
        try:
            logger.info(f"📡 Подключаюсь к серверу ID: {user.server_id}")
            vpn_client = await self._get_vpn_client(user.server_id)
            vpn_config = await vpn_client.get_vpn_config(user.username)
            
            if vpn_config:
                logger.info(f"✅ Конфигурация найдена для {user.username}")
            else:
                logger.warning(f"⚠️ Конфигурация не найдена для {user.username}")
                
            return vpn_config
        except ValueError as e:
            logger.error(f"❌ Ошибка получения конфигурации: {e}")
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
        logger.info(f"🔄 Начинаю продление подписки для пользователя: {user.username}")
        logger.info(f"📊 Параметры: subscription_days={subscription_days}, new_expire_ts={new_expire_ts}")
        logger.info(f"👤 Состояние пользователя: server_id={user.server_id}, vpn_link={'Есть' if user.vpn_link else 'Нет'}")
        
        # Если у пользователя нет server_id или vpn_link, создаем новую конфигурацию
        if user.server_id is None or user.vpn_link is None:
            logger.info(f"🆕 Пользователь {user.username} не имеет VPN конфигурации, создаю новую")
            
            try:
                # Создаем новую VPN конфигурацию с сервера по умолчанию
                vpn_client, assigned_server_id = await self._get_default_vpn_client()
                
                # Определяем срок действия
                if new_expire_ts:
                    expire_ts = new_expire_ts
                    logger.info(f"⏰ Использую переданный timestamp: {expire_ts}")
                else:
                    days = subscription_days or 30
                    expire_ts = int((datetime.utcnow() + timedelta(days=days)).timestamp())
                    logger.info(f"⏰ Рассчитанный timestamp на {days} дней: {expire_ts}")
                
                # Создаем VPN конфигурацию
                logger.info("📡 Создаю новую VPN конфигурацию...")
                vpn_config = await vpn_client.create_vpn_config(
                    username=user.username,
                    expire_days=subscription_days or 30
                )
                
                if not vpn_config or not vpn_config.get('links'):
                    logger.error(f"❌ Не удалось создать VPN конфигурацию для {user.username}")
                    return False
                
                # Обновляем данные пользователя
                user.vpn_link = vpn_config['links'][0]
                user.server_id = assigned_server_id
                
                logger.info("💾 Сохраняю новую конфигурацию в БД...")
                await self.db.commit()
                logger.info(f"✅ Создана новая VPN конфигурация для {user.username} на сервере {assigned_server_id}")
                return True
                
            except Exception as e:
                logger.error(f"❌ Ошибка при создании новой конфигурации: {e}")
                logger.exception("Детали ошибки:")
                return False
        
        # Если у пользователя уже есть VPN конфигурация, обновляем её
        logger.info(f"🔄 У пользователя есть конфигурация, обновляю её")
        try:
            vpn_client = await self._get_vpn_client(user.server_id)
        except ValueError as e:
            logger.error(f"❌ Ошибка получения VPN клиента: {e}")
            return False

        old_vpn_config = await self.get_user_config(user=user)
        if not old_vpn_config:
            # Конфигурация потеряна на сервере, создаем новую
            logger.warning(f"⚠️ Конфигурация пользователя {user.username} не найдена на сервере {user.server_id}, создаю новую")
            
            # Пытаемся создать новую конфигурацию на том же сервере
            try:
                vpn_client = await self._get_vpn_client(user.server_id)
                
                # Определяем срок действия
                if new_expire_ts:
                    expire_ts = new_expire_ts
                    logger.info(f"⏰ Использую переданный timestamp: {expire_ts}")
                else:
                    days = subscription_days or 30
                    expire_ts = int((datetime.utcnow() + timedelta(days=days)).timestamp())
                    logger.info(f"⏰ Рассчитанный timestamp на {days} дней: {expire_ts}")
                
                logger.info("📡 Создаю новую VPN конфигурацию на том же сервере...")
                vpn_config = await vpn_client.create_vpn_config(
                    username=user.username,
                    expire_days=subscription_days or 30
                )
                
                if vpn_config and vpn_config.get('links'):
                    user.vpn_link = vpn_config['links'][0]
                    logger.info("💾 Сохраняю восстановленную конфигурацию в БД...")
                    await self.db.commit()
                    logger.info(f"✅ Создана новая VPN конфигурация для {user.username} на сервере {user.server_id}")
                    return True
                else:
                    logger.error(f"❌ Не удалось создать новую конфигурацию для {user.username}")
                    return False
                    
            except ValueError as e:
                logger.error(f"❌ Ошибка при создании новой конфигурации: {e}")
                return False

        # Обновляем существующую конфигурацию
        logger.info("🔄 Обновляю существующую конфигурацию")
        old_expire_ts = old_vpn_config["expire"]
        now = datetime.utcnow().timestamp()
        
        logger.info(f"⏰ Текущее время: {now} ({datetime.fromtimestamp(now)})")
        logger.info(f"⏰ Старое истечение: {old_expire_ts} ({datetime.fromtimestamp(old_expire_ts)})")
        
        if old_expire_ts < now:
            base_time = datetime.utcnow()
            logger.info("⏰ Подписка истекла, продлеваю от текущего времени")
        else:
            base_time = datetime.utcfromtimestamp(old_expire_ts)
            logger.info("⏰ Подписка активна, продлеваю от текущего истечения")

        if new_expire_ts:
            new_expire = new_expire_ts
            logger.info(f"⏰ Использую переданный timestamp: {new_expire}")
        else:
            new_expire = int((base_time + timedelta(days=subscription_days)).timestamp())
            logger.info(f"⏰ Новое истечение: {new_expire} ({datetime.fromtimestamp(new_expire)})")

        # Update VPN configuration
        logger.info("📡 Отправляю запрос на обновление конфигурации...")
        vpn_config = await vpn_client.update_vpn_config(
            username=user.username,
            status="active",
            expire=new_expire
        )

        if not vpn_config or not vpn_config.get('links'):
            logger.error(f"❌ Не удалось обновить VPN конфигурацию для {user.username}")
            return False

        logger.info(f"✅ Обновлена VPN конфигурация для {user.username} на сервере {user.server_id}")
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
        
