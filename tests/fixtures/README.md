Regression fixtures in this directory are intentionally minimized and paraphrased by default.

They keep real sample DOIs, titles, and structural patterns that our parsers rely on,
but most fixtures do not embed full publisher pages or full article text. This keeps the
tests stable and offline while avoiding large copyrighted source dumps.

The current exception is the browser/full-page replay set for raw HTML regression:

- `pnas_10.1073_pnas.2309123120.html`
- `science_10.1126_science.ady3136.html`
- `science_10.1126_science.adp0212.html`
- `science_10.1126_science.aeg3511.html`
- `pnas_10.1073_pnas.2406303121.html`
- `wiley_10.1111_cas.16395.html`
- `wiley_10.1111_gcb.16414.html`

These fixtures preserve the final browser HTML so the HTML-to-markdown extraction chain
can be regression tested end to end and regenerated into `.extracted.md` snapshots.
Other fixtures should stay minimized unless there is a similar benchmark need.
