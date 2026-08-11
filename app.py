from flask import Flask, render_template, request, jsonify, redirect
import sqlite3
from datetime import timedelta, datetime
from contextlib import contextmanager

app = Flask(__name__)

DB_NAME = "database.db"
DB_TIMEOUT = 5


# =====================================================
# DB
# =====================================================

def get_db():
    conn = sqlite3.connect(DB_NAME, timeout=DB_TIMEOUT)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


@contextmanager
def db_transaction():
    conn = get_db()

    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def db_error_response():
    return jsonify(success=False, error="Ошибка базы данных. Изменения не сохранены, повторите операцию.")


def init_db():
    conn = get_db()
    try:
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
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


init_db()


def is_without_status(row):
    return row["status"] not in ("+", "-")


def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def person_sort_key(person):
    return " ".join(person.split()).casefold()


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


def find_alpha_insert_index(rows, person):
    new_key = person_sort_key(person)

    for index, row in enumerate(rows):
        if new_key < person_sort_key(row["person"]):
            return index

    return len(rows)


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


def apply_without_status_order(conn, ordered_ids):
    status_count = conn.execute("""
        SELECT COUNT(*)
        FROM records
        WHERE status IN ('+', '-')
    """).fetchone()[0]

    for index, record_id in enumerate(ordered_ids):
        conn.execute(
            "UPDATE records SET position=? WHERE id=?",
            (status_count + index, record_id)
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


def update_person_in_conn(conn, record_id, person):
    conn.execute(
        "UPDATE records SET person=? WHERE id=?",
        (person, record_id)
    )


def update_status_in_conn(conn, record_id, status):
    cur = conn.cursor()

    cur.execute("SELECT position, date, status FROM records WHERE id=?", (record_id,))
    row = cur.fetchone()

    if not row:
        return False

    old_without_status = is_without_status(row)
    new_without_status = status is None
    removed_position = row["position"]
    removed_date = parse_date(row["date"])

    cur.execute(
        "UPDATE records SET status=? WHERE id=?",
        (status, record_id)
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
            (cur.fetchone()[0], record_id)
        )
        recalc_without_status_dates(conn)
    elif old_without_status and new_without_status:
        recalc_without_status_dates(conn)

    normalize_positions(conn)
    return True


def update_base_date_in_conn(conn, record_id, new_date):
    cur = conn.cursor()

    cur.execute("SELECT id, status FROM records WHERE id=?", (record_id,))
    row = cur.fetchone()

    if not row:
        return False

    base_row = get_base_without_status_row(conn)

    if not base_row or row["id"] != base_row["id"] or not is_without_status(row):
        return False

    cur.execute(
        "UPDATE records SET date=? WHERE id=?",
        (new_date.isoformat(), record_id)
    )

    recalc_without_status_dates(conn, new_date)
    normalize_positions(conn)
    return True


def move_without_status_to_target(conn, record_id, target):
    rows = get_without_status_rows(conn)
    row_index = next((i for i, row in enumerate(rows) if row["id"] == record_id), None)

    if row_index is None:
        return False

    base_date = parse_date(rows[0]["date"])
    ordered_ids = [row["id"] for row in rows]
    moved_id = ordered_ids.pop(row_index)

    if target == "start":
        ordered_ids.insert(0, moved_id)
    elif target == "end":
        ordered_ids.append(moved_id)
    else:
        return False

    apply_without_status_order(conn, ordered_ids)
    recalc_without_status_dates(conn, base_date)
    normalize_without_status_positions(conn)
    return True


# =====================================================
# INDEX
# =====================================================

@app.route("/")
def index():

    try:
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
    except sqlite3.Error:
        rows = []
    finally:
        if "conn" in locals():
            conn.close()

    return render_template("index.html", schedule=rows)


# =====================================================
# ADD
# =====================================================

@app.route("/add", methods=["POST"])
def add():

    person = request.form.get("person", "").strip()

    if not person:
        return redirect("/")

    try:
        with db_transaction() as conn:
            cur = conn.cursor()
            rows = get_without_status_rows(conn)
            insert_index = find_alpha_insert_index(rows, person)
            base_date = parse_date(rows[0]["date"]) if rows else datetime.now().date()

            cur.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM records")
            position = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO records (person, status, position, date)
                VALUES (?, NULL, ?, ?)
            """, (person, position, base_date.isoformat()))

            new_id = cur.lastrowid
            ordered_ids = [row["id"] for row in rows]
            ordered_ids.insert(insert_index, new_id)

            apply_without_status_order(conn, ordered_ids)
            recalc_without_status_dates(conn, base_date)
            normalize_positions(conn)
    except sqlite3.Error:
        return redirect("/?error=db")

    return redirect("/")


# =====================================================
# DELETE
# =====================================================

@app.route("/delete", methods=["POST"])
def delete():

    record_id = request.json.get("id")

    try:
        with db_transaction() as conn:
            cur = conn.cursor()

            cur.execute("SELECT position, date, status FROM records WHERE id=?", (record_id,))
            row = cur.fetchone()

            if not row:
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
    except sqlite3.Error:
        return db_error_response()

    return jsonify(success=True)


# =====================================================
# MOVE
# =====================================================

@app.route("/move", methods=["POST"])
def move():

    record_id = request.json.get("id")
    direction = request.json.get("direction")
    target = request.json.get("target")

    try:
        with db_transaction() as conn:
            cur = conn.cursor()

            cur.execute("SELECT id, position, status FROM records WHERE id=?", (record_id,))
            row = cur.fetchone()

            if not row or not is_without_status(row):
                return jsonify(success=True)

            rows = get_without_status_rows(conn)
            row_index = next((i for i, item in enumerate(rows) if item["id"] == row["id"]), None)

            if row_index is None:
                return jsonify(success=True)

            if target in ("start", "end"):
                move_without_status_to_target(conn, row["id"], target)
                return jsonify(success=True)

            neighbor_index = row_index - 1 if direction == "up" else row_index + 1

            if neighbor_index < 0 or neighbor_index >= len(rows):
                return jsonify(success=True)

            base_date = parse_date(rows[0]["date"])
            neighbor = rows[neighbor_index]

            cur.execute("UPDATE records SET position=? WHERE id=?", (neighbor["position"], row["id"]))
            cur.execute("UPDATE records SET position=? WHERE id=?", (row["position"], neighbor["id"]))

            recalc_without_status_dates(conn, base_date)
            normalize_without_status_positions(conn)
    except sqlite3.Error:
        return db_error_response()

    return jsonify(success=True)


# =====================================================
# UPDATE PERSON
# =====================================================

@app.route("/update-person", methods=["POST"])
def update_person():

    data = request.json

    try:
        with db_transaction() as conn:
            update_person_in_conn(conn, data["id"], data["person"])
    except sqlite3.Error:
        return db_error_response()

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

    try:
        with db_transaction() as conn:
            if not update_status_in_conn(conn, data["id"], status):
                return jsonify(success=False)
    except sqlite3.Error:
        return db_error_response()

    return jsonify(success=True)


# =====================================================
# UPDATE DATE
# =====================================================

@app.route("/update-date", methods=["POST"])
def update_date():

    data = request.json
    record_id = data["id"]

    try:
        new_date = datetime.strptime(data["date"], "%Y-%m-%d").date()
    except ValueError:
        return jsonify(success=False, error="Некорректная дата.")

    try:
        with db_transaction() as conn:
            if not update_base_date_in_conn(conn, record_id, new_date):
                return jsonify(success=False)
    except sqlite3.Error:
        return db_error_response()

    return jsonify(success=True)


# =====================================================
# UPDATE RECORD
# =====================================================

@app.route("/update-record", methods=["POST"])
def update_record():

    data = request.json
    record_id = data["id"]
    person = data.get("person", "").strip()
    status = data.get("status") or None
    date = data.get("date")

    if not person or status not in ("+", "-", None):
        return jsonify(success=False)

    try:
        new_date = datetime.strptime(date, "%Y-%m-%d").date() if date else None
    except ValueError:
        return jsonify(success=False, error="Некорректная дата.")

    try:
        with db_transaction() as conn:
            update_person_in_conn(conn, record_id, person)

            if status is None and new_date is not None:
                if not update_base_date_in_conn(conn, record_id, new_date):
                    return jsonify(success=False)

            if not update_status_in_conn(conn, record_id, status):
                return jsonify(success=False)
    except sqlite3.Error:
        return db_error_response()

    return jsonify(success=True)


# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
