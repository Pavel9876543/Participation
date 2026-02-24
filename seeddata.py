"""
Seed-скрипт для начального заполнения базы данных.

Модель:
- порядок (position) — главный
- дата — производная от position
- сортировка при добавлении — по алфавиту
"""

import sqlite3
from datetime import date, timedelta

DB_NAME = "database.db"
START_DATE = date(2026, 3, 1)  # первое воскресенье


PEOPLE = [
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


def main():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Берём уже существующих людей
    cursor.execute("SELECT person FROM records")
    existing = {row[0] for row in cursor.fetchall()}

    # Сортируем алфавитно (как базовый порядок)
    sorted_people = sorted(PEOPLE, key=lambda x: x.lower())

    position = 0

    for person in sorted_people:
        if person in existing:
            continue

        person = person.strip()

        person_date = START_DATE + timedelta(days=7 * position)

        cursor.execute("""
            INSERT INTO records (position, date, person, status)
            VALUES (?, ?, ?, NULL)
        """, (position, person_date, person))

        position += 1

    conn.commit()
    conn.close()

    print("Seed-данные успешно добавлены.")


if __name__ == "__main__":
    main()
