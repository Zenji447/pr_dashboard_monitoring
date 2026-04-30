from core.providers.base import PRProvider
from core.notifiers.base import Notifier


class PREngine:
    """Orquestador central — independiente del provider y notifier."""

    def __init__(self, provider: PRProvider, notifier: Notifier, ta_users: dict):
        self.provider  = provider
        self.notifier  = notifier
        self.ta_users  = ta_users   # {"nombre lowercase": "user_id"}

    def approve(self, pr_id: int) -> dict:
        self.provider.approve(pr_id)
        self.notifier.notify_approved(pr_id)
        return {"ok": True}

    def reject(self, pr_id: int, comment: str) -> dict:
        self.provider.reject(pr_id, comment)
        self.notifier.notify_rejected(pr_id)
        return {"ok": True}

    def complete(self, pr_id: int) -> dict:
        self.provider.complete(pr_id)
        self.notifier.notify_completed(pr_id)
        return {"ok": True}

    def request_ta_review(self, pr_id: int, pr_reviewers: list[dict]) -> dict:
        """Menciona a los TAs pendientes en el hilo del PR."""
        mentions = [
            self.notifier.mention(self.ta_users[name])
            for r in pr_reviewers
            if (name := (r.get("name") or "").lower().strip()) in self.ta_users
            and r.get("vote", 0) != 10
        ]
        self.notifier.request_ta_review(pr_id, mentions)
        return {"ok": True}

    def notify_conflict(self, pr_id: int) -> None:
        self.notifier.notify_conflict(pr_id)
