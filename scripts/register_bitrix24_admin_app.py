# register_bitrix24_admin_app.py
# -*- coding: utf-8 -*-
"""
Скрипт-помощник для регистрации админ-панели в Битрикс24

Этот скрипт выводит инструкции и настройки для регистрации
веб-админки как локального приложения в Битрикс24.
"""

import os
import sys
from dotenv import load_dotenv

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()


def main():
    """Главная функция скрипта"""

    print("=" * 70)
    print("Регистрация FAQ Админ-Панели в Битрикс24")
    print("=" * 70)
    print()

    # Получаем домен из .env или запрашиваем у пользователя
    admin_domain = os.getenv('BITRIX24_ADMIN_URL', '')
    if admin_domain:
        # Извлекаем домен из полного URL
        if '://' in admin_domain:
            admin_domain = admin_domain.split('://')[1].split('/')[0]
    else:
        print("ВНИМАНИЕ: Переменная BITRIX24_ADMIN_URL не найдена в .env")
        print("Пожалуйста, укажите публичный домен вашего сервера")
        print("Например: your-domain.com или abc123.ngrok.io")
        print()
        admin_domain = input("Введите домен: ").strip()

    if not admin_domain:
        print("Ошибка: домен не указан")
        return

    print()
    print("Шаг 1: Откройте настройки Битрикс24")
    print("-" * 70)
    print("1. Войдите в ваш портал Битрикс24")
    print("2. Перейдите: Приложения → Разработчикам → Другое → Добавить приложение")
    print("3. Выберите тип: Локальное приложение")
    print()

    input("Нажмите Enter когда будете готовы к следующему шагу...")
    print()

    print("Шаг 2: Заполните основную информацию")
    print("-" * 70)
    print("Название приложения:")
    print("  FAQ Админ Панель")
    print()
    print("Код приложения (латиница, цифры, подчеркивание):")
    print("  faq_admin_panel")
    print()
    print("Описание:")
    print("  Веб-интерфейс для управления базой знаний FAQ бота")
    print()

    input("Нажмите Enter когда будете готовы к следующему шагу...")
    print()

    print("Шаг 3: Укажите URL обработчиков")
    print("-" * 70)
    print()
    print("URL обработчика установки (Install handler):")
    print(f"  https://{admin_domain}/bitrix24/install")
    print()
    print("URL обработчика первого открытия (Index handler):")
    print(f"  https://{admin_domain}/bitrix24/index")
    print()
    print("URL встраивания приложения (Application URL):")
    print(f"  https://{admin_domain}/bitrix24/app")
    print()

    input("Нажмите Enter когда будете готовы к следующему шагу...")
    print()

    print("Шаг 4: Настройте права доступа (Scopes)")
    print("-" * 70)
    print("Минимальные права:")
    print("  [✓] app - базовый доступ к приложению")
    print("  [✓] user - доступ к данным пользователей")
    print()
    print("Дополнительные права (опционально):")
    print("  [ ] department - доступ к структуре компании")
    print("  [ ] im - доступ к мессенджеру")
    print()

    input("Нажмите Enter когда будете готовы к следующему шагу...")
    print()

    print("Шаг 5: Сохраните учетные данные")
    print("-" * 70)
    print("После создания приложения вы получите:")
    print()
    print("1. CLIENT_ID (Application ID)")
    print("   Например: local.5c8bb1b0891cf2.87252039")
    print()
    print("2. CLIENT_SECRET (Application key)")
    print("   Например: SakeVG5mbRdcQet45UUrt6q72AMTo7fkwXSO7Y5LYFYNCRsA6f")
    print()
    print("ВАЖНО: Скопируйте эти значения в файл .env:")
    print()
    print("BITRIX24_CLIENT_ID=<ваш CLIENT_ID>")
    print("BITRIX24_CLIENT_SECRET=<ваш CLIENT_SECRET>")
    print()

    input("Нажмите Enter когда будете готовы к следующему шагу...")
    print()

    print("Шаг 6: Обновите .env файл")
    print("-" * 70)
    print("Откройте файл .env и убедитесь, что заполнены следующие переменные:")
    print()
    print(f"BITRIX24_CLIENT_ID=local.xxxxxxxxxx.xxxxxxxx")
    print(f"BITRIX24_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx")
    print(f"BITRIX24_REDIRECT_URI=https://{admin_domain}/bitrix24/callback")
    print(f"BITRIX24_ADMIN_URL=https://{admin_domain}/bitrix24/app")
    print()
    print("Также укажите домен вашего портала Битрикс24 (БЕЗ https://):")
    print(f"BITRIX24_DOMAIN=your-company.bitrix24.ru")
    print()
    print("JWT секреты (сгенерируйте случайные строки):")
    print("JWT_SECRET=<случайная строка минимум 32 символа>")
    print("REFRESH_SECRET=<случайная строка минимум 32 символа>")
    print()
    print("Режим окружения (для production ограничивает прямой доступ):")
    print("ENVIRONMENT=development  # или production")
    print()

    input("Нажмите Enter когда будете готовы к следующему шагу...")
    print()

    print("Шаг 7: Установите приложение")
    print("-" * 70)
    print("1. Перезапустите веб-админку:")
    print("   python src/web/web_admin.py")
    print()
    print("2. В Битрикс24 перейдите: Приложения → Мои приложения")
    print("3. Найдите 'FAQ Админ Панель' и нажмите 'Установить'")
    print()
    print("4. При первой установке:")
    print("   - Пользователь, который установил приложение, автоматически")
    print("     получает роль 'admin' (администратор)")
    print("   - Администратор может управлять правами других пользователей")
    print()

    input("Нажмите Enter когда будете готовы к следующему шагу...")
    print()

    print("Шаг 8: Управление правами доступа")
    print("-" * 70)
    print("После установки приложения администратор может:")
    print()
    print("Роли пользователей:")
    print("  • admin (администратор)")
    print("    - Полный доступ к FAQ (создание, редактирование, удаление)")
    print("    - Доступ к логам и статистике")
    print("    - Управление настройками бота")
    print("    - Управление правами других пользователей")
    print()
    print("  • observer (модератор)")
    print("    - Полный доступ к FAQ (создание, редактирование, удаление)")
    print("    - Доступ к логам и статистике")
    print("    - БЕЗ доступа к настройкам бота")
    print("    - БЕЗ доступа к управлению правами")
    print()
    print("  • Обычный пользователь (без роли)")
    print("    - Только публичный поиск по базе знаний")
    print("    - БЕЗ доступа к админке")
    print()

    input("Нажмите Enter для завершения...")
    print()

    print("=" * 70)
    print("Готово!")
    print("=" * 70)
    print()
    print("Дополнительная информация:")
    print()
    print("• Документация: см. файл BITRIX24_AI_INTEGRATION_GUIDE.md")
    print("• Техподдержка: создайте issue на GitHub")
    print()
    print("Полезные команды:")
    print("  # Запуск веб-админки")
    print("  python src/web/web_admin.py")
    print()
    print("  # Проверка базы данных")
    print("  python -c \"from src.core.database import get_all_bitrix24_domains; print(get_all_bitrix24_domains())\"")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nПрервано пользователем")
    except Exception as e:
        print(f"\nОшибка: {e}")
