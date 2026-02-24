from flask import Flask, render_template, request, jsonify, redirect
import sqlite3
from datetime import date, timedelta, datetime

app = Flask(__name__)

DB_NAME = "database.db"
SYSTEM_YEAR = 2026
BASE_DATE = date(2026, 3, 1)

# =====================================================
# DB
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
            date TEXT NOT NULL,
            person TEXT NOT NULL,
            status TEXT
        )
    """)
    conn.commit()
    conn.close()


init_db()


# =====================================================
# INDEX
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
    raw_rows = cur.fetchall()
    conn.close()

    rows = []
    for r in raw_rows:
        r = dict(r)
        # формат даты для отображения: dd.mm
        r["date_fmt"] = datetime.strptime(r["date"], "%Y-%m-%d").strftime("%d.%m")
        rows.append(r)

    return render_template("index.html", schedule=rows)


# =====================================================
# ADD
# Алфавит → position
# Сдвиг ТОЛЬКО дат
# =====================================================

@app.route("/add", methods=["POST"])
def add():
    person = request.form.get("person", "").strip()
    status = request.form.get("status") or None

    if not person:
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()

    # 1. Все записи в текущем порядке
    cur.execute("""
        SELECT id, person, status, date, position
        FROM records
        ORDER BY position
    """)
    rows = [dict(r) for r in cur.fetchall()]

    # 2. Только "подвижные" (НЕ +) — для алфавита
    movable = [
        r for r in rows
        if r["status"] != "+"
    ]

    # 3. Алфавитный список (виртуальный)
    alpha = sorted(
        movable + [{"person": person}],
        key=lambda r: r["person"].lower()
    )

    # 4. Кто перед новым в алфавите
    idx_alpha = next(
        i for i, r in enumerate(alpha)
        if r["person"].lower() == person.lower()
    )

    prev_person = alpha[idx_alpha - 1]["person"] if idx_alpha > 0 else None

    # 5. Реальный индекс вставки
    if prev_person is None:
        # перед всеми подвижными
        insert_index = min(
            (i for i, r in enumerate(rows) if r["status"] != "+"),
            default=len(rows)
        )
    else:
        # после алфавитного соседа
        insert_index = next(
            i for i, r in enumerate(rows)
            if r["person"] == prev_person
        ) + 1

    # 6. Дата нового
    if insert_index == 0:
        new_date = BASE_DATE
    else:
        prev_date = datetime.strptime(
            rows[insert_index - 1]["date"], "%Y-%m-%d"
        ).date()
        new_date = prev_date + timedelta(days=7)

    # 7. Сдвиг дат после
    for r in rows[insert_index:]:
        cur.execute(
            "UPDATE records SET date = date(date, '+7 days') WHERE id = ?",
            (r["id"],)
        )

    # 8. Сдвиг position
    cur.execute("""
        UPDATE records
        SET position = position + 1
        WHERE position >= ?
    """, (insert_index,))

    # 9. Вставка нового
    cur.execute("""
        INSERT INTO records (person, status, position, date)
        VALUES (?, ?, ?, ?)
    """, (
        person,
        status,
        insert_index,
        new_date.isoformat()
    ))

    conn.commit()
    conn.close()
    return redirect("/")

# =====================================================
# DELETE
# Сдвиг ТОЛЬКО дат
# =====================================================
@app.route("/delete", methods=["POST"])
def delete():
    record_id = request.json.get("id")

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT position FROM records WHERE id = ?",
        (record_id,)
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify(success=True)

    removed_position = row["position"]

    cur.execute("DELETE FROM records WHERE id = ?", (record_id,))

    # сдвиг дат вверх
    cur.execute("""
        UPDATE records
        SET date = date(date, '-7 days')
        WHERE position > ?
    """, (removed_position,))

    # сдвиг position
    cur.execute("""
        UPDATE records
        SET position = position - 1
        WHERE position > ?
    """, (removed_position,))

    conn.commit()
    conn.close()
    return jsonify(success=True)


# =====================================================
# MOVE
# swap соседей + swap дат
# =====================================================
@app.route("/move", methods=["POST"])
def move():
    record_id = request.json.get("id")
    direction = request.json.get("direction")  # up | down

    conn = get_db()
    cur = conn.cursor()

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

    neighbor_pos = cur_pos - 1 if direction == "up" else cur_pos + 1

    cur.execute(
        "SELECT id, position, date FROM records WHERE position = ?",
        (neighbor_pos,)
    )
    nb_row = cur.fetchone()
    if not nb_row:
        conn.close()
        return jsonify(success=True)

    # swap position + date
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

@app.route("/update-person", methods=["POST"])
def update_person():
    data = request.json
    conn = get_db()
    conn.execute(
        "UPDATE records SET person = ? WHERE id = ?",
        (data["person"], data["id"])
    )
    conn.commit()
    conn.close()
    return jsonify(success=True)


@app.route("/update-status", methods=["POST"])
def update_status():
    data = request.json
    conn = get_db()
    conn.execute(
        "UPDATE records SET status = ? WHERE id = ?",
        (data["status"] or None, data["id"])
    )
    conn.commit()
    conn.close()
    return jsonify(success=True)


@app.route("/update-date", methods=["POST"])
def update_date():
    data = request.json
    conn = get_db()
    conn.execute(
        "UPDATE records SET date = ? WHERE id = ?",
        (data["date"], data["id"])
    )
    conn.commit()
    conn.close()
    return jsonify(success=True)

# =====================================================
# RUN
# =====================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
