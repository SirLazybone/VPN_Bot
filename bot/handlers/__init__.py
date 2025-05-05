from aiogram import Dispatcher
from bot.handlers.start import router as start_router
from bot.handlers.payment import router as payment_router
from bot.handlers.device import router as device_router
from bot.handlers.home import router as home_router


def register_handlers(dp: Dispatcher):
    dp.include_router(start_router)
    dp.include_router(payment_router)
    dp.include_router(device_router)
    dp.include_router(home_router)