from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")
    app_demo_mode: bool = Field(default=True, alias="APP_DEMO_MODE")
    database_url: str = Field(
        default="sqlite+pysqlite:///./storage/case_ai.db", alias="DATABASE_URL"
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    storage_root: Path = Field(default=Path("storage"), alias="STORAGE_ROOT")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    gigachat_client_id: str = Field(default="", alias="GIGACHAT_CLIENT_ID")
    gigachat_client_secret: str = Field(default="", alias="GIGACHAT_CLIENT_SECRET")
    yandex_api_key: str = Field(default="", alias="YANDEX_API_KEY")
    yandex_folder_id: str = Field(default="", alias="YANDEX_FOLDER_ID")
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    default_llm_provider: str = Field(default="fake", alias="DEFAULT_LLM_PROVIDER")
    default_analysis_model: str = Field(default="demo-analysis-v1", alias="DEFAULT_ANALYSIS_MODEL")
    default_code_model: str = Field(default="demo-code-v1", alias="DEFAULT_CODE_MODEL")
    default_test_model: str = Field(default="demo-test-v1", alias="DEFAULT_TEST_MODEL")
    enable_provider_fallback: bool = Field(default=True, alias="ENABLE_PROVIDER_FALLBACK")
    enable_openrouter_for_openai: bool = Field(
        default=False, alias="ENABLE_OPENROUTER_FOR_OPENAI"
    )
    enable_openrouter_for_anthropic: bool = Field(
        default=False, alias="ENABLE_OPENROUTER_FOR_ANTHROPIC"
    )
    cors_origins: str = Field(default="http://localhost:5173,http://localhost:8080", alias="CORS_ORIGINS")
    api_rate_limit_per_minute: int = Field(default=120, alias="API_RATE_LIMIT_PER_MINUTE")
    max_upload_size_mb: int = Field(default=10, alias="MAX_UPLOAD_SIZE_MB")
    deployment_dry_run_default: bool = Field(default=True, alias="DEPLOYMENT_DRY_RUN_DEFAULT")
    mcp_enable_remote: bool = Field(default=True, alias="MCP_ENABLE_REMOTE")
    mcp_allowed_hosts: str = Field(default="localhost,127.0.0.1", alias="MCP_ALLOWED_HOSTS")
    mcp_require_approval_for_side_effect_tools: bool = Field(
        default=True, alias="MCP_REQUIRE_APPROVAL_FOR_SIDE_EFFECT_TOOLS"
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def mcp_allowed_hosts_list(self) -> list[str]:
        return [host.strip() for host in self.mcp_allowed_hosts.split(",") if host.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

