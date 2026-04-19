import time
import logging
from datetime import datetime, timedelta
from vk_api import VKAPI
from db import Database

logger = logging.getLogger(__name__)


class VKParser:
    def __init__(self, vk_token: str, vk_api_version: str, request_delay: float,
                 groups_file: str, db_file: str, start_date: str = None,
                 end_date: str = None, days_back: int = 30):
        self.vk = VKAPI(vk_token, vk_api_version, request_delay)
        self.db = Database(db_file)
        self.groups_file = groups_file
        self.request_delay = request_delay
        self.start_timestamp = self._get_start_timestamp(start_date, days_back)
        self.end_timestamp = self._get_end_timestamp(end_date)
        self.progress_interval = 10   # можно вынести в конфиг
        logger.info("Период сбора: с %s по %s",
                    datetime.fromtimestamp(self.start_timestamp),
                    datetime.fromtimestamp(self.end_timestamp) if self.end_timestamp else "наст. время")

    def _get_start_timestamp(self, start_date, days_back):
        if start_date:
            return int(datetime.strptime(start_date, "%Y-%m-%d").timestamp())
        else:
            return int((datetime.now() - timedelta(days=days_back)).timestamp())

    def _get_end_timestamp(self, end_date):
        if end_date:
            return int(datetime.strptime(end_date, "%Y-%m-%d").timestamp())
        return None

    def read_groups_from_file(self):
        with open(self.groups_file, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]

    def run(self):
        logger.info("Чтение списка групп из файла %s", self.groups_file)
        group_screen_names = self.read_groups_from_file()
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
            time.sleep(self.request_delay)
        logger.info("Сбор завершён")

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
                    if total_processed % self.progress_interval == 0:
                        print(f"  Группа {group_id}: обработано {total_processed} постов")
                else:
                    print(f"  Группа {group_id}: достигнут пост старше периода, остановка")
                    return

            offset += count
            time.sleep(self.request_delay)
        print(f"Группа {group_id} завершена, всего обработано {total_processed} постов")
