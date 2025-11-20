"""
Патч для web_admin.py для работы в Docker окружении
Замените соответствующие строки в src/web/web_admin.py
"""

# ===========================================================
# ЗАМЕНИТЕ СТРОКИ 82-90 в src/web/web_admin.py на:
# ===========================================================

# Эндпоинты для уведомления ботов (поддержка Docker и localhost)
# В Docker используем имена контейнеров из переменных окружения
TELEGRAM_BOT_HOST = os.getenv('TELEGRAM_BOT_HOST', '127.0.0.1')
BITRIX24_BOT_HOST = os.getenv('BITRIX24_BOT_HOST', '127.0.0.1')

TELEGRAM_BOT_RELOAD_URL = f"http://{TELEGRAM_BOT_HOST}:5001/reload"
TELEGRAM_BOT_RELOAD_SETTINGS_URL = f"http://{TELEGRAM_BOT_HOST}:5001/reload-settings"

BITRIX24_BOT_RELOAD_URL = f"http://{BITRIX24_BOT_HOST}:5002/api/reload-chromadb"
BITRIX24_BOT_RELOAD_SETTINGS_URL = f"http://{BITRIX24_BOT_HOST}:5002/api/reload-settings"

# Список всех ботов для уведомления
ALL_BOT_RELOAD_URLS = [TELEGRAM_BOT_RELOAD_URL, BITRIX24_BOT_RELOAD_URL]
ALL_BOT_RELOAD_SETTINGS_URLS = [TELEGRAM_BOT_RELOAD_SETTINGS_URL, BITRIX24_BOT_RELOAD_SETTINGS_URL]

# ===========================================================
# ЗАМЕНИТЕ СТРОКУ 93 в src/web/web_admin.py на:
# ===========================================================

# Инициализация ChromaDB (поддержка Docker путей)
CHROMA_PATH = os.getenv('CHROMA_PATH', './chroma_db')
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
