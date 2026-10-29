"""Object Retrieval credentials on the independent supplementary route."""

from contextlib import closing
from urllib.parse import urlsplit
from unittest import mock

import pytest

from paper_fetch.http import HttpTransport
from paper_fetch.http.url_policy import SafeRemoteUrlPolicy, ValidatedRemoteUrl
from paper_fetch.providers.elsevier import ElsevierClient, _object_request_headers
from paper_fetch.runtime import RuntimeContext
from tests.support.http_cache import FakeHTTPResponse


@pytest.mark.parametrize(
    "url,authorized",
    [
        ("https://api.elsevier.com/content/object/mmc1", True),
        ("https://api.elsevier.com:443/content/object/mmc1", True),
        ("http://api.elsevier.com/content/object/mmc1", False),
        ("https://api.elsevier.com:8443/content/object/mmc1", False),
        ("https://api.elsevier.com/content/other/mmc1", False),
        ("https://api.elsevier.com.evil.test/content/object/mmc1", False),
        ("https://api.elsevier.com@evil.test/content/object/mmc1", False),
        ("https://api.elsevier.com:invalid/content/object/mmc1", False),
    ],
)
def test_object_credentials_are_scoped_to_https_origin_and_path(url, authorized):
    headers = {"x-ELS-apikey": "virtual-key", "Accept": "*/*"}
    filtered = _object_request_headers(url, headers)
    assert ("x-ELS-apikey" in filtered) is authorized
    assert filtered["Accept"] == "*/*"
    assert headers["x-ELS-apikey"] == "virtual-key"


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("archive", [False, True])
def test_supplementary_auth_downloads_redirects_and_partial_failure(
    monkeypatch, tmp_path, streaming, archive
):
    doi = "10.1016/test.supplementary"
    official = "https://api.elsevier.com/content/object/"
    urls = [
        official + "mmc1.csv",
        "https://assets.example.test/mmc2.csv",
        official + "mmc3.csv",
        official + "mmc4.csv",
    ]
    redirect_target = "https://cdn.example.test/mmc3.csv"
    xml = (
        "<response><doi>"
        + doi
        + "</doi>"
        + "".join(
            f'<object ref="mmc{i}" type="MULTIMEDIA" mimetype="text/csv">{url}</object>'
            for i, url in enumerate(urls, 1)
        )
        + "</response>"
    ).encode()

    def validate(self, url, **kwargs):
        parsed = urlsplit(url)
        return ValidatedRemoteUrl(
            url=url,
            scheme=parsed.scheme,
            host=parsed.hostname,
            port=parsed.port or 443,
            addresses=("93.184.216.34",),
        )

    monkeypatch.setattr(SafeRemoteUrlPolicy, "validate", validate)
    calls = []
    with closing(HttpTransport(cache_ttl=0)) as transport:
        transport._streaming_ready = streaming
        client = ElsevierClient(transport, {"ELSEVIER_API_KEY": "virtual-key"})
        index_url = client._official_article_url(doi)

        def request(method, url, *, headers, **kwargs):
            calls.append((url, {k.lower(): v for k, v in headers.items()}))
            if url.startswith(index_url):
                body, status, response_headers = xml, 200, {"content-type": "text/xml"}
            elif url == urls[2]:
                body, status, response_headers = b"", 302, {"location": redirect_target}
            elif url == urls[3]:
                body, status, response_headers = (
                    b"Forbidden",
                    403,
                    {"content-type": "text/plain"},
                )
            else:
                body, status, response_headers = (
                    b"a,b\n1,2\n",
                    200,
                    {"content-type": "text/csv"},
                )
            return FakeHTTPResponse(body, url, status=status, headers=response_headers)

        monkeypatch.setattr(transport._pool, "request", request)
        monkeypatch.setattr(
            client,
            "fetch_raw_fulltext",
            mock.Mock(side_effect=AssertionError("body request")),
        )
        with RuntimeContext(env={}, transport=transport) as context:
            result, _ = client.fetch_supplementary(
                doi, {"doi": doi}, tmp_path if archive else None, context=context
            )
    assert len(result.assets) == 4
    assert result.discovery_complete
    if not archive:
        assert len(calls) == 1
        assert not result.asset_failures
        assert not list(tmp_path.rglob("*.csv"))
        return
    assert len(calls) == 6
    for url, headers in calls:
        if url.startswith("https://api.elsevier.com/"):
            assert headers["x-els-apikey"] == "virtual-key"
        else:
            assert "x-els-apikey" not in headers
    assert len(result.asset_failures) == 1
    assert result.asset_failures[0]["source_url"] == urls[3]
    assert result.asset_failures[0]["status"] == 403
    assert result.asset_failures[0]["reason"]
    assert len([asset for asset in result.assets if asset.get("path")]) == 3
    assert len(list(tmp_path.rglob("*.csv"))) == 3
