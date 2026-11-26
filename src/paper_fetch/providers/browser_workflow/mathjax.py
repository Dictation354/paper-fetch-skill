"""Bind runtime MathML to its own typeset element before DOM extraction."""

from typing import Any

from bs4 import BeautifulSoup

from ...extraction.html.parsing import choose_parser

_MATHJAX_ORIGINALS_SCRIPT = r"""() => {
  let recovered = 0;
  const bind = (node, original) => {
    if (!node || typeof original !== 'string' || !/^\s*<(?:[\w-]+:)?math[\s>]/.test(original)) return;
    node.setAttribute('data-paper-fetch-mathml', original);
    recovered++;
  };
  if (window.MathJax && MathJax.Hub && MathJax.Hub.getAllJax) {
    for (const jax of MathJax.Hub.getAllJax()) {
      const source = jax.SourceElement && jax.SourceElement();
      const node = document.getElementById(jax.inputID + '-Frame')
        || (source && source.previousElementSibling);
      bind(node, jax.originalText);
    }
  }
  const doc = window.MathJax && MathJax.startup && MathJax.startup.document;
  if (doc && doc.getMathItemsWithin) {
    for (const item of doc.getMathItemsWithin(document.body)) bind(item.typesetRoot, item.math);
  }
  return { mathjax_original_mathml: recovered };
}"""


def prepare_browser_page(page: Any, *, timeout_ms: int, cancel_check=None):
    del timeout_ms
    if cancel_check is not None:
        cancel_check()
    from ..browser_runtime.navigation import evaluate_main_world

    return evaluate_main_world(page, _MATHJAX_ORIGINALS_SCRIPT)


def restore_runtime_mathml(soup):
    for node in soup.select("[data-paper-fetch-mathml]"):
        math = BeautifulSoup(
            str(node["data-paper-fetch-mathml"]), choose_parser()
        ).find("math")
        if math is not None and math.find(True) is not None:
            node.clear()
            node.append(math)
            node.attrs.pop("aria-hidden", None)
            node["class"] = [
                "display-formula"
                if math.get("display") == "block"
                else "inline-formula"
            ]
