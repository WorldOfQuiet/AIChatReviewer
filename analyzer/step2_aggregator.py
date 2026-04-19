import json
import os
import time
from typing import Optional
from tqdm import tqdm

from .base_analyzer import BaseAnalyzer
from core.api_client import AliceAIAgent
from core.data_processor import DataProcessor


class Step2Aggregator(BaseAnalyzer):
    """Шаг 2: агрегация промежуточных результатов через второго агента."""

    def step2_aggregate_results(self, main_pbar: Optional[tqdm] = None):
        """Шаг 2: агрегация промежуточных результатов через второго агента."""
        self.current_stage = "Этап 2: Агрегация"
        step1_json_path = "agent_data/analysis_step_1.json"
        step2_json_path = "agent_data/analysis_step_2.json"

        # Проверка существования файла шага 1
        if not os.path.exists(step1_json_path):
            self._log(1, f"  Файл {step1_json_path} не найден. Сначала выполните шаг 1.")
            return

        # Загрузка данных шага 1
        step1_data = self._load_step1_data(step1_json_path)
        if step1_data is None:
            return

        # Создание списка items для агрегации
        items = self._build_items_from_step1(step1_data)

        # Создание агента для агрегации
        agent2 = AliceAIAgent(self.api_key_file, self.agent_id, self.system_prompt_file_2,
                              self.base_url, self.model_name)

        limit = self.problems_per_packet
        ungrouped_indices = []  # накопитель для неклассифицированных

        # Рекурсивная агрегация
        final_other_groups = self._aggregate_level(items, limit, agent2, ungrouped_indices, level=0)

        # Формирование итогового результата
        step2_result = self._build_step2_result(final_other_groups, ungrouped_indices)

        # Сохранение результата шага 2
        self._save_step2_results(step2_json_path, step2_result)

        if self.logging_level == 1 and main_pbar:
            main_pbar.update(1)

    def _load_step1_data(self, path: str) -> Optional[list]:
        """Загрузить данные шага 1 из JSON."""
        with open(path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                self._log(1, f"  Ошибка чтения файла {path}.")
                return None

    def _build_items_from_step1(self, step1_data: list) -> list:
        """Построить список items (проблем) из данных шага 1."""
        items = []
        for chat_entry in step1_data:
            problems = chat_entry.get('analisis_result', [])
            for prob in problems:
                name = prob.get('name', 'Без названия')
                items.append({'name': name, 'indices': []})
        for idx, item in enumerate(items, start=1):
            item['indices'] = [idx]
        return items

    def _aggregate_level(self, current_items: list, limit: int, agent: AliceAIAgent,
                         ungrouped_indices: list, level: int) -> list:
        """Рекурсивная агрегация одного уровня. Возвращает группы (без 'Не классифицировано')."""
        # Базовый случай: количество элементов не превышает limit
        if len(current_items) <= limit:
            return self._process_base_case(current_items, agent, ungrouped_indices, level)

        # Рекурсивный случай: разбиваем на чанки и обрабатываем каждый
        chunks = [current_items[i:i+limit] for i in range(0, len(current_items), limit)]
        all_groups = []
        for chunk in chunks:
            chunk_groups = self._aggregate_level(chunk, limit, agent, ungrouped_indices, level+1)
            all_groups.extend(chunk_groups)

        # Повторная агрегация полученных групп, если их больше limit
        if len(all_groups) <= limit:
            return self._aggregate_level(all_groups, limit, agent, ungrouped_indices, level+1)
        else:
            return self._aggregate_level(all_groups, limit, agent, ungrouped_indices, level+1)

    def _process_base_case(self, current_items: list, agent: AliceAIAgent,
                           ungrouped_indices: list, level: int) -> list:
        """Обработка базового случая: отправка запроса агенту и разделение на группы."""
        # Формирование запроса
        lines = [f"{i} | {item['name']}" for i, item in enumerate(current_items, start=1)]
        user_query = "\n".join(lines)

        self._log(2, f"    Отправка пакета из {len(current_items)} элементов (уровень {level})")
        self._log(2, user_query[:200] + "..." if len(user_query) > 200 else user_query)

        # Отправка с повторными попытками
        final_parsed = self._send_aggregation_request(agent, user_query, level)

        # Разбор ответа в группы
        groups = self._parse_aggregation_response(final_parsed, current_items)

        # Разделение на "Не классифицировано" и остальные
        other_groups = []
        for g in groups:
            if g['name'] == 'Не классифицировано':
                ungrouped_indices.extend(g['indices'])
            else:
                other_groups.append(g)
        return other_groups

    def _send_aggregation_request(self, agent: AliceAIAgent, query: str, level: int) -> Optional[list]:
        """Отправить запрос на агрегацию и получить распарсенный ответ."""
        for attempt in range(self.max_retries):
            try:
                response = agent.send_full_conversation(query, temperature=0.7, max_tokens=4096)
                self._log(2, f"    Ответ агента (уровень {level}, попытка {attempt+1}):")
                self._log(2, response)
                parsed = DataProcessor.extract_groups_from_step2_response(response)
                if parsed is not None:
                    return parsed
                self._log(2, f"    Попытка {attempt+1}: не удалось извлечь группы, повтор через 2 сек...")
                time.sleep(2)
            except Exception as e:
                self._log(2, f"    Ошибка при попытке {attempt+1}: {e}")
                if attempt < self.max_retries - 1:
                    self._log(2, "    Повтор через 5 сек...")
                    time.sleep(5)
        self._log(2, "    Достигнут лимит попыток. Все проблемы этого пакета будут отнесены к группе 'Не классифицировано'.")
        return []

    def _parse_aggregation_response(self, parsed: Optional[list], current_items: list) -> list:
        """Преобразовать ответ агента в список групп с индексами."""
        groups = []
        if parsed and isinstance(parsed, list):
            covered = set()
            for group in parsed:
                if not isinstance(group, dict) or 'name' not in group or 'complaints' not in group:
                    self._log(2, f"    Пропуск некорректной группы: {group}")
                    continue
                name = group['name']
                local_nums = group['complaints']
                all_indices = []
                for local in local_nums:
                    if 1 <= local <= len(current_items):
                        all_indices.extend(current_items[local-1]['indices'])
                        covered.add(local)
                    else:
                        self._log(2, f"    Предупреждение: локальный номер {local} вне диапазона")
                groups.append({'name': name, 'indices': all_indices})

            all_nums = set(range(1, len(current_items)+1))
            missing = all_nums - covered
            if missing:
                self._log(2, f"    Найдены нераспределённые локальные номера: {sorted(missing)}. Добавляем группу 'Не классифицировано'.")
                all_indices = []
                for local in sorted(missing):
                    all_indices.extend(current_items[local-1]['indices'])
                groups.append({'name': 'Не классифицировано', 'indices': all_indices})
        else:
            # Невалидный ответ – все в "Не классифицировано"
            self._log(2, f"    Ответ агента невалиден. Все {len(current_items)} локальных проблем отправлены в группу 'Не классифицировано'.")
            all_indices = []
            for local in range(1, len(current_items)+1):
                all_indices.extend(current_items[local-1]['indices'])
            groups.append({'name': 'Не классифицировано', 'indices': all_indices})
        return groups

    def _build_step2_result(self, other_groups: list, ungrouped_indices: list) -> list:
        """Собрать финальный результат шага 2 из групп и накопленных неклассифицированных."""
        result = [{'name': g['name'], 'complaints': g['indices']} for g in other_groups]
        if ungrouped_indices:
            result.append({'name': 'Не классифицировано', 'complaints': ungrouped_indices})
        return result

    def _save_step2_results(self, path: str, data: list):
        """Сохранить результаты шага 2 в JSON."""
        self._save_results(path, data, "Итоговый результат")