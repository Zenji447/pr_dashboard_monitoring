from dataclasses import dataclass
from typing import Optional


@dataclass
class ProviderConfig:
    type: str                          # "azure_devops" | "github" | "bitbucket"
    org_url: str
    project: str
    repository: str
    extra: dict = None                 # Parámetros específicos del provider


@dataclass
class NotifierConfig:
    type: str                          # "slack" | "teams"
    channel_id: str
    token: str
    ta_users: dict = None              # {"nombre lowercase": "user_id"}


@dataclass
class Config:
    provider: ProviderConfig
    notifier: NotifierConfig
    watched_branches: list[str] = None  # Ramas destino a monitorear


def load_config(path: str = "config.yml") -> Config:
    import yaml
    with open(path) as f:
        raw = yaml.safe_load(f)

    p = raw["provider"]
    n = raw["notifier"]

    return Config(
        provider=ProviderConfig(
            type=p["type"],
            org_url=p.get("org_url", ""),
            project=p.get("project", ""),
            repository=p.get("repository", ""),
            extra=p.get("extra", {}),
        ),
        notifier=NotifierConfig(
            type=n["type"],
            channel_id=n["channel_id"],
            token=n["token"],
            ta_users=n.get("ta_users", {}),
        ),
        watched_branches=raw.get("watched_branches", ["main", "develop"]),
    )
