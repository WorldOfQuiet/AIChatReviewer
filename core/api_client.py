import httpx
from openai import OpenAI


class LLMClient:
    """Клиент для взаимодействия с LLM через OpenAI-совместимый API."""

    def __init__(self, api_key: str, system_prompt_file_path: str,
                 base_url: str, model_name: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=httpx.Client(transport=httpx.HTTPTransport(retries=0))
        )
        self.system_prompt = self._load_system_prompt(system_prompt_file_path)

    def _load_system_prompt(self, file_path: str) -> str:
        """Загрузить системный промпт из текстового файла."""
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read().strip()

    def send_full_conversation(self, conversation_text: str, temperature: float = 0.0,
                               max_tokens: int = 16000) -> str:
        """Отправить полный текст беседы агенту и получить ответ."""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": conversation_text}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body={"thinking": {"type": "disabled"}}
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"Ошибка при отправке запроса агенту: {e}")