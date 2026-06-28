from pydantic_settings import BaseSettings, SettingsConfigDict


class IngestionSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    google_api_key: str = ""
    cag_model: str = "gemini-2.5-pro"

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "knowledge_base"
    qdrant_dense_vector_name: str = "dense"
    qdrant_sparse_vector_name: str = "sparse"
    qdrant_dense_size: int = 1024
    # Persist the sparse index on disk instead of RAM. Default OFF (current
    # behaviour). Only applied when a collection is CREATED — existing
    # collections must be migrated/recreated to change this.
    qdrant_sparse_on_disk: bool = False

    supabase_url: str = ""
    supabase_key: str = ""

    redis_url: str = "redis://localhost:6379/0"

    bge_embedding_model: str = "BAAI/bge-m3"
    bge_reranker_model: str = "BAAI/bge-reranker-v2-m3"
    gliner_model: str = "urchade/gliner_mediumv2.1"
    spacy_model: str = "en_core_web_sm"

    bm25_index_path: str = "data/bm25_index.pkl"
    # Opt-in BM25. Default OFF: no per-ingest rebuild_from_supabase() (kills the
    # O(corpus) ingest bottleneck). Keep in sync with agent.config.enable_bm25.
    enable_bm25: bool = False

    embed_batch_size: int = 32
    chunk_target_tokens: int = 512
    chunk_max_tokens: int = 768
    chunk_overlap_ratio: float = 0.15

    confluence_base_url: str = ""
    confluence_token: str = ""
    confluence_email: str = ""

    github_token: str = ""
    github_api_url: str = "https://api.github.com"
    github_path_filter: str = "docs/"
    github_branch: str = "main"

    jira_base_url: str = ""
    jira_api_token: str = ""
    jira_project_key: str = ""

    cag_lookback_days: int = 14
    cag_max_tokens: int = 50_000


settings = IngestionSettings()
