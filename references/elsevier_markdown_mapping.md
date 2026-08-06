# Elsevier XML to Markdown Mapping

This project renders Elsevier full text from the official Article Retrieval XML.
Element and asset classification rules live in [`src/paper_fetch/providers/_elsevier_xml_rules.py`](../src/paper_fetch/providers/_elsevier_xml_rules.py), official object selection lives in [`src/paper_fetch/providers/_elsevier_objects.py`](../src/paper_fetch/providers/_elsevier_objects.py), and Markdown rendering lives in [`src/paper_fetch/providers/_article_markdown_elsevier.py`](../src/paper_fetch/providers/_article_markdown_elsevier.py).

## Basis

- Elsevier Journal Article / CEP DTD element semantics
- Elsevier Tag-by-Tag guidance for common-text (`ce:`) structures
- Official asset references exposed through `<object>` and `attachment-metadata-doc`

## Element Mapping

- `ce:sections`, `ce:appendices`, `ce:appendix`: container only, recurse into children
- `ce:section`, `ce:abstract-sec`: render heading from `ce:section-title` or `title`, then recurse
- `ce:para`, `ce:simple-para`: render paragraph text, then render nested display blocks
- `ce:display`: classify in this order
  1. figure
  2. table
  3. supplementary `e-component`
  4. formula / MathML / `tex-math`
- `ce:figure`: render linked local image near the figure anchor or caption when a body or appendix image asset exists
- `ce:table`: parse each `tgroup` with its own `cols` / `colspec` and render the groups in source order; table label, caption, and footnotes are emitted once, while a source prefix such as `(a) WBGT` stays immediately before its group
- `ce:e-component`: omit from body Markdown, collect into `## Supplementary Materials`
- `ce:formula`, `mml:math`, `ce:tex-math`: render as display math; when no mathematical expression is available, resolve a nested `link@locator` (or the basename of `xlink:href`) to the best official `<object>` image
- `ce:inline-formula`: render inline math
- `ce:bibliography` / `ce:bib-reference`: build structured numbered references before falling back to metadata references

## Ignored Sections

These section titles are intentionally omitted from body Markdown:

- `Graphical abstract`
- `Supplementary data`

## Asset Rules

- `gr*`: body figure image
- `fx*`: appendix figure image by default; when referenced from a formula locator, classify it as a body formula image without changing ordinary appendix figures
- `ga*`: graphical abstract image, never shown in `Additional Figures`
- `tbl*`: table asset
- `mmc*`, `si*`, `sup*`, `am`: supplementary material

## Rendering Notes

- Appendix figures stay in appendix context even if the body text mentions `Fig. A1`.
- `Supplementary data` placeholder displays are not treated as formulas.
- `Additional Figures` / `Additional Tables` only contain still-unused body assets.
- Assets already rendered inline are marked as consumed by the article model and must not be appended again at the end.
- Multiple CALS `tgroup` elements are never forced into one rectangular grid. Each successful `exact` / `normalized` group avoids degradation; each group that truly falls back to a readable list contributes one `table_fallback_count` and one `table_layout_degraded_count`. A failed group does not downgrade successful sibling groups.
- Formula output goes through shared LaTeX normalization after backend conversion. Publisher-specific `\updelta`-style upright Greek macros become standard KaTeX macros, and `\mspace{Nmu}` becomes `\mkernNmu`.
- Formula object images are fidelity fallbacks, not OCR input. A downloaded local path wins over the official remote URL; either image increments `formula_fallback_count`, keeps overall quality `degraded`, and does not increment `formula_missing_count`. A visible unavailable placeholder remains mandatory when neither an expression nor a matching object exists.
- References extracted from XML should keep original order and numbering. Missing DOI/page/year fields are left missing rather than invented.
