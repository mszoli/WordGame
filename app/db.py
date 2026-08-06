import sqlite3
from pathlib import Path
from typing import Optional

from app.letters import hungarian_sort_key

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "wordgame.db"
WORDLIST_DIR = Path(__file__).resolve().parent.parent / "wordlists"

SEED_CATEGORY_FILES = {
    "Magyar anyakönyvezhető lánynevek": "lany_nevek.txt",
    "Kémiai elemek": "kemiai_elemek.txt",
    "Olimpiai sportágak (2024 nyár vagy 2026 tél)": "olimpiai_sportok.txt",
    "Brawl Stars karakterek": "brawl_stars_karakterek.txt",
    "ENSZ tagállamok (országok)": "ensz_tagallamok.txt",
    "Magyar oktatásban tanulható klasszikus zenei hangszerek": "hangszerek.txt",
}


def _load_wordlist(filename: str) -> list[str]:
    path = WORDLIST_DIR / filename
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def _hungarian_collation(a: str, b: str) -> int:
    ka, kb = hungarian_sort_key(a), hungarian_sort_key(b)
    return -1 if ka < kb else (1 if ka > kb else 0)


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.create_collation("HUNGARIAN", _hungarian_collation)
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

        existing = {
            row["name"]: row["id"] for row in conn.execute("SELECT id, name FROM categories").fetchall()
        }
        # korabbi/mar nem hasznalt kategorianevek eltavolitasa (a hozzajuk tartozo
        # szavak is torlodnek a CASCADE miatt), hogy a kategorialista mindig
        # pontosan a SEED_CATEGORY_FILES-ban rogzitett vegleges listat tukrozze
        for name, category_id in list(existing.items()):
            if name not in SEED_CATEGORY_FILES:
                conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
                del existing[name]
        conn.commit()

        # minden kategoria szolistaja mindig a hozza tartozo txt fajl aktualis
        # tartalmat tukrozi, ugy hogy egy tartalomfrissites (txt fajl szerkesztese)
        # egyszeru git pull + szerver-ujrainditas utan azonnal ervenybe lep
        for name, filename in SEED_CATEGORY_FILES.items():
            words = [w.strip().upper() for w in _load_wordlist(filename) if w.strip()]
            if name in existing:
                category_id = existing[name]
            else:
                cur = conn.execute("INSERT INTO categories (name) VALUES (?)", (name,))
                category_id = cur.lastrowid
            conn.execute("DELETE FROM words WHERE category_id = ?", (category_id,))
            conn.executemany(
                "INSERT OR IGNORE INTO words (category_id, word) VALUES (?, ?)",
                [(category_id, w) for w in words],
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
            ORDER BY c.name COLLATE HUNGARIAN
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
            "SELECT word FROM words WHERE category_id = ? ORDER BY word COLLATE HUNGARIAN", (category_id,)
        ).fetchall()
        return [r["word"] for r in rows]
    finally:
        conn.close()


def get_word_set(category_id: int) -> set[str]:
    return set(get_words(category_id))
