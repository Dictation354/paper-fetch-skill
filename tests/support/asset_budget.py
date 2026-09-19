"""Shared test support; contains no collected tests."""

from __future__ import annotations
from io import BytesIO


class _FakeStreamResponse:
    def __init__(
        self,
        body: bytes,
        *,
        headers: dict[str, str] | None = None,
        status: int = 200,
    ) -> None:
        self.status = status
        self.headers = headers or {}
        self._body = BytesIO(body)
        self._paper_fetch_final_url = "https://assets.example/file.bin"
        self.closed = False
        self.released = False
        self.bytes_read = 0

    def read(self, amount: int, **_kwargs: object) -> bytes:
        payload = self._body.read(amount)
        self.bytes_read += len(payload)
        return payload

    def geturl(self) -> str:
        return self._paper_fetch_final_url

    def close(self) -> None:
        self.closed = True

    def release_conn(self) -> None:
        self.released = True
