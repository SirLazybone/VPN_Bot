from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import User
from bot.vpn_api import VPNClient
from config.config import VPN_PRICE
from bot.vpn_logger import vpn_manager_logger as logger
import asyncio


class VPNManager:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    def _get_vpn_client(self) -> VPNClient:
        """Получает VPN клиент для единой API"""
        logger.info("🔍 Создаю VPN клиент для единой API")
        return VPNClient.from_fallback()

    async def create_vpn_config(
            self,
            user: User,
            subscription_days: int = 14,
            is_trial: bool = False
    ) -> Optional[str]:
        """
        Create VPN configuration for a user and return the VPN link
        """
        logger.info(f"🚀 Начинаю создание VPN конфигурации для пользователя: {user.username}")
        logger.info(f"📊 Параметры: subscription_days={subscription_days}, is_trial={is_trial}")
        
        try:
            logger.info("🎯 Использую единую API")
            vpn_client = self._get_vpn_client()
            
            logger.info(f"✅ VPN клиент создан")
            
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
                
            if not vpn_config.get('subscription_url'):
                logger.error(f"❌ В ответе VPN API нет поля 'subscription_url': {vpn_config}")
                return None

            vpn_link = vpn_config['subscription_url']
            logger.info(f"✅ Получена VPN ссылка: {vpn_link[:50]}...")

            # Обновляем данные пользователя
            logger.info(f"💰 Списываю с баланса: {VPN_PRICE} руб. (текущий баланс: {user.balance})")
            user.balance -= VPN_PRICE
                
            user.vpn_link = vpn_link
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
        """Получает конфигурацию пользователя"""
        logger.info(f"🔍 Получаю конфигурацию для пользователя: {user.username}")
        
        try:
            logger.info(f"📡 Подключаюсь к API")
            vpn_client = self._get_vpn_client()
            vpn_config = await vpn_client.get_vpn_config(user.username)
            
            if vpn_config:
                logger.info(f"✅ Конфигурация найдена для {user.username}")
            else:
                logger.warning(f"⚠️ Конфигурация не найдена для {user.username}")
                
            return vpn_config
        except Exception as e:
            logger.error(f"❌ Ошибка получения конфигурации: {e}")
            return None

    async def renew_subscription(
            self,
            user: User,
            subscription_days: Optional[int] = None,
            new_expire_ts: Optional[int] = None
    ) -> bool:
        """
        Renew user's VPN subscription
        Если у пользователя нет VPN конфигурации, создает новую
        """
        logger.info(f"🔄 Начинаю продление подписки для пользователя: {user.username}")
        logger.info(f"📊 Параметры: subscription_days={subscription_days}, new_expire_ts={new_expire_ts}")
        logger.info(f"👤 Состояние пользователя: vpn_link={'Есть' if user.vpn_link else 'Нет'}")
        
        # Если у пользователя нет vpn_link, создаем новую конфигурацию
        if user.vpn_link is None:
            logger.info(f"🆕 Пользователь {user.username} не имеет VPN конфигурации, создаю новую")
            
            try:
                # Создаем новую VPN конфигурацию
                vpn_client = self._get_vpn_client()
                
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
                
                if not vpn_config or not vpn_config.get('subscription_url'):
                    logger.error(f"❌ Не удалось создать VPN конфигурацию для {user.username}")
                    return False
                
                # Обновляем данные пользователя
                user.vpn_link = vpn_config['subscription_url']
                
                logger.info("💾 Сохраняю новую конфигурацию в БД...")
                await self.db.commit()
                logger.info(f"✅ Создана новая VPN конфигурация для {user.username}")
                return True
                
            except Exception as e:
                logger.error(f"❌ Ошибка при создании новой конфигурации: {e}")
                logger.exception("Детали ошибки:")
                return False
        
        # Если у пользователя уже есть VPN конфигурация, обновляем её
        logger.info(f"🔄 У пользователя есть конфигурация, обновляю её")
        try:
            vpn_client = self._get_vpn_client()
        except Exception as e:
            logger.error(f"❌ Ошибка получения VPN клиента: {e}")
            return False

        old_vpn_config = await self.get_user_config(user=user)
        if not old_vpn_config:
            # Конфигурация потеряна на сервере, создаем новую
            logger.warning(f"⚠️ Конфигурация пользователя {user.username} не найдена на сервере, создаю новую")
            
            # Пытаемся создать новую конфигурацию
            try:
                vpn_client = self._get_vpn_client()
                
                # Определяем срок действия
                if new_expire_ts:
                    expire_ts = new_expire_ts
                    logger.info(f"⏰ Использую переданный timestamp: {expire_ts}")
                else:
                    days = subscription_days or 30
                    expire_ts = int((datetime.utcnow() + timedelta(days=days)).timestamp())
                    logger.info(f"⏰ Рассчитанный timestamp на {days} дней: {expire_ts}")
                
                logger.info("📡 Создаю новую VPN конфигурацию...")
                vpn_config = await vpn_client.create_vpn_config(
                    username=user.username,
                    expire_days=subscription_days or 30
                )
                
                if vpn_config and vpn_config.get('subscription_url'):
                    user.vpn_link = vpn_config['subscription_url']
                    logger.info("💾 Сохраняю восстановленную конфигурацию в БД...")
                    await self.db.commit()
                    logger.info(f"✅ Создана новая VPN конфигурация для {user.username}")
                    return True
                else:
                    logger.error(f"❌ Не удалось создать новую конфигурацию для {user.username}")
                    return False
                    
            except Exception as e:
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

        if not vpn_config or not vpn_config.get('subscription_url'):
            logger.error(f"❌ Не удалось обновить VPN конфигурацию для {user.username}")
            return False

        logger.info(f"✅ Обновлена VPN конфигурация для {user.username}")
        return True

    async def delete_user(self, username: str) -> bool:
        """Удаляет пользователя"""
        try:
            vpn_client = self._get_vpn_client()
            response = await vpn_client.delete_user(username=username)
            return response == 200
        except Exception as e:
            logger.error(f"Ошибка при удалении пользователя {username}: {e}")
            return False
        
