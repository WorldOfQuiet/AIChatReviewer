import time
import logging
from datetime import datetime, timedelta
from vk_api import VKAPI
from db import Database
from exporter import export_to_json

logger = logging.getLogger(__name__)

class VKParser:
    def __init__(self, prefs: dict):
        self.prefs = prefs
        self.vk = VKAPI(
            token=prefs.get('vk_token'),
            api_version=prefs.get('vk_api_version', '5.131'),
            request_delay=prefs.get('request_delay', 0.5)
        )
        self.db = Database(prefs.get('db_file', 'vk_data.db'))
        self.groups_file = prefs.get('groups_file', 'groups.txt')
        self.start_timestamp = self._get_start_timestamp()
        self.end_timestamp = self._get_end_timestamp()
        logger.info("Период сбора: с %s по %s",
                    datetime.fromtimestamp(self.start_timestamp),
                    datetime.fromtimestamp(self.end_timestamp) if self.end_timestamp else "наст. время")

    def _get_start_timestamp(self):
        start_date = self.prefs.get('start_date')
        days_back = self.prefs.get('days_back', 30)
        if start_date:
            return int(datetime.strptime(start_date, "%Y-%m-%d").timestamp())
        else:
            return int((datetime.now() - timedelta(days=days_back)).timestamp())

    def _get_end_timestamp(self):
        end_date = self.prefs.get('end_date')
        if end_date:
            return int(datetime.strptime(end_date, "%Y-%m-%d").timestamp())
        return None

    def read_groups_from_file(self, filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]

    def run(self):
        logger.info("Чтение списка групп из файла %s", self.groups_file)
        group_screen_names = self.read_groups_from_file(self.groups_file)
        logger.info("Найдено групп для обработки: %d", len(group_screen_names))

        for screen_name in group_screen_names:
            try:
                group_info = self.vk.get_group_info(screen_name)[0]
                group_id = group_info['id']
                group_screen = group_info.get('screen_name', '')
                group_name = group_info.get('name', '')
                self.db.add_group(group_id, group_screen, group_name)
                logger.info("Обработка группы %s (ID %d)", group_name, group_id)
                self._parse_group_wall(group_id)
            except Exception as e:
                logger.error("Ошибка при обработке группы %s: %s", screen_name, e)
                continue
            time.sleep(0.5)

        logger.info("Сбор завершён. Экспорт в JSON...")
        export_to_json(self.prefs.get('db_file', 'vk_data.db'), "output.json")
        logger.info("Экспорт завершён.")

    def _parse_group_wall(self, group_id):
        offset = 0
        count = 100
        total_processed = 0
        print(f"\nНачинаем сбор постов в группе {group_id}")
        while True:
            try:
                wall_data = self.vk.get_wall_posts(-group_id, count=count, offset=offset)
            except Exception as e:
                logger.error("Ошибка получения стены группы %d: %s", group_id, e)
                break

            posts = wall_data.get("items", [])
            if not posts:
                break

            for post in posts:
                post_date = post["date"]
                if self.end_timestamp and post_date > self.end_timestamp:
                    continue
                if post_date >= self.start_timestamp:
                    self._process_post(group_id, post)
                    total_processed += 1
                    # Обновляем строку прогресса (одна строка)
                    print(f"\r  Группа {group_id}: обработано {total_processed} постов", end="", flush=True)
                else:
                    # Когда вышли за период, переводим строку и выходим
                    print(f"\n  Группа {group_id}: достигнут пост старше периода, остановка")
                    return

            offset += count
            time.sleep(0.5)
        print(f"\nГруппа {group_id} завершена, всего обработано {total_processed} постов")

    def _process_post(self, group_id, post):
        from_id = post["from_id"]
        author_id = self._get_or_create_user(from_id)

        post_vk_id = post["id"]
        post_text = post.get("text", "")
        post_date = post["date"]

        local_post_id = self.db.add_post(post_vk_id, self.db.get_group_by_vk_id(group_id), post_text, post_date, author_id)

        attachments = post.get("attachments", [])
        for att in attachments:
            self._process_attachment("post", local_post_id, att)

        self._parse_comments(-group_id, post_vk_id, local_post_id)

    def _parse_comments(self, owner_id, post_vk_id, local_post_id):
        offset = 0
        count = 100
        max_retries = 3

        while True:
            for attempt in range(max_retries):
                try:
                    comments_data = self.vk.get_comments(owner_id, post_vk_id, count=count, offset=offset)
                    break
                except Exception as e:
                    logger.error(f"Попытка {attempt+1} для поста {post_vk_id} offset {offset} не удалась: {e}")
                    if attempt == max_retries - 1:
                        logger.error(f"Не удалось получить комментарии для поста {post_vk_id}, пропускаем")
                        return
                    time.sleep(2 ** attempt)

            total = comments_data.get('count', 0)
            items = comments_data.get("items", [])

            if not items:
                logger.info(f"Пост {post_vk_id}: нет комментариев")
                break

            for comment in items:
                comment_date = comment["date"]
                if comment_date >= self.start_timestamp:
                    try:
                        self._process_comment(comment, local_post_id)
                    except Exception as e:
                        logger.error(f"Ошибка при сохранении комментария {comment['id']}: {e}")
                else:
                    logger.debug(f"Комментарий {comment['id']} пропущен по дате")

            offset += count
            time.sleep(0.5)

            if total > 0 and offset >= total:
                logger.info(f"Пост {post_vk_id}: собрано {total} комментариев")
                break

    def _process_comment(self, comment, local_post_id):
        from_id = comment["from_id"]
        author_id = self._get_or_create_user(from_id)

        comment_vk_id = comment["id"]
        comment_text = comment.get("text", "")
        comment_date = comment["date"]

        local_comment_id = self.db.add_comment(comment_vk_id, local_post_id, comment_text, comment_date, author_id)

        attachments = comment.get("attachments", [])
        for att in attachments:
            self._process_attachment("comment", local_comment_id, att)

    def _get_or_create_user(self, vk_id):
        screen_name = first_name = last_name = ""

        if vk_id > 0:
            # Пользователь
            try:
                user_info = self.vk.get_users([vk_id])[0]
                screen_name = user_info.get("screen_name", "")
                first_name = user_info.get("first_name", "")
                last_name = user_info.get("last_name", "")
            except Exception as e:
                logger.error(f"Не удалось получить информацию о пользователе {vk_id}: {e}")
        else:
            # Группа (vk_id < 0)
            try:
                group_info = self.vk.get_group_info(abs(vk_id))[0]  # передаём положительный ID
                screen_name = group_info.get("screen_name", "")
                first_name = group_info.get("name", "")  # название группы
                last_name = ""  # у групп нет фамилии
            except Exception as e:
                logger.error(f"Не удалось получить информацию о группе {vk_id}: {e}")

        return self.db.add_user(vk_id, screen_name, first_name, last_name)

    def _process_attachment(self, owner_type, owner_id, attachment):
        att_type = attachment["type"]
        url = None

        if att_type == "photo":
            sizes = attachment["photo"]["sizes"]
            max_size = max(sizes, key=lambda s: s["height"] * s["width"] if s.get("height") and s.get("width") else 0)
            url = max_size["url"]
        elif att_type == "video":
            video = attachment["video"]
            owner_id_video = video["owner_id"]
            video_id = video["id"]
            url = f"https://vk.com/video{owner_id_video}_{video_id}"
        elif att_type == "doc":
            doc = attachment["doc"]
            url = doc.get("url")

        if url:
            self.db.add_media(owner_type, owner_id, url, att_type)