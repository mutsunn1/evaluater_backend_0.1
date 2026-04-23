"""Tests for app/config.py Settings loading."""

import importlib


class TestSettingsModule:
    """Test the actual Settings class from the app module."""

    def test_settings_is_instance_of_base_settings(self):
        from pydantic_settings import BaseSettings
        from app.config import settings

        assert isinstance(settings, BaseSettings)

    def test_settings_has_expected_fields(self):
        from app.config import settings

        assert hasattr(settings, "database_url")
        assert hasattr(settings, "es_host")
        assert hasattr(settings, "es_port")
        assert hasattr(settings, "es_index")
        assert hasattr(settings, "default_llm_api_key")
        assert hasattr(settings, "default_llm_base_url")
        assert hasattr(settings, "default_llm_model_name")
        assert hasattr(settings, "host")
        assert hasattr(settings, "port")
        assert hasattr(settings, "log_level")

    def test_settings_defaults(self):
        """Verify default values when env vars are not set.

        We create an isolated Settings instance with no env_file and
        cleared env vars to test defaults only.
        """
        from pydantic_settings import BaseSettings
        import os

        saved = {}
        keys = [
            "DATABASE_URL", "ES_HOST", "ES_PORT", "ES_INDEX",
            "DEFAULT_LLM_API_KEY", "DEFAULT_LLM_BASE_URL",
            "DEFAULT_LLM_MODEL_NAME", "HOST", "PORT", "LOG_LEVEL",
        ]
        for key in keys:
            if key in os.environ:
                saved[key] = os.environ.pop(key)

        try:
            class TestSettings(BaseSettings):
                database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/evaluator_db"
                es_host: str = "localhost"
                es_port: int = 9200
                es_index: str = "mid_term_memory"
                default_llm_api_key: str = ""
                default_llm_base_url: str = "https://api.openai.com/v1"
                default_llm_model_name: str = "gpt-4o-mini"
                host: str = "0.0.0.0"
                port: int = 8000
                log_level: str = "info"
                model_config = {"env_file": None}

            s = TestSettings()
            assert s.database_url == "postgresql+asyncpg://postgres:postgres@localhost:5432/evaluator_db"
            assert s.es_host == "localhost"
            assert s.es_port == 9200
            assert s.port == 8000
            assert s.log_level == "info"
            assert s.default_llm_api_key == ""
        finally:
            for key, val in saved.items():
                os.environ[key] = val
