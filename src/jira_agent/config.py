from __future__ import annotations

from pydantic_settings import BaseSettings


class JiraAgentConfig(BaseSettings):
    jira_base_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_keys: str = ""          # comma-separated, e.g. "BACKEND,INFRA"
    jira_webhook_secret: str = ""
    team_id: str = "default"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def project_key_list(self) -> list[str]:
        return [k.strip() for k in self.jira_project_keys.split(",") if k.strip()]


jira_config = JiraAgentConfig()
