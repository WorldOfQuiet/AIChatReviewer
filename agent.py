import json
import requests
import re
import os
import time
import sys

class AliceAIAgent:
    def __init__(self, api_key_file_path: str, agent_id: str, system_prompt_file_path: str):
        """
        Initialize the agent for working with Alice AI LLM via Yandex AI Studio.

        :param api_key_file_path: path to the file containing the API key in JSON format.
        :param agent_id: catalog identifier (not model) — used as part of modelUri.
        :param system_prompt_file_path: path to the file with the system prompt.
        """
        self.agent_id = agent_id
        self.api_key = self._load_api_key(api_key_file_path)
        self.base_url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
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
        Send full conversation text to the Alice AI LLM agent and return the response.

        :param conversation_text: full conversation text (loaded from file).
        :param temperature: generation randomness parameter (0.0–1.0).
        :param max_tokens: maximum number of tokens in the response.
        :return: agent's response text.
        """
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json"
        }

        # Construct modelUri according to the format gpt://<catalog_id>/aliceai-llm/latest
        model_uri = f"gpt://{self.agent_id}/aliceai-llm/latest"

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
                    {"id": 0, "text": "...", "author": "...", "media": [...], "reply_to": -1, "date": 123456},
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
            if max_messages_per_chat is not None and max_messages_per_chat > 0:
                # берём последние max_messages_per_chat сообщений
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
    def group_messages_by_reply_chain(messages: list, isolated_packet_size: int = None) -> list:
        """
        Group messages based on reply_to chains (transitive closure).
        Returns a list of packets, where each packet is a list of messages (sorted by id).
        Handles missing parent messages (due to loading only a subset) by treating them as roots.

        :param messages: list of message dictionaries.
        :param isolated_packet_size: if given, isolated messages (with no reply chain) are split into
                                      packets of this size (last messages first). If None, all isolated
                                      messages go into one packet.
        :return: list of packets, each packet is a list of messages.
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

        # Build packets: chain groups become separate packets
        packets = []
        for ids in chain_groups:
            ids_sorted = sorted(ids)
            packet_msgs = [msg_dict[i] for i in ids_sorted]
            packets.append(packet_msgs)

        # Split isolated messages into packets of size isolated_packet_size
        if isolated_ids:
            isolated_ids_sorted = sorted(isolated_ids)
            if isolated_packet_size is not None and isolated_packet_size > 0:
                # Split into chunks from the end (to keep newest messages together)
                for i in range(0, len(isolated_ids_sorted), isolated_packet_size):
                    chunk_ids = isolated_ids_sorted[i:i+isolated_packet_size]
                    packet_msgs = [msg_dict[i] for i in chunk_ids]
                    packets.append(packet_msgs)
            else:
                # All isolated in one packet
                packet_msgs = [msg_dict[i] for i in isolated_ids_sorted]
                packets.append(packet_msgs)

        return packets


class DataAnalyzer:
    """Класс для выполнения многошагового анализа чатов."""

    def __init__(self, config: dict):
        """
        Инициализация анализатора на основе конфигурации.

        :param config: словарь с настройками из analyzer.preferences.
        """
        self.config = config
        self.logging_level = config.get('logging_level', 2)
        self.max_chats = config.get('max_chats', 1)
        self.max_messages_per_chat = config.get('max_messages_per_chat', 2000)
        self.max_packets = config.get('max_packets', 10)
        self.max_packet_messages = config.get('max_packet_messages', 50)
        self.isolated_packet_size = config.get('isolated_packet_size', 400)
        self.max_retries = config.get('max_retries', 3)

        self.api_key_file = config.get('api_key_file')
        self.agent_id = config.get('agent_id')
        self.system_prompt_file = config.get('system_prompt_file')
        self.system_prompt_file_2 = config.get('system_prompt_file_2')
        self.chats_file = config.get('chats_file')  # путь к файлу с чатами

        # Шаги, которые нужно выполнить
        steps_config = config.get('steps', {})
        self.step1_enabled = steps_config.get('step1_analyze_chats', True)
        self.step2_enabled = steps_config.get('step2_aggregate_results', True)
        self.step4_enabled = steps_config.get('step4_backward_mapping', True)
        # step3 игнорируем

        self._log(1, "Анализатор инициализирован")

    def _log(self, level: int, message: str):
        """Логирование с учётом уровня."""
        if self.logging_level >= level:
            print(message)

    def step1_analyze_chats(self):
        """
        Шаг 1: анализ исходных чатов с группировкой по цепочкам ответов.
        Сохраняет результаты в agent_data/analysis_step_1.json.
        """
        self._log(1, "Запуск шага 1: анализ чатов")
        step1_json_path = "agent_data/analysis_step_1.json"

        if self.chats_file is None:
            self._log(1, "Ошибка: не указан путь к файлу чатов (chats_file).")
            return

        # Load all chats from the input JSON file
        try:
            chats = DataProcessor.load_chats_from_json(
                self.chats_file,
                max_messages_per_chat=self.max_messages_per_chat,
                max_chats=self.max_chats
            )
        except Exception as e:
            self._log(1, f"Ошибка загрузки JSON: {e}")
            return

        if not chats:
            self._log(1, "Нет данных для обработки.")
            return

        self._log(1, f"Загружено чатов: {len(chats)}")
        self._log(2, "-" * 50)

        # Create agent instance for chat analysis (reused for all chats)
        agent = AliceAIAgent(self.api_key_file, self.agent_id, self.system_prompt_file)

        # List to collect all interim entries from all chats and packets
        interim_entries = []

        # Process each chat
        for chat in chats:
            chat_id = chat['chat_id']
            chat_name = chat['chat_name']
            messages = chat['messages']

            # Group messages by reply chains, splitting isolated messages into packets of isolated_packet_size
            all_packets = DataProcessor.group_messages_by_reply_chain(messages, self.isolated_packet_size)
            self._log(2, f"\nЧат '{chat_name}' (ID: {chat_id}) исходно разбит на {len(all_packets)} пакетов.")

            # Apply max_packets limit (take last packets)
            if self.max_packets is not None and self.max_packets > 0 and len(all_packets) > self.max_packets:
                packets_to_process = all_packets[-self.max_packets:]
                self._log(2, f"  Ограничение max_packets={self.max_packets}: взято последних {len(packets_to_process)} пакетов.")
            else:
                packets_to_process = all_packets

            for idx, packet_msgs in enumerate(packets_to_process, start=1):
                # Apply max_packet_messages limit to this packet (take last messages)
                if self.max_packet_messages is not None and self.max_packet_messages > 0 and len(packet_msgs) > self.max_packet_messages:
                    packet_msgs = packet_msgs[-self.max_packet_messages:]
                    self._log(2, f"    Пакет {idx}: ограничение max_packet_messages={self.max_packet_messages}, взято последних {len(packet_msgs)} сообщений.")

                # Convert packet messages to text format for the agent
                packet_lines = [DataProcessor.format_message_for_agent(m) for m in packet_msgs]
                packet_text = "\n".join(packet_lines)

                self._log(2, f"\n--- Обработка пакета {idx} (чат: {chat_name}) ---")
                self._log(2, "Текст пакета (первые 500 символов):")
                self._log(2, packet_text[:500] + "..." if len(packet_text) > 500 else packet_text)
                self._log(2, "-" * 50)

                # Retry loop
                parsed_data = None
                for attempt in range(self.max_retries):
                    try:
                        # Send this packet to the agent
                        response = agent.send_full_conversation(packet_text, temperature=0.7, max_tokens=4096)
                        self._log(2, "Ответ агента:")
                        self._log(2, response)

                        # Parse the response – None означает ошибку извлечения
                        parsed_data = DataProcessor.extract_from_response(response)
                        if parsed_data is not None:
                            break  # успешно получили данные (даже пустой список)
                        else:
                            self._log(2, f"Попытка {attempt+1}: не удалось извлечь данные (отсутствуют теги или невалидный JSON). Повтор через 2 сек...")
                            time.sleep(2)
                    except Exception as e:
                        self._log(2, f"Ошибка при попытке {attempt+1}: {e}")
                        if attempt < self.max_retries - 1:
                            self._log(2, "Повтор через 5 сек...")
                            time.sleep(5)
                        else:
                            self._log(2, "Достигнут лимит попыток. Пропускаем пакет.")
                            parsed_data = None
                if parsed_data is None:
                    self._log(2, "Не удалось получить корректный ответ для пакета, пропускаем.")
                    continue

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
                        # If structure is unexpected, keep as is or skip
                        problems_with_count.append(problem)

                # Create entry for this packet
                part_chat_name = f"{chat_name} (пакет {idx})"
                entry = {
                    "chat_id": chat_id,
                    "chat_name": part_chat_name,
                    "analisis_result": problems_with_count
                }
                interim_entries.append(entry)

        # Write all interim entries to the interim JSON file (overwrite)
        os.makedirs(os.path.dirname(step1_json_path), exist_ok=True)
        with open(step1_json_path, 'w', encoding='utf-8') as f:
            json.dump(interim_entries, f, ensure_ascii=False, indent=2)

        self._log(1, f"Все промежуточные результаты сохранены в файл: {step1_json_path}")
        self._log(2, "-" * 50)

    def step2_aggregate_results(self):
        """
        Шаг 2: агрегация промежуточных результатов через второго агента.
        Сохраняет результаты в agent_data/analysis_step_2.json.
        """
        self._log(1, "Запуск шага 2: агрегация результатов")
        step1_json_path = "agent_data/analysis_step_1.json"
        step2_json_path = "agent_data/analysis_step_2.json"

        if not os.path.exists(step1_json_path):
            self._log(1, f"Файл {step1_json_path} не найден. Сначала выполните шаг 1.")
            return

        agent2 = AliceAIAgent(self.api_key_file, self.agent_id, self.system_prompt_file_2)

        # Load all entries from step1 file
        with open(step1_json_path, 'r', encoding='utf-8') as f:
            try:
                step1_data = json.load(f)
            except json.JSONDecodeError:
                self._log(1, f"Ошибка чтения файла {step1_json_path}.")
                return

        # Build user query lines: "number | problem name | vote count"
        lines = []
        problem_index = 1
        for chat_entry in step1_data:
            problems = chat_entry.get('analisis_result', [])
            for prob in problems:
                name = prob.get('name', 'Без названия')
                count = prob.get('count', 0)
                lines.append(f"{problem_index} | {name} | {count}")
                problem_index += 1

        if not lines:
            self._log(1, "Нет данных для финального анализа.")
            return

        user_query = "\n".join(lines)
        self._log(1, "\nЗапрос второму агенту:")
        self._log(1, user_query)
        self._log(2, "-" * 50)

        # Retry loop
        final_parsed = None
        for attempt in range(self.max_retries):
            try:
                # Send to second agent
                response2 = agent2.send_full_conversation(user_query, temperature=0.7, max_tokens=4096)
                self._log(2, "Ответ второго агента:")
                self._log(2, response2)

                # Extract final result – None означает ошибку извлечения
                final_parsed = DataProcessor.extract_from_response(response2)
                if final_parsed is not None:
                    break
                else:
                    self._log(2, f"Попытка {attempt+1}: не удалось извлечь данные (отсутствуют теги или невалидный JSON). Повтор через 2 сек...")
                    time.sleep(2)
            except Exception as e:
                self._log(2, f"Ошибка при попытке {attempt+1}: {e}")
                if attempt < self.max_retries - 1:
                    self._log(2, "Повтор через 5 сек...")
                    time.sleep(5)
                else:
                    self._log(2, "Достигнут лимит попыток. Сохраняем пустой результат.")
                    final_parsed = []

        if final_parsed is None:
            final_parsed = []

        # Save to step2 JSON file (overwrite)
        os.makedirs(os.path.dirname(step2_json_path), exist_ok=True)
        with open(step2_json_path, 'w', encoding='utf-8') as f:
            json.dump(final_parsed, f, ensure_ascii=False, indent=2)

        self._log(1, f"Итоговый результат сохранён в файл: {step2_json_path}")
        self._log(2, "-" * 50)

    def step4_backward_mapping(self):
        """
        Шаг 4: обратный проход — сопоставление групп с исходными проблемами и участниками.
        Сохраняет результаты в agent_data/analysis_step_4.json.
        """
        self._log(1, "Запуск шага 4: обратный проход")
        step1_json_path = "agent_data/analysis_step_1.json"
        step2_json_path = "agent_data/analysis_step_2.json"
        step4_json_path = "agent_data/analysis_step_4.json"

        # Проверим наличие необходимых файлов
        for path in [step1_json_path, step2_json_path]:
            if not os.path.exists(path):
                self._log(1, f"Файл {path} не найден. Выполните предыдущие шаги.")
                return

        # 1. Загружаем исходные чаты из входного JSON-файла (без ограничений)
        try:
            chats = DataProcessor.load_chats_from_json(self.chats_file, max_chats=None)
        except Exception as e:
            self._log(1, f"Ошибка загрузки исходного JSON: {e}")
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

        # 4. Формируем результат шага 4 с добавлением participants (полная информация о сообщениях)
        step4_result = []
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
                                # Добавляем полное сообщение
                                participants.append(messages_by_chat[chat_id][msg_id])
                            else:
                                self._log(2, f"Предупреждение: сообщение {msg_id} в чате {chat_id} не найдено")
                else:
                    self._log(2, f"Предупреждение: номер проблемы {prob_num} вне диапазона (всего {len(problem_entries)})")
            # Правильный подсчёт голосов – количество уникальных участников
            total_votes = len(participants)
            step4_result.append({
                "name": group_name,
                "total_votes": total_votes,
                "complaints": original_names,
                "participants": participants
            })

        os.makedirs(os.path.dirname(step4_json_path), exist_ok=True)
        with open(step4_json_path, 'w', encoding='utf-8') as f:
            json.dump(step4_result, f, ensure_ascii=False, indent=2)

        self._log(1, f"Результат четвёртого шага сохранён в файл: {step4_json_path}")
        self._log(2, "Содержимое (группы с исходными названиями проблем и списком участников):")
        # Для краткости выведем только первые несколько групп при уровне 2
        if self.logging_level >= 2:
            print(json.dumps(step4_result[:2], ensure_ascii=False, indent=2) + "...")
        self._log(2, "-" * 50)

    def run(self):
        """Запуск шагов в соответствии с настройками."""
        if self.step1_enabled:
            self.step1_analyze_chats()
        else:
            self._log(1, "Шаг 1 отключён в конфигурации")

        if self.step2_enabled:
            self.step2_aggregate_results()
        else:
            self._log(1, "Шаг 2 отключён в конфигурации")

        # Шаг 3 пропущен
        if self.step4_enabled:
            self.step4_backward_mapping()
        else:
            self._log(1, "Шаг 4 отключён в конфигурации")


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