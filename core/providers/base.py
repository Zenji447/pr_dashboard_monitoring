from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PR:
    id: int
    title: str
    source: str
    target: str
    created_by: str
    url: str
    creation_date: str
    closed_date: str = ""
    my_vote: Optional[str] = None       # "approved" | "rejected" | None
    has_conflicts: bool = False
    can_complete: bool = False
    verdict: str = "revisar"
    reasons: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    scope: str = ""
    changed_files: int = 0
    policy_status: str = "unknown"      # "approved" | "running" | "failed" | "unknown"
    reviewers: list = field(default_factory=list)  # [{"name": str, "vote": int}]


@dataclass
class DeployStatus:
    status: str   # "inProgress" | "succeeded" | "failed" | "unknown"


class PRProvider(ABC):
    """Abstracción sobre cualquier plataforma de PRs (Azure DevOps, GitHub, Bitbucket...)."""

    @abstractmethod
    def get_active_prs(self) -> list[PR]:
        """Retorna los PRs activos relevantes con veredicto ya calculado."""
        ...

    @abstractmethod
    def get_completed_prs(self, date_from: str, date_to: str) -> list[PR]:
        """Retorna PRs completados en el rango de fechas (YYYY-MM-DD)."""
        ...

    @abstractmethod
    def approve(self, pr_id: int) -> None:
        """Aprueba el PR."""
        ...

    @abstractmethod
    def reject(self, pr_id: int, comment: str) -> None:
        """Rechaza el PR con un comentario."""
        ...

    @abstractmethod
    def complete(self, pr_id: int) -> None:
        """Completa/mergea el PR."""
        ...

    @abstractmethod
    def get_deploy_status(self, pr: PR) -> DeployStatus:
        """Retorna el estado del despliegue asociado al PR."""
        ...
