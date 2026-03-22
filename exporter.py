import sqlite3
import json
from datetime import datetime

def export_to_json(db_file, output_file):
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT id, vk_id, screen_name, name FROM groups")
    groups = cursor.fetchall()

    result = []

    for group in groups:
        group_id = group['id']
        chat_name = group['name'] or group['screen_name'] or f"group_{group['vk_id']}"

        cursor.execute("""
            SELECT p.id as db_id, p.text, p.date, p.author_id,
                   u.screen_name as author_screen, u.first_name, u.last_name
            FROM posts p
            JOIN users u ON p.author_id = u.id
            WHERE p.group_id = ?
        """, (group_id,))
        posts = cursor.fetchall()

        cursor.execute("""
            SELECT c.id as db_id, c.text, c.date, c.author_id, c.post_id,
                   u.screen_name as author_screen, u.first_name, u.last_name
            FROM comments c
            JOIN users u ON c.author_id = u.id
            WHERE c.post_id IN (SELECT id FROM posts WHERE group_id = ?)
        """, (group_id,))
        comments = cursor.fetchall()

        def get_media(owner_type, owner_db_id):
            cur = conn.cursor()
            cur.execute("SELECT url FROM media WHERE owner_type = ? AND owner_id = ?", (owner_type, owner_db_id))
            return [row['url'] for row in cur.fetchall()]

        messages_raw = []

        for p in posts:
            author = p['author_screen'] or f"{p['first_name']} {p['last_name']}".strip() or f"id{p['author_id']}"
            media = get_media('post', p['db_id'])
            messages_raw.append({
                'type': 'post',
                'db_id': p['db_id'],
                'date': p['date'],
                'text': p['text'],
                'author': author,
                'media': media,
                'post_db_id': None
            })

        for c in comments:
            author = c['author_screen'] or f"{c['first_name']} {c['last_name']}".strip() or f"id{c['author_id']}"
            media = get_media('comment', c['db_id'])
            messages_raw.append({
                'type': 'comment',
                'db_id': c['db_id'],
                'date': c['date'],
                'text': c['text'],
                'author': author,
                'media': media,
                'post_db_id': c['post_id']
            })

        messages_raw.sort(key=lambda x: x['date'])

        post_db_to_local = {}
        for msg in messages_raw:
            if msg['type'] == 'post':
                post_db_to_local[msg['db_id']] = len(post_db_to_local)
        local_id = 0
        for msg in messages_raw:
            if msg['type'] == 'post':
                post_db_to_local[msg['db_id']] = local_id
            local_id += 1

        messages_final = []
        local_id = 0
        for msg in messages_raw:
            if msg['type'] == 'post':
                reply_to = -1
            else:
                reply_to = post_db_to_local.get(msg['post_db_id'], -1)

            dt = datetime.fromtimestamp(msg['date'])
            date_str = dt.strftime("%H:%M %d.%m.%Y")

            messages_final.append({
                "id": local_id,
                "text": msg['text'],
                "author": msg['author'],
                "media": msg['media'],
                "reply_to": reply_to,
                "date": date_str
            })
            local_id += 1

        result.append({
            "chat_id": len(result),
            "chat_name": chat_name,
            "messages": messages_final
        })

    conn.close()

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Экспортировано {len(result)} чатов в {output_file}")