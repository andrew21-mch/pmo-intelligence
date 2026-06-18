from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_secret_key: str = "dev-secret"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://pmo:pmo_secret@localhost:5432/pmo_intelligence"

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "pmo_documents"

    # LLM — defaults to local Ollama (no API key required)
    llm_provider: str = "ollama"  # ollama | openai
    ollama_base_url: str = "http://host.docker.internal:11434/v1"
    ollama_model: str = "llama3.2"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    jira_base_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_sync_interval_minutes: int = 60

    @property
    def llm_model(self) -> str:
        return self.ollama_model if self.llm_provider == "ollama" else self.openai_model


settings = Settings()
