"""Playwright page scripts for browser workflow fetchers."""

from __future__ import annotations

_LOADED_IMAGE_CANVAS_EXPORT_SCRIPT = """
([targetUrl, minWidth, minHeight]) => {
  const bytesToBase64 = (bytes) => {
    let binary = '';
    const chunkSize = 0x8000;
    for (let index = 0; index < bytes.length; index += chunkSize) {
      const chunk = bytes.subarray(index, index + chunkSize);
      binary += String.fromCharCode(...chunk);
    }
    return btoa(binary);
  };
  const normalizeUrl = (value) => {
    try {
      return new URL(String(value || ''), document.baseURI).href;
    } catch (error) {
      return String(value || '');
    }
  };
  const classifyCanvasError = (error) => {
    const name = String((error && error.name) || '');
    const message = String((error && error.message) || error || '');
    const blob = `${name} ${message}`.toLowerCase();
    if (
      name === 'SecurityError'
      || blob.includes('tainted')
      || blob.includes('cross-origin')
      || blob.includes('insecure operation')
    ) {
      return {
        reason: 'canvas_tainted',
        error: name || message,
      };
    }
    return {
      reason: 'canvas_serialization_failed',
      error: name || message,
    };
  };
  const normalizedTarget = normalizeUrl(targetUrl);
  const loadedImages = Array.from(document.images || []).filter((image) =>
    image.complete
    && image.naturalWidth >= minWidth
    && image.naturalHeight >= minHeight
  );
  const image = loadedImages.find((candidate) =>
    normalizedTarget
    && normalizeUrl(candidate.currentSrc || candidate.src || '') === normalizedTarget
  ) || loadedImages
    .sort((left, right) => (right.naturalWidth * right.naturalHeight) - (left.naturalWidth * left.naturalHeight))[0];
  if (!image) {
    return {
      ok: false,
      reason: 'no_loaded_image',
      url: normalizedTarget || normalizeUrl(document.location.href),
      title: document.title || '',
      contentType: document.contentType || '',
    };
  }
  const chosenUrl = normalizeUrl(image.currentSrc || image.src || normalizedTarget || document.location.href);
  const canvas = document.createElement('canvas');
  canvas.width = image.naturalWidth || image.width || 0;
  canvas.height = image.naturalHeight || image.height || 0;
  const context = canvas.getContext('2d');
  if (!context || !canvas.width || !canvas.height) {
    return {
      ok: false,
      reason: 'missing_canvas_context',
      url: chosenUrl,
      title: document.title || '',
      contentType: document.contentType || '',
    };
  }
  try {
    context.drawImage(image, 0, 0);
  } catch (error) {
    const classified = classifyCanvasError(error);
    return {
      ok: false,
      reason: classified.reason,
      error: classified.error,
      url: chosenUrl,
      title: document.title || '',
      contentType: document.contentType || '',
    };
  }
  try {
    const dataUrl = canvas.toDataURL('image/png');
    const bodyB64 = String(dataUrl || '').split(',', 2)[1] || '';
    if (!bodyB64) {
      return {
        ok: false,
        reason: 'canvas_serialization_failed',
        url: chosenUrl,
        title: document.title || '',
        contentType: document.contentType || '',
      };
    }
    return {
      ok: true,
      status: 200,
      url: chosenUrl,
      contentType: 'image/png',
      bodyB64,
      width: image.naturalWidth || canvas.width,
      height: image.naturalHeight || canvas.height,
    };
  } catch (error) {
    const classified = classifyCanvasError(error);
    return {
      ok: false,
      reason: classified.reason,
      error: classified.error,
      url: chosenUrl,
      title: document.title || '',
      contentType: document.contentType || '',
    };
  }
}
"""
