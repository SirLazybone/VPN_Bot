#!/usr/bin/env python3
"""
Скрипт для полной синхронизации данных из базы данных в Google Sheets.
Очищает все существующие данные и записывает их заново с учетом новых полей.
"""

import asyncio
import sys
import os
from datetime import datetime

# Добавляем корневую директорию в path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db.database import async_session
from db.models import User, Payment, Server
from sqlalchemy import select
from sheets.sheets import (
    sheet_users, sheet_payments, sheet_servers,
    client, spreadsheets_id
)


class SheetsSync:
    def __init__(self):
        self.headers_users = [
            'id', 'telegram_id', 'username', 'balance', 'created_at',
            'subscription_start', 'subscription_end', 'is_active', 
            'vpn_link', 'server_id', 'trial_used'
        ]
        
        self.headers_payments = [
            'id', 'user_id', 'amount', 'payment_id', 'status',
            'created_at', 'completed_at', 'nickname', 'message', 'pay_system'
        ]
        
        self.headers_servers = [
            'id', 'name', 'url', 'is_active', 'is_default',
            'created_at', 'description'
        ]

    def clear_sheet(self, sheet, sheet_name):
        """Очищает лист полностью"""
        try:
            print(f"🧹 Очищаю лист '{sheet_name}'...")
            sheet.clear()
            print(f"✅ Лист '{sheet_name}' очищен")
        except Exception as e:
            print(f"❌ Ошибка при очистке листа '{sheet_name}': {e}")
            raise

    def setup_headers(self, sheet, headers, sheet_name):
        """Устанавливает заголовки для листа"""
        try:
            print(f"📝 Устанавливаю заголовки для '{sheet_name}'...")
            sheet.append_row(headers)
            # Делаем заголовки жирными
            sheet.format('A1:Z1', {'textFormat': {'bold': True}})
            print(f"✅ Заголовки для '{sheet_name}' установлены")
        except Exception as e:
            print(f"❌ Ошибка при установке заголовков для '{sheet_name}': {e}")
            raise

    async def sync_users(self):
        """Синхронизирует всех пользователей"""
        print("\n👥 Синхронизация пользователей...")
        
        async with async_session() as session:
            # Получаем всех пользователей
            result = await session.execute(select(User).order_by(User.id))
            users = result.scalars().all()
            
            if not users:
                print("📭 Пользователи не найдены")
                return
                
            print(f"📊 Найдено пользователей: {len(users)}")
            
            # Очищаем и устанавливаем заголовки
            self.clear_sheet(sheet_users, "Users")
            self.setup_headers(sheet_users, self.headers_users, "Users")
            
            # Подготавливаем данные для массовой записи
            rows_data = []
            for user in users:
                row = [
                    str(user.id),
                    str(user.telegram_id),
                    str(user.username) if user.username else "",
                    str(user.balance),
                    str(user.created_at),
                    str(user.subscription_start) if user.subscription_start else "",
                    str(user.subscription_end) if user.subscription_end else "",
                    str(user.is_active),
                    user.vpn_link if user.vpn_link else "",
                    str(user.server_id) if user.server_id else "",
                    str(user.trial_used)
                ]
                rows_data.append(row)
            
            # Массовая запись всех пользователей
            if rows_data:
                print(f"📝 Записываю {len(rows_data)} пользователей...")
                
                # Записываем пачками по 100 строк для избежания лимитов API
                batch_size = 100
                for i in range(0, len(rows_data), batch_size):
                    batch = rows_data[i:i + batch_size]
                    sheet_users.append_rows(batch)
                    print(f"   ✅ Записано {min(i + batch_size, len(rows_data))}/{len(rows_data)} пользователей")
                
                print("✅ Все пользователи синхронизированы")

    async def sync_payments(self):
        """Синхронизирует все платежи"""
        print("\n💳 Синхронизация платежей...")
        
        async with async_session() as session:
            # Получаем все платежи
            result = await session.execute(select(Payment).order_by(Payment.id))
            payments = result.scalars().all()
            
            if not payments:
                print("📭 Платежи не найдены")
                return
                
            print(f"📊 Найдено платежей: {len(payments)}")
            
            # Очищаем и устанавливаем заголовки
            self.clear_sheet(sheet_payments, "Payments")
            self.setup_headers(sheet_payments, self.headers_payments, "Payments")
            
            # Подготавливаем данные для массовой записи
            rows_data = []
            for payment in payments:
                row = [
                    str(payment.id),
                    str(payment.user_id),
                    str(payment.amount) if payment.amount else "",
                    str(payment.payment_id) if payment.payment_id else "",
                    str(payment.status),
                    str(payment.created_at),
                    str(payment.completed_at) if payment.completed_at else "",
                    str(payment.nickname) if payment.nickname else "",
                    str(payment.message) if payment.message else "",
                    str(payment.pay_system) if payment.pay_system else ""
                ]
                rows_data.append(row)
            
            # Массовая запись всех платежей
            if rows_data:
                print(f"📝 Записываю {len(rows_data)} платежей...")
                
                # Записываем пачками по 100 строк
                batch_size = 100
                for i in range(0, len(rows_data), batch_size):
                    batch = rows_data[i:i + batch_size]
                    sheet_payments.append_rows(batch)
                    print(f"   ✅ Записано {min(i + batch_size, len(rows_data))}/{len(rows_data)} платежей")
                
                print("✅ Все платежи синхронизированы")

    async def sync_servers(self):
        """Синхронизирует все серверы"""
        print("\n🖥️  Синхронизация серверов...")
        
        async with async_session() as session:
            # Получаем все серверы
            result = await session.execute(select(Server).order_by(Server.id))
            servers = result.scalars().all()
            
            if not servers:
                print("📭 Серверы не найдены")
                return
                
            print(f"📊 Найдено серверов: {len(servers)}")
            
            # Очищаем и устанавливаем заголовки
            self.clear_sheet(sheet_servers, "Servers")
            self.setup_headers(sheet_servers, self.headers_servers, "Servers")
            
            # Подготавливаем данные для массовой записи
            rows_data = []
            for server in servers:
                row = [
                    str(server.id),
                    str(server.name),
                    str(server.url),
                    str(server.is_active),
                    str(server.is_default),
                    str(server.created_at),
                    str(server.description) if server.description else ""
                ]
                rows_data.append(row)
            
            # Массовая запись всех серверов
            if rows_data:
                print(f"📝 Записываю {len(rows_data)} серверов...")
                sheet_servers.append_rows(rows_data)
                print("✅ Все серверы синхронизированы")

    async def get_database_stats(self):
        """Получает статистику базы данных"""
        print("\n📊 Статистика базы данных:")
        
        async with async_session() as session:
            # Пользователи
            users_result = await session.execute(select(User))
            users_count = len(users_result.scalars().all())
            
            # Активные пользователи
            active_users_result = await session.execute(select(User).where(User.is_active == True))
            active_users_count = len(active_users_result.scalars().all())
            
            # Пользователи с VPN
            vpn_users_result = await session.execute(select(User).where(User.vpn_link.isnot(None)))
            vpn_users_count = len(vpn_users_result.scalars().all())
            
            # Платежи
            payments_result = await session.execute(select(Payment))
            payments_count = len(payments_result.scalars().all())
            
            # Серверы
            servers_result = await session.execute(select(Server))
            servers_count = len(servers_result.scalars().all())
            
            print(f"   👥 Всего пользователей: {users_count}")
            print(f"   ✅ Активных пользователей: {active_users_count}")
            print(f"   🔐 Пользователей с VPN: {vpn_users_count}")
            print(f"   💳 Всего платежей: {payments_count}")
            print(f"   🖥️  Всего серверов: {servers_count}")

    async def full_sync(self):
        """Выполняет полную синхронизацию"""
        print("🚀 Начинаю полную синхронизацию базы данных с Google Sheets...")
        print(f"🕐 Время начала: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
        
        try:
            # Показываем статистику
            await self.get_database_stats()
            
            # Синхронизируем все данные
            await self.sync_users()
            await self.sync_payments()
            await self.sync_servers()
            
            print(f"\n🎉 Синхронизация завершена успешно!")
            print(f"🕐 Время завершения: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
            print(f"📊 Google Sheets: https://docs.google.com/spreadsheets/d/{spreadsheets_id}")
            
        except Exception as e:
            print(f"\n❌ Ошибка при синхронизации: {e}")
            import traceback
            traceback.print_exc()
            raise


async def main():
    """Главная функция"""
    print("=" * 60)
    print("📋 СКРИПТ СИНХРОНИЗАЦИИ БАЗЫ ДАННЫХ С GOOGLE SHEETS")
    print("=" * 60)
    
    # Проверяем доступность Google Sheets
    try:
        print("🔗 Проверяю подключение к Google Sheets...")
        spreadsheet = client.open_by_key(spreadsheets_id)
        print(f"✅ Подключение установлено: {spreadsheet.title}")
    except Exception as e:
        print(f"❌ Ошибка подключения к Google Sheets: {e}")
        return
    
    # Запрашиваем подтверждение
    print("\n⚠️  ВНИМАНИЕ: Этот скрипт полностью очистит все данные в Google Sheets")
    print("   и запишет их заново из базы данных.")
    
    if len(sys.argv) > 1 and sys.argv[1] == "--force":
        confirm = "y"
    else:
        confirm = input("\n❓ Продолжить? (y/N): ").lower().strip()
    
    if confirm not in ['y', 'yes', 'да', 'д']:
        print("❌ Синхронизация отменена")
        return
    
    # Выполняем синхронизацию
    sync = SheetsSync()
    await sync.full_sync()


if __name__ == "__main__":
    asyncio.run(main()) 