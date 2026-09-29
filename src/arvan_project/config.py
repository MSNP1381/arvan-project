import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    google_api_key: str = Field(default="", validation_alias="GOOGLE_API_KEY")
    # Default to Gemini 3.8 Flash as requested
    llm_model: str = Field(default="gemini-3.8-flash", validation_alias="LLM_MODEL")
    embedding_model: str = Field(
        default="Gemini-embedding-001", validation_alias="EMBEDDING_MODEL"
    )
    arvan_ai_base_url: str = Field(
        default="", validation_alias="ARVAN_AI_BASE_URL"
    )
    arvan_ai_api_key: str = Field(
        default="", validation_alias="ARVAN_AI_API_KEY"
    )
    chroma_persist_dir: str = Field(
        default="./.chroma_data", validation_alias="CHROMA_PERSIST_DIR"
    )
    doc_registry_path: str = Field(
        default="./.chroma_data/documents_registry.json",
        validation_alias="DOC_REGISTRY_PATH",
    )
    default_alpha: float = Field(default=0.5, validation_alias="DEFAULT_ALPHA")
    top_k: int = Field(default=4, validation_alias="TOP_K")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
