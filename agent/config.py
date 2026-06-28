from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    google_api_key: str = ""
    openai_api_key: str = ""

    planner_model: str = "gemini-2.0-flash"
    synthesiser_model: str = "gemini-2.0-flash"
    summariser_model: str = "gemini-2.0-flash"
    guardrail_model: str = "gemini-2.0-flash"

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_url: str = ""        # overrides host+port when set (Qdrant Cloud)
    qdrant_api_key: str = ""    # required for Qdrant Cloud
    qdrant_collection: str = "knowledge_base"
    qdrant_dense_vector_name: str = "dense"
    qdrant_sparse_vector_name: str = "sparse"
    qdrant_dense_size: int = 1024

    bge_embedding_model: str = "BAAI/bge-m3"
    bge_reranker_model: str = "BAAI/bge-reranker-v2-m3"

    bm25_index_path: str = "data/bm25_index.pkl"
    # BM25 (rank_bm25) is opt-in. Default OFF: retrieval is dense + BGE-M3 sparse
    # (the scalable, RBAC-filtered lexical index). Enable only for a labeled A/B —
    # the flag-on path re-ranks RBAC-filtered candidates only (no tenant leak).
    enable_bm25: bool = False

    gliner_model: str = "urchade/gliner_mediumv2.1"

    rrf_top_k: int = 50
    final_top_k: int = 5
    reranker_high_threshold: float = 0.6
    reranker_medium_threshold: float = 0.3
    live_docs_confidence_threshold: float = 0.5

    gemini_max_retries: int = 3
    gemini_retry_base_delay: float = 1.0

    jira_base_url: str = ""
    jira_api_token: str = ""
    jira_project_key: str = ""

    firecrawl_api_key: str = ""
    tavily_api_key: str = ""

    # NL-to-SQL tool — direct PostgreSQL connection string.
    # e.g. postgresql://postgres:password@db.yourproject.supabase.co:5432/postgres
    # Leave empty to disable the sql_query agent gracefully.
    # Reads DATABASE_URL or PG_DSN from environment.
    database_url: str = ""
    pg_dsn: str = ""
    sql_max_rows: int = 20

    @property
    def effective_database_url(self) -> str:
        return self.database_url or self.pg_dsn


settings = Settings()
