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
API_URL = os.getenv("API_URL")
VPN_PRICE = float(os.getenv("VPN_PRICE"))
ADMIN_NAME = os.getenv("ADMIN_NAME")
