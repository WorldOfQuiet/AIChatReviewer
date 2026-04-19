import json
import requests
from typing import Optional


class AliceAIAgent:
    """Агент для взаимодействия с LLM через Yandex AI Studio."""

    def __init__(self, api_key_file_path: str, agent_id: str, system_prompt_file_path: str,
                 base_url: str, model_name: str):
        # Загрузка API-ключа из файла
        self.api_key = self._load_api_key(api_key_file_path)
        self.agent_id = agent_id
        self.base_url = base_url
        self.model_name = model_name
        # Загрузка системного промпта
        self.system_prompt = self._load_system_prompt(system_prompt_file_path)

    def _load_api_key(self, file_path: str) -> str:
        """Загрузить API-ключ из JSON-файла."""
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
            return data['api_key']

    def _load_system_prompt(self, file_path: str) -> str:
        """Загрузить системный промпт из текстового файла."""
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read().strip()

    def send_full_conversation(self, conversation_text: str, temperature: float = 0.7,
                               max_tokens: int = 4096) -> str:
        """Отправить полный текст беседы агенту и получить ответ."""
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json"
        }
        model_uri = f"gpt://{self.agent_id}/{self.model_name}"
        payload = {
            "modelUri": model_uri,
            "completionOptions": {
                "stream": False,
                "temperature": temperature,
                "maxTokens": max_tokens
            },
            "messages": [
                {"role": "system", "text": self.system_prompt},
                {"role": "user", "text": conversation_text}
            ]
        }
        try:
            response = requests.post(self.base_url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()
            return result['result']['alternatives'][0]['message']['text']
        except Exception as e:
            raise Exception(f"Ошибка при отправке запроса агенту: {e}")