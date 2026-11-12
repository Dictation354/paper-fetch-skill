"""IEEE existing multimedia control discovery."""

from __future__ import annotations
import re
from urllib.parse import urlsplit


def _ieee_filename_control(page, asset):
    filename = str(asset.get("filename_hint") or "")
    if not filename:
        return None
    scope = page.locator(
        "#multimedia, #media, xpl-document-multimedia, xpl-document-media, "
        "xpl-document-media-list, .multimedia, .media-list, "
        "[id*='supplement']"
    )
    controls = scope.locator(
        "button:not([data-url]), a:not([href]), a[href='#'], a[href^='javascript:']"
    ).filter(has_text=filename)
    visible = [
        controls.nth(index)
        for index in range(controls.count())
        if controls.nth(index).is_visible()
    ]
    if len(visible) == 1:
        return visible[0]
    # IEEE's desktop media list can attach its action to the filename label.
    # Restrict this to the known attachment name in the media component; the
    # resulting request must still match that attachment's JSON file URL.
    labels = scope.get_by_text(filename)
    visible = [
        labels.nth(index)
        for index in range(labels.count())
        if labels.nth(index).is_visible()
    ]
    if len(visible) == 1:
        return visible[0]
    media_doi = str(asset.get("doi") or "")
    if not media_doi:
        return None
    # Translated PDFs may show only their multimedia DOI and a PDF icon.
    # Bind the existing icon to the exact DOI provided by multimedia discovery.
    items = scope.locator(".media-item").filter(
        has=page.get_by_text(re.compile(r"^" + re.escape(media_doi) + r"$", re.I))
    )
    icons = items.locator("a[class*='stats-Multimedia_']:visible")
    return icons.first if icons.count() == 1 else None


def find_ieee_missing_link(page, urls, asset, remaining_ms, tab_opened):
    if not asset.get("filename_hint"):
        asset = {**asset, "filename_hint": urlsplit(urls[0]).path.rsplit("/", 1)[-1]}
    control = _ieee_filename_control(page, asset)
    if control is not None:
        return control, tab_opened
    if not tab_opened:
        tab_name = re.compile(
            r"^(Media|Multimedia|Supplemental Items|Supplemental Material|Supplementary Material)$",
            re.I,
        )
        tabs = page.get_by_role("tab", name=tab_name)
        if not tabs.count():
            tabs = page.get_by_text(tab_name)
        for index in range(tabs.count()):
            if tabs.nth(index).is_visible():
                tabs.nth(index).click(timeout=remaining_ms())
                tab_opened = True
                break
    return None, tab_opened
