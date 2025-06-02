import httpx
from typing import Optional, Dict, Any, List, Union
from config.config import API_TOKEN, API_URL
from datetime import datetime, timedelta
from bot.vpn_logger import vpn_api_logger as logger

class VPNClient:
    def __init__(self, server_url: str, server_name: str = "VPN Server"):
        self.api_token = API_TOKEN
        self.base_url = server_url
        self.server_name = server_name
        
        logger.info(f"🔧 Инициализация VPN клиента для {server_name}")
        logger.info(f"🌐 URL сервера: {server_url}")
        logger.info(f"🔑 API токен: {'*' * 10}{API_TOKEN[-5:] if API_TOKEN else 'НЕ УСТАНОВЛЕН'}")
        
        if not self.base_url:
            logger.error("❌ URL сервера не может быть пустым")
            raise ValueError(f"URL сервера не может быть пустым")
            
        if not self.api_token:
            logger.warning("⚠️ API токен не установлен")
            
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"✅ VPN клиент для {server_name} инициализирован")

    @classmethod
    def from_server(cls, server):
        """Создает VPNClient из объекта Server"""
        logger.info(f"🏗️ Создаю VPN клиент из объекта сервера: {server.name}")
        return cls(server_url=server.url, server_name=server.name)

    @classmethod 
    def from_fallback(cls):
        """Создает VPNClient из fallback конфигурации"""
        logger.info("🏗️ Создаю VPN клиент из fallback конфигурации")
        if not API_URL:
            logger.error("❌ Нет доступных серверов и fallback URL не настроен")
            raise ValueError("Нет доступных серверов и fallback URL не настроен")
        return cls(server_url=API_URL, server_name="Fallback Server")

    async def create_vpn_config(
        self, 
        username: str,
        data_limit: int = 0,
        expire_days: int = 30,
        inbounds: Optional[Dict[str, List[str]]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new VPN configuration for a user
        
        Args:
            username: Username for the VPN account
            data_limit: Data limit in bytes (0 for unlimited)
            expire_days: Number of days until expiration
            inbounds: Dictionary of inbounds to enable
        """
        logger.info(f"🚀 Создаю VPN конфигурацию для пользователя: {username}")
        logger.info(f"📊 Параметры: data_limit={data_limit}, expire_days={expire_days}")

        expire_timestamp = int((datetime.now() + timedelta(days=expire_days)).timestamp())
        logger.info(f"⏰ Timestamp истечения: {expire_timestamp} ({datetime.fromtimestamp(expire_timestamp)})")
        
        request_data = {
            "username": username,
            "data_limit": data_limit,
            "data_limit_reset_strategy": "no_reset",
            "expire": expire_timestamp,
            "inbounds": {
                "vless": ["VLESS TCP REALITY"]
            },
            "next_plan": {
                "add_remaining_traffic": False,
                "data_limit": 0,
                "expire": 0,
                "fire_on_either": True
            },
            "note": "",
            "on_hold_expire_duration": 0,
            "on_hold_timeout": datetime.now().isoformat(),
            "proxies": {
                "vless": {
                    "id": self._generate_uuid()
                }
            },
            "status": "active"
        }
        
        logger.info(f"📤 Отправляю запрос на {self.base_url}/api/user")
        logger.info(f"📄 Данные запроса: {request_data}")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/user",
                    headers=self.headers,
                    json=request_data
                )
                
                logger.info(f"📡 Статус ответа: {response.status_code}")
                logger.info(f"📋 Заголовки ответа: {dict(response.headers)}")
                
                if response.status_code != 200:
                    logger.error(f"❌ HTTP ошибка: {response.status_code}")
                    logger.error(f"📄 Тело ответа: {response.text}")
                
                response.raise_for_status()
                response_data = response.json()
                
                logger.info(f"✅ Успешный ответ от API")
                logger.info(f"📥 Данные ответа: {response_data}")
                
                return response_data
                
        except httpx.TimeoutException as e:
            logger.error(f"⏰ Таймаут при создании VPN конфигурации: {e}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"🚫 HTTP ошибка при создании VPN конфигурации: {e}")
            logger.error(f"📄 Ответ сервера: {e.response.text}")
            return None
        except httpx.RequestError as e:
            logger.error(f"🔌 Ошибка подключения при создании VPN конфигурации: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при создании VPN конфигурации: {e}")
            logger.exception("Детали ошибки:")
            return None

    async def get_vpn_config(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get existing VPN configuration for a user
        """
        logger.info(f"🔍 Получаю VPN конфигурацию для пользователя: {username}")
        logger.info(f"📤 GET запрос на {self.base_url}/api/user/{username}")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/user/{username}",
                    headers=self.headers
                )
                
                logger.info(f"📡 Статус ответа: {response.status_code}")
                
                if response.status_code == 404:
                    logger.warning(f"👤 Пользователь {username} не найден на сервере")
                    return None
                elif response.status_code != 200:
                    logger.error(f"❌ HTTP ошибка: {response.status_code}")
                    logger.error(f"📄 Тело ответа: {response.text}")
                
                response.raise_for_status()
                response_data = response.json()
                
                logger.info(f"✅ Конфигурация найдена для {username}")
                return response_data
                
        except httpx.TimeoutException as e:
            logger.error(f"⏰ Таймаут при получении VPN конфигурации: {e}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"🚫 HTTP ошибка при получении VPN конфигурации: {e}")
            return None
        except httpx.RequestError as e:
            logger.error(f"🔌 Ошибка подключения при получении VPN конфигурации: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при получении VPN конфигурации: {e}")
            logger.exception("Детали ошибки:")
            return None

    def _generate_uuid(self) -> str:
        """Generate a UUID for VMess proxy"""
        import uuid
        generated_uuid = str(uuid.uuid4())
        logger.info(f"🆔 Сгенерирован UUID: {generated_uuid}")
        return generated_uuid

    async def update_vpn_config(
        self,
        username: str,
        status: Optional[str] = None,
        expire: Optional[int] = None,
        data_limit: Optional[int] = None,
        data_limit_reset_strategy: Optional[str] = None,
        proxies: Optional[Dict[str, Any]] = None,
        inbounds: Optional[Dict[str, List[str]]] = None,
        note: Optional[str] = None,
        on_hold_timeout: Optional[str] = None,
        on_hold_expire_duration: Optional[int] = None,
        next_plan: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update an existing VPN user configuration
        
        Args:
            username: Username of the user to update
            status: New status ('active', 'disabled', 'on_hold', 'limited', 'expired')
            expire: UTC timestamp for new expiration (0 for unlimited)
            data_limit: New data limit in bytes (0 for unlimited)
            data_limit_reset_strategy: New reset strategy ('daily', 'weekly', 'monthly', 'no_reset')
            proxies: New protocol settings
            inbounds: New protocol tags for inbound connections
            note: New note text
            on_hold_timeout: UTC timestamp for on_hold status
            on_hold_expire_duration: Duration in seconds for on_hold status
            next_plan: Next user plan settings
        """
        logger.info(f"🔄 Обновляю VPN конфигурацию для пользователя: {username}")
        logger.info(f"📊 Параметры обновления: status={status}, expire={expire}")
        if expire:
            logger.info(f"⏰ Новое время истечения: {datetime.fromtimestamp(expire)}")
        
        update_data = {}
        
        if status is not None:
            update_data["status"] = status
        if expire is not None:
            update_data["expire"] = expire
        if data_limit is not None:
            update_data["data_limit"] = data_limit
        if data_limit_reset_strategy is not None:
            update_data["data_limit_reset_strategy"] = data_limit_reset_strategy
        if proxies is not None:
            update_data["proxies"] = proxies
        if inbounds is not None:
            update_data["inbounds"] = inbounds
        if note is not None:
            update_data["note"] = note
        if on_hold_timeout is not None:
            update_data["on_hold_timeout"] = on_hold_timeout
        if on_hold_expire_duration is not None:
            update_data["on_hold_expire_duration"] = on_hold_expire_duration
        if next_plan is not None:
            update_data["next_plan"] = next_plan

        logger.info(f"📤 PUT запрос на {self.base_url}/api/user/{username}")
        logger.info(f"📄 Данные обновления: {update_data}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.put(
                    f"{self.base_url}/api/user/{username}",
                    headers=self.headers,
                    json=update_data
                )
                
                logger.info(f"📡 Статус ответа: {response.status_code}")
                
                if response.status_code == 404:
                    logger.warning(f"👤 Пользователь {username} не найден на сервере")
                    return None
                elif response.status_code != 200:
                    logger.error(f"❌ HTTP ошибка: {response.status_code}")
                    logger.error(f"📄 Тело ответа: {response.text}")
                
                response.raise_for_status()
                response_data = response.json()
                
                logger.info(f"✅ Конфигурация обновлена для {username}")
                logger.info(f"📥 Данные ответа: {response_data}")
                
                return response_data
                
        except httpx.TimeoutException as e:
            logger.error(f"⏰ Таймаут при обновлении VPN конфигурации: {e}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"🚫 HTTP ошибка при обновлении VPN конфигурации: {e}")
            logger.error(f"📄 Ответ сервера: {e.response.text}")
            return None
        except httpx.RequestError as e:
            logger.error(f"🔌 Ошибка подключения при обновлении VPN конфигурации: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при обновлении VPN конфигурации: {e}")
            logger.exception("Детали ошибки:")
            return None

    # async def activate_user(self, username: str) -> Optional[Dict[str, Any]]:
    #     """
    #     Convenience method to activate a user
    #     """
    #     return await self.update_vpn_config(
    #         username=username,
    #         status="active",
    #         expire=30
    #     )

    async def delete_user(self, username: str):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    url=f"{self.base_url}/api/user/{username}",
                    headers=self.headers,
                )
                response.raise_for_status()
                return response.status_code
        except httpx.HTTPError as e:
            print(f"Error deleting VPN config: {e}")
            return None
