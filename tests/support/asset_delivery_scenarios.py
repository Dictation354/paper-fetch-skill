"""Small article/index and streaming image boundary for directed asset contracts."""

from paper_fetch.providers.base import ProviderContent
from paper_fetch.targeted_assets import AssetContext, discover_content_images
from tests.support.transport import RecordedStreamTransport
from tests.support.wiley_page_assets import png_bytes

SOURCE = "https://example.test/article"
HTML = b"""<article><h1>Example Article</h1><p>Text with equations.</p>
<span class="inline-equation"><img src="/math-1.gif"/></span>
<span class="inline-equation"><img src="/math-1.gif"/></span>
<span class="inline-equation"><img src="/math-2.gif"/></span>
<figure id="f1"><img src="/fig1.png"/><figcaption>Figure 1. Caption.</figcaption></figure>
</article>"""
GIF = bytes.fromhex(
    "47494638396101000100800000000000ffffff21f90401000000002c000000000100010000020144003b"
)
PNG = png_bytes(100, 100)


def asset_state():
    content = ProviderContent(
        route_kind="html", source_url=SOURCE, content_type="text/html", body=HTML
    )
    return AssetContext(
        doi="10.1000/example",
        provider="",
        source_url=SOURCE,
        assets=discover_content_images(content, provider=""),
        discovery_complete=True,
    )


class ImageTransport(RecordedStreamTransport):
    def __init__(self, *, fail=()):
        self.requests = []
        self.fail = set(fail)

    def request(self, method, url, **kwargs):
        self.requests.append(url)
        if url == SOURCE:
            return {
                "status_code": 200,
                "url": url,
                "headers": {"content-type": "text/html"},
                "body": HTML,
            }
        if url in self.fail:
            return {"status_code": 404, "url": url, "headers": {}, "body": b""}
        assert url in {
            SOURCE.replace("/article", name)
            for name in ("/math-1.gif", "/math-2.gif", "/fig1.png", "/table.png")
        }, url
        return {
            "status_code": 200,
            "url": url,
            "headers": {
                "content-type": "image/gif" if url.endswith(".gif") else "image/png"
            },
            "body": GIF if url.endswith(".gif") else PNG,
        }
