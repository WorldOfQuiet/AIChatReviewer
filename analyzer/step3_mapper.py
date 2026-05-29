import json
import os
from typing import Optional
from tqdm import tqdm

from .base_analyzer import BaseAnalyzer
from core.data_processor import DataProcessor


class Step3Mapper(BaseAnalyzer):
    """Шаг 3: обратный проход — сопоставление групп с исходными проблемами и участниками."""

    def step3_backward_mapping(self, main_pbar: Optional[tqdm] = None):
        """Шаг 3: обратный проход — сопоставление групп с исходными проблемами и участниками."""
        self.current_stage = "Этап 3: Обратный проход"
        step1_json_path = "agent_data/analysis_step_1.json"
        step2_json_path = "agent_data/analysis_step_2.json"
        step3_json_path = "agent_data/analysis_step_3.json"

        # Проверка наличия файлов
        for path in [step1_json_path, step2_json_path]:
            if not os.path.exists(path):
                self._log(1, f"  Файл {path} не найден. Выполните предыдущие шаги.")
                return

        # Загрузка исходных чатов (полных) и построение словаря сообщений
        chats = self._load_full_chats()
        if chats is None:
            return
        messages_by_chat = self._build_messages_dict(chats)

        # Загрузка step1 и построение problem_entries
        step1_data = self._load_step1_data(step1_json_path)
        if step1_data is None:
            return
        problem_entries = self._build_problem_entries(step1_data)

        # Загрузка step2 (групп)
        with open(step2_json_path, 'r', encoding='utf-8') as f:
            step2_data = json.load(f)

        # Формирование результата шага 3
        step3_result = self._build_step3_result(step2_data, problem_entries, messages_by_chat)

        # Сохранение результата
        self._save_step3_results(step3_json_path, step3_result)

        if self.logging_level == 1 and main_pbar:
            main_pbar.update(1)

    def _load_full_chats(self) -> Optional[list]:
        """Загрузить исходные чаты из JSON без ограничений."""
        try:
            return DataProcessor.load_chats_from_json(self.chats_file, max_chats=0)
        except Exception as e:
            self._log(1, f"  Ошибка загрузки исходного JSON: {e}")
            return None

    def _build_messages_dict(self, chats: list) -> dict:
        """Построить словарь сообщений по чатам: {chat_id: {msg_id: msg}}."""
        messages_by_chat = {}
        for chat in chats:
            chat_id = chat['chat_id']
            msg_dict = {msg['id']: msg for msg in chat['messages']}
            messages_by_chat[chat_id] = msg_dict
        return messages_by_chat

    def _load_step1_data(self, path: str) -> Optional[list]:
        """Загрузить данные шага 1 из JSON."""
        with open(path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                self._log(1, f"  Ошибка чтения файла {path}.")
                return None

    def _build_problem_entries(self, step1_data: list) -> list:
        """Построить список problem_entries из данных шага 1."""
        entries = []
        for chat_entry in step1_data:
            chat_id = chat_entry['chat_id']
            problems = chat_entry.get('analisis_result', [])
            for prob in problems:
                if not isinstance(prob, dict):
                    continue
                name = prob.get('name', 'Без названия')
                complaints = prob.get('complaints', [])
                entries.append({
                    'name': name,
                    'chat_id': chat_id,
                    'complaints': complaints
                })
        return entries

    def _build_step3_result(self, step2_data: list, problem_entries: list,
                            messages_by_chat: dict) -> list:
        """Сформировать результат шага 3 для каждой группы."""
        result = []
        if self.logging_level == 1:
            pbar = tqdm(total=len(step2_data), desc=self.current_stage, position=1, leave=False)
        else:
            pbar = None

        for group in step2_data:
            group_name = group.get('name')
            problem_numbers = group.get('complaints', [])
            original_names = []
            participants = []
            seen = set()

            # Сбор оригинальных названий и участников
            for prob_num in problem_numbers:
                if 1 <= prob_num <= len(problem_entries):
                    prob_entry = problem_entries[prob_num-1]
                    original_names.append(prob_entry['name'])
                    chat_id = prob_entry['chat_id']
                    for msg_id in prob_entry['complaints']:
                        key = (chat_id, msg_id)
                        if key not in seen:
                            seen.add(key)
                            msg = messages_by_chat.get(chat_id, {}).get(msg_id)
                            if msg:
                                msg_copy = msg.copy()
                                msg_copy.pop('_dt', None)
                                participants.append(msg_copy)
                            else:
                                self._log(2, f"    Предупреждение: сообщение {msg_id} в чате {chat_id} не найдено", indent=2)
                else:
                    self._log(2, f"    Предупреждение: номер проблемы {prob_num} вне диапазона", indent=2)

            total_votes = len(participants)
            result.append({
                "name": group_name,
                "total_votes": total_votes,
                "complaints": original_names,
                "participants": participants
            })
            if pbar:
                pbar.update(1)

        if pbar:
            pbar.close()
        return result

    def _save_step3_results(self, path: str, data: list):
        """Сохранить результаты шага 3 в JSON."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._log(1, f"  Результат третьего шага сохранён в файл: {path}")
        self._log(2, "  Содержимое (первые 2 группы):", indent=1)
        if self.logging_level >= 2:
            print(json.dumps(data[:2], ensure_ascii=False, indent=2) + "...")
        self._log(2, "  " + "-" * 50, indent=1)