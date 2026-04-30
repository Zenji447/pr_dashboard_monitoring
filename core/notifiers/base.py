from abc import ABC, abstractmethod
from typing import Optional


class Notifier(ABC):
    """Abstracción sobre cualquier plataforma de mensajería (Slack, Teams...)."""

    @abstractmethod
    def find_thread(self, pr_id: int) -> Optional[str]:
        """Busca el hilo/mensaje del PR en el canal. Retorna el ID del hilo o None."""
        ...

    @abstractmethod
    def wait_for_thread(self, pr_id: int, interval: int = 15) -> str:
        """Espera indefinidamente hasta que aparezca el hilo del PR. Retorna el ID."""
        ...

    @abstractmethod
    def post_message(self, text: str, thread_id: Optional[str] = None) -> None:
        """Publica un mensaje en el canal, opcionalmente en un hilo."""
        ...

    @abstractmethod
    def mention(self, user_id: str) -> str:
        """Retorna el formato de mención para un usuario. Ej: <@U123> en Slack, <at>Nombre</at> en Teams."""
        ...

    def notify_approved(self, pr_id: int) -> None:
        thread = self.wait_for_thread(pr_id)
        self.post_message("✅ Aprobado", thread_id=thread)

    def notify_rejected(self, pr_id: int) -> None:
        thread = self.find_thread(pr_id)
        self.post_message("❌ Rechazado", thread_id=thread)

    def notify_completed(self, pr_id: int) -> None:
        thread = self.find_thread(pr_id)
        self.post_message(
            "🚀 PR integrado — el despliegue está en curso, te avisamos cuando termine.",
            thread_id=thread
        )

    def notify_conflict(self, pr_id: int) -> None:
        thread = self.wait_for_thread(pr_id)
        self.post_message("⚠️ ¡Por favor resolver conflicto!", thread_id=thread)

    def request_ta_review(self, pr_id: int, mentions: list[str]) -> None:
        thread = self.wait_for_thread(pr_id)
        text = " ".join(mentions) if mentions else "TA Reviewer"
        self.post_message(f"{text} por favor revisa este PR 🙏", thread_id=thread)
