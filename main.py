import sys
import json
import logging


def setup_logging(level: int):
    """Настраивает корневой логгер на заданный уровень."""
    numeric_level = {
        0: logging.NOTSET,
        1: logging.WARNING,
        2: logging.DEBUG
    }.get(level, logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


def load_config(config_path: str = "config.json") -> dict:
    """Загружает конфигурационный файл JSON."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main() -> None:
    """Основная функция: запускает парсер, анализатор и визуализатор согласно конфигурации."""
    # Загрузка конфигурации
    try:
        config = load_config()
    except Exception as e:
        logging.error(f"Ошибка загрузки конфигурации: {e}")
        sys.exit(1)

    # Настройка логирования
    shared_logging_level = config.get("shared", {}).get("logging_level", 2)
    setup_logging(shared_logging_level)
    logger = logging.getLogger(__name__)
    logger.info("Логирование настроено, уровень %d", shared_logging_level)

    # ===== Парсер =====
    parser_cfg = config.get('parser', {})
    if parser_cfg.get("enabled", False):
        # Импортируем модули парсера только при необходимости
        from parser import VKParser
        from exporter import export_to_json

        logger.info("Запуск парсера ВК")
        prefs = parser_cfg.get("preferences", {})
        parser = VKParser(
            vk_token=prefs['vk_token'],
            vk_api_version=prefs.get('vk_api_version', '5.131'),
            request_delay=prefs.get('request_delay', 0.5),
            groups_file=prefs.get('groups_file', 'groups.txt'),
            db_file=prefs.get('db_file', 'vk_data.db'),
            start_date=prefs.get('start_date'),
            end_date=prefs.get('end_date'),
            days_back=prefs.get('days_back', 30)
        )
        parser.run()

        # Экспорт собранных данных в JSON
        logger.info("Экспорт данных в JSON...")
        export_to_json(prefs.get('db_file', 'vk_data.db'), "output.json")
        logger.info("Парсер завершил работу.")
    else:
        logger.info("Парсер отключён в конфигурации.")

    # ===== Анализатор =====
    analyzer_config = config.get("analyzer", {})
    if analyzer_config.get("enabled", True):
        # Импортируем анализатор только при включении
        from agent import DataAnalyzer

        # Подготавливаем настройки для анализатора
        prefs = analyzer_config.get("preferences", {}).copy()
        prefs["chats_file"] = config.get("shared", {}).get("chats_file", "agent_data/chats.json")
        prefs["logging_level"] = shared_logging_level  # добавляем общий уровень

        logger.info("Запуск анализатора")
        analyzer = DataAnalyzer(prefs)
        analyzer.run()
    else:
        logger.info("Анализатор отключён в конфигурации.")

    # ===== Визуализатор =====
    visualizer_cfg = config.get('visualizer', {})
    if visualizer_cfg.get("enabled", False):
        from visualization.visualizer import Visualizer

        prefs = visualizer_cfg.get("preferences", {}).copy()
        prefs["log_level"] = shared_logging_level  # добавляем общий уровень (визуализатор ожидает log_level)

        logger.info("Запуск визуализатора")
        vis = Visualizer(prefs)
        vis.run()
        logger.info("Визуализация завершена.")
    else:
        logger.info("Визуализатор отключён в конфигурации.")


if __name__ == "__main__":
    main()