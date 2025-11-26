#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест функциональности BASE_PATH для HANDLER_URL
"""

import os
from urllib.parse import urlparse, urlunparse


def apply_base_path_to_handler_url(handler_url: str, base_path: str) -> str:
    """
    Применить BASE_PATH к HANDLER_URL

    Args:
        handler_url: Исходный HANDLER_URL
        base_path: Префикс пути (например, /faqbot)

    Returns:
        URL с применённым BASE_PATH
    """
    base_path = base_path.rstrip('/')

    # Если BASE_PATH пустой или уже есть в URL - не меняем
    if not base_path or base_path in handler_url:
        return handler_url

    # Вставляем BASE_PATH между доменом и путём
    parsed = urlparse(handler_url)
    new_path = f"{base_path}{parsed.path}"
    return urlunparse((
        parsed.scheme, parsed.netloc, new_path,
        parsed.params, parsed.query, parsed.fragment
    ))


def test_base_path_scenarios():
    """Тест различных сценариев BASE_PATH"""

    print("="*70)
    print("TEST: BASE_PATH application to HANDLER_URL")
    print("="*70)

    test_cases = [
        # (handler_url, base_path, expected_result)
        (
            "https://domain.com/webhook/bitrix24",
            "/faqbot",
            "https://domain.com/faqbot/webhook/bitrix24"
        ),
        (
            "https://domain.com/webhook/bitrix24",
            "",
            "https://domain.com/webhook/bitrix24"
        ),
        (
            "https://domain.com/webhook/bitrix24",
            "/bot",
            "https://domain.com/bot/webhook/bitrix24"
        ),
        (
            "https://domain.com/faqbot/webhook/bitrix24",
            "/faqbot",
            "https://domain.com/faqbot/webhook/bitrix24"  # Не дублируется
        ),
        (
            "https://domain.com/api/v1/webhook/bitrix24",
            "/services",
            "https://domain.com/services/api/v1/webhook/bitrix24"
        ),
        (
            "http://localhost:5002/webhook/bitrix24",
            "/test",
            "http://localhost:5002/test/webhook/bitrix24"
        ),
    ]

    passed = 0
    failed = 0

    for i, (handler_url, base_path, expected) in enumerate(test_cases, 1):
        result = apply_base_path_to_handler_url(handler_url, base_path)

        status = "PASS" if result == expected else "FAIL"
        if result == expected:
            passed += 1
        else:
            failed += 1

        print(f"\nTest {i}: {status}")
        print(f"  Handler URL: {handler_url}")
        print(f"  BASE_PATH:   {base_path or '(empty)'}")
        print(f"  Expected:    {expected}")
        print(f"  Got:         {result}")

        if result != expected:
            print(f"  ❌ MISMATCH!")

    print("\n" + "="*70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*70)

    return failed == 0


if __name__ == "__main__":
    success = test_base_path_scenarios()
    exit(0 if success else 1)
