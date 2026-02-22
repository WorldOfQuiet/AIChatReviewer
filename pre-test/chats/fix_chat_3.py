#!/usr/bin/env python3
import json

# Имена файлов
input_txt = "pre-test/chats/chat_4.txt"
output_json = "pre-test/chats/chat_4.json"

# Читаем содержимое текстового файла
with open(input_txt, "r", encoding="utf-8") as f:
    messages_text = f.read().strip()

# Формируем структуру данных
data = {
    "chat_id": "city_problems_2025",
    "chat_name": "Проблемы города N",
    "messages": messages_text
}

# Записываем в JSON с отступами и экранированием
with open(output_json, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Файл {output_json} успешно создан на основе {input_txt}.")
