from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Secrets are read from environment only."""

    alpaca_key_id: str | None = Field(default=None, validation_alias="APCA_API_KEY_ID")
    alpaca_secret_key: str | None = Field(default=None, validation_alias="APCA_API_SECRET_KEY")
    alpaca_paper_base_url: str = Field(default="https://paper-api.alpaca.markets", validation_alias="ALPACA_PAPER_BASE_URL")
    alpaca_data_base_url: str = Field(default="https://data.alpaca.markets", validation_alias="ALPACA_DATA_BASE_URL")
    demo_mode: bool = Field(default=True, validation_alias="RAPTORCLICK_DEMO_MODE")
    enable_paper_execution: bool = Field(default=False, validation_alias="ENABLE_PAPER_EXECUTION")
    featherless_api_key: str | None = Field(default=None, validation_alias="FEATHERLESS_API_KEY")
    featherless_base_url: str = Field(default="https://api.featherless.ai/v1", validation_alias="FEATHERLESS_BASE_URL")
    featherless_model: str = Field(default="zai-org/GLM-5.3-Flash", validation_alias="FEATHERLESS_MODEL")
    reauction_drift_threshold_pct: float = Field(default=1.5, validation_alias="REAUCTION_DRIFT_THRESHOLD_PCT")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def alpaca_configured(self) -> bool:
        return bool(self.alpaca_key_id and self.alpaca_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
