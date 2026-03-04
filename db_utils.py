import sqlite3
import time
from functools import wraps

def db_operation(max_retries=3, delay=0.1):
    """Декоратор для повторных попыток при блокировке БД"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if 'database is locked' in str(e) and attempt < max_retries - 1:
                        time.sleep(delay * (attempt + 1))  # Увеличиваем задержку с каждой попыткой
                        continue
                    else:
                        raise e
            return None
        return wrapper
    return decorator

def get_db_connection():
    """Создает подключение к БД с правильными настройками"""
    conn = sqlite3.connect('climate_repair.db', timeout=10)  # Увеличиваем таймаут
    conn.execute('PRAGMA journal_mode=WAL')  # Включаем WAL режим
    return conn