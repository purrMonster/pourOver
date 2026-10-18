"""ntfy is output only: replies to queued messages, and errors."""

from __future__ import annotations

from typing import Optional

import httpx


class Ntfy:
    def __init__(self, base_url: Optional[str], client: Optional[httpx.Client] = None):
        self.base_url = base_url
        self.client = client or httpx.Client(timeout=10.0)

    def send(self, topic: Optional[str], token: Optional[str], message: str, title: str = "pourOver") -> bool:
        if not self.base_url or not topic:
            return False
        headers = {"Title": title, "Tags": "coffee"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            r = self.client.post(f"{self.base_url}/{topic}", content=message.encode(), headers=headers)
            return r.status_code < 300
        except httpx.HTTPError:
            return False
