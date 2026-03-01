import sys
import json
from agent import DataAnalyzer

# Парсер будет импортирован позже другим разработчиком
# from parser_module import Parser


def load_config(config_path: str = "config.json") -> dict:
    """
    Загружает конфигурационный файл.

    :param config_path: путь к файлу конфигурации
    :return: словарь с конфигурацией
    :raises Exception: если файл не найден или не является валидным JSON
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    # Загрузка конфигурации
    try:
        config = load_config()
    except Exception as e:
        print(f"Ошибка загрузки конфигурации: {e}")
        sys.exit(1)

    # ===== Парсер (будет реализован позже) =====
    parser_config = config.get("parser", {})
    if parser_config.get("enabled", False):
        # Здесь будет импорт и запуск парсера
        # parser = Parser(parser_config.get("preferences", {}))
        # parser.run()
        print("Парсер пока не реализован, пропускаем...")
    else:
        print("Парсер отключён в конфигурации.")

    # ===== Анализатор =====
    analyzer_config = config.get("analyzer", {})
    if analyzer_config.get("enabled", True):
        # Извлекаем настройки анализатора
        prefs = analyzer_config.get("preferences", {}).copy()
        # Добавляем путь к файлу чатов из общей секции
        prefs["chats_file"] = config.get("shared", {}).get("chats_file", "agent_data/chats.json")

        # Создаём экземпляр анализатора и запускаем
        analyzer = DataAnalyzer(prefs)
        analyzer.run()
    else:
        print("Анализатор отключён в конфигурации.")


if __name__ == "__main__":
    main()
