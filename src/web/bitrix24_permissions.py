# bitrix24_permissions.py
# -*- coding: utf-8 -*-
"""
API для управления правами пользователей Битрикс24
"""

import os
from flask import Blueprint, request, jsonify
from src.core.database import (
    check_bitrix24_permission,
    add_bitrix24_permission,
    get_bitrix24_permissions,
    remove_bitrix24_permission
)
import jwt
from dotenv import load_dotenv

load_dotenv()

# Создаем Blueprint для API прав доступа
bitrix24_permissions_bp = Blueprint('bitrix24_permissions', __name__)

# JWT секреты
JWT_SECRET = os.getenv('JWT_SECRET', 'supersecretkey')
REFRESH_SECRET = os.getenv('REFRESH_SECRET', 'refreshsecretkey')
ACCESS_TOKEN_EXPIRES = '15m'
REFRESH_TOKEN_EXPIRES = '7d'


@bitrix24_permissions_bp.route('/check', methods=['GET'])
def check_permission():
    """
    Проверка прав пользователя
    GET /api/bitrix24/permissions/check?domain=xxx&user_id=yyy

    Возвращает:
        {"hasPermission": true, "role": "admin"}
        или
        {"hasPermission": false, "role": null}
    """
    try:
        domain = request.args.get('domain')
        user_id = request.args.get('user_id')

        if not domain or not user_id:
            return jsonify({'error': 'Domain and user_id are required'}), 400

        permission = check_bitrix24_permission(domain, user_id)

        if permission:
            return jsonify({
                'hasPermission': True,
                'role': permission['role']
            })
        else:
            return jsonify({
                'hasPermission': False,
                'role': None
            })

    except Exception as e:
        print(f"Ошибка проверки прав: {e}")
        return jsonify({'error': 'Failed to check permissions'}), 500


@bitrix24_permissions_bp.route('/list', methods=['GET'])
def list_permissions():
    """
    Получить список пользователей с правами для портала
    GET /api/bitrix24/permissions/list?domain=xxx

    Возвращает:
        {"permissions": [{user_id, user_name, role, created_at, created_by}, ...]}
    """
    try:
        domain = request.args.get('domain')

        if not domain:
            return jsonify({'error': 'Domain is required'}), 400

        permissions = get_bitrix24_permissions(domain)

        return jsonify({'permissions': permissions})

    except Exception as e:
        print(f"Ошибка получения списка прав: {e}")
        return jsonify({'error': 'Failed to get permissions list'}), 500


@bitrix24_permissions_bp.route('/add', methods=['POST'])
def add_permission():
    """
    Добавить права пользователю
    POST /api/bitrix24/permissions/add
    Body: {domain, user_id, user_name, role, created_by}

    Возвращает:
        {"message": "Permission added successfully"}
    """
    try:
        data = request.get_json()

        domain = data.get('domain')
        user_id = data.get('user_id')
        user_name = data.get('user_name')
        role = data.get('role')
        created_by = data.get('created_by')

        if not domain or not user_id or not role:
            return jsonify({'error': 'Domain, user_id, and role are required'}), 400

        # Validate role
        if role not in ['admin', 'observer']:
            return jsonify({'error': 'Role must be admin or observer'}), 400

        success = add_bitrix24_permission(domain, user_id, user_name, role, created_by)

        if success:
            return jsonify({
                'success': True,
                'message': 'Permission added successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to add permission'
            }), 500

    except Exception as e:
        print(f"Ошибка добавления прав: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to add permission'
        }), 500


@bitrix24_permissions_bp.route('/remove', methods=['DELETE'])
def remove_permission():
    """
    Удалить права пользователя
    DELETE /api/bitrix24/permissions/remove
    Body: {domain, user_id}

    Возвращает:
        {"message": "Permission removed successfully"}
    """
    try:
        data = request.get_json()

        domain = data.get('domain')
        user_id = data.get('user_id')

        if not domain or not user_id:
            return jsonify({'error': 'Domain and user_id are required'}), 400

        success = remove_bitrix24_permission(domain, user_id)

        if success:
            return jsonify({
                'success': True,
                'message': 'Permission removed successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Permission not found'
            }), 404

    except Exception as e:
        print(f"Ошибка удаления прав: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to remove permission'
        }), 500


@bitrix24_permissions_bp.route('/auth', methods=['POST'])
def bitrix24_auth():
    """
    Получить JWT токены для Bitrix24 пользователя
    POST /api/bitrix24/permissions/auth
    Body: {domain, user_id, user_name}

    Возвращает:
        {
            "accessToken": "...",
            "user": {
                "id": "123",
                "username": "Иванов Иван",
                "role": "admin"
            }
        }
    """
    try:
        data = request.get_json()

        domain = data.get('domain')
        user_id = data.get('user_id')
        user_name = data.get('user_name')

        if not domain or not user_id:
            return jsonify({'error': 'Domain and user_id are required'}), 400

        # Проверяем права пользователя
        permission = check_bitrix24_permission(domain, user_id)

        if not permission:
            return jsonify({'error': 'User does not have permissions'}), 403

        role = permission['role']

        # Генерируем JWT токены
        access_token = jwt.encode(
            {'id': user_id, 'username': user_name, 'role': role},
            JWT_SECRET,
            algorithm='HS256'
        )

        refresh_token = jwt.encode(
            {'id': user_id, 'username': user_name, 'role': role},
            REFRESH_SECRET,
            algorithm='HS256'
        )

        # Устанавливаем refresh токен в httpOnly cookie
        response = jsonify({
            'accessToken': access_token,
            'user': {
                'id': user_id,
                'username': user_name,
                'role': role
            }
        })

        # Устанавливаем cookie с refresh токеном
        response.set_cookie(
            'refreshToken',
            refresh_token,
            httponly=True,
            secure=os.getenv('ENVIRONMENT', 'development') == 'production',
            samesite='Lax',
            max_age=7 * 24 * 60 * 60  # 7 дней
        )

        return response

    except Exception as e:
        print(f"Ошибка авторизации: {e}")
        return jsonify({'error': 'Failed to authenticate'}), 500
