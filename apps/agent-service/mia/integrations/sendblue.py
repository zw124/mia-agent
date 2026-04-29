from typing import Any

import httpx

from mia.settings import Settings


class SendBlueClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _require_credentials(self) -> None:
        if not self.settings.sendblue_api_key_id or not self.settings.sendblue_api_secret_key:
            raise RuntimeError("Missing SendBlue API credentials")
        if not self.settings.sendblue_from_number:
            raise RuntimeError("Missing SENDBLUE_FROM_NUMBER")

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "sb-api-key-id": self.settings.sendblue_api_key_id,
            "sb-api-secret-key": self.settings.sendblue_api_secret_key,
        }

    def _base_url(self) -> str:
        return str(self.settings.sendblue_api_base_url).rstrip("/")

    async def send_typing_indicator(self, *, number: str) -> dict[str, Any]:
        self._require_credentials()
        body: dict[str, Any] = {
            "from_number": self.settings.sendblue_from_number,
            "number": number,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{self._base_url()}/api/send-typing-indicator",
                headers=self._headers(),
                json=body,
            )
            response.raise_for_status()
            return response.json()

    async def send_message(self, *, number: str, content: str) -> dict[str, Any]:
        self._require_credentials()
        body: dict[str, Any] = {
            "content": content,
            "from_number": self.settings.sendblue_from_number,
            "number": number,
        }
        if self.settings.sendblue_status_callback:
            body["status_callback"] = self.settings.sendblue_status_callback

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self._base_url()}/api/send-message",
                headers=self._headers(),
                json=body,
            )
            response.raise_for_status()
            return response.json()
