from typing import Optional
from core.notifiers.base import Notifier


class TeamsNotifier(Notifier):
    def __init__(self, config):
        self.config = config

    def find_thread(self, pr_id: int) -> Optional[str]: raise NotImplementedError
    def wait_for_thread(self, pr_id: int, interval: int = 15) -> str: raise NotImplementedError
    def post_message(self, text: str, thread_id: Optional[str] = None) -> None: raise NotImplementedError
    def mention(self, user_id: str) -> str: raise NotImplementedError
