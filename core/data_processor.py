import json
import re
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


class DataProcessor:
    """Обработка данных чатов и извлечение информации из ответов агента."""

    @staticmethod
    def parse_date(date_value) -> Optional[datetime]:
        """Преобразовать дату из различных форматов в datetime."""
        if isinstance(date_value, (int, float)):
            return datetime.fromtimestamp(date_value)
        if isinstance(date_value, str):
            formats = [
                "%H:%M %d.%m.%Y", "%d.%m.%Y %H:%M",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
            ]
            for fmt in formats:
                try:
                    return datetime.strptime(date_value, fmt)
                except ValueError:
                    continue
        return None

    @staticmethod
    def extract_from_response(response_text: str):
        """Извлечь данные между тегами <result> из ответа модели."""
        match = re.search(r'<result>(.*?)</result>', response_text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            return None

    @staticmethod
    def extract_groups_from_step2_response(response_text: str) -> Optional[List[Dict[str, Any]]]:
        """Извлечь группы из ответа второго агента (формат с <separator>)."""
        match = re.search(r'<result>(.*?)</result>', response_text, re.DOTALL)
        if not match:
            return None
        content = match.group(1).strip()
        if '<separator>' not in content:
            return None
        groups_json_str, lines_str = content.split('<separator>', 1)
        groups_dict = json.loads(groups_json_str.strip())
        num_to_name = {v: k for k, v in groups_dict.items()}
        group_complaints = {num: [] for num in num_to_name.keys()}
        for line in lines_str.strip().split('\n'):
            if '|' not in line:
                continue
            parts = line.split('|')
            if len(parts) != 2:
                continue
            try:
                prob_num = int(parts[0].strip())
                group_num = int(parts[1].strip())
                if group_num in group_complaints:
                    group_complaints[group_num].append(prob_num)
            except ValueError:
                continue
        result = []
        for group_num, complaints in group_complaints.items():
            result.append({'name': num_to_name[group_num], 'complaints': complaints})
        return result

    @staticmethod
    def load_chats_from_json(file_path: str, max_messages_per_chat: int = None,
                             max_chats: int = None) -> list:
        """Загрузить чаты из JSON-файла с ограничениями."""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("Expected a list of chat objects")
        result = []
        for chat in data:
            # Проверка обязательных ключей
            for key in ['chat_id', 'chat_name', 'messages']:
                if key not in chat:
                    raise ValueError(f"Missing key '{key}' in chat")
            messages = chat['messages']
            # Добавление временного поля _dt для сортировки
            for msg in messages:
                msg['_dt'] = DataProcessor.parse_date(msg.get('date'))
            messages.sort(key=lambda m: (m['_dt'] is None, m['_dt'] or m['id']))
            if max_messages_per_chat and max_messages_per_chat > 0:
                messages = messages[-max_messages_per_chat:]
            result.append({
                'chat_id': chat['chat_id'],
                'chat_name': chat['chat_name'],
                'messages': messages
            })
        if max_chats and max_chats > 0 and len(result) > max_chats:
            result = result[-max_chats:]
        return result

    @staticmethod
    def format_message_for_agent(msg: dict) -> str:
        """Преобразовать сообщение в строку для отправки агенту."""
        media_status = "yes" if msg.get('media') else "no"
        return f"{msg['id']} | {msg['text']} | {msg['author']} | {media_status} | {msg['reply_to']}"

    @staticmethod
    def parse_message_line(line: str) -> dict:
        """Разобрать строку сообщения из формата агента."""
        parts = line.split(' | ', maxsplit=4)
        if len(parts) != 5:
            parts = line.split(' | ')
        if len(parts) == 5:
            num = int(parts[0].strip())
            text = parts[1].strip()
            author = parts[2].strip()
            media_str = parts[3].strip()
            if media_str.startswith('[') and media_str.endswith(']'):
                media_content = media_str[1:-1].strip()
                media = [item.strip() for item in media_content.split(',')] if media_content else []
            else:
                media = []
            reply_to = int(parts[4].strip())
            return {'num': num, 'text': text, 'author': author, 'media': media, 'reply_to': reply_to}
        return {'num': -1, 'text': line, 'author': 'unknown', 'media': [], 'reply_to': -1}

    @staticmethod
    def group_messages_by_reply_chain(messages: list, isolated_packet_size: int = None) -> Tuple[list, list]:
        """Сгруппировать сообщения по цепочкам ответов (транзитивное замыкание)."""
        msg_dict = {m['id']: m for m in messages}
        root_of = {}

        def find_root(msg_id):
            if msg_id in root_of:
                return root_of[msg_id]
            msg = msg_dict.get(msg_id)
            if not msg or msg['reply_to'] == -1 or msg['reply_to'] not in msg_dict:
                root_of[msg_id] = msg_id
                return msg_id
            parent_root = find_root(msg['reply_to'])
            root_of[msg_id] = parent_root
            return parent_root

        for m in messages:
            find_root(m['id'])

        groups = {}
        for msg_id, root in root_of.items():
            groups.setdefault(root, []).append(msg_id)

        chain_groups = []
        isolated_ids = []
        for root, ids in groups.items():
            if len(ids) > 1:
                chain_groups.append(ids)
            else:
                isolated_ids.append(root)

        # Построение цепочечных пакетов
        chain_packets = []
        for ids in chain_groups:
            packet = [msg_dict[i] for i in ids]
            packet.sort(key=lambda m: (m.get('_dt') is None, m.get('_dt') or m['id']))
            chain_packets.append(packet)

        # Построение изолированных пакетов
        isolated_packets = []
        if isolated_ids:
            isolated_msgs = [msg_dict[i] for i in isolated_ids]
            isolated_msgs.sort(key=lambda m: (m.get('_dt') is None, m.get('_dt') or m['id']))
            if isolated_packet_size and isolated_packet_size > 0:
                for i in range(0, len(isolated_msgs), isolated_packet_size):
                    isolated_packets.append(isolated_msgs[i:i+isolated_packet_size])
            else:
                isolated_packets.append(isolated_msgs)
        return chain_packets, isolated_packets