from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    JWT_SECRET: str
    LANGSMITH_API_KEY: str = ""
    CHROMA_PATH: str = str(Path(__file__).resolve().parent.parent / "chroma_db")
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Phase 3: when to re-run the agent (no LLM on every event / every view)
    # Fire after a small concentrated signal batch (2–3), not a long manual grind
    EVENT_TRIGGER_THRESHOLD: int = 3
    EVENT_COOLDOWN_SECONDS: int = 45
    EVENT_VIEW_DEDUPE_SECONDS: int = 90
    RECOMMENDATION_TTL_HOURS: int = 24

    LLM_PROVIDER: str = "mesh"

    # Mesh (submission)
    MESH_API_KEY: str = ""
    MESH_BASE_URL: str = "https://api.meshapi.ai/v1"
    MESH_MODEL: str = "openai/gpt-4o-mini"


    AGENT_EVENT_LIMIT: int = 40
    AGENT_TOP_K: int = 8
    AGENT_TARGET_RESOURCES: int = 3
    AGENT_MAX_RETRIES: int = 2
    AGENT_SIGNAL_LIMIT: int = 6


    @property
    def llm_api_key(self) -> str:
        p = self.LLM_PROVIDER.lower()
        if p == "mesh":
            return self.MESH_API_KEY
      
    @property
    def llm_base_url(self) -> str:
        p = self.LLM_PROVIDER.lower()
        if p == "mesh":
            return self.MESH_BASE_URL
        

    @property
    def llm_model(self) -> str:
        p = self.LLM_PROVIDER.lower()
        if p == "mesh":
            return self.MESH_MODEL

settings = Settings()
