import sqlite3
import pandas as pd
import os

# --- КОНФИГУРАЦИЯ ---
DB_NAME = r'C:\Users\sar\Downloads\Projects\FAQBot\scripts\faq_database.db'          # Имя файла вашей базы данных
EXCEL_FILE = 'report.xlsx'   # Имя выходного файла Excel

def export_logs_to_excel():
    try:
        # 1. Подключение к БД и получение данных
        conn = sqlite3.connect(DB_NAME)
        
        # Читаем данные сразу в DataFrame pandas
        query = "SELECT username, query_text FROM query_logs"
        df = pd.read_sql_query(query, conn)
        
        conn.close()

        if df.empty:
            print("База данных пуста. Файл не создан.")
            return

        # 2. Подготовка данных для второго листа (Статистика)
        
        # Считаем количество запросов по каждому username
        # value_counts() считает уникальные значения, reset_index превращает это обратно в таблицу
        stats_per_user = df['username'].value_counts().reset_index()
        stats_per_user.columns = ['username', 'count'] # Переименуем колонки для красоты

        # Считаем общее количество запросов
        total_queries = len(df)
        
        # Создаем строку с итогом, чтобы добавить её в конец таблицы статистики
        total_row = pd.DataFrame({'username': ['ИТОГО (TOTAL)'], 'count': [total_queries]})
        
        # Объединяем таблицу по юзерам и строку итога
        final_stats = pd.concat([stats_per_user, total_row], ignore_index=True)

        # 3. Запись в Excel
        with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl') as writer:
            # Лист 1: Сырые данные
            df.to_excel(writer, sheet_name='Raw Data', index=False)
            
            # Лист 2: Статистика
            final_stats.to_excel(writer, sheet_name='Statistics', index=False)
            
        print(f"Готово! Данные успешно сохранены в файл: {EXCEL_FILE}")
        print(f"Всего обработано строк: {total_queries}")

    except sqlite3.Error as e:
        print(f"Ошибка при работе с SQL: {e}")
    except Exception as e:
        print(f"Произошла ошибка: {e}")

if __name__ == "__main__":
    export_logs_to_excel()