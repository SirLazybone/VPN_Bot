#!/usr/bin/env python3
"""
Скрипт для проверки синхронизации данных между базой данных и Google Sheets.
Сравнивает количество записей и выявляет расхождения.
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
from sheets.sheets_service import (
    sheet_users, sheet_payments, sheet_servers,
    client, spreadsheets_id
)


class SyncChecker:
    def __init__(self):
        self.issues = []

    def add_issue(self, issue):
        """Добавляет проблему в список"""
        self.issues.append(issue)
        print(f"⚠️  {issue}")

    async def check_users_sync(self):
        """Проверяет синхронизацию пользователей"""
        print("\n👥 Проверка синхронизации пользователей...")
        
        # Получаем данные из БД
        async with async_session() as session:
            result = await session.execute(select(User).order_by(User.id))
            db_users = result.scalars().all()
        
        # Получаем данные из Sheets
        try:
            sheets_records = sheet_users.get_all_records()
        except Exception as e:
            self.add_issue(f"Ошибка получения данных из Google Sheets Users: {e}")
            return
        
        # Сравниваем количество
        db_count = len(db_users)
        sheets_count = len(sheets_records)
        
        print(f"   📊 БД: {db_count} пользователей")
        print(f"   📊 Sheets: {sheets_count} записей")
        
        if db_count != sheets_count:
            self.add_issue(f"Количество пользователей не совпадает: БД={db_count}, Sheets={sheets_count}")
        else:
            print("   ✅ Количество записей совпадает")
        
        # Проверяем заголовки
        if sheets_records:
            expected_headers = ['id', 'telegram_id', 'username', 'balance', 'created_at',
                              'subscription_start', 'subscription_end', 'is_active', 
                              'vpn_link', 'server_id', 'trial_used']
            actual_headers = list(sheets_records[0].keys())
            
            if actual_headers != expected_headers:
                self.add_issue(f"Заголовки Users не совпадают. Ожидалось: {expected_headers}, получено: {actual_headers}")
            else:
                print("   ✅ Заголовки корректны")
        
        # Проверяем несколько случайных записей
        if db_users and sheets_records and len(db_users) == len(sheets_records):
            for i in [0, len(db_users)//2, -1]:  # первая, средняя, последняя
                if i < len(db_users):
                    db_user = db_users[i]
                    sheets_user = sheets_records[i]
                    
                    if str(db_user.id) != str(sheets_user['id']):
                        self.add_issue(f"ID пользователя не совпадает в позиции {i}: БД={db_user.id}, Sheets={sheets_user['id']}")

    async def check_payments_sync(self):
        """Проверяет синхронизацию платежей"""
        print("\n💳 Проверка синхронизации платежей...")
        
        # Получаем данные из БД
        async with async_session() as session:
            result = await session.execute(select(Payment).order_by(Payment.id))
            db_payments = result.scalars().all()
        
        # Получаем данные из Sheets
        try:
            sheets_records = sheet_payments.get_all_records()
        except Exception as e:
            self.add_issue(f"Ошибка получения данных из Google Sheets Payments: {e}")
            return
        
        # Сравниваем количество
        db_count = len(db_payments)
        sheets_count = len(sheets_records)
        
        print(f"   📊 БД: {db_count} платежей")
        print(f"   📊 Sheets: {sheets_count} записей")
        
        if db_count != sheets_count:
            self.add_issue(f"Количество платежей не совпадает: БД={db_count}, Sheets={sheets_count}")
        else:
            print("   ✅ Количество записей совпадает")
        
        # Проверяем заголовки
        if sheets_records:
            expected_headers = ['id', 'user_id', 'amount', 'payment_id', 'status',
                              'created_at', 'completed_at', 'nickname', 'message', 'pay_system']
            actual_headers = list(sheets_records[0].keys())
            
            if actual_headers != expected_headers:
                self.add_issue(f"Заголовки Payments не совпадают. Ожидалось: {expected_headers}, получено: {actual_headers}")
            else:
                print("   ✅ Заголовки корректны")

    async def check_servers_sync(self):
        """Проверяет синхронизацию серверов"""
        print("\n🖥️  Проверка синхронизации серверов...")
        
        # Получаем данные из БД
        async with async_session() as session:
            result = await session.execute(select(Server).order_by(Server.id))
            db_servers = result.scalars().all()
        
        # Получаем данные из Sheets
        try:
            sheets_records = sheet_servers.get_all_records()
        except Exception as e:
            self.add_issue(f"Ошибка получения данных из Google Sheets Servers: {e}")
            return
        
        # Сравниваем количество
        db_count = len(db_servers)
        sheets_count = len(sheets_records)
        
        print(f"   📊 БД: {db_count} серверов")
        print(f"   📊 Sheets: {sheets_count} записей")
        
        if db_count != sheets_count:
            self.add_issue(f"Количество серверов не совпадает: БД={db_count}, Sheets={sheets_count}")
        else:
            print("   ✅ Количество записей совпадает")
        
        # Проверяем заголовки
        if sheets_records:
            expected_headers = ['id', 'name', 'url', 'is_active', 'is_default',
                              'created_at', 'description']
            actual_headers = list(sheets_records[0].keys())
            
            if actual_headers != expected_headers:
                self.add_issue(f"Заголовки Servers не совпадают. Ожидалось: {expected_headers}, получено: {actual_headers}")
            else:
                print("   ✅ Заголовки корректны")

    async def check_database_integrity(self):
        """Проверяет целостность данных в БД"""
        print("\n🔍 Проверка целостности базы данных...")
        
        async with async_session() as session:
            # Пользователи с несуществующими серверами
            result = await session.execute(
                select(User).where(
                    User.server_id.isnot(None)
                ).outerjoin(Server, User.server_id == Server.id).where(Server.id.is_(None))
            )
            orphan_users = result.scalars().all()
            
            if orphan_users:
                self.add_issue(f"Найдено {len(orphan_users)} пользователей с несуществующими server_id")
                for user in orphan_users[:5]:  # показываем первые 5
                    print(f"   👤 Пользователь {user.username} (ID: {user.id}) -> server_id: {user.server_id}")
            else:
                print("   ✅ Все пользователи имеют корректные server_id")
            
            # Платежи с несуществующими пользователями
            result = await session.execute(
                select(Payment).outerjoin(User, Payment.user_id == User.id).where(User.id.is_(None))
            )
            orphan_payments = result.scalars().all()
            
            if orphan_payments:
                self.add_issue(f"Найдено {len(orphan_payments)} платежей с несуществующими user_id")
            else:
                print("   ✅ Все платежи имеют корректные user_id")

    async def full_check(self):
        """Выполняет полную проверку синхронизации"""
        print("🔍 Начинаю проверку синхронизации...")
        print(f"🕐 Время начала: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
        
        try:
            await self.check_database_integrity()
            await self.check_users_sync()
            await self.check_payments_sync()
            await self.check_servers_sync()
            
            print(f"\n📋 Результат проверки:")
            if not self.issues:
                print("✅ Синхронизация прошла успешно! Проблем не обнаружено.")
            else:
                print(f"⚠️  Обнаружено проблем: {len(self.issues)}")
                print("\n📝 Список проблем:")
                for i, issue in enumerate(self.issues, 1):
                    print(f"   {i}. {issue}")
                print(f"\n💡 Рекомендуется повторить синхронизацию")
            
            print(f"\n🕐 Время завершения: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
            
        except Exception as e:
            print(f"\n❌ Ошибка при проверке: {e}")
            import traceback
            traceback.print_exc()
            raise


async def main():
    """Главная функция"""
    print("=" * 60)
    print("🔍 ПРОВЕРКА СИНХРОНИЗАЦИИ GOOGLE SHEETS")
    print("=" * 60)
    
    # Проверяем доступность Google Sheets
    try:
        print("🔗 Проверяю подключение к Google Sheets...")
        spreadsheet = client.open_by_key(spreadsheets_id)
        print(f"✅ Подключение установлено: {spreadsheet.title}")
    except Exception as e:
        print(f"❌ Ошибка подключения к Google Sheets: {e}")
        return
    
    # Выполняем проверку
    checker = SyncChecker()
    await checker.full_check()
    
    # Возвращаем код выхода
    return 0 if not checker.issues else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 