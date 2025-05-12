from aiogram import BaseMiddleware
from aiogram.types import Message
from typing import Callable, Dict, Any, Awaitable
from bot.utils import check_subscription
from config.config import CHANNEL_USERNAME


class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        # Пропускаем проверку для команды /start
        if event.text and event.text.startswith('/start'):
            return await handler(event, data)
            
        # Проверяем подписку для всех остальных команд
        if not await check_subscription(event.from_user.id, data['bot']):
            await event.answer(
                "Для использования бота необходимо подписаться на наш канал!\n"
                f"Подпишитесь на канал: https://t.me/{CHANNEL_USERNAME}\n"
                "После подписки нажмите /start"
            )
            return
            
        return await handler(event, data) 