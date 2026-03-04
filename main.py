import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
from datetime import datetime
import qrcode
import os
import time
from functools import wraps


def get_db_connection():
    """Создает подключение к БД с правильными настройками"""
    conn = sqlite3.connect('climate_repair.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    return conn


def with_retry(func):
    """Декоратор для повторных попыток при блокировке БД"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except sqlite3.OperationalError as e:
                if 'database is locked' in str(e) and attempt < max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                else:
                    raise e

    return wrapper


class RepairApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Учет заявок - ООО Конди")
        self.geometry("900x500")

        style = ttk.Style(self)
        style.theme_use('clam')

        self.current_user_id = None
        self.current_user_role = None  # 1-Оператор, 2-Специалист, 3-Заказчик, 4-Менеджер
        self.current_user_name = None

        self.frames = {}
        for F in (LoginFrame, MainFrame, StatisticsFrame, NewRequestFrame):
            frame = F(self, self)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.show_frame(LoginFrame)

    def show_frame(self, frame_class):
        frame = self.frames[frame_class]
        frame.tkraise()
        if hasattr(frame, "update_data"):
            frame.update_data()


# ---------------- ЭКРАН АВТОРИЗАЦИИ ----------------
class LoginFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        ttk.Label(self, text="Авторизация", font=("Arial", 18, "bold")).pack(pady=40)

        ttk.Label(self, text="Логин:").pack()
        self.entry_login = ttk.Entry(self)
        self.entry_login.pack(pady=5)

        ttk.Label(self, text="Пароль:").pack()
        self.entry_password = ttk.Entry(self, show="*")
        self.entry_password.pack(pady=5)

        ttk.Button(self, text="Войти", command=self.login).pack(pady=20)

    def login(self):
        login = self.entry_login.get()
        password = self.entry_password.get()

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, role_id, fio FROM users WHERE login=? AND password=?", (login, password))
            user = cursor.fetchone()
            conn.close()

            if user:
                self.controller.current_user_id = user[0]
                self.controller.current_user_role = user[1]
                self.controller.current_user_name = user[2]
                self.controller.show_frame(MainFrame)
                self.entry_login.delete(0, tk.END)
                self.entry_password.delete(0, tk.END)
            else:
                messagebox.showerror("Ошибка", "Неверный логин или пароль!")
        except sqlite3.Error as e:
            messagebox.showerror("Ошибка БД", str(e))


# ---------------- ЭКРАН НОВОЙ ЗАЯВКИ ----------------
class NewRequestFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        ttk.Label(self, text="Создание новой заявки", font=("Arial", 16)).pack(pady=10)

        # Форма для новой заявки
        form_frame = ttk.Frame(self)
        form_frame.pack(pady=20, padx=50, fill="both", expand=True)

        # Тип оборудования
        ttk.Label(form_frame, text="Тип оборудования:").grid(row=0, column=0, sticky="w", pady=5)
        self.eq_type = ttk.Combobox(form_frame,
                                    values=["Кондиционер", "Увлажнитель воздуха", "Сушилка для рук", "Вентиляция",
                                            "Другое"], width=30)
        self.eq_type.grid(row=0, column=1, pady=5, padx=10)
        self.eq_type.set("Кондиционер")

        # Модель
        ttk.Label(form_frame, text="Модель устройства:").grid(row=1, column=0, sticky="w", pady=5)
        self.model = ttk.Entry(form_frame, width=33)
        self.model.grid(row=1, column=1, pady=5, padx=10)

        # Описание проблемы
        ttk.Label(form_frame, text="Описание проблемы:").grid(row=2, column=0, sticky="w", pady=5)
        self.problem_desc = tk.Text(form_frame, height=5, width=30)
        self.problem_desc.grid(row=2, column=1, pady=5, padx=10)

        # Кнопки
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=20)

        ttk.Button(btn_frame, text="Создать заявку", command=self.create_request).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Отмена", command=lambda: controller.show_frame(MainFrame)).pack(side="left", padx=5)

    @with_retry
    def create_request(self):
        # Проверка заполнения полей
        if not self.model.get().strip():
            messagebox.showwarning("Внимание", "Введите модель устройства")
            return

        if not self.problem_desc.get(1.0, tk.END).strip():
            messagebox.showwarning("Внимание", "Опишите проблему")
            return

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Получаем максимальный ID заявки
            cursor.execute("SELECT MAX(id) FROM requests")
            max_id = cursor.fetchone()[0]
            new_id = (max_id or 0) + 1

            # Текущая дата
            today = datetime.now().strftime("%Y-%m-%d")

            # Вставляем новую заявку
            cursor.execute("""
                INSERT INTO requests (id, start_date, equipment_type, device_model, problem_desc, 
                                    status, client_id, needs_help)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """, (new_id, today, self.eq_type.get(), self.model.get(),
                  self.problem_desc.get(1.0, tk.END).strip(), "Новая заявка",
                  self.controller.current_user_id))

            conn.commit()
            conn.close()

            messagebox.showinfo("Успех", f"Заявка №{new_id} успешно создана!")

            # Очищаем форму
            self.model.delete(0, tk.END)
            self.problem_desc.delete(1.0, tk.END)

            # Возвращаемся к списку заявок
            self.controller.show_frame(MainFrame)

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось создать заявку: {str(e)}")


# ---------------- ГЛАВНЫЙ ЭКРАН ----------------
class MainFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        top_frame = ttk.Frame(self)
        top_frame.pack(fill="x", padx=10, pady=10)

        # Приветствие с именем пользователя
        self.welcome_label = ttk.Label(top_frame, text="", font=("Arial", 12))
        self.welcome_label.pack(side="left")

        ttk.Label(top_frame, text="Список заявок", font=("Arial", 16)).pack(side="left", padx=(20, 0))

        # Поиск по номеру
        ttk.Label(top_frame, text="Поиск (№):").pack(side="left", padx=(20, 5))
        self.search_entry = ttk.Entry(top_frame, width=10)
        self.search_entry.pack(side="left")
        ttk.Button(top_frame, text="Найти", command=self.search_request).pack(side="left", padx=5)
        ttk.Button(top_frame, text="Сбросить", command=self.update_data).pack(side="left", padx=5)

        ttk.Button(top_frame, text="Выйти", command=self.logout).pack(side="right")
        ttk.Button(top_frame, text="QR Отзыв", command=self.generate_qr).pack(side="right", padx=5)
        ttk.Button(top_frame, text="Статистика", command=lambda: controller.show_frame(StatisticsFrame)).pack(
            side="right", padx=5)

        # Таблица
        columns = ("id", "date", "type", "model", "client", "status")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        self.tree.heading("id", text="№ Заявки")
        self.tree.heading("date", text="Дата")
        self.tree.heading("type", text="Тип")
        self.tree.heading("model", text="Модель")
        self.tree.heading("client", text="Заказчик")
        self.tree.heading("status", text="Статус")

        # Размеры колонок
        self.tree.column("id", width=60, anchor="center")
        self.tree.column("date", width=80, anchor="center")
        self.tree.column("type", width=120)
        self.tree.column("model", width=120)
        self.tree.column("client", width=150)
        self.tree.column("status", width=120, anchor="center")

        self.tree.pack(expand=True, fill="both", padx=10)

        # Кнопки действий
        action_frame = ttk.Frame(self)
        action_frame.pack(fill="x", padx=10, pady=10)

        self.btn_edit = ttk.Button(action_frame, text="Редактировать статус", command=self.edit_request)
        self.btn_edit.pack(side="left", padx=5)

        self.btn_help = ttk.Button(action_frame, text="Запросить помощь (Специалист)", command=self.ask_help)
        self.btn_help.pack(side="left", padx=5)

        self.btn_details = ttk.Button(action_frame, text="Детали заявки", command=self.show_request_details)
        self.btn_details.pack(side="left", padx=5)

        self.btn_new_request = ttk.Button(action_frame, text="Новая заявка", command=self.new_request)
        self.btn_new_request.pack(side="left", padx=5)

    def update_data(self, search_id=None):
        for row in self.tree.get_children():
            self.tree.delete(row)

        # Обновляем приветствие
        role_names = {1: "Оператор", 2: "Специалист", 3: "Заказчик", 4: "Менеджер"}
        role_name = role_names.get(self.controller.current_user_role, "Пользователь")
        self.welcome_label.config(text=f"{self.controller.current_user_name} ({role_name})    ")

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Базовый SQL запрос
            sql = """
                SELECT r.id,
                       r.start_date,
                       r.equipment_type,
                       r.device_model,
                       u.fio as client_name,
                       r.status
                FROM requests r
                LEFT JOIN users u ON r.client_id = u.id
            """

            params = []

            # Если пользователь - заказчик, показываем только его заявки
            if self.controller.current_user_role == 3:  # Заказчик
                sql += " WHERE r.client_id = ?"
                params.append(self.controller.current_user_id)

            # Если указан поиск по ID
            if search_id:
                if 'WHERE' in sql:
                    sql += " AND r.id = ?"
                else:
                    sql += " WHERE r.id = ?"
                params.append(search_id)

            sql += " ORDER BY r.id DESC"

            cursor.execute(sql, params)

            for row in cursor.fetchall():
                self.tree.insert("", tk.END, values=row)
            conn.close()

            # Настройка видимости кнопок в зависимости от роли
            role = self.controller.current_user_role

            # Кнопка помощи только для специалистов
            if role == 2:  # Специалист
                self.btn_help.state(['!disabled'])
            else:
                self.btn_help.state(['disabled'])

            # Кнопка новой заявки для всех, кроме заказчика?
            # Пока оставим для всех, но можно настроить
            if role == 3:  # Заказчик
                self.btn_new_request.state(['!disabled'])
                self.btn_edit.state(['disabled'])  # Заказчик не может менять статус
            else:
                self.btn_new_request.state(['!disabled'])
                self.btn_edit.state(['!disabled'])

        except sqlite3.Error as e:
            messagebox.showwarning("Ошибка", str(e))

    def search_request(self):
        req_id = self.search_entry.get()
        if req_id.isdigit():
            self.update_data(req_id)
        else:
            messagebox.showwarning("Внимание", "Введите числовой номер заявки")

    def logout(self):
        self.controller.current_user_id = None
        self.controller.current_user_role = None
        self.controller.current_user_name = None
        self.controller.show_frame(LoginFrame)

    @with_retry
    def edit_request(self):
        # Проверка прав: заказчик не может редактировать статус
        if self.controller.current_user_role == 3:
            messagebox.showinfo("Инфо", "Заказчик не может изменять статус заявки")
            return

        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Инфо", "Выберите заявку из списка")
            return

        req_id = self.tree.item(selected[0])['values'][0]

        # Диалог смены статуса
        new_status = simpledialog.askstring("Изменение статуса",
                                            "Введите новый статус:\n(В процессе ремонта, Ожидание комплектующих, Завершена, Готова к выдаче)",
                                            parent=self)
        if new_status:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                if new_status.lower() in ['завершена', 'готова к выдаче']:
                    today = datetime.now().strftime("%Y-%m-%d")
                    cursor.execute("UPDATE requests SET status=?, completion_date=? WHERE id=?",
                                   (new_status, today, req_id))
                else:
                    cursor.execute("UPDATE requests SET status=? WHERE id=?", (new_status, req_id))

                conn.commit()
                conn.close()
                self.update_data()
                messagebox.showinfo("Успех", "Статус успешно обновлен!")
            except sqlite3.Error as e:
                messagebox.showerror("Ошибка", str(e))

    @with_retry
    def ask_help(self):
        if self.controller.current_user_role != 2:
            messagebox.showinfo("Инфо", "Только специалист может запросить помощь")
            return

        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Инфо", "Выберите заявку из списка")
            return

        req_id = self.tree.item(selected[0])['values'][0]

        comment = simpledialog.askstring("Запрос помощи",
                                         "Опишите проблему, с которой нужна помощь:",
                                         parent=self)

        if comment:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                cursor.execute("""
                               INSERT INTO comments (message, master_id, request_id, comment_date)
                               VALUES (?, ?, ?, ?)
                               """, (f"ЗАПРОС ПОМОЩИ: {comment}",
                                     self.controller.current_user_id,
                                     req_id,
                                     datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

                cursor.execute("UPDATE requests SET needs_help=1 WHERE id=?", (req_id,))

                conn.commit()
                conn.close()
                messagebox.showinfo("Успех", "Запрос на помощь отправлен Менеджеру по качеству!")
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))

    @with_retry
    def show_request_details(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Инфо", "Выберите заявку из списка")
            return

        req_id = self.tree.item(selected[0])['values'][0]

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Получаем детальную информацию о заявке
            cursor.execute("""
                           SELECT r.*,
                                  client.fio   as client_fio,
                                  client.phone as client_phone,
                                  master.fio   as master_fio
                           FROM requests r
                                    LEFT JOIN users client ON r.client_id = client.id
                                    LEFT JOIN users master ON r.master_id = master.id
                           WHERE r.id = ?
                           """, (req_id,))

            req = cursor.fetchone()

            # Получаем комментарии к заявке
            cursor.execute("""
                           SELECT c.*, u.fio
                           FROM comments c
                                    LEFT JOIN users u ON c.master_id = u.id
                           WHERE c.request_id = ?
                           ORDER BY c.comment_date
                           """, (req_id,))

            comments = cursor.fetchall()
            conn.close()

            if req:
                # Создаем окно с деталями
                details_window = tk.Toplevel(self)
                details_window.title(f"Детали заявки №{req_id}")
                details_window.geometry("600x500")

                # Добавляем скроллбар
                frame = ttk.Frame(details_window)
                frame.pack(expand=True, fill="both")

                text = tk.Text(frame, wrap=tk.WORD, padx=10, pady=10)
                scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
                text.configure(yscrollcommand=scrollbar.set)

                text.pack(side="left", expand=True, fill="both")
                scrollbar.pack(side="right", fill="y")

                # Формируем текст с деталями
                detail_text = f"ЗАЯВКА №{req[0]}\n"
                detail_text += f"{'=' * 50}\n\n"
                detail_text += f"Дата создания: {req[1]}\n"
                detail_text += f"Тип оборудования: {req[2]}\n"
                detail_text += f"Модель: {req[3]}\n"
                detail_text += f"Описание проблемы: {req[4]}\n"
                detail_text += f"Статус: {req[5]}\n"
                detail_text += f"Дата завершения: {req[6] if req[6] else 'Не завершена'}\n"
                detail_text += f"Запчасти: {req[7] if req[7] else 'Не указаны'}\n\n"

                detail_text += f"Клиент: {req[10] if len(req) > 10 else 'Не указан'}\n"
                detail_text += f"Телефон клиента: {req[11] if len(req) > 11 else 'Не указан'}\n"
                detail_text += f"Мастер: {req[12] if len(req) > 12 and req[12] else 'Не назначен'}\n\n"

                detail_text += "КОММЕНТАРИИ:\n"
                detail_text += f"{'=' * 50}\n"

                if comments:
                    for comment in comments:
                        detail_text += f"\n{comment[4] if len(comment) > 4 else 'Дата не указана'}: {comment[1]}"
                        if len(comment) > 5 and comment[5]:
                            detail_text += f" (автор: {comment[5]})"
                else:
                    detail_text += "\nНет комментариев"

                text.insert(tk.END, detail_text)
                text.config(state="disabled")

        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def new_request(self):
        self.controller.show_frame(NewRequestFrame)

    def generate_qr(self):
        # Генерация QR кода для отзыва по ссылке из Прил_3
        link = "https://docs.google.com/forms/d/e/1FAIpQLSdhZcExx6LSIXxk0ub55mSu-WIh23WYdGG9HY5EZhLDo7P8eA/viewform?usp=sf_link"
        try:
            img = qrcode.make(link)
            img.save("feedback_qr.png")
            os.startfile("feedback_qr.png")  # Откроет картинку стандартным средством Windows
            messagebox.showinfo("Успех", "QR-код создан и открыт!")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось создать QR код. Проверьте установку qrcode.\n{e}")


# ---------------- ЭКРАН СТАТИСТИКИ ----------------
class StatisticsFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        ttk.Label(self, text="Статистика работы", font=("Arial", 16)).pack(pady=10)

        # Создаем фрейм для текста с прокруткой
        text_frame = ttk.Frame(self)
        text_frame.pack(expand=True, fill="both", padx=20, pady=10)

        self.text_result = tk.Text(text_frame, height=15, width=70, state="disabled", wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.text_result.yview)
        self.text_result.configure(yscrollcommand=scrollbar.set)

        self.text_result.pack(side="left", expand=True, fill="both")
        scrollbar.pack(side="right", fill="y")

        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Обновить статистику", command=self.calculate).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Назад", command=lambda: controller.show_frame(MainFrame)).pack(side="left", padx=5)

    @with_retry
    def calculate(self):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                           SELECT equipment_type, status, start_date, completion_date
                           FROM requests
                           """)
            records = cursor.fetchall()
            conn.close()

            completed_count = 0
            total_days = 0
            fault_stats = {}
            status_stats = {}
            total_requests = len(records)

            for rec in records:
                eq_type, status, start, end = rec

                # Статистика по типам оборудования
                fault_stats[eq_type] = fault_stats.get(eq_type, 0) + 1

                # Статистика по статусам
                status_stats[status] = status_stats.get(status, 0) + 1

                # Расчет среднего времени для завершенных заявок
                if status.lower() in ['завершена', 'готова к выдаче'] and end and end != 'null':
                    completed_count += 1
                    try:
                        date_format = "%Y-%m-%d"
                        d1 = datetime.strptime(start, date_format)
                        d2 = datetime.strptime(end, date_format)
                        total_days += (d2 - d1).days
                    except (ValueError, TypeError):
                        pass

            avg_time = (total_days / completed_count) if completed_count > 0 else 0

            self.text_result.config(state="normal")
            self.text_result.delete(1.0, tk.END)

            res = "=== СТАТИСТИКА РАБОТЫ ===\n\n"
            res += f"Всего заявок: {total_requests}\n"
            res += f"Выполненных заявок: {completed_count}\n"
            res += f"Среднее время выполнения (дней): {avg_time:.1f}\n\n"

            res += "Статистика по статусам:\n"
            for status, count in status_stats.items():
                res += f" • {status}: {count} шт. ({count / total_requests * 100:.1f}%)\n"

            res += "\nКоличество заявок по типам оборудования:\n"
            for eq_type, count in fault_stats.items():
                res += f" • {eq_type}: {count} шт. ({count / total_requests * 100:.1f}%)\n"

            self.text_result.insert(tk.END, res)
            self.text_result.config(state="disabled")

        except Exception as e:
            messagebox.showerror("Ошибка", str(e))


if __name__ == "__main__":
    app = RepairApp()
    app.mainloop()