import json
import sys
import os
from collections import defaultdict

OLD_CHAT = "agent_data/chats.json"
NEW_CHAT = "agent_data/chat-new.json"
OLD_STEP1 = "agent_data/analysis_step_1.json"
ID_MAP = "agent_data/msg_id_map.json"
REMAPPED_STEP1 = "agent_data/analysis_step_1_remapped.json"
TEMP_NEW_ONLY = "agent_data/temp_chats_new_only.json"
TEMP_NEW_STEP1 = "agent_data/temp_step1_result.json"
MERGED_STEP1 = "agent_data/analysis_step_1.json"


def make_key(msg):
    text = msg['text'].strip()
    if text:
        return ('text', text, msg['author'], msg['date'])
    media = msg.get('media', [])
    media_sig = tuple(media[:1]) if media else ()
    return ('media', media_sig, msg['author'], msg['date'])


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def cmd_prepare():
    print("=== Загрузка файлов ===")
    old = load_json(OLD_CHAT)[0]
    new = load_json(NEW_CHAT)[0]
    step1 = load_json(OLD_STEP1)

    old_msgs = old['messages']
    new_msgs = new['messages']

    print(f"  Старый чат: {len(old_msgs)} сообщений, {old['chat_name']}")
    print(f"  Новый чат:  {len(new_msgs)} сообщений, {new['chat_name']}")
    print(f"  Step 1 записей: {len(step1)}")

    print("\n=== Матчинг сообщений ===")
    new_by_key = defaultdict(list)
    for m in new_msgs:
        new_by_key[make_key(m)].append(m['id'])

    matched = 0
    unmatched = 0
    old_to_new = {}
    for m in old_msgs:
        key = make_key(m)
        queue = new_by_key[key]
        if queue:
            new_id = queue.pop(0)
            old_to_new[m['id']] = new_id
            matched += 1
        else:
            unmatched += 1

    print(f"  Совпало: {matched}, не найдено в новом: {unmatched}")

    if unmatched > 0:
        print("  ВНИМАНИЕ: часть старых сообщений не найдена в новом чате!")
        print("  Они будут пропущены при ремапинге.")

    save_json(ID_MAP, old_to_new)
    print(f"\n  Сохранён маппинг: {ID_MAP}")

    print("\n=== Ремапинг analysis_step_1.json ===")
    remapped = []
    unmapped_ids = set()
    total_complaints = 0
    for entry in step1:
        new_entry = {
            'chat_id': entry['chat_id'],
            'chat_name': entry['chat_name'],
            'analisis_result': []
        }
        for prob in entry.get('analisis_result', []):
            restored = []
            for c in prob.get('complaints', []):
                if isinstance(c, int):
                    new_c = old_to_new.get(c)
                    if new_c is not None:
                        restored.append(new_c)
                    else:
                        unmapped_ids.add(c)
                else:
                    restored.append(c)
            new_entry['analisis_result'].append({
                'name': prob['name'],
                'count': len(restored),
                'complaints': restored
            })
            total_complaints += len(restored)
        remapped.append(new_entry)

    if unmapped_ids:
        print(f"  ПРЕДУПРЕЖДЕНИЕ: {len(unmapped_ids)} старых ID не найдены в маппинге (пропущены)")
    print(f"  Всего complaint-ссылок в ремапнутом: {total_complaints}")

    save_json(REMAPPED_STEP1, remapped)
    print(f"  Сохранён ремапнутый step1: {REMAPPED_STEP1}")

    print("\n=== Экстракт новых (только unmatched) сообщений ===")
    mapped_new_ids = set(old_to_new.values())
    new_only_msgs = []
    for m in new_msgs:
        if m['id'] not in mapped_new_ids:
            new_only_msgs.append(m)

    print(f"  Новых сообщений (нет в старом файле): {len(new_only_msgs)}")

    local_id_map = {}
    for local_id, m in enumerate(new_only_msgs):
        local_id_map[m['id']] = local_id

    temp_messages = []
    for i, m in enumerate(new_only_msgs):
        orig_reply = m['reply_to']
        if orig_reply >= 0 and orig_reply in local_id_map:
            reply = local_id_map[orig_reply]
        else:
            reply = -1

        temp_messages.append({
            'id': i,
            'text': m['text'],
            'author': m['author'],
            'media': m.get('media', []),
            'reply_to': reply,
            'date': m['date']
        })

    temp_chat = [{
        'chat_id': 0,
        'chat_name': new['chat_name'],
        'messages': temp_messages
    }]

    save_json(TEMP_NEW_ONLY, temp_chat)
    print(f"  Сохранён временный чат: {TEMP_NEW_ONLY}")

    print("\n=== Готово ===")
    print(f"\nДалее:")
    print(f"  1. В config.json укажите:")
    print(f"     - chats_file: {TEMP_NEW_ONLY}")
    print(f"     - max_messages_per_chat: {len(temp_messages)}")
    print(f"     - steps.step1_analyze_chats: true")
    print(f"     - steps.step2_aggregate_results: false")
    print(f"     - steps.step3_backward_mapping: false")
    print(f"  2. Запустите: python main.py")
    print(f"  3. После завершения, скопируйте результат:")
    print(f"     cp agent_data/analysis_step_1.json {TEMP_NEW_STEP1}")
    print(f"  4. Запустите: python adapt_analysis.py merge")
    print(f"  5. В config.json укажите:")
    print(f"     - chats_file: {NEW_CHAT}")
    print(f"     - steps.step1_analyze_chats: false")
    print(f"     - steps.step2_aggregate_results: true")
    print(f"     - steps.step3_backward_mapping: true")
    print(f"  6. Запустите: python main.py")


def cmd_merge():
    if not os.path.exists(REMAPPED_STEP1):
        print(f"ОШИБКА: {REMAPPED_STEP1} не найден. Сначала выполните prepare.")
        sys.exit(1)
    if not os.path.exists(TEMP_NEW_STEP1):
        print(f"ОШИБКА: {TEMP_NEW_STEP1} не найден.")
        print(f"Скопируйте результат Step 1 (agent_data/analysis_step_1.json) в {TEMP_NEW_STEP1}")
        sys.exit(1)

    print("=== Слияние результатов ===")
    remapped = load_json(REMAPPED_STEP1)
    new_result = load_json(TEMP_NEW_STEP1)

    print(f"  Ремапнутых (старых) записей: {len(remapped)}")
    print(f"  Новых записей: {len(new_result)}")

    merged = remapped + new_result
    print(f"  Всего после слияния: {len(merged)}")

    save_json(MERGED_STEP1, merged)
    print(f"  Сохранён финальный step1: {MERGED_STEP1}")

    old_complaints = sum(len(p.get('complaints', [])) for e in merged for p in e.get('analisis_result', []))
    print(f"  Всего complaint-ссылок: {old_complaints}")
    print("\nГотово. Переключите config.json на chat-new.json и запустите шаги 2 и 3.")


def main():
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python adapt_analysis.py prepare  — подготовка (маппинг, ремапинг, экстракт)")
        print("  python adapt_analysis.py merge    — слияние результатов после Step 1")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == 'prepare':
        cmd_prepare()
    elif cmd == 'merge':
        cmd_merge()
    else:
        print(f"Неизвестная команда: {cmd}")
        sys.exit(1)


if __name__ == '__main__':
    main()
