from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    google_api_key: str = ""

    planner_model: str = "gemini-2.5-pro"
    synthesiser_model: str = "gemini-2.5-pro"
    summariser_model: str = "gemini-2.5-flash"
    guardrail_model: str = "gemini-2.5-flash"

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "knowledge_base"
    qdrant_dense_vector_name: str = "dense"
    qdrant_sparse_vector_name: str = "sparse"
    qdrant_dense_size: int = 1024

    bge_embedding_model: str = "BAAI/bge-m3"
    bge_reranker_model: str = "BAAI/bge-reranker-v2-m3"

    bm25_index_path: str = "data/bm25_index.pkl"

    gliner_model: str = "urchade/gliner_mediumv2.1"

    rrf_top_k: int = 50
    final_top_k: int = 5
    reranker_high_threshold: float = 0.6
    reranker_medium_threshold: float = 0.4
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
    database_url: str = ""
    sql_max_rows: int = 20


settings = Settings()
