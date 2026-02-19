"""Configuración centralizada para Investigador de Prospectos."""
import os
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


@dataclass
class LLMConfig:
    deepseek_api_key: str
    anthropic_api_key: str
    deepseek_model: str = "deepseek-chat"
    haiku_model: str = "claude-3-5-haiku-20241022"


@dataclass
class ScraperConfig:
    max_results_per_source: int = 10
    timeout_seconds: int = 15
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


@dataclass
class AppConfig:
    mode: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    min_research_score: int = 40
    sender_name: str = "Gustavo Peralta"
    sender_company: str = "Faymex"


class Settings:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.llm = LLMConfig(
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        )
        self.scraper = ScraperConfig()
        self.app = AppConfig(
            mode=os.getenv("APP_MODE", "development"),
            port=int(os.getenv("PORT", "8000")),
            sender_name=os.getenv("SENDER_NAME", "Gustavo Peralta"),
            sender_company=os.getenv("SENDER_COMPANY", "Faymex"),
        )

    def validate(self) -> list[str]:
        errors = []
        if not self.llm.deepseek_api_key and not self.llm.anthropic_api_key:
            errors.append("Se requiere DEEPSEEK_API_KEY o ANTHROPIC_API_KEY")
        return errors


settings = Settings()


def get_settings() -> Settings:
    return settings
