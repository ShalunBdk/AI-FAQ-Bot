"""
Модуль для работы с Bitrix24 REST API
Аналог python-telegram-bot, но для Bitrix24
"""

import requests
import logging
from typing import Dict, List, Optional, Any
import json

logger = logging.getLogger(__name__)


class Bitrix24API:
    """Класс для работы с REST API Bitrix24"""

    def __init__(self, webhook_url: str, client_id: str = None, bot_id: int = None):
        """
        Args:
            webhook_url: Полный URL вебхука, например:
                https://your-domain.bitrix24.ru/rest/1/webhook_key/
            client_id: CLIENT_ID для авторизации API запросов (опционально)
            bot_id: BOT_ID - числовой ID бота для регистрации команд (опционально)
        """
        self.webhook_url = webhook_url.rstrip('/')
        self.client_id = client_id
        self.bot_id = bot_id
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json'
        })

    def _call(self, method: str, params: Dict = None, use_bot_id: bool = False) -> Dict:
        """
        Базовый метод для вызова REST API

        Args:
            method: Название метода (например, 'imbot.message.add')
            params: Параметры запроса
            use_bot_id: Использовать BOT_ID вместо CLIENT_ID

        Returns:
            Ответ от API в виде словаря
        """
        url = f"{self.webhook_url}/{method}"

        # Добавляем CLIENT_ID или BOT_ID в параметры, если он задан
        if params is None:
            params = {}
        if self.client_id:
            if use_bot_id:
                params['BOT_ID'] = self.client_id
            else:
                params['CLIENT_ID'] = self.client_id

        logger.debug(f"🔵 Bitrix24 API запрос: {method}")
        logger.debug(f"   URL: {url}")
        logger.debug(f"   Params: {json.dumps(params, ensure_ascii=False, indent=2) if params else '{}'}")

        try:
            response = self.session.post(
                url,
                json=params or {},
                timeout=10
            )

            logger.debug(f"   HTTP Status: {response.status_code}")

            response.raise_for_status()
            result = response.json()

            logger.debug(f"🟢 Bitrix24 API ответ: {json.dumps(result, ensure_ascii=False, indent=2)}")

            if 'error' in result:
                logger.error(f"❌ Bitrix24 API error: {result['error']}")
                if 'error_description' in result:
                    logger.error(f"   Описание: {result['error_description']}")
                return {'success': False, 'error': result['error']}

            return result

        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP Error при запросе к Bitrix24: {e}")
            logger.error(f"   Response text: {response.text if 'response' in locals() else 'N/A'}")
            return {'success': False, 'error': f'HTTP Error: {str(e)}'}
        except requests.exceptions.Timeout as e:
            logger.error(f"❌ Timeout при запросе к Bitrix24: {e}")
            return {'success': False, 'error': f'Timeout: {str(e)}'}
        except requests.RequestException as e:
            logger.error(f"❌ Request to Bitrix24 failed: {e}")
            return {'success': False, 'error': str(e)}

    # ========== BOT METHODS ==========

    def register_bot(self, code: str, name: str, handler_url: str,
                    avatar_base64: str = None) -> Dict:
        """
        Регистрация бота в Bitrix24

        Args:
            code: Уникальный код бота (например, 'FAQBot')
            name: Имя бота
            handler_url: URL для обработки событий
            avatar_base64: Аватар в base64 (опционально)

        Returns:
            Результат регистрации с BOT_ID
        """
        params = {
            'CODE': code,
            'TYPE': 'B',  # B = бот (мгновенные ответы), H = человек (с задержкой)
            'EVENT_MESSAGE_ADD': handler_url,
            'EVENT_WELCOME_MESSAGE': handler_url,
            'EVENT_BOT_DELETE': handler_url,
            'PROPERTIES': {
                'NAME': name,
                'COLOR': 'PURPLE',
                'WORK_POSITION': 'Отвечаю на часто задаваемые вопросы',
                'PERSONAL_GENDER': 'M',
            }
        }

        if avatar_base64:
            params['PROPERTIES']['PERSONAL_PHOTO'] = avatar_base64

        result = self._call('imbot.register', params)
        logger.info(f"Бот зарегистрирован: {result}")
        return result

    def register_command(self, command: str, title: str,
                        handler_url: str, params: str = '', hidden: bool = True) -> Dict:
        """
        Регистрация команды для бота

        Args:
            command: Название команды (например, 'helpful_yes')
            title: Описание команды для пользователя
            handler_url: URL обработчика события команды
            params: Параметры команды (опционально)
            hidden: Скрыть команду из списка (только для клавиатуры)

        Returns:
            Результат регистрации
        """
        # Проверяем наличие BOT_ID
        if not self.bot_id:
            logger.error(f"❌ BOT_ID не установлен!")
            logger.error(f"❌ Добавьте BITRIX24_BOT_ID=ваш_числовой_id в .env")
            logger.error(f"❌ Найдите BOT_ID в: Настройки → Разработчикам → Чат-боты")
            return {'success': False, 'error': 'BOT_ID не установлен'}

        command_params = {
            'BOT_ID': self.bot_id,
            'COMMAND': command,
            'COMMON': 'N',  # N = только в диалоге с ботом
            'HIDDEN': 'Y' if hidden else 'N',
            'EXTRANET_SUPPORT': 'N',
            'CLIENT_ID': '',  # Пустой CLIENT_ID согласно документации
            'EVENT_COMMAND_ADD': handler_url,
            'LANG': [
                {
                    'LANGUAGE_ID': 'ru',
                    'TITLE': title or command,
                    'PARAMS': params or ''
                }
            ]
        }

        # Не используем автоматическое добавление CLIENT_ID/BOT_ID
        result = self._call('imbot.command.register', command_params, use_bot_id=False)
        logger.debug(f"Команда '{command}' зарегистрирована: {result}")
        return result

    def send_message(self, dialog_id: int, message: str,
                    keyboard: List[List[Dict]] = None,
                    attach: List[Dict] = None) -> Dict:
        """
        Отправка сообщения в чат

        Args:
            dialog_id: ID диалога
            message: Текст сообщения
            keyboard: Клавиатура с кнопками (опционально)
            attach: Вложения (опционально)

        Returns:
            Результат отправки с MESSAGE_ID
        """
        params = {
            'DIALOG_ID': dialog_id,
            'MESSAGE': message
        }

        # Добавляем клавиатуру если есть
        if keyboard:
            params['KEYBOARD'] = keyboard

        # Добавляем вложения если есть
        if attach:
            params['ATTACH'] = attach

        # CLIENT_ID будет добавлен автоматически в _call()
        result = self._call('imbot.message.add', params)
        return result

    def send_typing(self, dialog_id: int) -> Dict:
        """
        Показать индикатор печатания

        Args:
            dialog_id: ID диалога

        Note: Этот метод может не работать с incoming webhooks
        """
        result = self._call('imbot.chat.setTyping', {
            'DIALOG_ID': dialog_id
        })
        # Игнорируем ошибки для typing indicator
        if result.get('success') == False:
            logger.debug(f"⚠️ send_typing не поддерживается (это нормально для incoming webhooks)")
        return result

    def update_message(self, message_id: int, message: str = None,
                      keyboard: List[Dict] = None, remove_keyboard: bool = False) -> Dict:
        """
        Обновить существующее сообщение

        Args:
            message_id: ID сообщения
            message: Новый текст (опционально)
            keyboard: Новая клавиатура (опционально)
            remove_keyboard: Удалить клавиатуру (передать пустую строку)
        """
        params = {
            'MESSAGE_ID': message_id
        }

        # Добавляем BOT_ID если есть
        if self.bot_id:
            params['BOT_ID'] = self.bot_id

        if message is not None:
            params['MESSAGE'] = message

        if remove_keyboard:
            params['KEYBOARD'] = ''  # Пустая строка удаляет клавиатуру
        elif keyboard is not None:
            params['KEYBOARD'] = keyboard

        return self._call('imbot.message.update', params)

    def delete_message(self, message_id: int) -> Dict:
        """
        Удалить сообщение

        Args:
            message_id: ID сообщения
        """
        return self._call('imbot.message.delete', {
            'MESSAGE_ID': message_id
        })

    def answer_command(self, command_id: int, message_id: int, message: str,
                      keyboard: List[Dict] = None, attach: List[Dict] = None) -> Dict:
        """
        Ответить на команду (используется при нажатии на кнопки)

        Args:
            command_id: ID команды из события
            message_id: ID сообщения из события
            message: Текст ответа
            keyboard: Клавиатура (опционально)
            attach: Вложения (опционально)

        Returns:
            Результат отправки
        """
        params = {
            'COMMAND_ID': command_id,
            'MESSAGE_ID': message_id,
            'MESSAGE': message
        }

        if keyboard:
            params['KEYBOARD'] = keyboard

        if attach:
            params['ATTACH'] = attach

        return self._call('imbot.command.answer', params)

    # ========== USER METHODS ==========

    def get_user(self, user_id: int) -> Dict:
        """
        Получить информацию о пользователе

        Args:
            user_id: ID пользователя
        """
        return self._call('user.get', {'ID': user_id})

    # ========== HELPER METHODS ==========

    def create_keyboard(self, buttons: List[List[Dict]]) -> List[Dict]:
        """
        Создать клавиатуру для сообщения

        Args:
            buttons: Список кнопок (двумерный массив), например:
                [[{'text': 'Да', 'action': 'yes', 'params': '123'}, {'text': 'Нет', 'action': 'no'}]]

        Returns:
            Плоский массив кнопок для Bitrix24 с разделителями {"TYPE": "NEWLINE"}
        """
        keyboard = []

        for row_index, row in enumerate(buttons):
            for button in row:
                btn_data = {
                    'TEXT': button.get('text', ''),
                    'DISPLAY': 'LINE',
                }

                # Добавляем COMMAND если есть action
                if 'action' in button:
                    btn_data['COMMAND'] = button['action']

                # Добавляем COMMAND_PARAMS если есть params
                if 'params' in button:
                    btn_data['COMMAND_PARAMS'] = button['params']

                # Добавляем цвета только если они указаны
                if 'text_color' in button:
                    btn_data['TEXT_COLOR'] = button['text_color']
                if 'bg_color' in button:
                    btn_data['BG_COLOR'] = button['bg_color']

                keyboard.append(btn_data)

            # Добавляем NEWLINE после каждой строки, кроме последней
            if row_index < len(buttons) - 1:
                keyboard.append({'TYPE': 'NEWLINE'})

        return keyboard

    def create_attach(self, items: List[Dict]) -> List[Dict]:
        """
        Создать вложение (attach) для сообщения

        Примеры items:
            {'type': 'message', 'text': 'Текст'}
            {'type': 'link', 'name': 'Ссылка', 'url': 'https://...'}
            {'type': 'delimiter'}

        Args:
            items: Список элементов для вложения

        Returns:
            Форматированные вложения для Bitrix24
        """
        if not items:
            return []

        attach = []
        for item in items:
            if item['type'] == 'message':
                attach.append({'MESSAGE': item['text']})
            elif item['type'] == 'link':
                link_data = {
                    'LINK': {
                        'NAME': item['name'],
                        'LINK': item.get('url', '#')
                    }
                }
                attach.append(link_data)
            elif item['type'] == 'delimiter':
                attach.append({
                    'DELIMITER': {
                        'SIZE': item.get('size', 400),
                        'COLOR': item.get('color', '#c6c6c6')
                    }
                })

        logger.debug(f"📎 Создан attach: {json.dumps(attach, ensure_ascii=False, indent=2)}")
        return attach


class Bitrix24Event:
    """Класс для парсинга событий от Bitrix24"""

    def __init__(self, event_data: Dict):
        """
        Args:
            event_data: Данные события из request от Bitrix24
        """
        self.raw_data = event_data
        self.event_type = event_data.get('event')

        # Преобразуем плоский формат Bitrix24 в вложенную структуру
        self.auth = self._parse_flat_dict(event_data, 'auth')
        self.data = self._parse_flat_dict(event_data, 'data')

    @staticmethod
    def _parse_flat_dict(data: Dict, prefix: str) -> Dict:
        """
        Преобразует плоские ключи типа 'data[PARAMS][MESSAGE]' в вложенную структуру
        Также обрабатывает структуры с числовыми индексами: 'data[COMMAND][15][COMMAND]'

        Args:
            data: Исходный словарь с плоскими ключами
            prefix: Префикс для фильтрации (например, 'data' или 'auth')

        Returns:
            Вложенный словарь
        """
        result = {}
        prefix_pattern = f'{prefix}['

        for key, value in data.items():
            if key.startswith(prefix_pattern):
                # Извлекаем путь: 'data[PARAMS][MESSAGE]' -> ['PARAMS', 'MESSAGE']
                # или 'data[COMMAND][15][COMMAND]' -> ['COMMAND', '15', 'COMMAND']
                path = key[len(prefix)+1:-1].split('][')

                # Фильтруем числовые индексы из пути
                filtered_path = [p for p in path if not p.isdigit()]

                if not filtered_path:
                    continue

                # Создаем вложенную структуру
                current = result
                for i, part in enumerate(filtered_path[:-1]):
                    if part not in current:
                        current[part] = {}
                    current = current[part]

                # Устанавливаем значение
                current[filtered_path[-1]] = value

        return result

    @property
    def is_message(self) -> bool:
        """Событие - новое сообщение"""
        return self.event_type == 'ONIMBOTMESSAGEADD'

    @property
    def is_join_chat(self) -> bool:
        """Событие - добавление бота в чат"""
        return self.event_type == 'ONIMBOTJOINCHAT'

    @property
    def is_bot_delete(self) -> bool:
        """Событие - удаление бота"""
        return self.event_type == 'ONIMBOTDELETE'

    @property
    def is_app_install(self) -> bool:
        """Событие - установка приложения"""
        return self.event_type == 'ONAPPINSTALL'

    @property
    def is_command(self) -> bool:
        """Событие - команда от пользователя (кнопка или текст)"""
        return self.event_type == 'ONIMCOMMANDADD'

    @property
    def message_text(self) -> Optional[str]:
        """Текст сообщения от пользователя"""
        # Возвращаем текст из PARAMS если он есть (работает для сообщений и команд)
        return self.data.get('PARAMS', {}).get('MESSAGE')

    @message_text.setter
    def message_text(self, value: str):
        """Устанавливает текст сообщения (для подмены при обработке команд)"""
        if 'PARAMS' not in self.data:
            self.data['PARAMS'] = {}
        self.data['PARAMS']['MESSAGE'] = value

    @property
    def command_data(self) -> Optional[Dict]:
        """Данные команды (при нажатии на кнопку)"""
        if self.is_command:
            return self.data.get('COMMAND', {})
        return None

    @property
    def command_name(self) -> Optional[str]:
        """Название команды"""
        if self.is_command:
            return self.data.get('COMMAND', {}).get('COMMAND')
        return None

    @property
    def command_params(self) -> Optional[str]:
        """Параметры команды"""
        if self.is_command:
            return self.data.get('COMMAND', {}).get('COMMAND_PARAMS', '')
        return None

    @property
    def command_context(self) -> Optional[str]:
        """Контекст команды: TEXTAREA, KEYBOARD, MENU"""
        if self.is_command:
            return self.data.get('COMMAND', {}).get('COMMAND_CONTEXT')
        return None

    @property
    def user_id(self) -> Optional[int]:
        """ID пользователя"""
        if self.is_message or self.is_join_chat or self.is_command:
            # Для всех типов событий (включая команды) user_id находится в PARAMS
            user_id_str = self.data.get('PARAMS', {}).get('FROM_USER_ID', 0)
            try:
                return int(user_id_str)
            except (ValueError, TypeError):
                return 0
        return None

    @property
    def dialog_id(self) -> Optional[str]:
        """ID диалога"""
        if self.is_message or self.is_join_chat or self.is_command:
            # Для всех типов событий (включая команды) dialog_id находится в PARAMS
            return str(self.data.get('PARAMS', {}).get('DIALOG_ID', ''))
        return None

    @property
    def domain(self) -> str:
        """Домен Bitrix24"""
        return self.auth.get('domain', '')

    @property
    def application_token(self) -> str:
        """Токен приложения"""
        return self.auth.get('application_token', '')

    @property
    def access_token(self) -> str:
        """Access token для API вызовов"""
        return self.auth.get('access_token', '')
