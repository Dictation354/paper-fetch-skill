# Elsevier XML to Markdown Mapping

This project renders Elsevier full text from the official Article Retrieval XML.
Element and asset classification rules live in [`src/paper_fetch/providers/_elsevier_xml_rules.py`](../src/paper_fetch/providers/_elsevier_xml_rules.py), and Markdown rendering lives in [`src/paper_fetch/providers/_article_markdown_elsevier.py`](../src/paper_fetch/providers/_article_markdown_elsevier.py).

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
- `ce:table`: render Markdown table from `tgroup/thead/tbody`; row/column spans are semantically expanded into rectangular cells with a conversion note
- `ce:e-component`: omit from body Markdown, collect into `## Supplementary Materials`
- `ce:formula`, `mml:math`, `ce:tex-math`: render as display math
- `ce:inline-formula`: render inline math
- `ce:bibliography` / `ce:bib-reference`: build structured numbered references before falling back to metadata references

## Ignored Sections

These section titles are intentionally omitted from body Markdown:

- `Graphical abstract`
- `Supplementary data`

## Asset Rules

- `gr*`: body figure image
- `fx*`: appendix figure image
- `ga*`: graphical abstract image, never shown in `Additional Figures`
- `tbl*`: table asset
- `mmc*`, `si*`, `sup*`, `am`: supplementary material

## Rendering Notes

- Appendix figures stay in appendix context even if the body text mentions `Fig. A1`.
- `Supplementary data` placeholder displays are not treated as formulas.
- `Additional Figures` / `Additional Tables` only contain still-unused body assets.
- Assets already rendered inline are marked as consumed by the article model and must not be appended again at the end.
- Complex Elsevier tables with row/column spans keep a readable Markdown table plus conversion note. The quality signal is `table_layout_degraded` when layout fidelity is reduced but cell semantics are still present; reserve semantic-loss flags for actual content loss.
- Formula output goes through shared LaTeX normalization after backend conversion. Publisher-specific `\updelta`-style upright Greek macros become standard KaTeX macros, and `\mspace{Nmu}` becomes `\mkernNmu`.
- References extracted from XML should keep original order and numbering. Missing DOI/page/year fields are left missing rather than invented.
