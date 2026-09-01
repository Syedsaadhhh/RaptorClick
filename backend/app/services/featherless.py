import json
from typing import Any

import httpx

from app.models import PortfolioSnapshot, StressScenario
from app.settings import Settings

_ALLOWED = {"protective_put", "put_spread", "tail_put"}

async def get_strategy_hints(settings: Settings, portfolio: PortfolioSnapshot, scenarios: list[StressScenario]) -> list[str]:
    """Return untrusted strategy labels only. Numeric scoring remains deterministic."""
    if not settings.featherless_api_key:
        return []
    prompt = {
        "equity": portfolio.equity,
        "gross_exposure": portfolio.gross_exposure,
        "drawdown_pct": portfolio.drawdown_pct,
        "top_symbols": [p.symbol for p in portfolio.positions[:5]],
        "stress_losses": [s.estimated_loss for s in scenarios],
    }
    body: dict[str, Any] = {
        "model": settings.featherless_model,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": "You propose hedge strategy categories only. Return a JSON array containing up to three items chosen only from: protective_put, put_spread, tail_put. Do not invent prices, returns, contracts, or risk numbers."},
            {"role": "user", "content": json.dumps(prompt, separators=(",", ":"))},
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{settings.featherless_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {settings.featherless_api_key}", "Content-Type": "application/json"},
                json=body,
            )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"]
        start, end = text.find("["), text.rfind("]")
        if start < 0 or end <= start:
            return []
        parsed = json.loads(text[start : end + 1])
        if not isinstance(parsed, list):
            return []
        return [item for item in parsed if isinstance(item, str) and item in _ALLOWED][:3]
    except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return []
