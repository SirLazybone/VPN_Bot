import datetime
import asyncio
import httpx
import logging
import time
import uuid
from db.database import async_session
from db.models import User
from sqlalchemy import select, update
from aiogram import Bot
from config.config import BOT_TOKEN, ADMIN_NAME_1, ADMIN_NAME_2, API_TOKEN, API_URL


bot = Bot(token=BOT_TOKEN)
ADMINS = [ADMIN_NAME_1, ADMIN_NAME_2]
logger = logging.getLogger(__name__)

async def give_new_url(server_id: int):
    """
    Создает новые VPN ссылки для пользователей с активной подпиской
    """
    if not API_URL:
        logger.error("❌ API_URL не настроен в конфигурации")
        return
    
    async with async_session() as session:
        now = datetime.datetime.utcnow()
        result = await session.execute(select(User).where(
            User.subscription_end > now,
            User.is_active == True,
            User.server_id == server_id
        ))

        users = result.scalars().all()
        logger.info(f"Найдено {len(users)} пользователей с истекшей подпиской на сервере {server_id}")
        
        success_count = 0
        error_count = 0
        
        for user in users:
            try:
                expire_timestamp = int(user.subscription_end.timestamp())
                response = await get_url(user.username, expire_timestamp)
                
                if response and 'subscription_url' in response:
                    new_url = response['subscription_url']
                    logger.info(f'Новая ссылка для пользователя {user.username}: {new_url}')
                    

                    await session.execute(
                        update(User)
                        .where(User.id == user.id)
                        .values(vpn_link=new_url)
                    )
                    await session.commit()
                    

                    message = f"""
🔄 Обновление VPN конфигурации

Привет, {user.username}! 

🎯 Мы создали новую VPN ссылку для вашего аккаунта

🔗 Ваша новая VPN ссылка:
{new_url}

📋 Как использовать:
1. Перейдите по ссылке выше
2. Выбрать устройство которое используете и приложение
3. Скачайте приложение \ перенесите подписку в приложение по кнопке
4. Теперь вам доступно множество серверов по одной подписке

⏰ Действительна до: {user.subscription_end.strftime('%d.%m.%Y %H:%M')}

❓ Если возникли вопросы - обращайтесь в поддержку!
                    """
                    
                    try:
                        await bot.send_message(
                            user.telegram_id,
                            message
                        )
                        success_count += 1
                        logger.info(f"Успешно отправлено сообщение пользователю {user.username}")
                    except Exception as e:
                        logger.error(f"Ошибка отправки сообщения пользователю {user.telegram_id}: {e}")
                        error_count += 1
                else:
                    logger.error(f"Не удалось создать VPN ссылку для пользователя {user.username}")
                    error_count += 1
                    
            except Exception as e:
                logger.error(f"Ошибка обработки пользователя {user.username}: {e}")
                error_count += 1
                continue

            time.sleep(1)  # Задержка между запросами
        
        report_message = f"""
📊 Отчет по созданию новых VPN ссылок

🌐 API URL: {API_URL}

📈 Статистика:
✅ Успешно: {success_count}
❌ Ошибок: {error_count}
👥 Всего обработано: {len(users)}

🕐 Время выполнения: {datetime.datetime.utcnow().strftime('%d.%m.%Y %H:%M:%S')} UTC
        """
        
        for admin_username in ADMINS:
            if admin_username:
                try:
                    admin_result = await session.execute(
                        select(User).where(User.username == admin_username.replace('@', ''))
                    )
                    admin_user = admin_result.scalar_one_or_none()
                    if admin_user:
                        await bot.send_message(admin_user.telegram_id, report_message)
                except Exception as e:
                    logger.error(f"Не удалось отправить отчет администратору {admin_username}: {e}")


async def get_url(username: str, expire_timestamp: int):
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Генерируем UUID для нового пользователя
    user_uuid = str(uuid.uuid4())
    
    request_data = {
        "username": username,
        "data_limit": 0,
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
        "on_hold_timeout": datetime.datetime.now().isoformat(),
        "proxies": {
            "vless": {
                "id": user_uuid
            }
        },
        "status": "active"
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{API_URL}/api/user",
                headers=headers,
                json=request_data
            )
            logger.info(f"Статус ответа для {username}: {response.status_code}")
            
            if response.status_code == 200:
                response_data = response.json()
                logger.info(f"Успешный ответ от API для {username}")
                return response_data
            else:
                logger.error(f"HTTP ошибка для {username}: {response.status_code}")
                logger.error(f"Тело ответа: {response.text}")
                return None

    except httpx.TimeoutException as e:
        logger.error(f"Таймаут при создании VPN конфигурации для {username}: {e}")
        return None
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP ошибка при создании VPN конфигурации для {username}: {e}")
        logger.error(f"Ответ сервера: {e.response.text}")
        return None
    except httpx.RequestError as e:
        logger.error(f"Ошибка подключения при создании VPN конфигурации для {username}: {e}")
        return None
    except Exception as e:
        logger.error(f"Неожиданная ошибка при создании VPN конфигурации для {username}: {e}")
        logger.exception("Детали ошибки:")
        return None





if __name__ == "__main__":
    asyncio.run(give_new_url(2))
