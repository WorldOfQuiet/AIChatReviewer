import sqlite3
from datetime import datetime

class Database:
    def __init__(self, db_file):
        self.conn = sqlite3.connect(db_file)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        # Группы
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY,
                vk_id INTEGER UNIQUE,
                screen_name TEXT,
                name TEXT
            )
        """)
        # Пользователи (авторы)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vk_id INTEGER UNIQUE,
                screen_name TEXT,
                first_name TEXT,
                last_name TEXT
            )
        """)
        # Посты
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vk_id INTEGER,
                group_id INTEGER,
                text TEXT,
                date INTEGER,
                author_id INTEGER,
                FOREIGN KEY(group_id) REFERENCES groups(id),
                FOREIGN KEY(author_id) REFERENCES users(id),
                UNIQUE(vk_id, group_id)  -- vk_id уникален внутри группы
            )
        """)
        # Комментарии
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vk_id INTEGER,
                post_id INTEGER,
                text TEXT,
                date INTEGER,
                author_id INTEGER,
                FOREIGN KEY(post_id) REFERENCES posts(id),
                FOREIGN KEY(author_id) REFERENCES users(id),
                UNIQUE(vk_id, post_id)
            )
        """)
        # Медиа
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_type TEXT,  -- 'post' или 'comment'
                owner_id INTEGER, -- id поста или комментария
                url TEXT,
                type TEXT        -- 'photo', 'video', 'doc' и т.д.
            )
        """)
        self.conn.commit()

    def add_group(self, vk_id, screen_name, name):
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO groups (vk_id, screen_name, name) VALUES (?, ?, ?)",
                       (vk_id, screen_name, name))
        self.conn.commit()
        return cursor.lastrowid

    def get_group_by_vk_id(self, vk_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM groups WHERE vk_id = ?", (vk_id,))
        row = cursor.fetchone()
        return row["id"] if row else None

    def add_user(self, vk_id, screen_name, first_name, last_name):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO users (vk_id, screen_name, first_name, last_name)
            VALUES (?, ?, ?, ?)
        """, (vk_id, screen_name, first_name, last_name))
        self.conn.commit()
        cursor.execute("SELECT id FROM users WHERE vk_id = ?", (vk_id,))
        row = cursor.fetchone()
        return row["id"]

    def add_post(self, vk_id, group_id, text, date, author_id):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO posts (vk_id, group_id, text, date, author_id)
            VALUES (?, ?, ?, ?, ?)
        """, (vk_id, group_id, text, date, author_id))
        self.conn.commit()
        cursor.execute("SELECT id FROM posts WHERE vk_id = ? AND group_id = ?", (vk_id, group_id))
        row = cursor.fetchone()
        return row["id"]

    def add_comment(self, vk_id, post_id, text, date, author_id):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO comments (vk_id, post_id, text, date, author_id)
            VALUES (?, ?, ?, ?, ?)
        """, (vk_id, post_id, text, date, author_id))
        self.conn.commit()
        cursor.execute("SELECT id FROM comments WHERE vk_id = ? AND post_id = ?", (vk_id, post_id))
        row = cursor.fetchone()
        return row["id"]

    def add_media(self, owner_type, owner_id, url, media_type):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO media (owner_type, owner_id, url, type)
            VALUES (?, ?, ?, ?)
        """, (owner_type, owner_id, url, media_type))
        self.conn.commit()

    def close(self):
        self.conn.close()