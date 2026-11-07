# Elsevier XML to Markdown Mapping

This project renders Elsevier full text from the official Article Retrieval XML.
Element and asset classification rules live in [`src/paper_fetch/providers/_elsevier_xml_rules.py`](../src/paper_fetch/providers/_elsevier_xml_rules.py), official object selection lives in [`src/paper_fetch/providers/_elsevier_objects.py`](../src/paper_fetch/providers/_elsevier_objects.py), and Markdown rendering lives in [`src/paper_fetch/providers/_article_markdown_elsevier.py`](../src/paper_fetch/providers/_article_markdown_elsevier.py).

## Basis

- Elsevier Journal Article / CEP DTD element semantics
- Elsevier Tag-by-Tag guidance for common-text (`ce:`) structures
- Official asset references exposed through `<object>` and `attachment-metadata-doc`

## Element Mapping

- All `ce:abstract` elements are rendered in source order, including parallel `xml:lang` variants; their structured subsection headings and paragraphs keep their original language and order.
- A `class="graphical"` abstract can contain textual `Highlights`; preserve those paragraphs under their source heading. The class alone does not imply an empty or duplicate image abstract.
- `ce:sections`, `ce:appendices`, `ce:appendix`: container only, recurse into children
- `ce:section`, `ce:abstract-sec`: combine the direct source `ce:label` with `ce:section-title` or `title` without repeating an existing number, then recurse; never infer absent labels
- `ce:data-availability`, `ce:conflict-of-interest`, `ce:acknowledgment`: collect from article head/body/tail in source order; traverse each subtree once
- `ce:keywords/ce:keyword`: merge article keywords into metadata
- `ce:para`, `ce:simple-para`: render paragraph text, then render nested display blocks
- `ce:display`: classify in this order
  1. figure
  2. table
  3. supplementary `e-component`
  4. formula / MathML / `tex-math`
- `ce:figure`: register assets before rendering abstracts; render graphical abstract images inside the abstract, and body/appendix images near their anchor or caption
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

## Rendering Semantics

User-visible rendering rules are maintained in [the Elsevier chapter](../docs/extraction-rules.md#elsevier):

- [Formula expressions and locator images](../docs/extraction-rules.md#rule-elsevier-formula-rendering), with the shared [source TeX boundary](../docs/extraction-rules.md#rule-formula-latex-normalization).
- [Supplementary materials](../docs/extraction-rules.md#rule-elsevier-supplementary-materials) and [appendix context](../docs/extraction-rules.md#rule-elsevier-appendix-context).
- [Inline figure/table placement](../docs/extraction-rules.md#rule-elsevier-inline-figure-table-placement), [consumed asset deduplication](../docs/extraction-rules.md#rule-elsevier-consumed-figure-table-dedup), and [CALS table groups](../docs/extraction-rules.md#rule-xml-table-groups).
- [Complex table spans](../docs/extraction-rules.md#rule-elsevier-complex-table-span-degradation), [structured references](../docs/extraction-rules.md#rule-elsevier-xml-references), and [graphical abstracts](../docs/extraction-rules.md#rule-elsevier-graphical-abstract).

HTML-specific extraction, source anchors, article notes and accepted DOI completion are described in [ScienceDirect HTML parsing](../docs/extraction-rules.md#sciencedirect-html-专用解析). Pure XML conversion has no network effects.
