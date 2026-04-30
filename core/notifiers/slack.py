import json
import time
from typing import Optional
from urllib.request import Request, urlopen

from core.notifiers.base import Notifier


class SlackNotifier(Notifier):

    def __init__(self, config):
        self.token      = config.token
        self.channel_id = config.channel_id

    def _api(self, method: str, payload: dict) -> dict:
        data = json.dumps(payload).encode()
        req = Request(
            f"https://slack.com/api/{method}",
            data=data,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        with urlopen(req, timeout=10) as r:
            return json.loads(r.read())

    def find_thread(self, pr_id: int) -> Optional[str]:
        result = self._api("conversations.history", {"channel": self.channel_id, "limit": 200})
        needle = f"pullrequest/{pr_id}"
        for msg in result.get("messages", []):
            if needle in msg.get("text", ""):
                return msg["ts"]
            for att in msg.get("attachments", []):
                if needle in att.get("text", "") or needle in att.get("fallback", "") or needle in att.get("title_link", ""):
                    return msg["ts"]
            for block in msg.get("blocks", []):
                if needle in json.dumps(block):
                    return msg["ts"]
        return None

    def wait_for_thread(self, pr_id: int, interval: int = 15) -> str:
        while True:
            ts = self.find_thread(pr_id)
            if ts:
                return ts
            time.sleep(interval)

    def post_message(self, text: str, thread_id: Optional[str] = None) -> None:
        payload = {"channel": self.channel_id, "text": text}
        if thread_id:
            payload["thread_ts"] = thread_id
        self._api("chat.postMessage", payload)

    def mention(self, user_id: str) -> str:
        return f"<@{user_id}>"
