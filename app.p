from flask import Flask, render_template, request, jsonify, redirect
import sqlite3
from datetime import date

app = Flask(__name__)

DB_NAME = "database.db"
SYSTEM_YEAR = 2026


# =====================================================
# БАЗА ДАННЫХ
# =====================================================
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            position INTEGER NOT NULL,
            date DATE NOT NULL,
            person TEXT NOT NULL,
            status TEXT
        )
    """)

    conn.commit()
    conn.close()


init_db()


# =====================================================
# ГЛАВНАЯ СТРАНИЦА
# =====================================================
@app.route("/")
def index():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, position, date, person, status
        FROM records
        ORDER BY position
    """)

    records = cur.fetchall()
    conn.close()

    return render_template("index.html", schedule=records)


# =====================================================
# ДОБАВЛЕНИЕ (АЛФАВИТ БЕЗ ПЕРЕСОРТИРОВКИ)
# =====================================================
@app.route("/add", methods=["POST"])
def add():
    person = request.form.get("person", "").strip()
    status = request.form.get("status")

    if not person:
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()

    # все записи в текущем порядке
    cur.execute("""
        SELECT id, person, position
        FROM records
        ORDER BY position
    """)
    rows = cur.fetchall()

    # ищем алфавитную позицию
    insert_position = len(rows)
    for row in rows:
        if person.lower() < row["person"].lower():
            insert_position = row["position"]
            break

    # сдвигаем ТОЛЬКО position у нижних
    cur.execute("""
        UPDATE records
        SET position = position + 1
        WHERE position >= ?
    """, (insert_position,))

    # нейтральная дата — ни на что не влияет
    neutral_date = date(SYSTEM_YEAR, 1, 1)

    cur.execute("""
        INSERT INTO records (position, date, person, status)
        VALUES (?, ?, ?, ?)
    """, (insert_position, neutral_date, person, status))

    conn.commit()
    conn.close()

    return redirect("/")


# =====================================================
# УДАЛЕНИЕ
# =====================================================
@app.route("/delete", methods=["POST"])
def delete():
    record_id = request.json.get("id")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT position FROM records WHERE id = ?", (record_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify(success=True)

    removed_position = row["position"]

    cur.execute("DELETE FROM records WHERE id = ?", (record_id,))
    cur.execute("""
        UPDATE records
        SET position = position - 1
        WHERE position > ?
    """, (removed_position,))

    conn.commit()
    conn.close()

    return jsonify(success=True)


# =====================================================
# ПЕРЕМЕЩЕНИЕ (SWAP СОСЕДЕЙ + ОБМЕН ДАТ)
# =====================================================
@app.route("/move", methods=["POST"])
def move():
    record_id = request.json.get("id")
    direction = request.json.get("direction")  # up | down

    conn = get_db()
    cur = conn.cursor()

    # текущая запись
    cur.execute(
        "SELECT id, position, date FROM records WHERE id = ?",
        (record_id,)
    )
    cur_row = cur.fetchone()
    if not cur_row:
        conn.close()
        return jsonify(success=True)

    cur_pos = cur_row["position"]
    cur_date = cur_row["date"]

    # сосед
    neighbor_pos = cur_pos - 1 if direction == "up" else cur_pos + 1
    cur.execute(
        "SELECT id, position, date FROM records WHERE position = ?",
        (neighbor_pos,)
    )
    nb_row = cur.fetchone()
    if not nb_row:
        conn.close()
        return jsonify(success=True)

    # SWAP position + date
    cur.execute(
        "UPDATE records SET position = ?, date = ? WHERE id = ?",
        (nb_row["position"], nb_row["date"], cur_row["id"])
    )
    cur.execute(
        "UPDATE records SET position = ?, date = ? WHERE id = ?",
        (cur_pos, cur_date, nb_row["id"])
    )

    conn.commit()
    conn.close()

    return jsonify(success=True)


# =====================================================
# ЗАПУСК
# =====================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
