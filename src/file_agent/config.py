from __future__ import annotations

from pydantic_settings import BaseSettings


class FileAgentConfig(BaseSettings):
    file_watch_folder: str = "./data_sources"
    team_id: str = "default"
    max_words_per_chunk: int = 400

    model_config = {"env_file": ".env", "extra": "ignore"}


file_config = FileAgentConfig()
