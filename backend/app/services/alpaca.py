from typing import Any

import httpx

from app.settings import Settings

class AlpacaError(RuntimeError):
    pass

class AlpacaClient:
    """Minimal Alpaca paper/data client with no secret logging."""

    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def headers(self) -> dict[str, str]:
        if not self.settings.alpaca_configured:
            raise AlpacaError("Alpaca paper credentials are not configured")
        return {"APCA-API-KEY-ID": self.settings.alpaca_key_id or "", "APCA-API-SECRET-KEY": self.settings.alpaca_secret_key or ""}

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, headers=self.headers, params=params)
        if response.status_code >= 400:
            raise AlpacaError(f"Alpaca GET failed with status {response.status_code}")
        return response.json()

    async def get_account(self) -> dict[str, Any]:
        return await self._get(f"{self.settings.alpaca_paper_base_url}/v2/account")

    async def get_positions(self) -> list[dict[str, Any]]:
        payload = await self._get(f"{self.settings.alpaca_paper_base_url}/v2/positions")
        if not isinstance(payload, list):
            raise AlpacaError("Unexpected Alpaca positions response")
        return payload

    async def get_option_chain(self, underlying: str, limit: int = 100) -> dict[str, Any]:
        payload = await self._get(f"{self.settings.alpaca_data_base_url}/v1beta1/options/snapshots/{underlying}", params={"feed": "indicative", "limit": limit})
        if not isinstance(payload, dict):
            raise AlpacaError("Unexpected Alpaca option-chain response")
        return payload

    async def submit_paper_order(self, order: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(f"{self.settings.alpaca_paper_base_url}/v2/orders", headers={**self.headers, "Content-Type": "application/json"}, json=order)
        if response.status_code >= 400:
            raise AlpacaError(f"Alpaca paper order failed with status {response.status_code}")
        return response.json()
