import sys
import json
import logging
from config import DB_FILE, LOG_FILE, START_DATE
from parser import VKParser
from exporter import export_to_json
from agent import DataAnalyzer


def setup_logging():
    """Настройка логирования: файл и консоль."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler()
        ]
    )


def load_config(config_path: str = "config.json") -> dict:
    """Загружает конфигурационный файл."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    # Единоразовая настройка логирования
    setup_logging()
    logger = logging.getLogger(__name__)

    # Загрузка конфигурации
    try:
        config = load_config()
    except Exception as e:
        logger.error(f"Ошибка загрузки конфигурации: {e}")
        sys.exit(1)

    # ===== Парсер =====
    parser_config = config.get("parser", {})
    if parser_config.get("enabled", False):
        logger.info("Запуск парсера ВК. Период с %s", START_DATE)
        parser = VKParser(DB_FILE)
        parser.run()
        logger.info("Экспорт данных в JSON...")
        export_to_json(DB_FILE, "output.json")
        logger.info("Парсер завершил работу.")
    else:
        logger.info("Парсер отключён в конфигурации.")

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
        logger.info("Анализатор отключён в конфигурации.")


if __name__ == "__main__":
    main()