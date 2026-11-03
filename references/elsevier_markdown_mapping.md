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

## Rendering Notes

- Appendix figures stay in appendix context even if the body text mentions `Fig. A1`.
- `Supplementary data` placeholder displays are not treated as formulas.
- `Additional Figures` / `Additional Tables` only contain still-unused body assets.
- Assets already rendered inline are marked as consumed by the article model and must not be appended again at the end.
- Multiple CALS `tgroup` elements are never forced into one rectangular grid. Each successful `exact` / `normalized` group avoids degradation; each group that truly falls back to a readable list contributes one `table_fallback_count` and one `table_layout_degraded_count`. A failed group does not downgrade successful sibling groups.
- Formula output goes through shared LaTeX normalization after backend conversion. Publisher-specific `\updelta`-style upright Greek macros become standard KaTeX macros, and `\mspace{Nmu}` becomes `\mkernNmu`.
- Formula object images are fidelity fallbacks, not OCR input. A downloaded local path wins over the official remote URL; either image increments `formula_fallback_count`, keeps overall quality `degraded`, and does not increment `formula_missing_count`. A visible unavailable placeholder remains mandatory when neither an expression nor a matching object exists.
- References extracted from XML keep original membership, order and numbering. After identity and full-text acceptance, missing DOIs may be filled from the parent Crossref record, a unique Crossref bibliographic match, or the identity-checked article's web bibliography. A reference key must have no bibliographic conflict; without one, full normalized title, first author, year and available volume/pages must agree. Completion evidence is kept in diagnostics/trace, existing DOIs are retained, and conversion remains free of network effects. Other missing fields remain missing.
- Extraction revision 11 displays HTML and XML references as sequential `1.` through `N.`; author/year source labels remain suffix annotations, and a year alone is never treated as a counter. The extracted HTML raw citation is reused by ArticleModel without adding another label.
- HTML front-matter `.author-highlights`, `.Highlights` and `.highlights` containers are omitted structurally; body content with those classes, bilingual abstracts, graphical abstracts and XML textual Highlights remain.
- HTML list items merge direct `.list-label` and `.list-content` into their first block. Explicit labels keep their original style; decorative bullets and empty leading blocks are omitted. Paragraphs, equations, figures/captions and nested lists stay within their owning item, including after shared Markdown image normalization. Continuation indentation follows the rendered marker width.

- HTML `.display` classification follows figure, table, attachment, then formula. Caption MathML stays inside its figure. Equations use source labels only, with `data-no-equation-label` for unlabelled source formulas; image fallbacks retain semantic loss counts.
- Elsevier opts into the section walker's table-cell callback, preserving explicit breaks (including headers), scripts, links and math through nested sections and lists. The default shared path is unchanged.
- HTML titles use ordered selector fallback (`h1 .title-text`, `h1.title-text`, `h1`) and omit the separate translated title. `div#p` followed by digits is a paragraph; underline does not split a sentence, and caption source blocks keep their boundaries.
- Topics links become their source text. Exact `Unlabelled Image` captions are omitted while retaining the image. Attachments keep source file type, size and URL without repeated download instructions.
- Source IDs become `elsevier-` HTML anchors after section headings and with their owning figures, tables, formulas, notes or inline content. Bibliography keys and explicit `ref-id-` aliases establish navigation; ordinal position never establishes a match. The optional provider finalizer resolves links against retained unique targets after reference/asset selection and token budgeting, ignores code/math/external links, and never runs for PDF conversion.
- HTML/XML citation formatting and existing DOI completion append a known DOI only when missing, keeping source author/year annotations last. Pure XML conversion performs no network access.
- Article-level `footnote` and `article-footnote` elements and HTML article notes retain source labels and complete content in `Article notes` before References. Table footnotes stay next to their table.
- The 15 paired sources are selected by the fixture manifest. `scripts/refresh_elsevier_baselines.py` rebuilds only derived text, final article/acceptance outputs and their output hashes, preserving original captures, assets, acquisition facts and historical failures.
