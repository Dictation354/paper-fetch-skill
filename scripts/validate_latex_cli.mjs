import katex from "katex";

const displayMode = process.argv.includes("--display");
let input = "";
for await (const chunk of process.stdin) {
  input += chunk;
}

try {
  katex.renderToString(input, {
    displayMode,
    throwOnError: true,
    output: "html",
    strict: "warn"
  });
  process.stdout.write("ok");
} catch (error) {
  process.stderr.write(String(error?.message || error));
  process.exit(1);
}
