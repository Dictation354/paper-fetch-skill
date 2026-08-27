"""Browser page scripts for browser workflow fetchers."""

from __future__ import annotations

_LOADED_IMAGE_CANVAS_EXPORT_SCRIPT = """
([targetUrl, minWidth, minHeight]) => {
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
      dataURL: dataUrl,
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


_ARTICLE_IMAGE_CANVAS_EXPORT_SCRIPT = """
([targetUrl, minWidth, minHeight]) => {
  const normalizeUrl = (value) => {
    try {
      return new URL(String(value || ''), document.baseURI).href;
    } catch (error) {
      return String(value || '');
    }
  };
  const srcsetUrls = (value) => String(value || '')
    .split(',')
    .map((part) => part.trim().split(/\\s+/, 1)[0] || '')
    .filter(Boolean)
    .map(normalizeUrl);
  const imageUrls = (image) => {
    const urls = [
      image.currentSrc,
      image.src,
      image.getAttribute('src'),
      image.getAttribute('data-src'),
      image.getAttribute('data-original'),
      image.getAttribute('data-lazy-src'),
      image.getAttribute('data-image-src'),
    ].map(normalizeUrl);
    urls.push(...srcsetUrls(image.getAttribute('srcset')));
    urls.push(...srcsetUrls(image.getAttribute('data-srcset')));
    const picture = image.closest && image.closest('picture');
    if (picture) {
      for (const source of Array.from(picture.querySelectorAll('source'))) {
        urls.push(...srcsetUrls(source.getAttribute('srcset')));
        urls.push(...srcsetUrls(source.getAttribute('data-srcset')));
      }
    }
    return urls.filter(Boolean);
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
  const images = Array.from(document.images || []);
  const image = images.find((candidate) =>
    normalizedTarget && imageUrls(candidate).includes(normalizedTarget)
  );
  if (!image) {
    return {
      ok: false,
      found: false,
      reason: 'target_image_not_found',
      url: normalizedTarget || normalizeUrl(document.location.href),
      title: document.title || '',
      contentType: document.contentType || '',
      imageCount: images.length,
    };
  }
  try {
    if (image.loading === 'lazy') {
      image.loading = 'eager';
    }
    image.scrollIntoView({block: 'center', inline: 'center'});
  } catch (error) {}
  const chosenUrl = normalizeUrl(image.currentSrc || image.src || normalizedTarget || document.location.href);
  if (
    !image.complete
    || image.naturalWidth < minWidth
    || image.naturalHeight < minHeight
  ) {
    return {
      ok: false,
      found: true,
      reason: 'target_image_not_loaded',
      url: chosenUrl,
      width: image.naturalWidth || image.width || 0,
      height: image.naturalHeight || image.height || 0,
      title: document.title || '',
      contentType: document.contentType || '',
    };
  }
  const canvas = document.createElement('canvas');
  canvas.width = image.naturalWidth || image.width || 0;
  canvas.height = image.naturalHeight || image.height || 0;
  const context = canvas.getContext('2d');
  if (!context || !canvas.width || !canvas.height) {
    return {
      ok: false,
      found: true,
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
      found: true,
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
        found: true,
        reason: 'canvas_serialization_failed',
        url: chosenUrl,
        title: document.title || '',
        contentType: document.contentType || '',
      };
    }
    return {
      ok: true,
      found: true,
      status: 200,
      url: chosenUrl,
      contentType: 'image/png',
      dataURL: dataUrl,
      bodyB64,
      width: image.naturalWidth || canvas.width,
      height: image.naturalHeight || canvas.height,
    };
  } catch (error) {
    const classified = classifyCanvasError(error);
    return {
      ok: false,
      found: true,
      reason: classified.reason,
      error: classified.error,
      url: chosenUrl,
      title: document.title || '',
      contentType: document.contentType || '',
    };
  }
}
"""
