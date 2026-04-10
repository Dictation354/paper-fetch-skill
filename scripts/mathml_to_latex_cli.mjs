import { MathMLToLaTeX } from "mathml-to-latex";

let input = "";
for await (const chunk of process.stdin) {
  input += chunk;
}

try {
  const output = MathMLToLaTeX.convert(input);
  process.stdout.write(String(output ?? "").trim());
} catch (error) {
  process.stderr.write(String(error?.stack || error?.message || error));
  process.exit(1);
}
