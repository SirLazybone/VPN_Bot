#!/usr/bin/env python3
"""
Скрипт для управления режимом отладки VPN
"""

import os
import sys
from pathlib import Path

def read_env_file():
    """Читает .env файл и возвращает словарь переменных"""
    env_file = Path(".env")
    env_vars = {}
    
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    
    return env_vars

def write_env_file(env_vars):
    """Записывает словарь переменных в .env файл"""
    with open(".env", 'w', encoding='utf-8') as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")

def get_current_status():
    """Получает текущий статус DEBUG_VPN"""
    env_vars = read_env_file()
    debug_vpn = env_vars.get('DEBUG_VPN', 'false').lower()
    return debug_vpn == 'true'

def toggle_debug():
    """Переключает состояние DEBUG_VPN"""
    env_vars = read_env_file()
    current_status = get_current_status()
    
    new_status = not current_status
    env_vars['DEBUG_VPN'] = 'true' if new_status else 'false'
    
    write_env_file(env_vars)
    return new_status

def set_debug(enabled: bool):
    """Устанавливает конкретное значение DEBUG_VPN"""
    env_vars = read_env_file()
    env_vars['DEBUG_VPN'] = 'true' if enabled else 'false'
    write_env_file(env_vars)
    return enabled

def main():
    """Главная функция"""
    print("🔧 Управление режимом отладки VPN")
    print("=" * 40)
    
    current = get_current_status()
    status_text = "🟢 ВКЛЮЧЕН" if current else "🔴 ВЫКЛЮЧЕН"
    print(f"Текущий статус: {status_text}")
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command in ['on', 'enable', 'true', '1']:
            new_status = set_debug(True)
            print("✅ Отладка VPN ВКЛЮЧЕНА")
            print("📝 Теперь все VPN операции будут подробно логироваться")
            
        elif command in ['off', 'disable', 'false', '0']:
            new_status = set_debug(False)
            print("✅ Отладка VPN ВЫКЛЮЧЕНА")
            print("📝 VPN операции будут работать без детального логирования")
            
        elif command in ['toggle', 'switch']:
            new_status = toggle_debug()
            status_text = "ВКЛЮЧЕНА" if new_status else "ВЫКЛЮЧЕНА"
            print(f"✅ Отладка VPN {status_text}")
            
        elif command in ['status', 'check']:
            print(f"📊 Режим отладки: {status_text}")
            
        else:
            print(f"❌ Неизвестная команда: {command}")
            show_help()
            
    else:
        # Интерактивный режим
        print("\nВыберите действие:")
        print("1. Включить отладку")
        print("2. Выключить отладку") 
        print("3. Переключить состояние")
        print("4. Показать статус")
        print("5. Выход")
        
        try:
            choice = input("\nВаш выбор (1-5): ").strip()
            
            if choice == '1':
                set_debug(True)
                print("✅ Отладка VPN ВКЛЮЧЕНА")
            elif choice == '2':
                set_debug(False)
                print("✅ Отладка VPN ВЫКЛЮЧЕНА")
            elif choice == '3':
                new_status = toggle_debug()
                status_text = "ВКЛЮЧЕНА" if new_status else "ВЫКЛЮЧЕНА"
                print(f"✅ Отладка VPN {status_text}")
            elif choice == '4':
                current = get_current_status()
                status_text = "🟢 ВКЛЮЧЕН" if current else "🔴 ВЫКЛЮЧЕН"
                print(f"📊 Режим отладки: {status_text}")
            elif choice == '5':
                print("👋 До свидания!")
                return
            else:
                print("❌ Неверный выбор")
                
        except KeyboardInterrupt:
            print("\n👋 Прервано пользователем")
    
    print("\n💡 Примечание: Перезапустите бота, чтобы изменения вступили в силу")

def show_help():
    """Показывает справку по использованию"""
    print("\nИспользование:")
    print("  python toggle_vpn_debug.py [команда]")
    print("\nКоманды:")
    print("  on, enable, true, 1    - Включить отладку")
    print("  off, disable, false, 0 - Выключить отладку")
    print("  toggle, switch         - Переключить состояние")
    print("  status, check          - Показать текущий статус")
    print("\nПримеры:")
    print("  python toggle_vpn_debug.py on")
    print("  python toggle_vpn_debug.py off")
    print("  python toggle_vpn_debug.py status")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1) 