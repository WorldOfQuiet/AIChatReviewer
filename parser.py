import time
import logging
from datetime import datetime
from config import SEARCH_QUERY, START_DATE, REQUEST_DELAY
from vk_api import VKAPI
from db import Database

logger = logging.getLogger(__name__)

class VKParser:
    def __init__(self, db_file):
        self.vk = VKAPI()
        self.db = Database(db_file)
        self.start_timestamp = int(datetime.strptime(START_DATE, "%Y-%m-%d").timestamp())

    def run(self):
        logger.info("Поиск групп по запросу '%s'", SEARCH_QUERY)
        groups = self.vk.search_groups(SEARCH_QUERY)
        logger.info("Найдено групп: %d", len(groups))

        for group in groups:
            group_id = group["id"]
            logger.info("Обработка группы ID %d", group_id)
            try:
                group_info = self.vk.get_group_info(group_id)[0]
                screen_name = group_info.get("screen_name", "")
                name = group_info.get("name", "")
                self.db.add_group(group_id, screen_name, name)
            except Exception as e:
                logger.error("Не удалось получить информацию о группе %d: %s", group_id, e)
                continue

            self._parse_group_wall(group_id)
            time.sleep(REQUEST_DELAY)

        logger.info("Сбор завершён")

    def _parse_group_wall(self, group_id):
        offset = 0
        count = 100
        while True:
            try:
                wall_data = self.vk.get_wall_posts(-group_id, count=count, offset=offset)
            except Exception as e:
                logger.error("Ошибка получения стены группы %d: %s", group_id, e)
                break

            posts = wall_data.get("items", [])
            if not posts:
                break

            all_old = True
            for post in posts:
                post_date = post["date"]
                if post_date >= self.start_timestamp:
                    all_old = False
                    self._process_post(group_id, post)
                else:
                    logger.info("Достигнут пост старше %s, остановка группы %d", START_DATE, group_id)
                    return
            if all_old:
                logger.info("Все посты выборки старше %s, остановка группы %d", START_DATE, group_id)
                return

            offset += count
            time.sleep(REQUEST_DELAY)

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
        while True:
            try:
                comments_data = self.vk.get_comments(owner_id, post_vk_id, count=count, offset=offset)
            except Exception as e:
                logger.error("Ошибка получения комментариев к посту %d: %s", post_vk_id, e)
                break

            comments = comments_data.get("items", [])
            if not comments:
                break

            for comment in comments:
                comment_date = comment["date"]
                if comment_date >= self.start_timestamp:
                    self._process_comment(comment, local_post_id)

            offset += count
            time.sleep(REQUEST_DELAY)

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
        if vk_id < 0:
            pass
        try:
            user_info = self.vk.get_users([vk_id])[0]
            screen_name = user_info.get("screen_name", "")
            first_name = user_info.get("first_name", "")
            last_name = user_info.get("last_name", "")
        except:
            screen_name = ""
            first_name = ""
            last_name = ""

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