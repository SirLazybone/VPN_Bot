from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from config.config import BOT_TOKEN
from bot.handlers import register_handlers
from bot.middleware import SubscriptionMiddleware
from bot.scheduler import start_scheduler
from bot.commands import set_bot_commands
import asyncio

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())

# Добавляем middleware
dp.message.middleware(SubscriptionMiddleware())

# Регистрируем обработчики
register_handlers(dp)


async def start_bot():
    await set_bot_commands(bot)
    start_scheduler()
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(start_bot())
