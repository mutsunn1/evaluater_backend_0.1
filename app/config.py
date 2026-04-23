from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    db_user: str = "postgres"
    db_password: str = "postgres"
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "evaluator_db"
    database_url: str = ""
    es_host: str = "localhost"
    es_port: int = 9200
    es_index: str = "mid_term_memory"
    default_llm_api_key: str = ""
    default_llm_base_url: str = "https://api.openai.com/v1"
    default_llm_model_name: str = "gpt-4o-mini"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.database_url:
            self.database_url = (
                f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}"
            )


settings = Settings()
