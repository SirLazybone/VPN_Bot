from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from config.config import BOT_TOKEN
from bot.handlers import register_handlers
from bot.middleware import SubscriptionMiddleware
from bot.handlers.payment import app, router as payment_router
from bot.scheduler import start_scheduler
import asyncio
import uvicorn
from threading import Thread

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())

# Добавляем middleware
dp.message.middleware(SubscriptionMiddleware())

# Регистрируем обработчики
register_handlers(dp)

async def start_bot():
    print("Bot is starting...")
    # Запускаем планировщик
    start_scheduler()
    await dp.start_polling(bot)

def start_webhook():
    print("Webhook server is starting...")
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == '__main__':
    # Запускаем вебхук в отдельном потоке
    webhook_thread = Thread(target=start_webhook)
    webhook_thread.start()
    
    # Запускаем бота в основном потоке
    asyncio.run(start_bot())