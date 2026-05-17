from typing import Any

import httpx

from mia.settings import Settings


class TelegramClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _require_token(self) -> str:
        if not self.settings.telegram_bot_token:
            raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")
        return self.settings.telegram_bot_token

    def _base_url(self) -> str:
        return f"https://api.telegram.org/bot{self._require_token()}"

    async def send_message(self, *, chat_id: str | int, content: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self._base_url()}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": content,
                    "disable_web_page_preview": True,
                },
            )
            response.raise_for_status()
            return response.json()

    async def set_webhook(self, *, url: str, secret_token: str = "") -> dict[str, Any]:
        body: dict[str, Any] = {"url": url}
        if secret_token:
            body["secret_token"] = secret_token
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{self._base_url()}/setWebhook", json=body)
            response.raise_for_status()
            return response.json()

    async def get_me(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(f"{self._base_url()}/getMe")
            response.raise_for_status()
            return response.json()
