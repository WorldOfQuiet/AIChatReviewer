import sys
import json
import logging

def setup_logging(level: int, log_file: str = None):
    """Настраивает логирование: в консоль только ERROR, в файл (если указан)"""
    numeric_level = {0: logging.NOTSET, 1: logging.INFO, 2: logging.DEBUG}.get(level, logging.INFO)

    handlers = []
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.ERROR)
    handlers.append(console_handler)

    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(numeric_level)
        handlers.append(file_handler)

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers
    )

def load_config(config_path: str = "config.json") -> dict:
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    config = load_config()
    shared_level = config.get("shared", {}).get("logging_level", 1)
    log_file = config.get("parser", {}).get("preferences", {}).get("log_file", None)
    setup_logging(shared_level, log_file)

    logger = logging.getLogger(__name__)
    logger.info("Логирование настроено, уровень %d, файл %s", shared_level, log_file)

    # Парсер
    parser_cfg = config.get('parser', {})
    if parser_cfg.get("enabled", False):
        from parser import VKParser
        parser = VKParser(parser_cfg.get("preferences", {}))
        parser.run()
    else:
        logger.info("Парсер отключён в конфигурации.")

    # Анализатор
    analyzer_cfg = config.get('analyzer', {})
    if analyzer_cfg.get("enabled", True):
        from agent import DataAnalyzer
        prefs = analyzer_cfg.get("preferences", {}).copy()
        prefs["chats_file"] = config.get("shared", {}).get("chats_file", "agent_data/chats.json")
        prefs["logging_level"] = shared_level
        logger.info("Запуск анализатора")
        analyzer = DataAnalyzer(prefs)
        analyzer.run()
    else:
        logger.info("Анализатор отключён в конфигурации.")

    # Визуализатор
    visualizer_cfg = config.get('visualizer', {})
    if visualizer_cfg.get("enabled", False):
        from visualizer import Visualizer
        prefs = visualizer_cfg.get("preferences", {}).copy()
        prefs["log_level"] = shared_level
        logger.info("Запуск визуализатора")
        vis = Visualizer(prefs)
        vis.run()
        logger.info("Визуализация завершена.")
    else:
        logger.info("Визуализатор отключён в конфигурации.")

if __name__ == "__main__":
    main()