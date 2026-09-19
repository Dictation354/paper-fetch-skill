"""Shared test support; contains no collected tests."""

from __future__ import annotations
import io
import urllib.error
import urllib.parse


class FakeHTTPResponse:
    def __init__(
        self,
        body: bytes,
        url: str,
        *,
        status: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._stream = io.BytesIO(body)
        self._url = url
        self.status = status
        self.headers = headers or {"content-type": "text/plain"}
        self.closed = False
        self.released = False

    def read(self, size: int = -1, *args, **kwargs) -> bytes:
        return self._stream.read(size)

    def geturl(self) -> str:
        return self._url

    def close(self) -> None:
        self.closed = True
        self._stream.close()

    def release_conn(self) -> None:
        self.released = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class FakeHTTPError(urllib.error.HTTPError):
    def read(self, *args, **kwargs):
        if getattr(self, "fp", None) is None:
            return b""
        payload = self.fp.read(*args, **kwargs)
        self.fp.close()
        self.fp = None
        return payload


def build_http_error(
    url: str, *, status: int, headers: dict[str, str] | None = None, body: bytes = b""
) -> urllib.error.HTTPError:
    return FakeHTTPError(url, status, f"HTTP {status}", headers or {}, io.BytesIO(body))
