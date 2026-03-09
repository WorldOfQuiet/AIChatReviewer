import logging
import sys
from config_loader import load_config
from parser import VKParser
from exporter import export_to_json
from agent import DataAnalyzer

def setup_logging(log_file: str):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler()
        ]
    )

def main():
    # Загрузка конфигурации
    config = load_config()

    # Настройка логирования (используем файл из секции parser, если есть, иначе по умолчанию)
    log_file = config.get('parser', {}).get('log_file', 'vk_parser.log')
    setup_logging(log_file)
    logger = logging.getLogger(__name__)

    parser_cfg = config.get('parser', {})
    if parser_cfg.get('enabled', False):
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

    analyzer_cfg = config.get('analyzer', {})
    if analyzer_cfg.get('enabled', False):
        prefs = analyzer_cfg.get('preferences', {}).copy()
        # Добавляем путь к файлу чатов из общей секции
        prefs['chats_file'] = config.get('shared', {}).get('chats_file', 'agent_data/chats.json')

        analyzer = DataAnalyzer(prefs)
        analyzer.run()
    else:
        logger.info("Анализатор отключён в конфигурации.")

if __name__ == "__main__":
    main()