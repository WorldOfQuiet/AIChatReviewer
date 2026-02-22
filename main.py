import logging
from config import DB_FILE, LOG_FILE, START_DATE
from parser import VKParser
from exporter import export_to_json

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler()
        ]
    )

def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Запуск парсера ВК. Период с %s", START_DATE)

    parser = VKParser(DB_FILE)
    parser.run()

    logger.info("Экспорт данных в JSON...")
    export_to_json(DB_FILE, "output.json")
    logger.info("Готово!")

if __name__ == "__main__":
    main()