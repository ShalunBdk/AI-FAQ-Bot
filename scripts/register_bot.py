"""
Скрипт для регистрации бота в Bitrix24
Запустить один раз для создания бота
"""

import os
from dotenv import load_dotenv
from b24_api import Bitrix24API

load_dotenv()

BITRIX24_WEBHOOK = os.getenv("BITRIX24_WEBHOOK")
BITRIX24_BOT_CODE = os.getenv("BITRIX24_BOT_CODE", "FAQBot")
BITRIX24_BOT_NAME = os.getenv("BITRIX24_BOT_NAME", "FAQ Помощник")
BITRIX24_HANDLER_URL = os.getenv("BITRIX24_HANDLER_URL")

if not BITRIX24_WEBHOOK:
    print("❌ BITRIX24_WEBHOOK не настроен в .env")
    exit(1)

if not BITRIX24_HANDLER_URL or BITRIX24_HANDLER_URL == "https://your-domain.com/webhook/bitrix24":
    print("❌ BITRIX24_HANDLER_URL не настроен в .env")
    print("Добавьте: BITRIX24_HANDLER_URL=https://ваш-tuna-url.ru.tuna.am/webhook/bitrix24")
    exit(1)

print("🤖 Регистрация бота в Bitrix24...")
print(f"Код бота: {BITRIX24_BOT_CODE}")
print(f"Имя бота: {BITRIX24_BOT_NAME}")
print(f"Handler URL: {BITRIX24_HANDLER_URL}")
print()

api = Bitrix24API(BITRIX24_WEBHOOK)

result = api.register_bot(
    code=BITRIX24_BOT_CODE,
    name=BITRIX24_BOT_NAME,
    handler_url=BITRIX24_HANDLER_URL
)

if result.get('success') == False:
    print(f"❌ Ошибка регистрации: {result.get('error')}")
    exit(1)

if 'result' in result:
    bot_id = result['result']
    print(f"✅ Бот успешно зарегистрирован!")
    print(f"BOT_ID (CLIENT_ID): {bot_id}")
    print()
    print(f"Добавьте в .env файл:")
    print(f"BITRIX24_BOT_ID={bot_id}")
    print()
    print(f"Затем перезапустите бота: python b24_bot.py")
else:
    print(f"⚠️ Непонятный ответ от Bitrix24:")
    print(result)
