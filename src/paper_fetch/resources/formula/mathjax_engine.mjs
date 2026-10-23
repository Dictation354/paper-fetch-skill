// Synchronous, offline MathJax: preload every supported TeX extension and the
// complete original TeX SVG font, as described in MathJax's server/preload guide.
import { mathjax } from '@mathjax/src/js/mathjax.js'
import { TeX } from '@mathjax/src/js/input/tex.js'
import { SVG } from '@mathjax/src/js/output/svg.js'
import { liteAdaptor } from '@mathjax/src/js/adaptors/liteAdaptor.js'
import { RegisterHTMLHandler } from '@mathjax/src/js/handlers/html.js'
import { AssistiveMmlHandler } from '@mathjax/src/js/a11y/assistive-mml.js'
import { MathJaxTexFont } from '@mathjax/mathjax-tex-font/js/svg.js'
import { MathJaxBbmFontExtension } from '@mathjax/mathjax-bbm-font-extension/js/svg.js'
import '@mathjax/src/js/input/tex/bbm/BbmConfiguration.js'
import '@mathjax/src/js/input/tex/textcomp/TextcompConfiguration.js'
import { MathJaxMhchemFontExtension } from '@mathjax/mathjax-mhchem-font-extension/js/svg.js'
import '@mathjax/src/js/input/tex/ams/AmsConfiguration.js'
import '@mathjax/src/js/input/tex/amscd/AmsCdConfiguration.js'
import '@mathjax/src/js/input/tex/newcommand/NewcommandConfiguration.js'
import '@mathjax/src/js/input/tex/configmacros/ConfigMacrosConfiguration.js'
import '@mathjax/src/js/input/tex/textmacros/TextMacrosConfiguration.js'
import '@mathjax/src/js/input/tex/boldsymbol/BoldsymbolConfiguration.js'
import '@mathjax/src/js/input/tex/mathtools/MathtoolsConfiguration.js'
import '@mathjax/src/js/input/tex/mhchem/MhchemConfiguration.js'
import '@mathjax/src/js/input/tex/upgreek/UpgreekConfiguration.js'
import '@mathjax/src/js/input/tex/unicode/UnicodeConfiguration.js'
import '@mathjax/src/js/input/tex/bbox/BboxConfiguration.js'
import '@mathjax/src/js/input/tex/braket/BraketConfiguration.js'
import '@mathjax/src/js/input/tex/cancel/CancelConfiguration.js'
import '@mathjax/src/js/input/tex/color/ColorConfiguration.js'
import '@mathjax/src/js/input/tex/enclose/EncloseConfiguration.js'
import '@mathjax/src/js/input/tex/extpfeil/ExtpfeilConfiguration.js'
import '@mathjax/src/js/input/tex/verb/VerbConfiguration.js'
import '@mathjax/src/js/input/tex/cases/CasesConfiguration.js'

export const mathjaxVersion = mathjax.version
export const mathjaxExtensions = Object.freeze([
  'base', 'ams', 'amscd', 'newcommand', 'configmacros', 'textmacros',
  'boldsymbol', 'mathtools', 'mhchem', 'upgreek', 'unicode', 'bbox',
  'braket', 'cancel', 'color', 'enclose', 'extpfeil', 'verb', 'cases', 'bbm', 'textcomp'
])

const adaptor = liteAdaptor()
AssistiveMmlHandler(RegisterHTMLHandler(adaptor))

// Convert only MathJax-generated nodes, after the reader's HTML sanitizer.
// Keep the SVG/MathML attributes intact; hast's JSX compiler maps them to React.
function toHast(node) {
  if (adaptor.kind(node) === '#text') return { type: 'text', value: adaptor.value(node) }
  const properties = Object.fromEntries(adaptor.allAttributes(node).map(({ name, value }) => (
    name === 'class' ? ['className', value.split(/\s+/u)] : [name, value]
  )))
  return {
    type: 'element', tagName: adaptor.kind(node), properties,
    children: adaptor.childNodes(node).map(toHast)
  }
}

/** A renderer belongs to one document: macros and errors never cross documents. */
export function createMathRenderer() {
  const errors = []
  const tex = new TeX({
    packages: [...mathjaxExtensions],
    // convert() propagates compile/typeset failures; promote TeX parse failures
    // to the same path instead of silently accepting MathJax's error MathML.
    formatError: (_jax, error) => { throw error }
  })
  const svg = new SVG({ fontData: MathJaxTexFont, fontCache: 'none' })
  svg.addExtension(MathJaxMhchemFontExtension)
  svg.addExtension(MathJaxBbmFontExtension)
  const document = mathjax.document('', {
    InputJax: tex,
    OutputJax: svg,
    enableAssistiveMml: true
  })
  return {
    errors,
    render(expression, displayMode = false) {
      try {
        const node = document.convert(expression, { display: displayMode })
        return { node: toHast(node), error: null }
      } catch (error) {
        const diagnostic = {
          expression, displayMode,
          message: typeof error?.message === 'string' ? error.message : String(error)
        }
        errors.push(diagnostic)
        return {
          node: {
            type: 'element', tagName: displayMode ? 'div' : 'span',
            properties: { className: ['mathjax-error'], title: diagnostic.message },
            children: [{ type: 'text', value: expression }]
          },
          error: diagnostic
        }
      }
    },
    stylesheet() {
      return toHast(document.outputJax.styleSheet(document))
    }
  }
}

const textContent = (node) => node.type === 'text'
  ? node.value : (node.children ?? []).map(textContent).join('')

/** Run after rehype-raw and rehype-sanitize, with a fresh renderer for each tree. */
export function rehypeMathjax() {
  return (tree, file) => {
    const renderer = createMathRenderer()
    let formulas = 0
    function visit(parent) {
      if (!parent.children) return
      parent.children = parent.children.map((node) => {
        const classes = node.properties?.className ?? []
        if (node.type === 'element' && ['math-inline', 'math-display', 'language-math'].some((name) => classes.includes(name))) {
          formulas++
          const result = renderer.render(textContent(node), classes.includes('math-display'))
          if (result.error) file.message(result.error.message, node.position, 'mathjax')
          return result.node
        }
        // A fenced math block is pre > code.language-math. Replace the pre too.
        if (node.type === 'element' && node.tagName === 'pre' && node.children?.length === 1 &&
          node.children[0].properties?.className?.includes('language-math')) {
          formulas++
          const code = node.children[0]
          const result = renderer.render(textContent(code).replace(/\n$/u, ''), true)
          if (result.error) file.message(result.error.message, code.position, 'mathjax')
          return result.node
        }
        visit(node)
        return node
      })
    }
    visit(tree)
    if (formulas) tree.children.unshift(renderer.stylesheet())
  }
}
