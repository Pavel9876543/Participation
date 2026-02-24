"""
Инициализация базы данных SQLite.
Создаёт таблицу people и заполняет её списком.
"""

import sqlite3

people = [
    "Бобровников Вениамин",
    "Бобровников Павел",
    "Бобровникова Вера",
    "Бобровникова Нелли",
    "Бородин Александр",
    "Бородин Максим",
    "Бородин Никита",
    "Бородина Лидия",
    "Бородина Вера",
    "Бородина Лилия",
    "Гусев Павел",
    "Гусев Роман",
    "Гусев Тимур",
    "Гусева Анна",
    "Кийко Эвелина",
    "Кийко Кирилл",
    "Кургузова Татьяна",
    "Литвиненко София",
    "Мануковский Давид",
    "Мишайкина Оля",
    "Мишайкина Людмила",
    "Морозов Павел",
    "Моргунов Владимир",
    "Наприенко Ева",
    "Полухина Лина",
    "Рудаков Михаил",
    "Шестакова Мария",
    "Щирская Анна",
    "Щирская Татьяна",
    "Шмарикова Катя",
]

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL
)
""")

cursor.execute("DELETE FROM people")

for person in sorted(people):
    cursor.execute(
        "INSERT INTO people (full_name) VALUES (?)",
        (person,)
    )

conn.commit()
conn.close()

print("База данных создана и заполнена.")
