import asyncio
import json
import aiohttp
import ssl
from db.database import async_session
from db.models import User, Payment
from datetime import datetime
from sqlalchemy import select

async def test_webhook():
    # URL от ngrok (замените на ваш)
    WEBHOOK_URL = "https://8c04-5-187-33-251.ngrok-free.app/webhook/donate"
    
    # Тестовые данные для вебхука
    test_data = {
        "sum": 150.0,
        "nickname": "test_user",
        "uid": "test_payment_459",  # Изменен ID для нового теста
        "date": datetime.utcnow().isoformat(),
        "message": "Тестовый платеж"
    }
    
    try:
        print(f"Отправляем тестовый запрос на {WEBHOOK_URL}")
        print(f"Данные запроса: {json.dumps(test_data, indent=2)}")
        
        # Создаем SSL контекст без проверки сертификата
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # Отправляем тестовый запрос на вебхук
        async with aiohttp.ClientSession() as session:
            async with session.post(
                WEBHOOK_URL,
                json=test_data,
                ssl=ssl_context
            ) as response:
                response_text = await response.text()
                print(f"Статус ответа: {response.status}")
                print(f"Тело ответа: {response_text}")
                
                if response.status == 200:
                    print("✅ Вебхук успешно обработан")
                    
                    # Проверяем, что платеж создан в базе данных
                    async with async_session() as db_session:
                        payment = await db_session.execute(
                            select(Payment).where(Payment.payment_id == test_data["uid"])
                        )
                        payment = payment.scalar_one_or_none()
                        
                        if payment:
                            print(f"✅ Платеж найден в базе данных:")
                            print(f"  - ID: {payment.id}")
                            print(f"  - Сумма: {payment.amount}")
                            print(f"  - Статус: {payment.status}")
                        else:
                            print("❌ Платеж не найден в базе данных")
                else:
                    print(f"❌ Ошибка при обработке вебхука: {response.status}")
                    
    except Exception as e:
        print(f"❌ Ошибка при тестировании вебхука: {e}")

if __name__ == "__main__":
    asyncio.run(test_webhook()) 