import sys
import json
import logging


def load_config(config_path: str = "config.json") -> dict:
    """Загружает конфигурационный файл JSON."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main() -> None:
    """Основная функция: запускает парсер, анализатор и визуализатор согласно конфигурации."""
    logger = logging.getLogger(__name__)

    # Загрузка конфигурации
    try:
        config = load_config()
    except Exception as e:
        logger.error(f"Ошибка загрузки конфигурации: {e}")
        sys.exit(1)

    # ===== Парсер =====
    parser_cfg = config.get('parser', {})
    if parser_cfg.get("enabled", False):
        # Импортируем модули парсера только при необходимости
        from parser import VKParser
        from exporter import export_to_json

        logger.info("Запуск парсера ВК")
        parser = VKParser(
            vk_token=parser_cfg['vk_token'],
            vk_api_version=parser_cfg.get('vk_api_version', '5.131'),
            request_delay=parser_cfg.get('request_delay', 0.5),
            groups_file=parser_cfg.get('groups_file', 'groups.txt'),
            db_file=parser_cfg.get('db_file', 'vk_data.db'),
            start_date=parser_cfg.get('start_date'),
            end_date=parser_cfg.get('end_date'),
            days_back=parser_cfg.get('days_back', 30)
        )
        parser.run()

        # Экспорт собранных данных в JSON
        logger.info("Экспорт данных в JSON...")
        export_to_json(parser_cfg.get('db_file', 'vk_data.db'), "output.json")
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

        analyzer = DataAnalyzer(prefs)
        analyzer.run()
    else:
        logger.info("Анализатор отключён в конфигурации.")

    # ===== Визуализатор =====
    visualizer_cfg = config.get('visualizer', {})
    if visualizer_cfg.get("enabled", False):
        from visualizer import Visualizer

        prefs = visualizer_cfg.get("preferences", {})

        logger.info("Запуск визуализатора")

        vis = Visualizer(prefs)
        vis.run()
        logger.info("Визуализация завершена.")
    else:
        logger.info("Визуализатор отключён в конфигурации.")


if __name__ == "__main__":
    main()