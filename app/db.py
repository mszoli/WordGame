import sqlite3
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "wordgame.db"
WORDLIST_DIR = Path(__file__).resolve().parent.parent / "wordlists"

SEED_CATEGORY_FILES = {
    "Fiú név": "fiu_nevek.txt",
    "Lány név": "lany_nevek.txt",
    "Ország": "orszagok.txt",
    "Magyar város/település": "magyar_varosok.txt",
    "Kémiai elemek": "kemiai_elemek.txt",
}


def _load_wordlist(filename: str) -> list[str]:
    path = WORDLIST_DIR / filename
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
                word TEXT NOT NULL,
                UNIQUE(category_id, word)
            )
            """
        )
        conn.commit()

        count = conn.execute("SELECT COUNT(*) AS c FROM categories").fetchone()["c"]
        if count == 0:
            for name, filename in SEED_CATEGORY_FILES.items():
                words = _load_wordlist(filename)
                cur = conn.execute("INSERT INTO categories (name) VALUES (?)", (name,))
                category_id = cur.lastrowid
                conn.executemany(
                    "INSERT OR IGNORE INTO words (category_id, word) VALUES (?, ?)",
                    [(category_id, w.upper()) for w in words],
                )
            conn.commit()
    finally:
        conn.close()


def list_categories() -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT c.id, c.name, COUNT(w.id) AS word_count
            FROM categories c
            LEFT JOIN words w ON w.category_id = c.id
            GROUP BY c.id
            ORDER BY c.name COLLATE NOCASE
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_category(category_id: int) -> Optional[dict]:
    conn = _connect()
    try:
        row = conn.execute("SELECT id, name FROM categories WHERE id = ?", (category_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_category(name: str) -> int:
    conn = _connect()
    try:
        cur = conn.execute("INSERT INTO categories (name) VALUES (?)", (name.strip(),))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def delete_category(category_id: int) -> None:
    conn = _connect()
    try:
        conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        conn.commit()
    finally:
        conn.close()


def add_words(category_id: int, words: list[str]) -> int:
    conn = _connect()
    try:
        cleaned = [w.strip().upper() for w in words if w.strip()]
        conn.executemany(
            "INSERT OR IGNORE INTO words (category_id, word) VALUES (?, ?)",
            [(category_id, w) for w in cleaned],
        )
        conn.commit()
        return len(cleaned)
    finally:
        conn.close()


def get_words(category_id: int) -> list[str]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT word FROM words WHERE category_id = ? ORDER BY word", (category_id,)
        ).fetchall()
        return [r["word"] for r in rows]
    finally:
        conn.close()


def get_word_set(category_id: int) -> set[str]:
    return set(get_words(category_id))
