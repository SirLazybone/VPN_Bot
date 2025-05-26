import httplib2
import gspread
import os
import json
from apiclient import discovery
from oauth2client.service_account import ServiceAccountCredentials
from db.models import User, Payment

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


async def add_user_to_sheets(user: User):
    row = [
        str(user.id),
        str(user.telegram_id),
        str(user.username),
        str(user.balance),
        str(user.created_at),
        str(user.subscription_start) if user.subscription_start else "",
        str(user.subscription_end) if user.subscription_end else "",
        str(user.is_active),
        user.vpn_link or ""
    ]
    sheet_users.append_row(row)


async def add_payment_to_sheets(payment: Payment):
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


async def update_user_by_telegram_id(telegram_id, user: User):
    records = sheet_users.get_all_records()
    for idx, record in enumerate(records, start=2):
        if str(record['telegram_id']) == str(telegram_id):
            sheet_users.update([[str(user.balance)]], f'D{idx}')
            sheet_users.update([[str(user.subscription_start)]], f'F{idx}')
            sheet_users.update([[str(user.subscription_end)]], f'G{idx}')
            sheet_users.update([[str(user.is_active)]], f'H{idx}')
            sheet_users.update([[str(user.vpn_link)]], f'I{idx}')


async def delete_user(telegram_id):
    try:
        cell = sheet_users.find(telegram_id, in_column=2)
        sheet_users.delete_rows(cell.row)
    except:
        print(f"Username '{telegram_id}' не найден.")


async def update_payment_by_nickname(nickname, payment: Payment):
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
    records = sheet_payments.get_all_records()
    for idx, record in enumerate(records, start=2):
        if str(record['id']) == str(id):
            sheet_payments.update([[str(payment.status)]], f'E{idx}')
            sheet_payments.update([[str(payment.amount)]], f'C{idx}')
            sheet_payments.update([[str(payment.payment_id)]], f'D{idx}')
            sheet_payments.update([[str(payment.completed_at)]], f'G{idx}')
            sheet_payments.update([[str(payment.message)]], f'I{idx}')
            sheet_payments.update([[str(payment.pay_system)]], f'J{idx}')
