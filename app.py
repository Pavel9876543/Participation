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


def is_without_status(row):
    return row["status"] not in ("+", "-")


def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def get_without_status_rows(conn):
    return conn.execute("""
        SELECT id, position, date, person, status
        FROM records
        WHERE status IS NULL OR status = ''
        ORDER BY position, id
    """).fetchall()


def get_base_without_status_row(conn):
    rows = get_without_status_rows(conn)
    return rows[0] if rows else None


def recalc_without_status_dates(conn, base_date=None):
    rows = get_without_status_rows(conn)

    if not rows:
        return

    if base_date is None:
        base_date = parse_date(rows[0]["date"])

    for index, row in enumerate(rows):
        new_date = base_date + timedelta(days=7 * index)
        conn.execute(
            "UPDATE records SET date=? WHERE id=?",
            (new_date.isoformat(), row["id"])
        )


def normalize_positions(conn):
    rows = conn.execute("""
        SELECT id
        FROM records
        ORDER BY
            CASE WHEN status IN ('+', '-') THEN 0 ELSE 1 END,
            date ASC,
            position ASC,
            id ASC
    """).fetchall()

    for position, row in enumerate(rows):
        conn.execute(
            "UPDATE records SET position=? WHERE id=?",
            (position, row["id"])
        )


def normalize_without_status_positions(conn):
    status_rows = conn.execute("""
        SELECT id
        FROM records
        WHERE status IN ('+', '-')
        ORDER BY date ASC, position ASC, id ASC
    """).fetchall()

    without_status_rows = get_without_status_rows(conn)
    ordered_rows = list(status_rows) + list(without_status_rows)

    for position, row in enumerate(ordered_rows):
        conn.execute(
            "UPDATE records SET position=? WHERE id=?",
            (position, row["id"])
        )


def cascade_without_status_after_removal(conn, removed_position, removed_date):
    rows = get_without_status_rows(conn)

    for row in rows:
        if row["position"] < removed_position:
            continue

        steps = row["position"] - removed_position
        new_date = removed_date + timedelta(days=7 * steps)
        conn.execute(
            "UPDATE records SET date=? WHERE id=?",
            (new_date.isoformat(), row["id"])
        )


# =====================================================
# INDEX
# =====================================================

@app.route("/")
def index():

    conn = get_db()
    cur = conn.cursor()

    base_row = get_base_without_status_row(conn)
    base_id = base_row["id"] if base_row else None

    cur.execute("""
        SELECT id, position, date, person, status
        FROM records
        ORDER BY
            CASE WHEN status IN ('+', '-') THEN 0 ELSE 1 END,
            date ASC,
            position ASC,
            id ASC
    """)

    rows = []

    for r in cur.fetchall():
        r = dict(r)
        r["date_fmt"] = datetime.strptime(
            r["date"], "%Y-%m-%d"
        ).strftime("%d.%m")
        r["without_status"] = r["status"] not in ("+", "-")
        r["can_edit_date"] = r["id"] == base_id
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

    if status is None:
        recalc_without_status_dates(conn)

    normalize_positions(conn)

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

    cur.execute("SELECT position, date, status FROM records WHERE id=?", (record_id,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return jsonify(success=True)

    pos = row["position"]
    removed_date = parse_date(row["date"])
    without_status = is_without_status(row)

    cur.execute("DELETE FROM records WHERE id=?", (record_id,))

    cur.execute("""
        UPDATE records
        SET position=position-1
        WHERE position>?
    """, (pos,))

    if without_status:
        cascade_without_status_after_removal(conn, pos, removed_date)

    normalize_positions(conn)

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

    cur.execute("SELECT id, position, status FROM records WHERE id=?", (record_id,))
    row = cur.fetchone()

    if not row or not is_without_status(row):
        conn.close()
        return jsonify(success=True)

    rows = get_without_status_rows(conn)
    row_index = next((i for i, item in enumerate(rows) if item["id"] == row["id"]), None)

    if row_index is None:
        conn.close()
        return jsonify(success=True)

    neighbor_index = row_index - 1 if direction == "up" else row_index + 1

    if neighbor_index < 0 or neighbor_index >= len(rows):
        conn.close()
        return jsonify(success=True)

    base_date = parse_date(rows[0]["date"])
    neighbor = rows[neighbor_index]

    cur.execute("UPDATE records SET position=? WHERE id=?", (neighbor["position"], row["id"]))
    cur.execute("UPDATE records SET position=? WHERE id=?", (row["position"], neighbor["id"]))

    recalc_without_status_dates(conn, base_date)
    normalize_without_status_positions(conn)

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
    cur = conn.cursor()

    cur.execute("SELECT position, date, status FROM records WHERE id=?", (data["id"],))
    row = cur.fetchone()

    if not row:
        conn.close()
        return jsonify(success=False)

    old_without_status = is_without_status(row)
    new_without_status = status is None
    removed_position = row["position"]
    removed_date = parse_date(row["date"])

    cur.execute(
        "UPDATE records SET status=? WHERE id=?",
        (status, data["id"])
    )

    if old_without_status and not new_without_status:
        cur.execute("""
            UPDATE records
            SET position=position-1
            WHERE position>?
        """, (removed_position,))
        cascade_without_status_after_removal(conn, removed_position, removed_date)
    elif not old_without_status and new_without_status:
        cur.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM records")
        cur.execute(
            "UPDATE records SET position=? WHERE id=?",
            (cur.fetchone()[0], data["id"])
        )
        recalc_without_status_dates(conn)
    elif old_without_status and new_without_status:
        recalc_without_status_dates(conn)

    normalize_positions(conn)

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

    cur.execute("SELECT id, status FROM records WHERE id=?", (record_id,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return jsonify(success=False)

    base_row = get_base_without_status_row(conn)

    if not base_row or row["id"] != base_row["id"] or not is_without_status(row):
        conn.close()
        return jsonify(success=False)

    cur.execute(
        "UPDATE records SET date=? WHERE id=?",
        (new_date.isoformat(), record_id)
    )

    recalc_without_status_dates(conn, new_date)
    normalize_positions(conn)

    conn.commit()
    conn.close()

    return jsonify(success=True)


# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
