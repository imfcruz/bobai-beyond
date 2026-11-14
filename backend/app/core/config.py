"""
Configurações centrais da aplicação via variáveis de ambiente.
"""

from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Projeto ───────────────────────────────────────────────────────────────
    PROJECT_NAME: str = "Adaptive Security MVP"
    VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = True

    # ── API ───────────────────────────────────────────────────────────────────
    API_V1_PREFIX: str = "/api/v1"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    # ── Banco de dados ────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/adaptive_security.db"

    # ── LLM — configuração agnóstica de provedor ──────────────────────────────
    LLM_PROVIDER: Literal["bob", "watsonx", "mock"] = "mock"
    LLM_MODEL: str = "mock-model"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 1024

    # ── Modo de operação dos agentes ──────────────────────────────────────────
    # AI_MODE: análise com modelo de linguagem real.
    # RULES_MODE: análise determinística sem LLM (padrão quando provider=mock).
    # Determinado automaticamente pelo provider, mas pode ser forçado via env.
    AGENT_MODE: Literal["AI_MODE", "RULES_MODE", "auto"] = "auto"

    # ── Watsonx específico ────────────────────────────────────────────────────
    WATSONX_PROJECT_ID: str = ""
    WATSONX_REGION: str = "us-south"

    # ── IBM Bob Shell ────────────────────────────────────────────────────────
    # A chave de inferência fica apenas no .env local e é repassada ao processo
    # pelo ambiente. Nunca aparece nos argumentos de linha de comando.
    BOB_API_KEY: str = ""
    BOB_TEAM_ID: str = ""  # necessário somente para chaves do tipo General
    BOB_SHELL_COMMAND: str = "bob"
    BOB_MAX_COST: float = 0.05
    BOB_TIMEOUT_SECONDS: float = 90.0
    AGENT_PIPELINE_TIMEOUT_SECONDS: float = 195.0

    # ── Segurança ─────────────────────────────────────────────────────────────
    SECRET_KEY: str = "change-this-in-production-use-secrets-generate"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ── Motor de decisão ──────────────────────────────────────────────────────
    RISK_THRESHOLD_LOW: float = 0.3
    RISK_THRESHOLD_MEDIUM: float = 0.6
    RISK_THRESHOLD_HIGH: float = 0.85

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v: str | list) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


settings = Settings()
