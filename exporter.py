import json
import sqlite3

def export_to_json(db_file, output_file):
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Получаем все посты
    cursor.execute("""
        SELECT p.id, p.text, p.date, u.screen_name, u.first_name, u.last_name
        FROM posts p
        JOIN users u ON p.author_id = u.id
        ORDER BY p.date
    """)
    posts = cursor.fetchall()

    # Получаем все комментарии
    cursor.execute("""
        SELECT c.id, c.text, c.date, u.screen_name, u.first_name, u.last_name, c.post_id
        FROM comments c
        JOIN users u ON c.author_id = u.id
        ORDER BY c.date
    """)
    comments = cursor.fetchall()

    # Функция для получения списка медиа-ссылок
    def get_media(owner_type, owner_id):
        cur = conn.cursor()
        cur.execute("SELECT url FROM media WHERE owner_type = ? AND owner_id = ?", (owner_type, owner_id))
        return [row["url"] for row in cur.fetchall()]

    # Список всех записей (посты + комментарии)
    records = []
    # Словарь для связи database id поста -> локальный id в records
    post_db_id_to_local = {}

    for post in posts:
        local_id = len(records)
        post_db_id_to_local[post["id"]] = local_id

        author = post["screen_name"] or f"{post['first_name']} {post['last_name']}".strip() or f"id{post['id']}"
        media = get_media("post", post["id"])

        records.append({
            "id": local_id,
            "text": post["text"],
            "author": author,
            "media": media,
            "reply_to": -1,
            "date": post["date"]
        })

    for comment in comments:
        local_id = len(records)
        author = comment["screen_name"] or f"{comment['first_name']} {comment['last_name']}".strip() or f"id{comment['id']}"
        media = get_media("comment", comment["id"])
        reply_to_local = post_db_id_to_local.get(comment["post_id"], -1)  # ссылка на id поста

        records.append({
            "id": local_id,
            "text": comment["text"],
            "author": author,
            "media": media,
            "reply_to": reply_to_local,
            "date": comment["date"]
        })

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    conn.close()
    print(f"✅ Экспортировано {len(records)} записей в {output_file}")