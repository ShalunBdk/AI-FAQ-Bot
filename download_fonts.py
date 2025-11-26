#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для скачивания шрифтов Inter и Material Symbols Outlined локально
"""
import os
import sys
import urllib.request
from pathlib import Path

# Устанавливаем правильную кодировку для Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Создаем директорию для шрифтов
fonts_dir = Path(__file__).parent / 'src' / 'web' / 'static' / 'fonts'
fonts_dir.mkdir(parents=True, exist_ok=True)

print("Скачивание шрифтов...")

# Inter font URLs (от Google Fonts v18 - актуальная версия)
inter_fonts = {
    'inter-v13-latin-regular.woff2': 'https://fonts.gstatic.com/s/inter/v18/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuLyfAZ9hiA.woff2',
    'inter-v13-latin-500.woff2': 'https://fonts.gstatic.com/s/inter/v18/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuI6fAZ9hiA.woff2',
    'inter-v13-latin-600.woff2': 'https://fonts.gstatic.com/s/inter/v18/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuGKYAZ9hiA.woff2',
    'inter-v13-latin-700.woff2': 'https://fonts.gstatic.com/s/inter/v18/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuFuYAZ9hiA.woff2',
    'inter-v13-latin-900.woff2': 'https://fonts.gstatic.com/s/inter/v18/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuDyYAZ9hiA.woff2',
}

# Material Symbols Outlined
material_icons = {
    'material-symbols-outlined.woff2': 'https://fonts.gstatic.com/s/materialsymbolsoutlined/v298/kJF1BvYX7BgnkSrUwT8OhrdQw4oELdPIeeII9v6oDMzByHX9rA6RzaxHMPdY43zj-jCxv3fzvRNU22ZXGJpEpjC_1v-p_4MrImHCIJIZrDCvHOej.woff2',
}

fonts_to_download = {**inter_fonts, **material_icons}

for filename, url in fonts_to_download.items():
    output_path = fonts_dir / filename
    if output_path.exists():
        print(f"[OK] {filename} уже существует")
    else:
        try:
            print(f"Скачивание {filename}...")
            urllib.request.urlretrieve(url, output_path)
            print(f"[OK] {filename} скачан")
        except Exception as e:
            print(f"[ERROR] Ошибка при скачивании {filename}: {e}")

print("\nВсе шрифты готовы!")
print(f"Шрифты находятся в: {fonts_dir.absolute()}")
