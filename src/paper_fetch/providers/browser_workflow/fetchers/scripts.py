"""Bounded browser URL/dimension discovery scripts.

These scripts never serialize image pixels. Binary transfer is delegated to
the pinned direct transport after Python validates the discovered URL.
"""

from __future__ import annotations

_LOADED_IMAGE_CANVAS_EXPORT_SCRIPT = r"""
([targetUrl, minWidth, minHeight]) => {
  const normalizeUrl = (value) => {
    try { return new URL(String(value || ''), document.baseURI).href; }
    catch (error) { return String(value || ''); }
  };
  const target = normalizeUrl(targetUrl);
  const loaded = Array.from(document.images || []).filter((image) =>
    image.complete
    && image.naturalWidth >= minWidth
    && image.naturalHeight >= minHeight
  );
  const image = loaded.find((candidate) =>
    target && normalizeUrl(candidate.currentSrc || candidate.src || '') === target
  ) || loaded.sort((left, right) =>
    (right.naturalWidth * right.naturalHeight)
    - (left.naturalWidth * left.naturalHeight)
  )[0];
  if (!image) {
    return {ok: false, reason: 'no_loaded_image', url: target};
  }
  const url = normalizeUrl(image.currentSrc || image.src || target);
  if (!/^https?:\/\//i.test(url)) {
    return {ok: false, reason: 'browser_stream_unavailable', url};
  }
  return {
    ok: true,
    streamOnly: true,
    status: 200,
    url,
    contentType: 'image/*',
    width: image.naturalWidth || image.width || 0,
    height: image.naturalHeight || image.height || 0,
  };
}
"""


_ARTICLE_IMAGE_CANVAS_EXPORT_SCRIPT = r"""
([targetUrl, minWidth, minHeight]) => {
  const normalizeUrl = (value) => {
    try { return new URL(String(value || ''), document.baseURI).href; }
    catch (error) { return String(value || ''); }
  };
  const target = normalizeUrl(targetUrl);
  const images = Array.from(document.images || []);
  const image = images.find((candidate) => {
    const url = normalizeUrl(candidate.currentSrc || candidate.src || '');
    return target && url === target;
  });
  if (!image) {
    return {ok: false, found: false, reason: 'target_image_not_found', url: target};
  }
  const url = normalizeUrl(image.currentSrc || image.src || target);
  if (!/^https?:\/\//i.test(url)) {
    return {ok: false, found: true, reason: 'browser_stream_unavailable', url};
  }
  const loaded = image.complete
    && image.naturalWidth >= minWidth
    && image.naturalHeight >= minHeight;
  return {
    ok: loaded,
    found: true,
    streamOnly: true,
    reason: loaded ? '' : 'target_image_not_loaded',
    status: 200,
    url,
    contentType: 'image/*',
    width: image.naturalWidth || image.width || 0,
    height: image.naturalHeight || image.height || 0,
  };
}
"""


__all__ = [
    "_ARTICLE_IMAGE_CANVAS_EXPORT_SCRIPT",
    "_LOADED_IMAGE_CANVAS_EXPORT_SCRIPT",
]
