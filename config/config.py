import os
from dotenv import load_dotenv
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # ID канала для проверки подписки
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")  # Username канала для ссылки
PAYMENT_TOKEN = os.getenv("PAYMENT_TOKEN")  # Токен платежной системы
ADMIN_CHAT = os.getenv("ADMIN_CHAT")  # ID администратора для отправки сообщений
DONATE_STREAM_URL = "https://donate.stream/donate_67f84fc4a11fb"
TECH_SUPPORT_USERNAME = os.getenv("TECH_SUPPORT_USERNAME")  # Username поддержки
API_TOKEN = os.getenv("API_TOKEN")

# Fallback URL для обратной совместимости (используется только если в БД нет серверов)
API_URL = os.getenv("API_URL")

VPN_PRICE = float(os.getenv("VPN_PRICE"))
ADMIN_NAME_1 = os.getenv("ADMIN_NAME_1")
ADMIN_NAME_2 = os.getenv("ADMIN_NAME_2")
WATA_JWT_TOKEN = os.getenv("WATA_JWT_TOKEN")
WATA_DONATE_URL = os.getenv("WATA_DONATE_URL")
BOT_LINK = os.getenv("BOT_LINK")

# Настройки отладки
DEBUG_VPN = os.getenv("DEBUG_VPN", "false").lower() == "true"

