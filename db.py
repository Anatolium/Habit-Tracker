import sqlite3
from config import DB_NAME


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # Включаем поддержку внешних ключей
    cur.execute("PRAGMA foreign_keys = ON")

    cur.execute('''
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY,
            active BOOLEAN NOT NULL DEFAULT 1,
            creation_date DATE
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS habit (
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            name TEXT NOT NULL,
            description TEXT
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS user_habit (
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            user_id INTEGER,
            habit_id INTEGER,
            active BOOLEAN NOT NULL DEFAULT 1,
            frequency_name TEXT CHECK(frequency_name IN ('ежедневно', 'еженедельно', 'ежемесячно')),
            frequency_count INTEGER,

            FOREIGN KEY (user_id) REFERENCES user(id),
            FOREIGN KEY (habit_id) REFERENCES habit(id),
            CONSTRAINT unique_user_habit UNIQUE (user_id, habit_id)
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS user_habit_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            user_id INTEGER,
            habit_id INTEGER,
            mark_date DATE,
            mark_count INTEGER,
            FOREIGN KEY (user_id) REFERENCES user(id),
            FOREIGN KEY (habit_id) REFERENCES habit(id),
            CONSTRAINT unique_user_habit UNIQUE (user_id, habit_id, mark_date)
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            session_id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            state TEXT,
            last_interaction REAL,
            data TEXT
        )
    ''')

    conn.commit()
    conn.close()
