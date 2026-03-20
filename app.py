from flask import Flask, render_template, request, jsonify, redirect
import sqlite3
from datetime import date, timedelta, datetime

app = Flask(__name__)

DB_NAME = "database.db"
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
# HELPERS
# =====================================================

def get_last_plus_date(rows):
    plus_dates = [
        datetime.strptime(r["date"], "%Y-%m-%d").date()
        for r in rows if r["status"] == "+"
    ]
    return max(plus_dates) if plus_dates else None


def recalc_chain(conn):
    """
    Пересчёт всей второй категории
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

    base_date = datetime.strptime(normals[0]["date"], "%Y-%m-%d").date()

    current = base_date

    for r in normals[1:]:
        current += timedelta(days=7)

        cur.execute(
            "UPDATE records SET date=? WHERE id=?",
            (current.isoformat(), r["id"])
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

    raw_rows = cur.fetchall()

    conn.close()

    rows = []

    for r in raw_rows:
        r = dict(r)

        r["date_fmt"] = datetime.strptime(
            r["date"], "%Y-%m-%d"
        ).strftime("%d.%m")

        rows.append(r)

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

    cur.execute("""
        SELECT *
        FROM records
        ORDER BY position
    """)

    rows = [dict(r) for r in cur.fetchall()]

    # ----------------------------
    # Плюсы
    # ----------------------------

    if status == "+":

        pos = len(rows)

        cur.execute("""
            INSERT INTO records (person,status,position,date)
            VALUES (?,?,?,?)
        """, (person, "+", pos, BASE_DATE.isoformat()))

        conn.commit()
        conn.close()

        return redirect("/")

    # ----------------------------
    # Вторая категория
    # ----------------------------

    normals = [r for r in rows if r["status"] != "+"]

    alpha = sorted(
        normals + [{"person": person}],
        key=lambda r: r["person"].lower()
    )

    idx = next(
        i for i, r in enumerate(alpha)
        if r["person"].lower() == person.lower()
    )

    prev_person = alpha[idx - 1]["person"] if idx > 0 else None

    if prev_person is None:

        insert_index = min(
            (i for i, r in enumerate(rows) if r["status"] != "+"),
            default=len(rows)
        )

    else:

        insert_index = next(
            i for i, r in enumerate(rows)
            if r["person"] == prev_person
        ) + 1

    # дата

    if insert_index == 0 or rows[insert_index - 1]["status"] == "+":

        first_normal = next(
            (r for r in rows if r["status"] != "+"),
            None
        )

        if first_normal:

            new_date = datetime.strptime(
                first_normal["date"], "%Y-%m-%d"
            ).date()

        else:

            last_plus = get_last_plus_date(rows)

            new_date = (
                last_plus + timedelta(days=7)
                if last_plus else BASE_DATE
            )

    else:

        prev_date = datetime.strptime(
            rows[insert_index - 1]["date"], "%Y-%m-%d"
        ).date()

        new_date = prev_date + timedelta(days=7)

    # сдвиг дат

    for r in rows[insert_index:]:
        if r["status"] != "+":
            cur.execute(
                "UPDATE records SET date=date(date,'+7 day') WHERE id=?",
                (r["id"],)
            )

    # сдвиг позиции

    cur.execute("""
        UPDATE records
        SET position=position+1
        WHERE position>=?
    """, (insert_index,))

    # вставка

    cur.execute("""
        INSERT INTO records (person,status,position,date)
        VALUES (?,?,?,?)
    """, (person, None, insert_index, new_date.isoformat()))

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

    cur.execute(
        "SELECT position,status FROM records WHERE id=?",
        (record_id,)
    )

    row = cur.fetchone()

    if not row:
        conn.close()
        return jsonify(success=True)

    pos = row["position"]
    status = row["status"]

    cur.execute("DELETE FROM records WHERE id=?", (record_id,))

    if status != "+":

        cur.execute("""
            UPDATE records
            SET date=date(date,'-7 day')
            WHERE position>? AND status IS NULL
        """, (pos,))

    cur.execute("""
        UPDATE records
        SET position=position-1
        WHERE position>?
    """, (pos,))

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

    cur.execute(
        "SELECT id,position,date FROM records WHERE id=?",
        (record_id,)
    )

    row = cur.fetchone()

    if not row:
        conn.close()
        return jsonify(success=True)

    pos = row["position"]
    date_val = row["date"]

    neighbor = pos - 1 if direction == "up" else pos + 1

    cur.execute(
        "SELECT id,position,date FROM records WHERE position=?",
        (neighbor,)
    )

    nb = cur.fetchone()

    if not nb:
        conn.close()
        return jsonify(success=True)

    cur.execute(
        "UPDATE records SET position=?,date=? WHERE id=?",
        (nb["position"], nb["date"], row["id"])
    )

    cur.execute(
        "UPDATE records SET position=?,date=? WHERE id=?",
        (pos, date_val, nb["id"])
    )

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

    conn = get_db()

    conn.execute(
        "UPDATE records SET status=? WHERE id=?",
        (data["status"] or None, data["id"])
    )

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

    cur.execute("""
        SELECT *
        FROM records
        ORDER BY position
    """)

    rows = [dict(r) for r in cur.fetchall()]

    normals = [r for r in rows if r["status"] != "+"]

    last_plus = get_last_plus_date(rows)

    if last_plus and new_date <= last_plus:
        conn.close()
        return jsonify(success=False)

    cur.execute(
        "UPDATE records SET date=? WHERE id=?",
        (new_date.isoformat(), record_id)
    )

    recalc_chain(conn)

    conn.commit()
    conn.close()

    return jsonify(success=True)


# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
