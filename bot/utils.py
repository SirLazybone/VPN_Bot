from aiogram import Bot
from config.config import CHANNEL_ID
from aiogram.enums import ChatMemberStatus

async def check_subscription(user_id: int, bot: Bot) -> bool:
    """
    Проверяет, подписан ли пользователь на канал
    :param user_id: ID пользователя
    :param bot: Объект бота
    :return: True если подписан, False если нет
    """
    try:
        chat_member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return chat_member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    except Exception as e:
        print(f"Error checking subscription: {e}")
        return False 