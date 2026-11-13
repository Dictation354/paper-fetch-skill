"""Streaming transport double using the test's recorded response source."""

from pathlib import Path
from paper_fetch.http import HttpStreamOptions, RequestFailure


class RecordedStreamTransport:
    def _cancellable_sleep(self, seconds):
        pass

    def stream_to_file(self, method, url, destination, *, headers=None, options=None):
        options = options or HttpStreamOptions()
        response = self.request(
            method,
            url,
            headers=headers,
            timeout=options.timeout or 20,
            retry_on_transient=bool(options.retry_on_transient),
            request_policy=options.request_policy,
        )
        body = response.get("body", b"")
        limit = getattr(options.request_policy, "max_response_bytes", None)
        if limit is not None and len(body) > limit:
            raise RequestFailure(None, "Response exceeded byte limit", url=url)
        if options.on_response_headers:
            options.on_response_headers(
                response.get("url", url), response.get("headers", {})
            )
        if options.on_content_length:
            options.on_content_length(len(body))
        if options.on_chunk:
            options.on_chunk(len(body))
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        Path(destination).write_bytes(body)
        return {
            **response,
            "staging_path": str(destination),
            "downloaded_bytes": len(body),
            "body_preview": body[:65536],
        }


def configure_stream_transport(transport):
    """Give an injected Mock the current streaming transport method."""
    transport.stream_to_file.side_effect = lambda *args, **kwargs: (
        RecordedStreamTransport.stream_to_file(transport, *args, **kwargs)
    )
    return transport
