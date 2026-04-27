import readline from "node:readline";
import { MathMLToLaTeX } from "mathml-to-latex";

const reader = readline.createInterface({
  input: process.stdin,
  crlfDelay: Infinity,
});

for await (const line of reader) {
  if (!line.trim()) {
    continue;
  }
  let request;
  try {
    request = JSON.parse(line);
    const output = MathMLToLaTeX.convert(String(request.mathml ?? ""));
    process.stdout.write(JSON.stringify({ id: request.id, ok: true, latex: String(output ?? "").trim() }) + "\n");
  } catch (error) {
    process.stdout.write(
      JSON.stringify({
        id: request?.id ?? null,
        ok: false,
        error: String(error?.stack || error?.message || error),
      }) + "\n",
    );
  }
}
