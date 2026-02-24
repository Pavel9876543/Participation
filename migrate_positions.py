import sqlite3

DB_PATH = "database.db"  # <-- если у тебя другое имя, поменяй

def migrate():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Берём записи В ТЕКУЩЕМ ПОРЯДКЕ
    cur.execute("""
        SELECT id, position
        FROM records
        ORDER BY position
    """)
    rows = cur.fetchall()

    print("До миграции:")
    for r in rows:
        print(f"id={r['id']} position={r['position']}")

    # Переписываем position как 0..N
    for new_pos, r in enumerate(rows):
        cur.execute(
            "UPDATE records SET position = ? WHERE id = ?",
            (new_pos, r["id"])
        )

    conn.commit()

    print("\nПосле миграции:")
    cur.execute("""
        SELECT id, position
        FROM records
        ORDER BY position
    """)
    for r in cur.fetchall():
        print(f"id={r['id']} position={r['position']}")

    conn.close()


if __name__ == "__main__":
    migrate()
