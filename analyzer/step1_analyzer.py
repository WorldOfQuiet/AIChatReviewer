import json
import os
import time
from typing import Optional
from tqdm import tqdm

from .base_analyzer import BaseAnalyzer
from core.api_client import AliceAIAgent
from core.data_processor import DataProcessor


class Step1Analyzer(BaseAnalyzer):
    """Шаг 1: анализ исходных чатов с группировкой по цепочкам ответов."""

    def step1_analyze_chats(self, main_pbar: Optional[tqdm] = None):
        """Шаг 1: анализ исходных чатов с группировкой по цепочкам ответов."""
        self.current_stage = "Этап 1: Анализ чатов"
        step1_json_path = "agent_data/analysis_step_1.json"

        # Загрузка чатов из JSON
        chats = self._load_chats_for_step1()
        if not chats:
            return

        # Создание агента для анализа чатов
        agent = AliceAIAgent(self.api_key_file, self.agent_id, self.system_prompt_file,
                             self.base_url, self.model_name)

        interim_entries = []
        outer_pbar = tqdm(total=len(chats), desc=self.current_stage, position=1, leave=False) \
                     if self.logging_level == 1 else None

        # Обработка каждого чата
        for chat in chats:
            self._process_single_chat(chat, agent, interim_entries, outer_pbar)

        if outer_pbar:
            outer_pbar.close()

        # Сохранение результатов шага 1
        self._save_step1_results(step1_json_path, interim_entries)

        if self.logging_level == 1 and main_pbar:
            main_pbar.update(1)

    def _load_chats_for_step1(self) -> list:
        """Загрузить чаты для шага 1 с учётом ограничений."""
        if self.chats_file is None:
            self._log(1, "  Ошибка: не указан путь к файлу чатов (chats_file).")
            return []
        try:
            chats = DataProcessor.load_chats_from_json(
                self.chats_file,
                max_messages_per_chat=self.max_messages_per_chat,
                max_chats=self.max_chats
            )
        except Exception as e:
            self._log(1, f"  Ошибка загрузки JSON: {e}")
            return []
        if not chats:
            self._log(1, "  Нет данных для обработки.")
        else:
            self._log(1, f"  Загружено чатов: {len(chats)}")
            self._log(2, "  " + "-" * 50, indent=1)
        return chats

    def _process_single_chat(self, chat: dict, agent: AliceAIAgent,
                             interim_entries: list, outer_pbar: Optional[tqdm]):
        """Обработать один чат: разбить на пакеты, отправить агентам."""
        chat_id = chat['chat_id']
        chat_name = chat['chat_name']
        messages = chat['messages']

        # Группировка сообщений по цепочкам ответов
        all_chain, all_isolated = DataProcessor.group_messages_by_reply_chain(
            messages, isolated_packet_size=self.isolated_packet_size
        )
        self._log(2, f"\n  Чат '{chat_name}' (ID: {chat_id}) разбит на {len(all_chain)} цепочечных и {len(all_isolated)} изолированных пакетов.", indent=2)

        # Отбор пакетов для обработки с учётом ограничений
        chain_packets = self._select_chain_packets(all_chain)
        isolated_packets = self._select_isolated_packets(all_isolated)

        # Объединение пакетов в один список с указанием типа
        all_packets = []
        for pkt in chain_packets:
            if self.max_chain_packet_messages and len(pkt) > self.max_chain_packet_messages:
                pkt = pkt[:self.max_chain_packet_messages]
            all_packets.append(('цепочечный', pkt))
        for pkt in isolated_packets:
            all_packets.append(('изолированный', pkt))

        # Внутренний прогресс-бар для пакетов чата
        inner_pbar = tqdm(total=len(all_packets), desc=f"Чат: {chat_name}", position=2, leave=False) \
                     if self.logging_level == 1 else None

        # Обработка каждого пакета
        for pkt_type, pkt_msgs in all_packets:
            self._process_packet(pkt_msgs, chat_name, chat_id, agent, interim_entries, pkt_type)
            if inner_pbar:
                inner_pbar.update(1)

        if inner_pbar:
            inner_pbar.close()
        if outer_pbar:
            outer_pbar.update(1)

    def _select_chain_packets(self, all_chain: list) -> list:
        """Выбрать цепочечные пакеты для обработки (с учётом max_chain_packets)."""
        if self.max_chain_packets == 0:
            self._log(2, "    Обработка цепочечных пакетов отключена.", indent=3)
            return []
        sorted_chain = sorted(all_chain, key=self._get_packet_first_date, reverse=True)
        if len(sorted_chain) > self.max_chain_packets:
            self._log(2, f"    Ограничение max_chain_packets={self.max_chain_packets}: взято последних {self.max_chain_packets}", indent=3)
            return sorted_chain[:self.max_chain_packets]
        return sorted_chain

    def _select_isolated_packets(self, all_isolated: list) -> list:
        """Выбрать изолированные пакеты для обработки (с учётом max_isolated_packets)."""
        if self.max_isolated_packets == 0:
            self._log(2, "    Обработка изолированных пакетов отключена.", indent=3)
            return []
        sorted_isolated = sorted(all_isolated, key=self._get_packet_first_date, reverse=True)
        if len(sorted_isolated) > self.max_isolated_packets:
            self._log(2, f"    Ограничение max_isolated_packets={self.max_isolated_packets}: взято последних {self.max_isolated_packets}", indent=3)
            return sorted_isolated[:self.max_isolated_packets]
        return sorted_isolated
    
    def _process_packet(self, packet_msgs: list, chat_name: str, chat_id: int,
                        agent: AliceAIAgent, interim_entries: list, packet_type: str = ""):
        """
        Обработать один пакет: анонимизировать авторов, отправить агенту,
        извлечь результат, сохранить.
        """
        # ---- Анонимизация авторов в пределах пакета ----
        unique_authors = {}
        next_author_id = 1
        anonymized_lines = []

        for msg in packet_msgs:
            original_author = msg['author']
            if original_author not in unique_authors:
                unique_authors[original_author] = f"автор{next_author_id}"
                next_author_id += 1
            anon_author = unique_authors[original_author]

            # Формируем строку в формате:
            # <id> | <text> | анонимный_автор | [media] | reply_to
            media_status = "yes" if msg.get('media') else "no"
            line = f"{msg['id']} | {msg['text']} | {anon_author} | {media_status} | {msg['reply_to']}"
            anonymized_lines.append(line)

        packet_text = "\n".join(anonymized_lines)

        self._log(2, f"\n      --- Обработка {packet_type} пакета (чат: {chat_name}) ---", indent=4)
        self._log(2, "      Текст пакета (первые 500 символов):", indent=4)
        preview = packet_text[:500] + "..." if len(packet_text) > 500 else packet_text
        self._log(2, "      " + preview, indent=4)

        # Отправка с повторными попытками
        parsed_data = self._send_with_retries(agent, packet_text, "packet")
        if parsed_data is None:
            self._log(2, "      Не удалось получить корректный ответ для пакета, пропускаем.", indent=4)
            return

        # Добавление поля count к каждой проблеме
        problems_with_count = []
        for problem in parsed_data:
            if isinstance(problem, dict) and 'name' in problem and 'complaints' in problem:
                count = len(problem['complaints'])
                problems_with_count.append({
                    'name': problem['name'],
                    'count': count,
                    'complaints': problem['complaints']
                })
            else:
                problems_with_count.append(problem)

        # Сохранение результата (с оригинальными именами авторов, которые уже лежат в packet_msgs)
        part_chat_name = f"{chat_name} ({packet_type} пакет)"
        interim_entries.append({
            "chat_id": chat_id,
            "chat_name": part_chat_name,
            "analisis_result": problems_with_count
        })

    def _save_step1_results(self, path: str, data: list):
        """Сохранить результаты шага 1 в JSON."""
        self._save_results(path, data, "Все промежуточные результаты")