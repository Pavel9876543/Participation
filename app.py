from flask import Flask, render_template, request, jsonify, redirect
import sqlite3
from datetime import timedelta, datetime

app = Flask(__name__)

DB_NAME = "database.db"


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
# 🔥 ПРАВИЛЬНЫЙ ПЕРЕСЧЁТ
# =====================================================

def recalc_chain(conn):
    """
    база = минимальная дата среди status IS NULL
    остальные = +7 дней строго
    """
    cur = conn.cursor()

    cur.execute("""
        SELECT id, date
        FROM records
        WHERE status IS NULL
        ORDER BY position
    """)

    normals = cur.fetchall()

    if not normals:
        return

    # 🔥 база = самая ранняя дата
    base_date = min(
        datetime.strptime(r["date"], "%Y-%m-%d").date()
        for r in normals
    )

    # строгий пересчёт
    for i, r in enumerate(normals):
        new_date = base_date + timedelta(days=7 * i)

        cur.execute(
            "UPDATE records SET date=? WHERE id=?",
            (new_date.isoformat(), r["id"])
        )


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

    rows = []

    for r in cur.fetchall():
        r = dict(r)
        r["date_fmt"] = datetime.strptime(
            r["date"], "%Y-%m-%d"
        ).strftime("%d.%m")
        rows.append(r)

    conn.close()

    return render_template("index.html", schedule=rows)


# =====================================================
# ADD
# =====================================================

@app.route("/add", methods=["POST"])
def add():

    person = request.form.get("person", "").strip()
    status = request.form.get("status") or None

    if not person:
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM records")
    position = cur.fetchone()[0]

    temp_date = datetime.now().date().isoformat()

    cur.execute("""
        INSERT INTO records (person, status, position, date)
        VALUES (?, ?, ?, ?)
    """, (person, status, position, temp_date))

    recalc_chain(conn)

    conn.commit()
    conn.close()

    return redirect("/")


# =====================================================
# DELETE
# =====================================================

@app.route("/delete", methods=["POST"])
def delete():

    record_id = request.json.get("id")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT position FROM records WHERE id=?", (record_id,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return jsonify(success=True)

    pos = row["position"]

    cur.execute("DELETE FROM records WHERE id=?", (record_id,))

    cur.execute("""
        UPDATE records
        SET position=position-1
        WHERE position>?
    """, (pos,))

    recalc_chain(conn)

    conn.commit()
    conn.close()

    return jsonify(success=True)


# =====================================================
# MOVE
# =====================================================

@app.route("/move", methods=["POST"])
def move():

    record_id = request.json.get("id")
    direction = request.json.get("direction")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id, position FROM records WHERE id=?", (record_id,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return jsonify(success=True)

    pos = row["position"]
    neighbor_pos = pos - 1 if direction == "up" else pos + 1

    cur.execute("SELECT id FROM records WHERE position=?", (neighbor_pos,))
    nb = cur.fetchone()

    if not nb:
        conn.close()
        return jsonify(success=True)

    cur.execute("UPDATE records SET position=? WHERE id=?", (neighbor_pos, row["id"]))
    cur.execute("UPDATE records SET position=? WHERE id=?", (pos, nb["id"]))

    recalc_chain(conn)

    conn.commit()
    conn.close()

    return jsonify(success=True)


# =====================================================
# UPDATE PERSON
# =====================================================

@app.route("/update-person", methods=["POST"])
def update_person():

    data = request.json

    conn = get_db()

    conn.execute(
        "UPDATE records SET person=? WHERE id=?",
        (data["person"], data["id"])
    )

    conn.commit()
    conn.close()

    return jsonify(success=True)


# =====================================================
# UPDATE STATUS
# =====================================================

@app.route("/update-status", methods=["POST"])
def update_status():

    data = request.json
    status = data["status"] or None

    if status not in ("+", "-", None):
        return jsonify(success=False)

    conn = get_db()

    conn.execute(
        "UPDATE records SET status=? WHERE id=?",
        (status, data["id"])
    )

    recalc_chain(conn)

    conn.commit()
    conn.close()

    return jsonify(success=True)


# =====================================================
# UPDATE DATE
# =====================================================

@app.route("/update-date", methods=["POST"])
def update_date():

    data = request.json
    record_id = data["id"]

    new_date = datetime.strptime(data["date"], "%Y-%m-%d").date()

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT status FROM records WHERE id=?", (record_id,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return jsonify(success=False)

    # обновляем ВСЕГДА (и +, и -, и NULL)
    cur.execute(
        "UPDATE records SET date=? WHERE id=?",
        (new_date.isoformat(), record_id)
    )

    # пересчитываем только если это NULL
    if row["status"] is None:
        recalc_chain(conn)

    conn.commit()
    conn.close()

    return jsonify(success=True)


# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
