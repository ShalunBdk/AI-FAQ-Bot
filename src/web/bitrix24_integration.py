# bitrix24_integration.py
# -*- coding: utf-8 -*-
"""
Модуль интеграции с Битрикс24 (OAuth и handlers)
"""

import os
import sqlite3
from typing import Dict, Optional
from flask import request, Response
from dotenv import load_dotenv
from src.core.database import add_bitrix24_permission, DB_FILE

load_dotenv()


# ============================================
# Хранилище токенов Битрикс24
# ============================================

class Bitrix24TokenStorage:
    """Хранилище OAuth токенов Битрикс24 в SQLite"""

    @staticmethod
    def _get_connection():
        """Получить подключение к БД"""
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _init_table():
        """Создать таблицу токенов если её нет"""
        conn = Bitrix24TokenStorage._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bitrix24_tokens (
                domain TEXT PRIMARY KEY,
                access_token TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                member_id TEXT,
                client_endpoint TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    @staticmethod
    def save_tokens(domain: str, tokens: Dict) -> None:
        """
        Сохранить токены для портала

        :param domain: Домен портала
        :param tokens: Словарь с токенами
        """
        Bitrix24TokenStorage._init_table()

        conn = Bitrix24TokenStorage._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO bitrix24_tokens
            (domain, access_token, refresh_token, expires_at, member_id, client_endpoint, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            domain,
            tokens.get('access_token', ''),
            tokens.get('refresh_token', ''),
            tokens.get('expires_at', 0),
            tokens.get('member_id', ''),
            tokens.get('client_endpoint', f'https://{domain}/rest/')
        ))

        conn.commit()
        conn.close()

    @staticmethod
    def get_tokens(domain: str) -> Optional[Dict]:
        """
        Получить токены для портала

        :param domain: Домен портала
        :return: Словарь с токенами или None
        """
        Bitrix24TokenStorage._init_table()

        conn = Bitrix24TokenStorage._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM bitrix24_tokens WHERE domain = ?", (domain,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'domain': row['domain'],
                'access_token': row['access_token'],
                'refresh_token': row['refresh_token'],
                'expires_at': row['expires_at'],
                'member_id': row['member_id'],
                'client_endpoint': row['client_endpoint']
            }
        return None

    @staticmethod
    def delete_tokens(domain: str) -> bool:
        """
        Удалить токены для портала

        :param domain: Домен портала
        :return: True если удалены
        """
        Bitrix24TokenStorage._init_table()

        conn = Bitrix24TokenStorage._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM bitrix24_tokens WHERE domain = ?", (domain,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()

        return deleted


# ============================================
# OAuth обработчики
# ============================================

def add_initial_admin(domain: str, access_token: str) -> None:
    """
    Добавить первого администратора при установке приложения

    :param domain: Домен портала
    :param access_token: Access token для REST API
    """
    try:
        import requests

        # Получаем текущего пользователя через REST API
        response = requests.get(
            f'https://{domain}/rest/user.current',
            params={'auth': access_token},
            timeout=10
        )
        user_data = response.json()

        if user_data.get('error'):
            print(f"Ошибка получения пользователя: {user_data.get('error_description')}")
            return

        current_user = user_data.get('result')
        if not current_user:
            return

        user_id = str(current_user.get('ID'))
        user_name = f"{current_user.get('LAST_NAME', '')} {current_user.get('NAME', '')}".strip()

        # Проверяем, есть ли уже администраторы для этого портала
        from src.core.database import get_bitrix24_permissions

        existing = get_bitrix24_permissions(domain)

        if len(existing) == 0:
            # Добавляем первого администратора (того кто установил приложение)
            add_bitrix24_permission(
                domain=domain,
                user_id=user_id,
                user_name=user_name,
                role='admin',
                created_by=user_id
            )
            print(f"Добавлен первый администратор: {user_name} ({user_id}) на портале {domain}")

    except Exception as e:
        print(f"Ошибка добавления первого администратора: {e}")


def handle_install(request_obj) -> Response:
    """
    Универсальный обработчик установки приложения
    Обрабатывает данные из query (GET) или body (POST)

    :param request_obj: Flask request объект
    :return: HTML ответ
    """
    try:
        # Битрикс24 может отправлять данные через GET (query) или POST (body)
        params = {**request_obj.args, **request_obj.form}
        if request_obj.is_json:
            params.update(request_obj.get_json(silent=True) or {})

        event = params.get('event')
        placement = params.get('PLACEMENT')

        # Обработка установки через событие ONAPPINSTALL
        if event == 'ONAPPINSTALL' and params.get('auth'):
            auth = params.get('auth')

            # auth может быть строкой (JSON) или уже dict
            if isinstance(auth, str):
                import json
                try:
                    auth = json.loads(auth)
                except:
                    pass

            if isinstance(auth, dict) and auth.get('domain') and auth.get('access_token'):
                import time
                domain = auth['domain']
                tokens = {
                    'domain': domain,
                    'access_token': auth['access_token'],
                    'refresh_token': auth.get('refresh_token', ''),
                    'expires_at': int(time.time() * 1000) + (int(auth.get('expires_in', 3600)) * 1000),
                    'member_id': auth.get('member_id', ''),
                    'client_endpoint': f'https://{domain}/rest/'
                }

                Bitrix24TokenStorage.save_tokens(domain, tokens)

                # Добавляем установщика как первого администратора
                add_initial_admin(domain, auth['access_token'])

                return Response(f"""
                    <!DOCTYPE html>
                    <html>
                        <head>
                            <meta charset="UTF-8">
                            <title>Установка приложения</title>
                            <script src="//api.bitrix24.com/api/v1/"></script>
                        </head>
                        <body>
                            <script>
                                BX24.init(function() {{
                                    BX24.installFinish();
                                }});
                            </script>
                            <h2>Приложение успешно установлено!</h2>
                            <p>Теперь вы можете использовать приложение из меню Битрикс24.</p>
                        </body>
                    </html>
                """, mimetype='text/html')

        # Обработка установки через PLACEMENT
        if placement == 'DEFAULT' or params.get('DOMAIN'):
            domain = params.get('DOMAIN')
            auth_id = params.get('AUTH_ID')
            refresh_id = params.get('REFRESH_ID')
            expires = params.get('AUTH_EXPIRES', '3600')
            member_id = params.get('member_id', '')

            if domain and auth_id:
                import time
                tokens = {
                    'domain': domain,
                    'access_token': auth_id,
                    'refresh_token': refresh_id or '',
                    'expires_at': int(time.time() * 1000) + (int(expires) * 1000),
                    'member_id': member_id,
                    'client_endpoint': f'https://{domain}/rest/'
                }

                Bitrix24TokenStorage.save_tokens(domain, tokens)

                # Добавляем установщика как первого администратора
                add_initial_admin(domain, auth_id)

                return Response(f"""
                    <!DOCTYPE html>
                    <html>
                        <head>
                            <meta charset="UTF-8">
                            <title>Установка приложения</title>
                            <script src="//api.bitrix24.com/api/v1/"></script>
                        </head>
                        <body>
                            <script>
                                BX24.init(function() {{
                                    BX24.installFinish();
                                }});
                            </script>
                            <h2>Приложение успешно установлено!</h2>
                        </body>
                    </html>
                """, mimetype='text/html')

        # Если параметры не подошли
        return Response("""
            <!DOCTYPE html>
            <html>
                <head>
                    <meta charset="UTF-8">
                    <title>Ошибка установки</title>
                </head>
                <body>
                    <h2>Ошибка установки приложения</h2>
                    <p>Не удалось получить данные авторизации от Битрикс24.</p>
                </body>
            </html>
        """, mimetype='text/html', status=400)

    except Exception as e:
        print(f"Ошибка при установке приложения: {e}")
        return Response(f"""
            <!DOCTYPE html>
            <html>
                <head><meta charset="UTF-8"><title>Ошибка</title></head>
                <body>
                    <h2>Ошибка при установке приложения</h2>
                    <p>{str(e)}</p>
                </body>
            </html>
        """, mimetype='text/html', status=500)


def handle_index(request_obj) -> Response:
    """
    Универсальный обработчик первого открытия приложения

    :param request_obj: Flask request объект
    :return: Редирект на /bitrix24/app
    """
    try:
        params = {**request_obj.args, **request_obj.form}
        if request_obj.is_json:
            params.update(request_obj.get_json(silent=True) or {})

        domain = params.get('DOMAIN', '')
        auth_id = params.get('AUTH_ID', '')
        refresh_id = params.get('REFRESH_ID', '')
        expires = params.get('AUTH_EXPIRES', '3600')
        member_id = params.get('member_id', '')

        # Сохранить токены если они есть
        if domain and auth_id:
            import time
            tokens = {
                'domain': domain,
                'access_token': auth_id,
                'refresh_token': refresh_id,
                'expires_at': int(time.time() * 1000) + (int(expires) * 1000),
                'member_id': member_id,
                'client_endpoint': f'https://{domain}/rest/'
            }

            Bitrix24TokenStorage.save_tokens(domain, tokens)

            # Добавляем первого администратора если его еще нет
            add_initial_admin(domain, auth_id)

        # Перенаправить на встраиваемое приложение
        from flask import redirect
        from urllib.parse import urlencode

        redirect_params = {
            'domain': domain,
            'auth': auth_id,
            'member_id': member_id
        }

        return redirect(f'/bitrix24/app?{urlencode(redirect_params)}')

    except Exception as e:
        print(f"Ошибка при открытии приложения: {e}")
        return Response('Ошибка при открытии приложения', status=500)


def handle_app(request_obj) -> Response:
    """
    Страница встраиваемого приложения
    Отдает HTML с Bitrix24 SDK

    :param request_obj: Flask request объект
    :return: HTML страница приложения
    """
    try:
        # Bitrix24 может отправлять данные через GET (query) или POST (body)
        params = {**request_obj.args, **request_obj.form}
        if request_obj.is_json:
            params.update(request_obj.get_json(silent=True) or {})

        domain = params.get('DOMAIN', '')
        auth_id = params.get('AUTH_ID', '')
        refresh_id = params.get('REFRESH_ID', '')
        expires = params.get('AUTH_EXPIRES', '3600')
        member_id = params.get('member_id', '')

        # Сохранить токены если они есть
        if domain and auth_id:
            import time
            tokens = {
                'domain': domain,
                'access_token': auth_id,
                'refresh_token': refresh_id,
                'expires_at': int(time.time() * 1000) + (int(expires) * 1000),
                'member_id': member_id,
                'client_endpoint': f'https://{domain}/rest/'
            }

            Bitrix24TokenStorage.save_tokens(domain, tokens)

            # Добавляем первого администратора если его еще нет
            add_initial_admin(domain, auth_id)

        from flask import render_template
        return Response(
            render_template('bitrix24/app.html'),
            mimetype='text/html'
        )
    except Exception as e:
        print(f"Ошибка при загрузке приложения: {e}")
        return Response(f"""
            <!DOCTYPE html>
            <html>
                <head><meta charset="UTF-8"><title>Ошибка</title></head>
                <body>
                    <h2>Приложение не найдено</h2>
                    <p>Шаблон bitrix24/app.html не найден</p>
                    <p>Ошибка: {str(e)}</p>
                </body>
            </html>
        """, mimetype='text/html', status=500)
