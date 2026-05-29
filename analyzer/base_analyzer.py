import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from tqdm import tqdm

from core.api_client import LLMClient
from core.data_processor import DataProcessor


class BaseAnalyzer:
    """Базовый класс анализатора с общими утилитами."""

    DEFAULT_BASE_URL = "https://routerai.ru/api/v1"
    DEFAULT_MODEL_NAME = "deepseek/deepseek-v4-flash"

    def __init__(self, config: dict):
        # Инициализация параметров из конфигурации
        self.config = config
        self.logging_level = self._get_int(config, 'logging_level', 2, 0, 2)
        self.max_chats = self._get_int(config, 'max_chats', 1, 1)
        self.max_messages_per_chat = self._get_int(config, 'max_messages_per_chat', 2000, 1)
        self.max_chain_packets = self._get_int(config, 'max_chain_packets', 20, 0)
        self.max_isolated_packets = self._get_int(config, 'max_isolated_packets', 10, 0)
        self.max_chain_packet_messages = self._get_int(config, 'max_chain_packet_messages', 150, 1)
        self.isolated_packet_size = self._get_int(config, 'isolated_packet_size', 400, 1)
        self.max_retries = self._get_int(config, 'max_retries', 3, 1)
        self.problems_per_packet = self._get_int(config, 'problems_per_packet', 200, 1)
        self.api_key = self._get_str(config, 'api_key')
        self.system_prompt_file = self._get_str(config, 'system_prompt_file')
        self.system_prompt_file_2 = self._get_str(config, 'system_prompt_file_2')
        self.chats_file = self._get_str(config, 'chats_file')
        self.base_url = config.get('base_url', self.DEFAULT_BASE_URL)
        self.model_name = config.get('model_name', self.DEFAULT_MODEL_NAME)
        steps = config.get('steps', {})
        self.step1_enabled = steps.get('step1_analyze_chats', True)
        self.step2_enabled = steps.get('step2_aggregate_results', True)
        self.step3_enabled = steps.get('step3_backward_mapping', True)
        self.current_stage = ""
        self._log(1, "Анализатор инициализирован")

    def _get_int(self, config: dict, key: str, default: int, min_val: Optional[int] = None,
                 max_val: Optional[int] = None) -> int:
        value = config.get(key, default)
        if not isinstance(value, int):
            raise TypeError(f"Параметр '{key}' должен быть целым числом")
        if min_val is not None and value < min_val:
            raise ValueError(f"Параметр '{key}' не может быть меньше {min_val}")
        if max_val is not None and value > max_val:
            raise ValueError(f"Параметр '{key}' не может быть больше {max_val}")
        return value

    def _get_str(self, config: dict, key: str) -> str:
        value = config.get(key)
        if value is None:
            raise ValueError(f"Обязательный параметр '{key}' отсутствует")
        if not isinstance(value, str):
            raise TypeError(f"Параметр '{key}' должен быть строкой")
        return value

    def _log(self, level: int, message: str, indent: int = 0):
        if self.logging_level >= level:
            if level == 1 and self.logging_level == 1:
                return
            print("  " * indent + message)

    def _get_packet_first_date(self, packet: list):
        if not packet:
            return 0  # Default value for empty packets
        first = packet[0]
        dt = first.get('_dt')
        return dt if dt is not None else first['id']

    def _send_with_retries(self, agent: LLMClient, text: str, context: str):
        """Отправить запрос агенту с повторными попытками."""
        for attempt in range(self.max_retries):
            try:
                response = agent.send_full_conversation(text, temperature=0.7, max_tokens=4096)
                self._log(2, f"      Ответ агента ({context}, попытка {attempt+1}):", indent=4)
                self._log(2, response, indent=5)
                parsed = DataProcessor.extract_from_response(response)
                if parsed is not None:
                    return parsed
                self._log(2, f"      Попытка {attempt+1}: не удалось извлечь данные. Повтор через 2 сек...", indent=4)
                time.sleep(2)
            except Exception as e:
                self._log(2, f"      Ошибка при попытке {attempt+1}: {e}", indent=4)
                if attempt < self.max_retries - 1:
                    self._log(2, "      Повтор через 5 сек...", indent=4)
                    time.sleep(5)
        return None

    def _save_results(self, path: str, data: list, message: str):
        """Сохранить результаты в JSON файл."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._log(1, f"  {message} сохранены в файл: {path}")
        self._log(2, "  " + "-" * 50, indent=1)