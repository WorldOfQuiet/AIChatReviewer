import json
import requests
import re
import os
import time
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from tqdm import tqdm


class AliceAIAgent:
    def __init__(self, api_key_file_path: str, agent_id: str, system_prompt_file_path: str,
                 base_url: str, model_name: str):
        """
        Initialize the agent for working with an LLM via Yandex AI Studio or compatible API.

        :param api_key_file_path: path to the file containing the API key in JSON format.
        :param agent_id: catalog identifier (not model) — used as part of modelUri.
        :param system_prompt_file_path: path to the file with the system prompt.
        :param base_url: base URL for the LLM API.
        :param model_name: name of the model (e.g., "aliceai-llm/latest").
        """
        self.agent_id = agent_id
        self.api_key = self._load_api_key(api_key_file_path)
        self.base_url = base_url
        self.model_name = model_name
        self.system_prompt = self._load_system_prompt(system_prompt_file_path)

    def _load_api_key(self, file_path: str) -> str:
        """Load API key from JSON file."""
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
            return data['api_key']

    def _load_system_prompt(self, file_path: str) -> str:
        """Load system prompt from text file."""
        with open(file_path, 'r', encoding='utf-8') as file:
            prompt = file.read().strip()
            return prompt

    def send_full_conversation(self, conversation_text: str, temperature: float = 0.7, max_tokens: int = 4096) -> str:
        """
        Send full conversation text to the LLM agent and return the response.

        :param conversation_text: full conversation text (loaded from file).
        :param temperature: generation randomness parameter (0.0–1.0).
        :param max_tokens: maximum number of tokens in the response.
        :return: agent's response text.
        """
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json"
        }

        # Construct modelUri according to the format gpt://<catalog_id>/<model_name>
        model_uri = f"gpt://{self.agent_id}/{self.model_name}"

        payload = {
            "modelUri": model_uri,
            "completionOptions": {
                "stream": False,
                "temperature": temperature,
                "maxTokens": max_tokens
            },
            "messages": [
                {
                    "role": "system",
                    "text": self.system_prompt
                },
                {
                    "role": "user",
                    "text": conversation_text
                }
            ]
        }

        try:
            response = requests.post(self.base_url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()
            return result['result']['alternatives'][0]['message']['text']
        except Exception as e:
            raise Exception(f"Ошибка при отправке запроса агенту: {e}")


class DataProcessor:
    """Класс для обработки данных чатов и извлечения информации из ответов агента."""

    @staticmethod
    def parse_date(date_value) -> Optional[datetime]:
        """
        Преобразует дату из различных форматов в объект datetime.
        Поддерживаются:
          - целое число (timestamp Unix)
          - строка в формате "ЧЧ:ММ ДД.ММ.ГГГГ" (например, "08:24 08.03.2025")
          - ISO-строка "ГГГГ-ММ-ДД ЧЧ:ММ:СС"
        Возвращает None, если не удалось распарсить.
        """
        if isinstance(date_value, (int, float)):
            # Предполагаем timestamp (секунды)
            return datetime.fromtimestamp(date_value)
        if isinstance(date_value, str):
            # Попробуем разные форматы
            formats = [
                "%H:%M %d.%m.%Y",      # 08:24 08.03.2025
                "%d.%m.%Y %H:%M",      # 08.03.2025 08:24
                "%Y-%m-%d %H:%M:%S",   # 2025-03-08 08:24:00
                "%Y-%m-%dT%H:%M:%S",   # ISO с T
            ]
            for fmt in formats:
                try:
                    return datetime.strptime(date_value, fmt)
                except ValueError:
                    continue
        return None

    @staticmethod
    def extract_from_response(response_text: str):
        """
        Extract data between <result> tags from the model response.
        Returns a list if parsing succeeds, None if tags not found or JSON invalid.
        """
        # Find content between <result> and </result>
        match = re.search(r'<result>(.*?)</result>', response_text, re.DOTALL)
        if not match:
            return None  # теги не найдены – неудача

        json_content = match.group(1).strip()

        try:
            parsed_data = json.loads(json_content)
            return parsed_data
        except json.JSONDecodeError:
            return None  # невалидный JSON – неудача

    @staticmethod
    def load_chats_from_json(file_path: str, max_messages_per_chat: int = None, max_chats: int = None) -> list:
        """
        Load chats data from a JSON file containing an array of chat objects.

        Expected JSON structure:
        [
            {
                "chat_id": 0,
                "chat_name": "Название чата",
                "messages": [
                    {"id": 0, "text": "...", "author": "...", "media": [...], "reply_to": -1, "date": 123456 или "08:24 08.03.2025"},
                    ...
                ]
            },
            ...
        ]

        :param file_path: path to the JSON file.
        :param max_messages_per_chat: maximum number of messages to load per chat (from the newest). If None, load all.
        :param max_chats: maximum number of chats to load (from the newest). If None, load all.
        :return: list of chat dictionaries.
        :raises ValueError: if required keys are missing.
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError("Expected a list of chat objects at the top level.")

        result = []
        for chat in data:
            required_keys = ['chat_id', 'chat_name', 'messages']
            for key in required_keys:
                if key not in chat:
                    raise ValueError(f"Missing required key '{key}' in chat: {chat}")

            messages = chat['messages']
            # Добавляем временное поле _dt для сортировки
            for msg in messages:
                if 'date' in msg:
                    msg['_dt'] = DataProcessor.parse_date(msg['date'])
                else:
                    msg['_dt'] = None

            # Сортируем сообщения по дате (от старых к новым).
            # Если дата отсутствует, используем id как запасной вариант.
            messages.sort(key=lambda m: (m['_dt'] is None, m['_dt'] or m['id']))

            # Применяем ограничение max_messages_per_chat (берём последние N – самые новые)
            if max_messages_per_chat is not None and max_messages_per_chat > 0:
                messages = messages[-max_messages_per_chat:]

            result.append({
                'chat_id': chat['chat_id'],
                'chat_name': chat['chat_name'],
                'messages': messages
            })

        # Ограничение количества чатов (берём последние)
        if max_chats is not None and max_chats > 0 and len(result) > max_chats:
            result = result[-max_chats:]

        return result

    @staticmethod
    def format_message_for_agent(msg: dict) -> str:
        """
        Convert a message dictionary into the string format expected by the agent.
        The media field is replaced with "yes" if there are photos, otherwise "no".
        """
        media_status = "yes" if msg.get('media') else "no"
        return f"{msg['id']} | {msg['text']} | {msg['author']} | {media_status} | {msg['reply_to']}"

    @staticmethod
    def parse_message_line(line: str) -> dict:
        """
        Parse a line from the conversation in format:
        <num> | <text> | <author> | [<media>] | <reply_to>
        Returns a dictionary with keys: num, text, author, media, reply_to.
        """
        parts = line.split(' | ', maxsplit=4)
        if len(parts) != 5:
            # fallback: try without maxsplit
            parts = line.split(' | ')
        if len(parts) == 5:
            num = int(parts[0].strip())
            text = parts[1].strip()
            author = parts[2].strip()
            media_str = parts[3].strip()
            # media is like [photo1, photo2] or []
            if media_str.startswith('[') and media_str.endswith(']'):
                media_content = media_str[1:-1].strip()
                if media_content:
                    media = [item.strip() for item in media_content.split(',')]
                else:
                    media = []
            else:
                media = []
            reply_to = int(parts[4].strip())
            return {
                'num': num,
                'text': text,
                'author': author,
                'media': media,
                'reply_to': reply_to
            }
        else:
            # If parsing fails, return a minimal dict
            return {
                'num': -1,
                'text': line,
                'author': 'unknown',
                'media': [],
                'reply_to': -1
            }

    @staticmethod
    def group_messages_by_reply_chain(messages: list, isolated_packet_size: int = None) -> Tuple[list, list]:
        """
        Group messages based on reply_to chains (transitive closure).
        Returns two lists:
          - chain_packets: list of packets, each packet is a list of messages from a reply chain.
          - isolated_packets: list of packets, each packet is a list of isolated messages,
                               split into packets of size isolated_packet_size (if given).
        Handles missing parent messages (due to loading only a subset) by treating them as roots.

        :param messages: list of message dictionaries.
        :param isolated_packet_size: if given, isolated messages are split into packets of this size.
        :return: (chain_packets, isolated_packets)
        """
        # Build dictionary id -> message
        msg_dict = {m['id']: m for m in messages}

        # Find root for each message using memoization
        root_of = {}

        def find_root(msg_id):
            if msg_id in root_of:
                return root_of[msg_id]
            msg = msg_dict.get(msg_id)
            if not msg or msg['reply_to'] == -1:
                root_of[msg_id] = msg_id
                return msg_id
            # Check if parent exists in our loaded messages
            if msg['reply_to'] not in msg_dict:
                # Parent not loaded, treat current as root
                root_of[msg_id] = msg_id
                return msg_id
            parent_root = find_root(msg['reply_to'])
            root_of[msg_id] = parent_root
            return parent_root

        for m in messages:
            find_root(m['id'])

        # Group ids by root
        groups = {}
        for msg_id, root in root_of.items():
            groups.setdefault(root, []).append(msg_id)

        # Separate chain groups (size>1) from isolated messages
        chain_groups = []
        isolated_ids = []
        for root, ids in groups.items():
            if len(ids) > 1:
                chain_groups.append(ids)
            else:
                # single message
                msg = msg_dict[root]
                if msg['reply_to'] == -1:
                    isolated_ids.append(root)
                else:
                    # This can happen if the parent is missing; we treat as isolated
                    isolated_ids.append(root)

        # Build chain packets: each chain becomes a separate packet, sorted chronologically
        chain_packets = []
        for ids in chain_groups:
            packet_msgs = [msg_dict[i] for i in ids]
            packet_msgs.sort(key=lambda m: (m.get('_dt') is None, m.get('_dt') or m['id']))
            chain_packets.append(packet_msgs)

        # Build isolated packets: split isolated messages into packets of size isolated_packet_size
        isolated_packets = []
        if isolated_ids:
            isolated_msgs = [msg_dict[i] for i in isolated_ids]
            isolated_msgs.sort(key=lambda m: (m.get('_dt') is None, m.get('_dt') or m['id']))
            if isolated_packet_size is not None and isolated_packet_size > 0:
                # Split into chunks from the beginning (oldest first) – so that each packet contains consecutive messages
                for i in range(0, len(isolated_msgs), isolated_packet_size):
                    chunk = isolated_msgs[i:i+isolated_packet_size]
                    isolated_packets.append(chunk)
            else:
                isolated_packets.append(isolated_msgs)

        return chain_packets, isolated_packets


class DataAnalyzer:
    """Класс для выполнения многошагового анализа чатов."""

    # Константы по умолчанию для модели (можно переопределить в конфиге)
    DEFAULT_BASE_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    DEFAULT_MODEL_NAME = "aliceai-llm/latest"

    def __init__(self, config: dict):
        """
        Инициализация анализатора на основе конфигурации.

        :param config: словарь с настройками из analyzer.preferences.
        """
        self.config = config
        self.logging_level = self._get_int(config, 'logging_level', 2, 0, 2)
        self.max_chats = self._get_int(config, 'max_chats', 1, 1)
        self.max_messages_per_chat = self._get_int(config, 'max_messages_per_chat', 2000, 1)
        self.max_chain_packets = self._get_int(config, 'max_chain_packets', 20, 0)  # может быть 0
        self.max_isolated_packets = self._get_int(config, 'max_isolated_packets', 10, 0)  # может быть 0
        self.max_chain_packet_messages = self._get_int(config, 'max_chain_packet_messages', 150, 1)
        self.isolated_packet_size = self._get_int(config, 'isolated_packet_size', 400, 1)
        self.max_retries = self._get_int(config, 'max_retries', 3, 1)
        self.problems_per_packet = self._get_int(config, 'problems_per_packet', 200, 1)

        self.api_key_file = self._get_str(config, 'api_key_file')
        self.agent_id = self._get_str(config, 'agent_id')
        self.system_prompt_file = self._get_str(config, 'system_prompt_file')
        self.system_prompt_file_2 = self._get_str(config, 'system_prompt_file_2')
        self.chats_file = self._get_str(config, 'chats_file')  # путь к файлу с чатами

        # Параметры модели (с запасными значениями)
        self.base_url = config.get('base_url', self.DEFAULT_BASE_URL)
        self.model_name = config.get('model_name', self.DEFAULT_MODEL_NAME)

        # Шаги, которые нужно выполнить
        steps_config = config.get('steps', {})
        self.step1_enabled = steps_config.get('step1_analyze_chats', True)
        self.step2_enabled = steps_config.get('step2_aggregate_results', True)
        self.step3_enabled = steps_config.get('step3_backward_mapping', True)

        self.current_stage = ""  # для отображения в прогресс-баре

        self._log(1, "Анализатор инициализирован")

    def _get_int(self, config: dict, key: str, default: int, min_val: Optional[int] = None, max_val: Optional[int] = None) -> int:
        """Получить целочисленное значение из конфига с проверкой."""
        value = config.get(key, default)
        if not isinstance(value, int):
            raise TypeError(f"Параметр '{key}' должен быть целым числом, получен {type(value).__name__}")
        if min_val is not None and value < min_val:
            raise ValueError(f"Параметр '{key}' не может быть меньше {min_val}")
        if max_val is not None and value > max_val:
            raise ValueError(f"Параметр '{key}' не может быть больше {max_val}")
        return value

    def _get_str(self, config: dict, key: str) -> str:
        """Получить строковое значение из конфига."""
        value = config.get(key)
        if value is None:
            raise ValueError(f"Обязательный параметр '{key}' отсутствует в конфигурации")
        if not isinstance(value, str):
            raise TypeError(f"Параметр '{key}' должен быть строкой, получен {type(value).__name__}")
        return value

    def _log(self, level: int, message: str, indent: int = 0):
        """Логирование с учётом уровня и отступов. При уровне 1 подавляем обычные сообщения."""
        if self.logging_level >= level:
            # На уровне 1 показываем только прогресс-бары, всё остальное игнорируем
            if level == 1 and self.logging_level == 1:
                return
            print("  " * indent + message)

    def _get_packet_first_date(self, packet: list):
        """
        Возвращает дату первого (самого старого) сообщения в пакете.
        Если дата отсутствует, использует id (меньше id = старше).
        """
        if not packet:
            return None
        first = packet[0]
        dt = first.get('_dt')
        if dt is None:
            # fallback to id
            return first['id']
        return dt

    def step1_analyze_chats(self, main_pbar: Optional[tqdm] = None):
        """
        Шаг 1: анализ исходных чатов с группировкой по цепочкам ответов.
        Сохраняет результаты в agent_data/analysis_step_1.json.
        """
        self.current_stage = "Этап 1: Анализ чатов"
        step1_json_path = "agent_data/analysis_step_1.json"

        if self.chats_file is None:
            self._log(1, "  Ошибка: не указан путь к файлу чатов (chats_file).")
            return

        # Load all chats from the input JSON file
        try:
            chats = DataProcessor.load_chats_from_json(
                self.chats_file,
                max_messages_per_chat=self.max_messages_per_chat,
                max_chats=self.max_chats
            )
        except Exception as e:
            self._log(1, f"  Ошибка загрузки JSON: {e}")
            return

        if not chats:
            self._log(1, "  Нет данных для обработки.")
            return

        self._log(1, f"  Загружено чатов: {len(chats)}")
        self._log(2, "  " + "-" * 50, indent=1)

        # Create agent instance for chat analysis (reused for all chats)
        agent = AliceAIAgent(
            self.api_key_file, self.agent_id, self.system_prompt_file,
            self.base_url, self.model_name
        )

        # List to collect all interim entries from all chats and packets
        interim_entries = []

        # Если уровень логирования 1, используем прогресс-бары
        if self.logging_level == 1:
            outer_pbar = tqdm(total=len(chats), desc=self.current_stage, position=1, leave=False)

        # Process each chat
        for chat_idx, chat in enumerate(chats):
            chat_id = chat['chat_id']
            chat_name = chat['chat_name']
            messages = chat['messages']

            # Group messages by reply chains
            all_chain_packets, all_isolated_packets = DataProcessor.group_messages_by_reply_chain(
                messages, isolated_packet_size=self.isolated_packet_size
            )
            self._log(2, f"\n  Чат '{chat_name}' (ID: {chat_id}) исходно разбит на {len(all_chain_packets)} цепочечных пакетов и {len(all_isolated_packets)} пакетов изолированных сообщений.", indent=2)

            # ===== Обработка цепочечных пакетов =====
            if self.max_chain_packets == 0:
                self._log(2, "    Обработка цепочечных пакетов отключена (max_chain_packets=0).", indent=3)
                chain_packets_to_process = []
            else:
                # Сортируем цепочечные пакеты по убыванию даты первого сообщения (новые первыми)
                sorted_chain = sorted(all_chain_packets, key=lambda p: self._get_packet_first_date(p), reverse=True)
                if len(sorted_chain) > self.max_chain_packets:
                    chain_packets_to_process = sorted_chain[:self.max_chain_packets]
                    self._log(2, f"    Ограничение max_chain_packets={self.max_chain_packets}: взято последних {len(chain_packets_to_process)} цепочечных пакетов (по новизне корня).", indent=3)
                else:
                    chain_packets_to_process = sorted_chain  # все

            # ===== Обработка изолированных пакетов =====
            if self.max_isolated_packets == 0:
                self._log(2, "    Обработка изолированных пакетов отключена (max_isolated_packets=0).", indent=3)
                isolated_packets_to_process = []
            else:
                sorted_isolated = sorted(all_isolated_packets, key=lambda p: self._get_packet_first_date(p), reverse=True)
                if len(sorted_isolated) > self.max_isolated_packets:
                    isolated_packets_to_process = sorted_isolated[:self.max_isolated_packets]
                    self._log(2, f"    Ограничение max_isolated_packets={self.max_isolated_packets}: взято последних {len(isolated_packets_to_process)} пакетов изолированных сообщений (по новизне корня).", indent=3)
                else:
                    isolated_packets_to_process = sorted_isolated

            # Объединяем все пакеты для обработки в этом чате
            all_packets = []
            # Цепочечные с учётом ограничения по сообщениям
            for pkt in chain_packets_to_process:
                if self.max_chain_packet_messages is not None and self.max_chain_packet_messages > 0 and len(pkt) > self.max_chain_packet_messages:
                    pkt = pkt[:self.max_chain_packet_messages]
                all_packets.append(('цепочечный', pkt))
            # Изолированные (без дополнительного ограничения)
            for pkt in isolated_packets_to_process:
                all_packets.append(('изолированный', pkt))

            # Если уровень логирования 1, создаём внутренний прогресс-бар для пакетов этого чата
            if self.logging_level == 1:
                inner_pbar = tqdm(total=len(all_packets), desc=f"Чат: {chat_name}", position=2, leave=False)

            # Обрабатываем пакеты
            for pkt_type, pkt_msgs in all_packets:
                self._process_packet(pkt_msgs, chat_name, chat_id, 0, agent, interim_entries, pkt_type)
                if self.logging_level == 1:
                    inner_pbar.update(1)

            if self.logging_level == 1:
                inner_pbar.close()
                outer_pbar.update(1)

        if self.logging_level == 1:
            outer_pbar.close()

        # Write all interim entries to the interim JSON file (overwrite)
        os.makedirs(os.path.dirname(step1_json_path), exist_ok=True)
        with open(step1_json_path, 'w', encoding='utf-8') as f:
            json.dump(interim_entries, f, ensure_ascii=False, indent=2)

        self._log(1, f"  Все промежуточные результаты сохранены в файл: {step1_json_path}")
        self._log(2, "  " + "-" * 50, indent=1)

        # Обновляем основной прогресс-бар после завершения шага
        if self.logging_level == 1 and main_pbar is not None:
            main_pbar.update(1)

    def _process_packet(self, packet_msgs: list, chat_name: str, chat_id: int, idx: int,
                        agent: AliceAIAgent, interim_entries: list, packet_type: str = ""):
        """Общая обработка одного пакета: отправка, извлечение, сохранение."""
        packet_lines = [DataProcessor.format_message_for_agent(m) for m in packet_msgs]
        packet_text = "\n".join(packet_lines)

        self._log(2, f"\n      --- Обработка {packet_type} пакета (чат: {chat_name}) ---", indent=4)
        self._log(2, "      Текст пакета (первые 500 символов):", indent=4)
        self._log(2, "      " + (packet_text[:500] + "..." if len(packet_text) > 500 else packet_text), indent=4)
        self._log(2, "      " + "-" * 50, indent=4)

        # Retry loop
        parsed_data = None
        for attempt in range(self.max_retries):
            try:
                response = agent.send_full_conversation(packet_text, temperature=0.7, max_tokens=4096)
                self._log(2, "      Ответ агента:", indent=4)
                self._log(2, response, indent=5)

                parsed_data = DataProcessor.extract_from_response(response)
                if parsed_data is not None:
                    break
                else:
                    self._log(2, f"      Попытка {attempt+1}: не удалось извлечь данные (отсутствуют теги или невалидный JSON). Повтор через 2 сек...", indent=4)
                    time.sleep(2)
            except Exception as e:
                self._log(2, f"      Ошибка при попытке {attempt+1}: {e}", indent=4)
                if attempt < self.max_retries - 1:
                    self._log(2, "      Повтор через 5 сек...", indent=4)
                    time.sleep(5)
                else:
                    self._log(2, "      Достигнут лимит попыток. Пропускаем пакет.", indent=4)
                    parsed_data = None
        if parsed_data is None:
            self._log(2, "      Не удалось получить корректный ответ для пакета, пропускаем.", indent=4)
            return

        # Add count field to each problem
        problems_with_count = []
        for problem in parsed_data:
            if isinstance(problem, dict) and 'name' in problem and 'complaints' in problem:
                count = len(problem['complaints'])
                problem_with_count = {
                    'name': problem['name'],
                    'count': count,
                    'complaints': problem['complaints']
                }
                problems_with_count.append(problem_with_count)
            else:
                problems_with_count.append(problem)

        # Create entry for this packet
        part_chat_name = f"{chat_name} ({packet_type} пакет)"
        entry = {
            "chat_id": chat_id,
            "chat_name": part_chat_name,
            "analisis_result": problems_with_count
        }
        interim_entries.append(entry)

    def step2_aggregate_results(self, main_pbar: Optional[tqdm] = None):
        """
        Шаг 2: агрегация промежуточных результатов через второго агента.
        Реализует рекурсивное разбиение на пакеты по problems_per_packet элементов.
        Сохраняет результаты в agent_data/analysis_step_2.json.
        """
        self.current_stage = "Этап 2: Агрегация"
        step1_json_path = "agent_data/analysis_step_1.json"
        step2_json_path = "agent_data/analysis_step_2.json"

        if not os.path.exists(step1_json_path):
            self._log(1, f"  Файл {step1_json_path} не найден. Сначала выполните шаг 1.")
            return

        agent2 = AliceAIAgent(
            self.api_key_file, self.agent_id, self.system_prompt_file_2,
            self.base_url, self.model_name
        )

        with open(step1_json_path, 'r', encoding='utf-8') as f:
            try:
                step1_data = json.load(f)
            except json.JSONDecodeError:
                self._log(1, f"  Ошибка чтения файла {step1_json_path}.")
                return

        # Построить список items для рекурсии: каждый item содержит имя и список исходных индексов
        items = []
        for chat_entry in step1_data:
            problems = chat_entry.get('analisis_result', [])
            for prob in problems:
                name = prob.get('name', 'Без названия')
                items.append({
                    'name': name,
                    'indices': []  # будет заполнено позже
                })

        for idx, item in enumerate(items, start=1):
            item['indices'] = [idx]

        limit = self.problems_per_packet

        def aggregate_level(current_items: list, level: int = 0) -> list:
            """
            current_items: список словарей с полями name, indices
            возвращает список групп: [{'name': str, 'indices': list}]
            """
            if len(current_items) <= limit:
                # Формируем запрос без количества голосов
                lines = [f"{i} | {item['name']}" for i, item in enumerate(current_items, start=1)]
                user_query = "\n".join(lines)

                self._log(2, f"    Отправка пакета из {len(current_items)} элементов (уровень {level})")
                self._log(2, user_query[:200] + "..." if len(user_query) > 200 else user_query)

                final_parsed = None
                for attempt in range(self.max_retries):
                    try:
                        response2 = agent2.send_full_conversation(user_query, temperature=0.7, max_tokens=4096)
                        self._log(2, f"    Ответ агента (уровень {level}, попытка {attempt+1}):")
                        self._log(2, response2[:200] + "..." if len(response2) > 200 else response2)

                        final_parsed = DataProcessor.extract_from_response(response2)
                        if final_parsed is not None:
                            break
                        else:
                            self._log(2, f"    Попытка {attempt+1}: не удалось извлечь данные, повтор через 2 сек...")
                            time.sleep(2)
                    except Exception as e:
                        self._log(2, f"    Ошибка при попытке {attempt+1}: {e}")
                        if attempt < self.max_retries - 1:
                            self._log(2, "    Повтор через 5 сек...")
                            time.sleep(5)
                        else:
                            self._log(2, "    Достигнут лимит попыток. Возвращаем пустой результат.")
                            final_parsed = []
                if final_parsed is None:
                    final_parsed = []

                groups = []
                for group in final_parsed:
                    if not isinstance(group, dict) or 'name' not in group or 'complaints' not in group:
                        self._log(2, f"    Пропуск некорректной группы: {group}")
                        continue
                    name = group['name']
                    local_nums = group['complaints']  # список локальных номеров (1..len(current_items))
                    # Собираем все исходные индексы из соответствующих элементов
                    all_indices = []
                    for local in local_nums:
                        if 1 <= local <= len(current_items):
                            item = current_items[local-1]
                            all_indices.extend(item['indices'])
                        else:
                            self._log(2, f"    Предупреждение: локальный номер {local} вне диапазона")
                    groups.append({
                        'name': name,
                        'indices': all_indices
                    })
                return groups
            else:
                # Рекурсивный случай: разбиваем на пакеты по limit
                chunks = [current_items[i:i+limit] for i in range(0, len(current_items), limit)]
                all_groups = []
                for chunk in chunks:
                    chunk_groups = aggregate_level(chunk, level+1)
                    all_groups.extend(chunk_groups)
                # Рекурсивно обрабатываем список групп как новый уровень
                if len(all_groups) <= limit:
                    return aggregate_level(all_groups, level+1)
                else:
                    return aggregate_level(all_groups, level+1)

        final_groups = aggregate_level(items)

        # Преобразуем в формат step2: список словарей с 'name' и 'complaints' (indices)
        step2_result = [{'name': g['name'], 'complaints': g['indices']} for g in final_groups]

        os.makedirs(os.path.dirname(step2_json_path), exist_ok=True)
        with open(step2_json_path, 'w', encoding='utf-8') as f:
            json.dump(step2_result, f, ensure_ascii=False, indent=2)

        self._log(1, f"  Итоговый результат сохранён в файл: {step2_json_path}")
        self._log(2, "  " + "-" * 50, indent=1)

        if self.logging_level == 1 and main_pbar is not None:
            main_pbar.update(1)

    def step3_backward_mapping(self, main_pbar: Optional[tqdm] = None):
        """
        Шаг 3: обратный проход — сопоставление групп с исходными проблемами и участниками.
        Сохраняет результаты в agent_data/analysis_step_3.json.
        """
        self.current_stage = "Этап 3: Обратный проход"
        step1_json_path = "agent_data/analysis_step_1.json"
        step2_json_path = "agent_data/analysis_step_2.json"
        step3_json_path = "agent_data/analysis_step_3.json"

        # Проверим наличие необходимых файлов
        for path in [step1_json_path, step2_json_path]:
            if not os.path.exists(path):
                self._log(1, f"  Файл {path} не найден. Выполните предыдущие шаги.")
                return

        # 1. Загружаем исходные чаты из входного JSON-файла (без ограничений)
        try:
            chats = DataProcessor.load_chats_from_json(self.chats_file, max_chats=None)
        except Exception as e:
            self._log(1, f"  Ошибка загрузки исходного JSON: {e}")
            return

        # Строим словарь сообщений по чатам: messages_by_chat[chat_id][msg_id] = сообщение
        messages_by_chat = {}
        for chat in chats:
            chat_id = chat['chat_id']
            msg_dict = {msg['id']: msg for msg in chat['messages']}
            messages_by_chat[chat_id] = msg_dict

        # 2. Загружаем step1_data и строим список problem_entries
        with open(step1_json_path, 'r', encoding='utf-8') as f:
            step1_data = json.load(f)

        problem_entries = []  # список словарей: {'name': ..., 'chat_id': ..., 'complaints': [номера сообщений]}
        for chat_entry in step1_data:
            chat_id = chat_entry['chat_id']
            problems = chat_entry.get('analisis_result', [])
            for prob in problems:
                name = prob.get('name', 'Без названия')
                complaints = prob.get('complaints', [])
                problem_entries.append({
                    'name': name,
                    'chat_id': chat_id,
                    'complaints': complaints
                })

        # 3. Загружаем step2_data (группы)
        with open(step2_json_path, 'r', encoding='utf-8') as f:
            step2_data = json.load(f)

        # Если уровень логирования 1, создаём прогресс-бар по группам (position=1)
        if self.logging_level == 1:
            pbar = tqdm(total=len(step2_data), desc=self.current_stage, position=1, leave=False)

        # 4. Формируем результат шага 3 с добавлением participants (полная информация о сообщениях)
        step3_result = []
        for group in step2_data:
            group_name = group.get('name')
            problem_numbers = group.get('complaints', [])
            original_names = []
            participants = []
            seen = set()  # для избежания дублирования сообщений (по (chat_id, msg_id))
            for prob_num in problem_numbers:
                if 1 <= prob_num <= len(problem_entries):
                    prob_entry = problem_entries[prob_num-1]
                    original_names.append(prob_entry['name'])
                    chat_id = prob_entry['chat_id']
                    for msg_id in prob_entry['complaints']:
                        key = (chat_id, msg_id)
                        if key not in seen:
                            seen.add(key)
                            if chat_id in messages_by_chat and msg_id in messages_by_chat[chat_id]:
                                # Добавляем полное сообщение, удалив временное поле _dt
                                msg_copy = messages_by_chat[chat_id][msg_id].copy()
                                if '_dt' in msg_copy:
                                    del msg_copy['_dt']
                                participants.append(msg_copy)
                            else:
                                self._log(2, f"    Предупреждение: сообщение {msg_id} в чате {chat_id} не найдено", indent=2)
                else:
                    self._log(2, f"    Предупреждение: номер проблемы {prob_num} вне диапазона (всего {len(problem_entries)})", indent=2)
            # Правильный подсчёт голосов – количество уникальных участников
            total_votes = len(participants)
            step3_result.append({
                "name": group_name,
                "total_votes": total_votes,
                "complaints": original_names,
                "participants": participants
            })
            if self.logging_level == 1:
                pbar.update(1)

        if self.logging_level == 1:
            pbar.close()

        os.makedirs(os.path.dirname(step3_json_path), exist_ok=True)
        with open(step3_json_path, 'w', encoding='utf-8') as f:
            json.dump(step3_result, f, ensure_ascii=False, indent=2)

        self._log(1, f"  Результат третьего шага сохранён в файл: {step3_json_path}")
        self._log(2, "  Содержимое (группы с исходными названиями проблем и списком участников):", indent=1)
        # Для краткости выведем только первые несколько групп при уровне 2
        if self.logging_level >= 2:
            print(json.dumps(step3_result[:2], ensure_ascii=False, indent=2) + "...")
        self._log(2, "  " + "-" * 50, indent=1)

        # Обновляем основной прогресс-бар после завершения шага
        if self.logging_level == 1 and main_pbar is not None:
            main_pbar.update(1)

    def run(self):
        """Запуск шагов в соответствии с настройками с замером времени."""
        start_time = time.time()
        self._log(1, "Запуск анализатора")
        self._log(1, "=" * 60)

        # Подсчитываем количество активных шагов для общего прогресс-бара
        total_steps = 0
        if self.step1_enabled:
            total_steps += 1
        if self.step2_enabled:
            total_steps += 1
        if self.step3_enabled:
            total_steps += 1

        # Если уровень логирования 1 и есть хотя бы один шаг, создаём общий прогресс-бар (position=0)
        main_pbar = None
        if self.logging_level == 1 and total_steps > 0:
            main_pbar = tqdm(total=total_steps, desc="Общий прогресс (3 этапа)", position=0)

        # Запуск шагов с передачей основного прогресс-бара
        if self.step1_enabled:
            self.step1_analyze_chats(main_pbar)
        else:
            self._log(1, "Шаг 1 отключён в конфигурации")

        if self.step2_enabled:
            self.step2_aggregate_results(main_pbar)
        else:
            self._log(1, "Шаг 2 отключён в конфигурации")

        if self.step3_enabled:
            self.step3_backward_mapping(main_pbar)
        else:
            self._log(1, "Шаг 3 отключён в конфигурации")

        if main_pbar is not None:
            main_pbar.close()

        elapsed = time.time() - start_time
        self._log(1, "=" * 60)
        self._log(1, f"Анализ завершён за {elapsed:.2f} секунд")


def load_config(config_path: str = "config.json") -> dict:
    """Загружает конфигурационный файл."""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return config


if __name__ == "__main__":
    # Загрузка конфигурации
    try:
        config = load_config()
    except Exception as e:
        print(f"Ошибка загрузки конфигурации: {e}")
        sys.exit(1)

    # Получение параметров анализатора
    analyzer_config = config.get("analyzer", {})
    if not analyzer_config.get("enabled", True):
        print("Анализатор отключён в конфигурации.")
        sys.exit(0)

    prefs = analyzer_config.get("preferences", {})
    # Добавляем путь к файлу чатов из shared
    prefs["chats_file"] = config.get("shared", {}).get("chats_file", "agent_data/chats.json")

    # Создание и запуск анализатора
    analyzer = DataAnalyzer(prefs)
    analyzer.run()