import httplib2
import gspread
import os
import json
from apiclient import discovery
from oauth2client.service_account import ServiceAccountCredentials
from db.models import User, Payment, Server

current_dir = os.path.dirname(__file__)
CREDENTIALS_FILE = os.path.join(current_dir, 'creds.json')

# CREDENTIALS_FILE = 'cred.json'
spreadsheets_id = '1ID5MNUNwL0e6O9880ap5-5i0w1qIxQvW1jndBz9D9Lg'

credentials = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE,
                                                               ['https://www.googleapis.com/auth/spreadsheets',
                                                                'https://www.googleapis.com/auth/drive'])

httpAuth = credentials.authorize(httplib2.Http())
service = discovery.build('sheets', 'v4', http=httpAuth)
client = gspread.authorize(credentials)

sheet_users = client.open_by_key(spreadsheets_id).worksheet('Users')
sheet_payments = client.open_by_key(spreadsheets_id).worksheet('Payments')
sheet_servers = client.open_by_key(spreadsheets_id).worksheet('Servers')


# ======================== USER FUNCTIONS ========================

async def add_user_to_sheets(user: User):
    """Добавляет пользователя в Google Sheets с обновленными полями"""
    row = [
        str(user.id),
        str(user.telegram_id),
        str(user.username),
        str(user.balance),
        str(user.created_at),
        str(user.subscription_start) if user.subscription_start else "",
        str(user.subscription_end) if user.subscription_end else "",
        str(user.is_active),
        user.vpn_link or "",
        str(user.server_id) if user.server_id else "",
        str(user.trial_used)
    ]
    sheet_users.append_row(row)


async def update_user_by_telegram_id(telegram_id, user: User):
    """Обновляет пользователя в Google Sheets по telegram_id"""
    records = sheet_users.get_all_records()
    for idx, record in enumerate(records, start=2):
        if str(record['telegram_id']) == str(telegram_id):
            sheet_users.update([[str(user.balance)]], f'D{idx}')
            sheet_users.update([[str(user.subscription_start)]], f'F{idx}')
            sheet_users.update([[str(user.subscription_end)]], f'G{idx}')
            sheet_users.update([[str(user.is_active)]], f'H{idx}')
            sheet_users.update([[str(user.vpn_link or "")]], f'I{idx}')
            sheet_users.update([[str(user.server_id) if user.server_id else ""]], f'J{idx}')
            sheet_users.update([[str(user.trial_used)]], f'K{idx}')


async def update_user_by_id(user_id, user: User):
    """Обновляет пользователя в Google Sheets по ID"""
    records = sheet_users.get_all_records()
    for idx, record in enumerate(records, start=2):
        if str(record['id']) == str(user_id):
            sheet_users.update([[str(user.telegram_id)]], f'B{idx}')
            sheet_users.update([[str(user.username)]], f'C{idx}')
            sheet_users.update([[str(user.balance)]], f'D{idx}')
            sheet_users.update([[str(user.created_at)]], f'E{idx}')
            sheet_users.update([[str(user.subscription_start)]], f'F{idx}')
            sheet_users.update([[str(user.subscription_end)]], f'G{idx}')
            sheet_users.update([[str(user.is_active)]], f'H{idx}')
            sheet_users.update([[str(user.vpn_link or "")]], f'I{idx}')
            sheet_users.update([[str(user.server_id) if user.server_id else ""]], f'J{idx}')
            sheet_users.update([[str(user.trial_used)]], f'K{idx}')


async def delete_user(telegram_id):
    """Удаляет пользователя из Google Sheets"""
    try:
        cell = sheet_users.find(telegram_id, in_column=2)
        sheet_users.delete_rows(cell.row)
    except:
        print(f"Username '{telegram_id}' не найден.")


# ======================== SERVER FUNCTIONS ========================

async def add_server_to_sheets(server: Server):
    """Добавляет сервер в Google Sheets"""
    row = [
        str(server.id),
        str(server.name),
        str(server.url),
        str(server.is_active),
        str(server.is_default),
        str(server.created_at),
        server.description or ""
    ]
    sheet_servers.append_row(row)


async def update_server_by_id(server_id, server: Server):
    """Обновляет сервер в Google Sheets по ID"""
    records = sheet_servers.get_all_records()
    for idx, record in enumerate(records, start=2):
        if str(record['id']) == str(server_id):
            sheet_servers.update([[str(server.name)]], f'B{idx}')
            sheet_servers.update([[str(server.url)]], f'C{idx}')
            sheet_servers.update([[str(server.is_active)]], f'D{idx}')
            sheet_servers.update([[str(server.is_default)]], f'E{idx}')
            sheet_servers.update([[str(server.created_at)]], f'F{idx}')
            sheet_servers.update([[str(server.description or "")]], f'G{idx}')


async def delete_server_by_id(server_id):
    """Удаляет сервер из Google Sheets по ID"""
    try:
        records = sheet_servers.get_all_records()
        for idx, record in enumerate(records, start=2):
            if str(record['id']) == str(server_id):
                sheet_servers.delete_rows(idx)
                break
    except Exception as e:
        print(f"Ошибка при удалении сервера {server_id}: {e}")


async def get_servers_from_sheets():
    """Получает все серверы из Google Sheets"""
    try:
        return sheet_servers.get_all_records()
    except Exception as e:
        print(f"Ошибка при получении серверов: {e}")
        return []


async def find_server_by_name(server_name):
    """Находит сервер в Google Sheets по имени"""
    try:
        records = sheet_servers.get_all_records()
        for record in records:
            if record['name'] == server_name:
                return record
        return None
    except Exception as e:
        print(f"Ошибка при поиске сервера {server_name}: {e}")
        return None


# ======================== PAYMENT FUNCTIONS ========================

async def add_payment_to_sheets(payment: Payment):
    """Добавляет платеж в Google Sheets"""
    row = [
        str(payment.id),
        str(payment.user_id),
        str(payment.amount),
        str(payment.payment_id),
        str(payment.status),
        str(payment.created_at),
        str(payment.completed_at),
        str(payment.nickname),
        str(payment.message),
        str(payment.pay_system)
    ]
    sheet_payments.append_row(row)


async def update_payment_by_nickname(nickname, payment: Payment):
    """Обновляет платеж в Google Sheets по nickname"""
    records = sheet_payments.get_all_records()
    for idx, record in enumerate(records, start=2):
        if str(record['nickname']) == str(nickname):
            sheet_payments.update([[str(payment.status)]], f'E{idx}')
            sheet_payments.update([[str(payment.amount)]], f'C{idx}')
            sheet_payments.update([[str(payment.payment_id)]], f'D{idx}')
            sheet_payments.update([[str(payment.completed_at)]], f'G{idx}')
            sheet_payments.update([[str(payment.message)]], f'I{idx}')
            sheet_payments.update([[str(payment.pay_system)]], f'J{idx}')


async def update_payment_by_id(id, payment: Payment):
    """Обновляет платеж в Google Sheets по ID"""
    records = sheet_payments.get_all_records()
    for idx, record in enumerate(records, start=2):
        if str(record['id']) == str(id):
            sheet_payments.update([[str(payment.status)]], f'E{idx}')
            sheet_payments.update([[str(payment.amount)]], f'C{idx}')
            sheet_payments.update([[str(payment.payment_id)]], f'D{idx}')
            sheet_payments.update([[str(payment.completed_at)]], f'G{idx}')
            sheet_payments.update([[str(payment.message)]], f'I{idx}')
            sheet_payments.update([[str(payment.pay_system)]], f'J{idx}')


# ======================== UTILITY FUNCTIONS ========================

async def get_users_from_sheets():
    """Получает всех пользователей из Google Sheets"""
    try:
        return sheet_users.get_all_records()
    except Exception as e:
        print(f"Ошибка при получении пользователей: {e}")
        return []


async def get_payments_from_sheets():
    """Получает все платежи из Google Sheets"""
    try:
        return sheet_payments.get_all_records()
    except Exception as e:
        print(f"Ошибка при получении платежей: {e}")
        return []


async def sync_server_status(server_id, is_active, is_default=None):
    """Синхронизирует статус сервера в Google Sheets"""
    records = sheet_servers.get_all_records()
    for idx, record in enumerate(records, start=2):
        if str(record['id']) == str(server_id):
            sheet_servers.update([[str(is_active)]], f'D{idx}')
            if is_default is not None:
                sheet_servers.update([[str(is_default)]], f'E{idx}')
            break
