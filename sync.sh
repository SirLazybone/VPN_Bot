#!/bin/bash

# Скрипт для управления синхронизацией Google Sheets

set -e  # Остановить выполнение при ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция для вывода заголовка
print_header() {
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================${NC}"
}

# Функция для проверки Python окружения
check_environment() {
    echo -e "${YELLOW}Проверяю окружение...${NC}"
    
    # Проверяем виртуальное окружение
    if [ -d ".venv" ]; then
        echo -e "${GREEN}✅ Виртуальное окружение найдено${NC}"
        source .venv/bin/activate
    else
        echo -e "${YELLOW}⚠️ Виртуальное окружение .venv не найдено${NC}"
    fi
    
    # Проверяем Python и зависимости
    if ! python -c "import asyncio, sqlalchemy, gspread" 2>/dev/null; then
        echo -e "${RED}❌ Не все зависимости установлены. Выполните: pip install -r requirements.txt${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Окружение готово${NC}"
}

# Функция для полной синхронизации
full_sync() {
    print_header "ПОЛНАЯ СИНХРОНИЗАЦИЯ GOOGLE SHEETS"
    
    echo -e "${YELLOW}⚠️ ВНИМАНИЕ: Все данные в Google Sheets будут удалены и записаны заново!${NC}"
    
    if [ "$1" != "--force" ]; then
        read -p "Продолжить? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${YELLOW}Синхронизация отменена${NC}"
            exit 0
        fi
    fi
    
    echo -e "${BLUE}Запускаю полную синхронизацию...${NC}"
    python sheets/sync_to_sheets.py --force
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Синхронизация завершена успешно!${NC}"
        echo -e "${BLUE}Запускаю проверку...${NC}"
        python sheets/check_sheets_sync.py
    else
        echo -e "${RED}❌ Ошибка при синхронизации${NC}"
        exit 1
    fi
}

# Функция для проверки синхронизации
check_sync() {
    print_header "ПРОВЕРКА СИНХРОНИЗАЦИИ"
    
    echo -e "${BLUE}Запускаю проверку синхронизации...${NC}"
    python sheets/check_sheets_sync.py
}

# Функция для показа статистики
show_stats() {
    print_header "СТАТИСТИКА БАЗЫ ДАННЫХ"
    
    python -c "
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath('.')))
from db.database import async_session
from db.models import User, Payment, Server
from sqlalchemy import select

async def show_stats():
    async with async_session() as session:
        # Пользователи
        users_result = await session.execute(select(User))
        users = users_result.scalars().all()
        active_users = [u for u in users if u.is_active]
        vpn_users = [u for u in users if u.vpn_link]
        trial_users = [u for u in users if u.trial_used]
        
        # Платежи
        payments_result = await session.execute(select(Payment))
        payments = payments_result.scalars().all()
        completed_payments = [p for p in payments if p.status == 'Closed']
        
        # Серверы
        servers_result = await session.execute(select(Server))
        servers = servers_result.scalars().all()
        active_servers = [s for s in servers if s.is_active]
        
        print(f'👥 Пользователи:')
        print(f'   Всего: {len(users)}')
        print(f'   Активных: {len(active_users)}')
        print(f'   С VPN: {len(vpn_users)}')
        print(f'   Использовавших пробный период: {len(trial_users)}')
        print(f'')
        print(f'💳 Платежи:')
        print(f'   Всего: {len(payments)}')
        print(f'   Завершенных: {len(completed_payments)}')
        print(f'')
        print(f'🖥️ Серверы:')
        print(f'   Всего: {len(servers)}')
        print(f'   Активных: {len(active_servers)}')

asyncio.run(show_stats())
"
}

# Основное меню
show_menu() {
    echo
    echo -e "${BLUE}Выберите действие:${NC}"
    echo "1) Полная синхронизация (с подтверждением)"
    echo "2) Полная синхронизация (принудительно)"
    echo "3) Проверка синхронизации"
    echo "4) Показать статистику БД"
    echo "5) Выход"
    echo
}

# Главная функция
main() {
    print_header "УПРАВЛЕНИЕ СИНХРОНИЗАЦИЕЙ GOOGLE SHEETS"
    
    check_environment
    
    # Если передан аргумент, выполняем соответствующее действие
    case "$1" in
        "sync")
            full_sync
            ;;
        "sync-force")
            full_sync --force
            ;;
        "check")
            check_sync
            ;;
        "stats")
            show_stats
            ;;
        *)
            # Интерактивное меню
            while true; do
                show_menu
                read -p "Ваш выбор (1-5): " choice
                case $choice in
                    1)
                        full_sync
                        ;;
                    2)
                        full_sync --force
                        ;;
                    3)
                        check_sync
                        ;;
                    4)
                        show_stats
                        ;;
                    5)
                        echo -e "${GREEN}До свидания!${NC}"
                        exit 0
                        ;;
                    *)
                        echo -e "${RED}Неверный выбор. Пожалуйста, выберите 1-5.${NC}"
                        ;;
                esac
                echo
                read -p "Нажмите Enter для продолжения..."
            done
            ;;
    esac
}

# Запуск
main "$@" 