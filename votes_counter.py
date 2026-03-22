import json
import os
import sys

def count_votes_step1(step1_file: str) -> int:
    """Подсчитывает общее количество голосов (сообщений) на шаге 1."""
    with open(step1_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    total = 0
    for chat_entry in data:
        problems = chat_entry.get('analisis_result', [])
        for prob in problems:
            complaints = prob.get('complaints', [])
            total += len(complaints)
    return total

def count_votes_step2(step2_file: str) -> int:
    """Подсчитывает общее количество голосов (сообщений) на шаге 2."""
    with open(step2_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    total = 0
    for group in data:
        complaints = group.get('complaints', [])
        total += len(complaints)
    return total

def count_votes_step3(step3_file: str) -> int:
    """Подсчитывает общее количество голосов (сообщений) на шаге 3."""
    with open(step3_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    total = 0
    for category in data:
        total += category.get('total_votes', 0)
    return total

def main():
    step1_file = "agent_data/analysis_step_1.json"
    step2_file = "agent_data/analysis_step_2.json"
    step3_file = "agent_data/analysis_step_3.json"

    if not os.path.exists(step1_file):
        print(f"Файл {step1_file} не найден.")
        sys.exit(1)
    if not os.path.exists(step2_file):
        print(f"Файл {step2_file} не найден.")
        sys.exit(1)
    if not os.path.exists(step3_file):
        print(f"Файл {step3_file} не найден.")
        sys.exit(1)

    votes_step1 = count_votes_step1(step1_file)
    votes_step2 = count_votes_step2(step2_file)
    votes_step3 = count_votes_step3(step3_file)

    print(f"Общее количество голосов на шаге 1: {votes_step1}")
    print(f"Общее количество голосов на шаге 2: {votes_step2}")
    print(f"Общее количество голосов на шаге 3: {votes_step3}")

    if votes_step1 == votes_step2 == votes_step3:
        print("Количество голосов совпадает на всех этапах.")
    else:
        print(f"Разница (шаг1 - шаг2): {votes_step1 - votes_step2}")
        print(f"Разница (шаг1 - шаг3): {votes_step1 - votes_step3}")

if __name__ == "__main__":
    main()
