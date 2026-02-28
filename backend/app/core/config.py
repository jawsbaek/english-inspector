import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "English Inspector API"
    debug: bool = True

    # LLM API Keys (DSPy/LiteLLM also reads from env vars directly)
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""

    # Model configuration (PDF spec 2026 models, LiteLLM format)
    generation_model: str = "openai/gpt-5.2"  # Main generation (reasoning model)
    evaluation_model: str = "anthropic/claude-sonnet-4-6"  # Evaluation & scoring
    multimodal_model: str = "gemini/gemini-3.1-pro"  # Long context / multimodal

    # DSPy settings
    best_of_n: int = 3  # Best-of-N sampling count
    max_retries: int = 2  # Retry on verification failure
    quality_threshold: int = 6  # Minimum score to pass quality filter

    # Database
    database_url: str = "sqlite+aiosqlite:///./english_inspector.db"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def configure_env(self):
        """Push API keys to environment for DSPy/LiteLLM to pick up."""
        if self.openai_api_key:
            os.environ["OPENAI_API_KEY"] = self.openai_api_key
        if self.anthropic_api_key:
            os.environ["ANTHROPIC_API_KEY"] = self.anthropic_api_key
        if self.gemini_api_key:
            os.environ["GEMINI_API_KEY"] = self.gemini_api_key


settings = Settings()
settings.configure_env()
