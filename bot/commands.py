from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
import asyncio


async def set_bot_commands(bot: Bot):
    commands = [
        types.BotCommand(command="start", description="Запуск бота"),
        types.BotCommand(command="home", description="Меню домой"),
    ]

    await bot.set_my_commands(commands)
