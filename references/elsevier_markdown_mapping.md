# Elsevier XML to Markdown Mapping

This project renders Elsevier full text from the official Article Retrieval XML.
The rules are centralized in [`scripts/elsevier_xml_rules.py`](../scripts/elsevier_xml_rules.py).

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
- `ce:figure`: render linked local image if a body or appendix image asset exists
- `ce:table`: render Markdown table from `tgroup/thead/tbody`
- `ce:e-component`: omit from body Markdown, collect into `## Supplementary Materials`
- `ce:formula`, `mml:math`, `ce:tex-math`: render as display math
- `ce:inline-formula`: render inline math

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
- `Additional Figures` only contains still-unused body figures.
- Complex Elsevier tables with row/column spans fall back to a short omission notice instead of producing broken Markdown.
