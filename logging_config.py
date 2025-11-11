# -*- coding: utf-8 -*-
"""
Конфигурация логирования с UTC+7
"""

import logging
from datetime import datetime, timedelta, timezone


class UTC7Formatter(logging.Formatter):
    """Форматтер для логов с временем в UTC+7"""

    def __init__(self, fmt=None, datefmt=None):
        super().__init__(fmt, datefmt)
        # Создаем timezone для UTC+7
        self.tz = timezone(timedelta(hours=7))

    def formatTime(self, record, datefmt=None):
        """
        Переопределяем метод formatTime для использования UTC+7
        """
        # Конвертируем timestamp в datetime с UTC+7
        dt = datetime.fromtimestamp(record.created, tz=self.tz)

        if datefmt:
            return dt.strftime(datefmt)
        else:
            # Формат по умолчанию с указанием часового пояса
            return dt.strftime('%Y-%m-%d %H:%M:%S UTC+7')


def setup_logging(name=None, level=logging.INFO, format_string=None):
    """
    Настройка логирования с UTC+7

    :param name: Имя логгера (None для root logger)
    :param level: Уровень логирования
    :param format_string: Формат сообщений
    :return: Настроенный logger
    """
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    # Создаем форматтер с UTC+7
    formatter = UTC7Formatter(format_string)

    # Настраиваем обработчик для консоли
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    # Получаем логгер
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Удаляем старые обработчики, если есть
    logger.handlers.clear()

    # Добавляем наш обработчик
    logger.addHandler(handler)

    return logger


def configure_root_logger(level=logging.INFO):
    """
    Конфигурация root logger с UTC+7

    :param level: Уровень логирования
    """
    # Создаем форматтер с UTC+7
    formatter = UTC7Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Получаем root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Удаляем все существующие обработчики
    root_logger.handlers.clear()

    # Создаем и настраиваем обработчик
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
