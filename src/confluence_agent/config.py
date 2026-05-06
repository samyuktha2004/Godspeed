from __future__ import annotations

from pydantic_settings import BaseSettings


class ConfluenceAgentConfig(BaseSettings):
    confluence_base_url: str = ""
    confluence_token: str = ""
    confluence_email: str = ""
    confluence_spaces: str = ""          # comma-separated, e.g. "ENG,PROD"
    confluence_webhook_secret: str = ""
    team_id: str = "default"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def space_list(self) -> list[str]:
        return [s.strip() for s in self.confluence_spaces.split(",") if s.strip()]


confluence_config = ConfluenceAgentConfig()
