import readline from 'node:readline'
import { createMathRenderer } from './mathjax_engine.mjs'

const sessions = new Map()
for await (const line of readline.createInterface({ input: process.stdin, crlfDelay: Infinity })) {
  if (!line.trim()) continue
  let request
  try {
    request = JSON.parse(line)
    if (request.operation === 'close') {
      sessions.delete(request.session)
      process.stdout.write(JSON.stringify({ id: request.id, ok: true }) + '\n')
      continue
    }
    let renderer = sessions.get(request.session)
    if (!renderer) {
      renderer = createMathRenderer()
      sessions.set(request.session, renderer)
    }
    const { error } = renderer.render(String(request.expression ?? ''), Boolean(request.displayMode))
    // Rendering errors are validation results, distinct from protocol/tool failures.
    process.stdout.write(JSON.stringify({ id: request.id, ok: true, valid: !error, error }) + '\n')
  } catch (error) {
    process.stdout.write(JSON.stringify({ id: request?.id ?? null, ok: false, error: String(error?.message ?? error) }) + '\n')
  }
}
