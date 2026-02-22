import json
import requests
import re
import os
import glob

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

        response = requests.post(self.base_url, headers=headers, json=payload)
        result = response.json()
        return result['result']['alternatives'][0]['message']['text']


class ResultParser:
    @staticmethod
    def extract_from_response(response_text: str) -> list:
        """
        Extract data between <result> tags from the model response.

        :param response_text: full response text from the AI model.
        :return: parsed JSON data as a list of dictionaries.
        """
        # Find content between <result> and </result>
        match = re.search(r'<result>(.*?)</result>', response_text, re.DOTALL)
        if not match:
            return []

        json_content = match.group(1).strip()

        try:
            parsed_data = json.loads(json_content)
            return parsed_data
        except json.JSONDecodeError:
            return []

    @staticmethod
    def load_chat_from_json(file_path: str) -> dict:
        """
        Load chat data from a JSON file containing chat_id, chat_name, and messages.

        Expected JSON structure:
        {
            "chat_id": 0,
            "chat_name": "Название чата",
            "messages": "строка с историей сообщений"
        }

        :param file_path: path to the JSON file.
        :return: dictionary with keys chat_id, chat_name, messages.
        :raises ValueError: if required keys are missing.
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        required_keys = ['chat_id', 'chat_name', 'messages']
        for key in required_keys:
            if key not in data:
                raise ValueError(f"Missing required key '{key}' in {file_path}")

        return data

    @staticmethod
    def split_conversation(conversation_text: str, chunk_size: int = 400) -> list:
        """
        Split the conversation text into chunks by number of messages (lines).

        :param conversation_text: full conversation text.
        :param chunk_size: number of messages per chunk.
        :return: list of strings, each containing a chunk of the conversation.
        """
        lines = conversation_text.strip().split('\n')
        chunks = []
        for i in range(0, len(lines), chunk_size):
            chunk_lines = lines[i:i+chunk_size]
            chunks.append('\n'.join(chunk_lines))
        return chunks


def load_conversation_text(file_path: str) -> str:
    """
    Load full conversation text from a plain text file.
    (Kept for backward compatibility.)

    :param file_path: path to the file containing conversation text.
    :return: full conversation text as a string.
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        conversation_text = file.read().strip()
    return conversation_text


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


if __name__ == "__main__":
    # Path to the API key file
    api_key_file = "api_key.json"
    # Catalog identifier (e.g., b1ghrgitp2eqakb9c44o)
    agent_id = "b1ghrgitp2eqakb9c44o"
    # Path to the system prompt file for the first agent
    system_prompt_file = "agent_data/analysis_of_chat(instructions_3).txt"
    # Directory containing chat JSON files
    chats_directory = "pre-test/chats/"

    # =========================================================================
    # ШАГ 1: Анализ исходных чатов (разбивка на части, отправка агенту)
    # =========================================================================
    # Этот блок закомментирован, так как предполагается, что analysis_step_1.json уже существует.
    # Для повторного использования достаточно раскомментировать код.
    """
    # Find all JSON files in the chats directory
    chat_files = glob.glob(os.path.join(chats_directory, "*.json"))
    if not chat_files:
        print(f"В директории {chats_directory} не найдено JSON-файлов.")
        exit(1)

    print(f"Найдено файлов для обработки: {len(chat_files)}")
    print("-" * 50)

    # Create agent instance for chat analysis (reused for all chats)
    agent = AliceAIAgent(api_key_file, agent_id, system_prompt_file)

    # List to collect all interim entries from all chats and chunks
    interim_entries = []

    # Process each chat file
    for chat_file in chat_files:
        print(f"\nОбработка файла: {chat_file}")
        try:
            chat_data = ResultParser.load_chat_from_json(chat_file)
        except ValueError as e:
            print(f"Ошибка загрузки JSON: {e}")
            continue  # skip this file, continue with next

        original_chat_id = chat_data['chat_id']
        original_chat_name = chat_data['chat_name']
        full_conversation = chat_data['messages']

        # Split conversation into chunks of 400 messages
        chunks = ResultParser.split_conversation(full_conversation, chunk_size=400)
        print(f"Диалог разбит на {len(chunks)} частей.")

        for idx, chunk_text in enumerate(chunks, start=1):
            print(f"\n--- Обработка части {idx} (чат: {original_chat_name}) ---")
            print("Текст части (первые 500 символов):")
            print(chunk_text[:500] + "..." if len(chunk_text) > 500 else chunk_text)
            print("-" * 50)

            # Send this chunk to the agent
            response = agent.send_full_conversation(chunk_text, temperature=0.7, max_tokens=4096)
            print("Ответ агента:")
            print(response)

            # Parse the response
            parsed_data = ResultParser.extract_from_response(response)

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

            # Create entry for this chunk
            part_chat_name = f"{original_chat_name} (часть {idx})"
            entry = {
                "chat_id": original_chat_id,
                "chat_name": part_chat_name,
                "analisis_result": problems_with_count
            }
            interim_entries.append(entry)

    # Write all interim entries to the interim JSON file (overwrite)
    step1_json_path = "agent_data/analysis_step_1.json"
    os.makedirs(os.path.dirname(step1_json_path), exist_ok=True)
    with open(step1_json_path, 'w', encoding='utf-8') as f:
        json.dump(interim_entries, f, ensure_ascii=False, indent=2)

    print(f"\nВсе промежуточные результаты сохранены в файл: {step1_json_path}")
    print("-" * 50)
    """

    # =========================================================================
    # ШАГ 2: Агрегация промежуточных результатов через второго агента
    # =========================================================================
    # Этот блок также закомментирован, так как предполагается, что analysis_step_2.json уже существует.
    """
    system_prompt_file_2 = "agent_data/analysis_of_results.txt"
    agent2 = AliceAIAgent(api_key_file, agent_id, system_prompt_file_2)

    # Load all entries from step1 file
    step1_json_path = "agent_data/analysis_step_1.json"
    if not os.path.exists(step1_json_path):
        print("Промежуточный файл не найден. Финальный анализ не выполнен.")
        exit(0)

    with open(step1_json_path, 'r', encoding='utf-8') as f:
        try:
            step1_data = json.load(f)
        except json.JSONDecodeError:
            print("Ошибка чтения промежуточного файла.")
            exit(1)

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
        print("Нет данных для финального анализа.")
        exit(0)

    user_query = "\n".join(lines)
    print("\nЗапрос второму агенту:")
    print(user_query)
    print("-" * 50)

    # Send to second agent
    response2 = agent2.send_full_conversation(user_query, temperature=0.7, max_tokens=4096)
    print("Ответ второго агента:")
    print(response2)

    # Extract final result
    final_parsed = ResultParser.extract_from_response(response2)

    # Save to step2 JSON file (overwrite)
    step2_json_path = "agent_data/analysis_step_2.json"
    with open(step2_json_path, 'w', encoding='utf-8') as f:
        json.dump(final_parsed, f, ensure_ascii=False, indent=2)

    print(f"Итоговый результат сохранён в файл: {step2_json_path}")
    print("-" * 50)
    """

    # =========================================================================
    # ШАГ 3: Подсчёт итоговых голосов по группам проблем (сумма элементов списка complaints)
    # =========================================================================
    # Загружаем результаты второго шага (список проблем с полями name и complaints)

    step2_json_path = "agent_data/analysis_step_2.json"
    if not os.path.exists(step2_json_path):
        print(f"Файл {step2_json_path} не найден. Выполните сначала шаги 1 и 2.")
        exit(1)

    with open(step2_json_path, 'r', encoding='utf-8') as f:
        try:
            step2_data = json.load(f)
        except json.JSONDecodeError:
            print(f"Ошибка чтения файла {step2_json_path}.")
            exit(1)

    # Ожидаем, что step2_data — это список объектов с полями 'name' и 'complaints'
    vote_summary = {}

    if isinstance(step2_data, list):
        for item in step2_data:
            if isinstance(item, dict):
                name = item.get('name', 'Без названия')
                complaints = item.get('complaints')
                # Проверяем, что complaints — список, иначе считаем сумму 0
                if isinstance(complaints, list):
                    vote_summary[name] = vote_summary.get(name, 0) + sum(complaints)
                else:
                    # Если complaints нет или не список, добавляем 0 (или пропускаем)
                    # Чтобы не потерять проблему, добавим с нулём, но можно и пропустить.
                    vote_summary[name] = vote_summary.get(name, 0)
    else:
        # Если step2_data — не список (например, уже словарь), просто сохраняем как есть
        vote_summary = step2_data

    # Сохраняем результат третьего шага
    step3_json_path = "agent_data/analysis_step_3.json"
    os.makedirs(os.path.dirname(step3_json_path), exist_ok=True)
    with open(step3_json_path, 'w', encoding='utf-8') as f:
        json.dump(vote_summary, f, ensure_ascii=False, indent=2)

    print(f"Результат третьего шага сохранён в файл: {step3_json_path}")
    print("Содержимое (сумма элементов complaints по каждой проблеме):")
    print(json.dumps(vote_summary, ensure_ascii=False, indent=2))
    print("-" * 50)

    # =========================================================================
    # ШАГ 4: Обратный проход — сопоставление групп с исходными проблемами и участниками
    # =========================================================================

    # 1. Загружаем все исходные чаты из директории, чтобы иметь доступ к сообщениям
    chat_files = glob.glob(os.path.join(chats_directory, "*.json"))
    messages_by_chat = {}  # ключ: chat_id, значение: словарь {номер_сообщения: словарь с данными}
    for chat_file in chat_files:
        try:
            chat_data = ResultParser.load_chat_from_json(chat_file)
        except Exception as e:
            print(f"Ошибка загрузки {chat_file}: {e}")
            continue
        chat_id = chat_data['chat_id']
        messages_str = chat_data['messages']
        lines = messages_str.strip().split('\n')
        msg_dict = {}
        for line in lines:
            if line.strip():
                parsed = parse_message_line(line)
                if parsed['num'] != -1:
                    msg_dict[parsed['num']] = parsed
        messages_by_chat[chat_id] = msg_dict

    # 2. Загружаем step1_data и строим список problem_entries с chat_id и complaints
    step1_json_path = "agent_data/analysis_step_1.json"
    if not os.path.exists(step1_json_path):
        print(f"Файл {step1_json_path} не найден. Невозможно выполнить шаг 4.")
        exit(1)

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
    step2_json_path = "agent_data/analysis_step_2.json"
    with open(step2_json_path, 'r', encoding='utf-8') as f:
        step2_data = json.load(f)

    # 4. Загружаем step3_data (суммы голосов) – уже есть в переменной vote_summary, но перечитаем для надёжности
    step3_json_path = "agent_data/analysis_step_3.json"
    with open(step3_json_path, 'r', encoding='utf-8') as f:
        step3_data = json.load(f)

    # 5. Формируем результат шага 4 с добавлением participants
    step4_result = []
    for group in step2_data:
        group_name = group.get('name')
        problem_numbers = group.get('complaints', [])
        # Собираем названия исходных проблем и список участников
        original_names = []
        participants = []
        seen = set()  # для избежания дублирования сообщений (по (chat_id, msg_num))
        for prob_num in problem_numbers:
            if 1 <= prob_num <= len(problem_entries):
                prob_entry = problem_entries[prob_num-1]
                original_names.append(prob_entry['name'])
                chat_id = prob_entry['chat_id']
                for msg_num in prob_entry['complaints']:
                    key = (chat_id, msg_num)
                    if key not in seen:
                        seen.add(key)
                        # Ищем сообщение в соответствующем чате
                        if chat_id in messages_by_chat and msg_num in messages_by_chat[chat_id]:
                            participants.append(messages_by_chat[chat_id][msg_num])
                        else:
                            print(f"Предупреждение: сообщение {msg_num} в чате {chat_id} не найдено")
            else:
                print(f"Предупреждение: номер проблемы {prob_num} вне диапазона (всего {len(problem_entries)})")
        total_votes = step3_data.get(group_name, 0)
        step4_result.append({
            "name": group_name,
            "total_votes": total_votes,
            "complaints": original_names,
            "participants": participants
        })

    # Сохраняем шаг 4
    step4_json_path = "agent_data/analysis_step_4.json"
    with open(step4_json_path, 'w', encoding='utf-8') as f:
        json.dump(step4_result, f, ensure_ascii=False, indent=2)

    print(f"Результат четвёртого шага сохранён в файл: {step4_json_path}")
    print("Содержимое (группы с исходными названиями проблем и списком участников):")
    # Для краткости выведем только первые несколько групп
    print(json.dumps(step4_result[:2], ensure_ascii=False, indent=2) + "...")
    print("-" * 50)