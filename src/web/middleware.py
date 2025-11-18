# middleware.py
# -*- coding: utf-8 -*-
"""
Middleware для авторизации и CORS
"""

import os
import re
from functools import wraps
from flask import request, jsonify
from typing import Optional, List, Callable
import jwt
from dotenv import load_dotenv

load_dotenv()


def is_production() -> bool:
    """
    Проверка production режима

    :return: True если production
    """
    return os.getenv('ENVIRONMENT', 'development').lower() == 'production'


def get_allowed_origins() -> List[str]:
    """
    Получить список разрешенных CORS доменов

    Возвращает:
    - BITRIX24_DOMAIN (основной портал)
    - ALLOWED_ORIGINS (дополнительные домены через запятую)
    - Localhost для development режима

    :return: Список разрешенных origins
    """
    origins = []

    # Основной домен Битрикс24
    bitrix_domain = os.getenv('BITRIX24_DOMAIN', '')
    if bitrix_domain:
        # Убираем https:// если указан
        bitrix_domain = bitrix_domain.replace('https://', '').replace('http://', '')
        origins.append(f'https://{bitrix_domain}')

    # Дополнительные домены
    allowed_origins = os.getenv('ALLOWED_ORIGINS', '')
    if allowed_origins:
        for origin in allowed_origins.split(','):
            origin = origin.strip()
            if origin:
                # Если не указан протокол, добавляем https://
                if not origin.startswith('http'):
                    origin = f'https://{origin}'
                origins.append(origin)

    # В development режиме разрешаем localhost
    if not is_production():
        origins.extend([
            'http://localhost:3000',
            'http://localhost:5000',
            'http://127.0.0.1:5000',
            'http://127.0.0.1:3000'
        ])

    return origins


def check_cors_origin(origin: str) -> bool:
    """
    Проверить, разрешен ли origin для CORS

    :param origin: Origin из заголовка запроса
    :return: True если разрешен
    """
    if not origin:
        return False

    allowed = get_allowed_origins()

    # Точное совпадение
    if origin in allowed:
        return True

    # Проверка wildcard паттернов (*.bitrix24.ru)
    for allowed_origin in allowed:
        if '*' in allowed_origin:
            # Заменяем * на регулярное выражение
            pattern = allowed_origin.replace('*', '.*').replace('.', '\\.')
            if re.match(f'^{pattern}$', origin):
                return True

    # В development режиме также разрешаем любые localhost варианты
    if not is_production():
        if 'localhost' in origin or '127.0.0.1' in origin:
            return True

    return False


def require_bitrix24_auth(require_role: Optional[str] = None) -> Callable:
    """
    Декоратор для защиты эндпоинтов админки

    Проверяет:
    1. Production режим → требует Bitrix24 origin
    2. Наличие JWT токена
    3. Роль пользователя (если require_role указана)

    :param require_role: 'admin' | 'observer' | None (любая роль с правами)

    Использование:
        @require_bitrix24_auth(require_role='admin')
        def admin_only_route():
            ...

        @require_bitrix24_auth(require_role='observer')
        def observer_or_admin_route():
            ...

        @require_bitrix24_auth()
        def any_authorized_user():
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1. Проверка production режима
            if is_production():
                # Получаем origin из заголовков
                origin = request.headers.get('Origin')
                if not origin:
                    # Пробуем получить из Referer
                    referer = request.headers.get('Referer', '')
                    if referer:
                        # Извлекаем origin из referer (protocol://domain)
                        match = re.match(r'^(https?://[^/]+)', referer)
                        if match:
                            origin = match.group(1)

                # Проверяем, что запрос идет с разрешенного домена
                if not origin or not check_cors_origin(origin):
                    return jsonify({
                        'error': 'Доступ запрещен',
                        'message': 'В production режиме доступ возможен только через Битрикс24'
                    }), 403

            # 2. Проверка JWT токена
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                return jsonify({'error': 'Требуется авторизация'}), 401

            token = auth_header.replace('Bearer ', '')

            try:
                # Декодирование JWT
                JWT_SECRET = os.getenv('JWT_SECRET', 'supersecretkey')
                payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])

                user_role = payload.get('role')

                # 3. Проверка роли
                if require_role:
                    if require_role == 'admin' and user_role != 'admin':
                        return jsonify({
                            'error': 'Недостаточно прав',
                            'message': 'Требуется роль администратора'
                        }), 403

                    if require_role == 'observer' and user_role not in ['admin', 'observer']:
                        return jsonify({
                            'error': 'Недостаточно прав',
                            'message': 'Требуется роль модератора или администратора'
                        }), 403

                # Добавляем данные пользователя в request
                request.user_id = payload.get('id')
                request.user_role = user_role
                request.username = payload.get('username')

            except jwt.ExpiredSignatureError:
                return jsonify({'error': 'Токен истек'}), 401
            except jwt.InvalidTokenError:
                return jsonify({'error': 'Неверный токен'}), 401

            return f(*args, **kwargs)

        return decorated_function
    return decorator


def cors_origin_validator(origin: str) -> bool:
    """
    Валидатор для Flask-CORS origins

    В production: только домены из BITRIX24_DOMAIN и ALLOWED_ORIGINS
    В development: + localhost

    :param origin: Origin для проверки
    :return: True если разрешен
    """
    return check_cors_origin(origin)
