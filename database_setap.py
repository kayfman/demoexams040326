import sqlite3
import csv
import os


def initialize_database():
    # Удаляем существующую БД для чистой инициализации
    if os.path.exists('climate_repair.db'):
        os.remove('climate_repair.db')
        print("Старая база данных удалена")

    conn = sqlite3.connect('climate_repair.db')
    cursor = conn.cursor()

    # Создаем таблицы с учетом структуры ваших данных
    cursor.execute('''CREATE TABLE roles
                      (
                          id   INTEGER PRIMARY KEY AUTOINCREMENT,
                          name VARCHAR(50) NOT NULL
                      )''')

    cursor.execute('''CREATE TABLE users
                      (
                          id        INTEGER PRIMARY KEY AUTOINCREMENT,
                          fio       VARCHAR(150) NOT NULL,
                          phone     VARCHAR(20),
                          login     VARCHAR(50) UNIQUE,
                          password  VARCHAR(50),
                          role_id   INTEGER      NOT NULL,
                          role_name VARCHAR(50),
                          FOREIGN KEY (role_id) REFERENCES roles (id)
                      )''')

    cursor.execute('''CREATE TABLE requests
                      (
                          id              INTEGER PRIMARY KEY AUTOINCREMENT,
                          start_date      DATE,
                          equipment_type  VARCHAR(100),
                          device_model    VARCHAR(100),
                          problem_desc    TEXT,
                          status          VARCHAR(50) DEFAULT 'Новая заявка',
                          completion_date DATE,
                          repair_parts    TEXT,
                          master_id       INTEGER,
                          client_id       INTEGER,
                          needs_help      INTEGER DEFAULT 0,
                          FOREIGN KEY (master_id) REFERENCES users (id),
                          FOREIGN KEY (client_id) REFERENCES users (id)
                      )''')

    cursor.execute('''CREATE TABLE comments
                      (
                          id           INTEGER PRIMARY KEY AUTOINCREMENT,
                          message      TEXT,
                          master_id    INTEGER,
                          request_id   INTEGER,
                          comment_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                          FOREIGN KEY (master_id) REFERENCES users (id),
                          FOREIGN KEY (request_id) REFERENCES requests (id)
                      )''')

    # Добавляем роли
    roles_data = [
        (1, 'Оператор'),
        (2, 'Специалист'),
        (3, 'Заказчик'),
        (4, 'Менеджер')
    ]
    cursor.executemany("INSERT INTO roles (id, name) VALUES (?, ?)", roles_data)
    print("Роли добавлены!")

    # Маппинг названий ролей на ID
    role_mapping = {
        'Менеджер': 4,
        'Специалист': 2,
        'Оператор': 1,
        'Заказчик': 3
    }

    # Импорт пользователей из CSV
    if os.path.exists('inputDataUsers.csv'):
        try:
            with open('inputDataUsers.csv', 'r', encoding='utf-8') as file:
                reader = csv.reader(file, delimiter=';')
                header = next(reader)  # Читаем заголовок
                print(f"Заголовок users: {header}")

                for row in reader:
                    if len(row) >= 6:
                        user_id, fio, phone, login, password, role_name = row
                        role_id = role_mapping.get(role_name, 3)  # По умолчанию Заказчик

                        cursor.execute(
                            "INSERT INTO users (id, fio, phone, login, password, role_id, role_name) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (user_id, fio, phone, login, password, role_id, role_name)
                        )
            print("Пользователи загружены из CSV!")
        except Exception as e:
            print(f"Ошибка при загрузке users CSV: {e}")

    # Импорт заявок из CSV
    if os.path.exists('inputDataRequests.csv'):
        try:
            with open('inputDataRequests.csv', 'r', encoding='utf-8') as file:
                reader = csv.reader(file, delimiter=';')
                header = next(reader)  # Читаем заголовок
                print(f"Заголовок requests: {header}")

                for row in reader:
                    if len(row) >= 10:
                        (req_id, start_date, eq_type, model, problem_desc,
                         status, completion_date, repair_parts, master_id, client_id) = row

                        # Преобразуем 'null' в None
                        completion_date = None if completion_date.lower() == 'null' else completion_date
                        repair_parts = None if repair_parts.lower() == 'null' else repair_parts
                        master_id = None if master_id.lower() == 'null' else int(master_id) if master_id else None
                        client_id = int(client_id) if client_id else None

                        cursor.execute('''INSERT INTO requests
                                          (id, start_date, equipment_type, device_model, problem_desc,
                                           status, completion_date, repair_parts, master_id, client_id, needs_help)
                                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)''',
                                       (req_id, start_date, eq_type, model, problem_desc,
                                        status, completion_date, repair_parts, master_id, client_id)
                                       )
            print("Заявки загружены из CSV!")
        except Exception as e:
            print(f"Ошибка при загрузке requests CSV: {e}")

    # Импорт комментариев из CSV
    if os.path.exists('inputDataComments.csv'):
        try:
            with open('inputDataComments.csv', 'r', encoding='utf-8') as file:
                reader = csv.reader(file, delimiter=';')
                header = next(reader)  # Читаем заголовок
                print(f"Заголовок comments: {header}")

                for row in reader:
                    if len(row) >= 4:
                        comment_id, message, master_id, request_id = row

                        cursor.execute('''INSERT INTO comments
                                              (id, message, master_id, request_id)
                                          VALUES (?, ?, ?, ?)''',
                                       (comment_id, message, master_id, request_id)
                                       )
            print("Комментарии загружены из CSV!")
        except Exception as e:
            print(f"Ошибка при загрузке comments CSV: {e}")

    conn.commit()

    # Проверяем, что данные добавились
    print("\n=== ПРОВЕРКА ДАННЫХ ===")

    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    print(f"Добавлено пользователей: {len(users)}")
    for user in users:
        print(f"ID: {user[0]}, ФИО: {user[1]}, Логин: {user[3]}, Роль: {user[6]}")

    cursor.execute("SELECT * FROM requests")
    requests = cursor.fetchall()
    print(f"\nДобавлено заявок: {len(requests)}")
    for req in requests:
        print(f"ID: {req[0]}, Статус: {req[5]}, Клиент: {req[9]}")

    cursor.execute("SELECT * FROM comments")
    comments = cursor.fetchall()
    print(f"\nДобавлено комментариев: {len(comments)}")

    conn.close()
    print("\nБаза данных успешно создана и заполнена!")

    # Выводим тестовые логины для входа
    print("\n=== ТЕСТОВЫЕ ДАННЫЕ ДЛЯ ВХОДА ===")
    print("Логин: login1, Пароль: pass1 (Менеджер)")
    print("Логин: login2, Пароль: pass2 (Специалист)")
    print("Логин: login4, Пароль: pass4 (Оператор)")
    print("Логин: login6, Пароль: pass6 (Заказчик)")


if __name__ == "__main__":
    initialize_database()