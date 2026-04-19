import json
import sys


def load_config(config_path: str = "config.json") -> dict:
    """Загрузить конфигурационный файл JSON."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)