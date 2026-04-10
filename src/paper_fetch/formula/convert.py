"""MathML formula conversion adapters and benchmark helpers."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from ..config import ROOT_DIR

SCRIPT_DIR = ROOT_DIR / "scripts"
FORMULA_TOOLS_DIR = ROOT_DIR / ".formula-tools"
FORMULA_TOOLS_BIN_DIR = FORMULA_TOOLS_DIR / "bin"
FORMULA_TOOLS_LIB_DIR = FORMULA_TOOLS_DIR / "lib"
FORMULA_TOOLS_VENDOR_DIR = FORMULA_TOOLS_DIR / "vendor"

BACKEND_AUTO = "auto"
BACKEND_TEXMATH = "texmath"
BACKEND_MATHML_TO_LATEX = "mathml-to-latex"
BACKEND_MML2TEX = "mml2tex"
BACKEND_LEGACY = "legacy"
SUPPORTED_BACKENDS = {
    BACKEND_AUTO,
    BACKEND_TEXMATH,
    BACKEND_MATHML_TO_LATEX,
    BACKEND_MML2TEX,
    BACKEND_LEGACY,
}
BENCHMARK_BACKENDS = (
    BACKEND_TEXMATH,
    BACKEND_MATHML_TO_LATEX,
    BACKEND_MML2TEX,
)
AUTO_BACKENDS = (
    BACKEND_TEXMATH,
    BACKEND_MATHML_TO_LATEX,
)
DEFAULT_BACKEND = BACKEND_TEXMATH
DEFAULT_TIMEOUT_SECONDS = 5.0
MATHML_NS = "http://www.w3.org/1998/Math/MathML"
ET.register_namespace("", MATHML_NS)


@dataclass(slots=True)
class FormulaConversionResult:
    backend: str
    status: str
    latex: str
    raw_mathml: str
    error: str | None
    duration_ms: int
    display_mode: bool


@dataclass(slots=True)
class FormulaSample:
    sample_id: str
    source_path: str
    source_provider: str
    display_mode: bool
    raw_mathml: str
    source_context: str | None = None


def xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def stringify_mathml(element: ET.Element | str | None) -> str:
    if element is None:
        return ""
    if isinstance(element, str):
        return element.strip()
    if element.tail:
        clone = deepcopy(element)
        clone.tail = None
        return ET.tostring(clone, encoding="unicode").strip()
    return ET.tostring(element, encoding="unicode").strip()


def normalize_latex(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.strip()
    if text.startswith("<?mml2tex"):
        match = re.search(r"<\?mml2tex\s+(.*?)\?>", text, flags=re.S)
        text = match.group(1).strip() if match else text
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"^\$(.+)\$$", r"\1", text)
    return text.strip()


def resolve_backend(env: Mapping[str, str] | None = None, backend: str | None = None) -> str:
    selected = (backend or (env or os.environ).get("MATHML_CONVERTER_BACKEND") or DEFAULT_BACKEND).strip().lower()
    aliases = {
        "mathml_to_latex": BACKEND_MATHML_TO_LATEX,
        "mathml-to-latex": BACKEND_MATHML_TO_LATEX,
        "legacy": BACKEND_LEGACY,
    }
    selected = aliases.get(selected, selected)
    if selected not in SUPPORTED_BACKENDS:
        raise ValueError(f"Unsupported formula backend: {selected}")
    return selected


def subprocess_env(overrides: Mapping[str, str] | None = None) -> dict[str, str]:
    merged = dict(os.environ)
    merged.update({key: str(value) for key, value in (overrides or {}).items()})
    return merged


def first_existing_path(candidates: Iterable[str | Path | None]) -> str:
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists():
            return str(path)
    return ""


def split_classpath(value: str | None) -> list[str]:
    return [item for item in (value or "").split(os.pathsep) if item]


def classpath_entries_exist(value: str | None) -> bool:
    entries = split_classpath(value)
    return bool(entries) and all(Path(entry).exists() for entry in entries)


def _completed_result(
    *,
    backend: str,
    raw_mathml: str,
    display_mode: bool,
    started_at: float,
    latex: str = "",
    error: str | None = None,
    status: str = "ok",
) -> FormulaConversionResult:
    return FormulaConversionResult(
        backend=backend,
        status=status,
        latex=normalize_latex(latex),
        raw_mathml=raw_mathml,
        error=error,
        duration_ms=max(0, round((time.monotonic() - started_at) * 1000)),
        display_mode=display_mode,
    )


def _run_command(
    args: list[str],
    *,
    input_text: str,
    env: Mapping[str, str] | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        env=subprocess_env(env),
        cwd=str(cwd) if cwd else None,
        check=False,
    )


def convert_with_texmath(
    raw_mathml: str,
    *,
    display_mode: bool,
    env: Mapping[str, str] | None = None,
) -> FormulaConversionResult:
    runtime_env = dict(env or os.environ)
    texmath_bin = (
        runtime_env.get("TEXMATH_BIN", "").strip()
        or first_existing_path(
            [
                FORMULA_TOOLS_BIN_DIR / "texmath",
            ]
        )
        or "texmath"
    )
    started_at = time.monotonic()
    if shutil.which(texmath_bin) is None and not Path(texmath_bin).exists():
        return _completed_result(
            backend=BACKEND_TEXMATH,
            raw_mathml=raw_mathml,
            display_mode=display_mode,
            started_at=started_at,
            status="failed",
            error=f"texmath executable not found: {texmath_bin}",
        )

    args = [texmath_bin, "-f", "mathml", "-t", "tex"]
    if not display_mode:
        args.append("--inline")

    try:
        process = _run_command(args, input_text=raw_mathml, env=runtime_env)
    except subprocess.TimeoutExpired:
        return _completed_result(
            backend=BACKEND_TEXMATH,
            raw_mathml=raw_mathml,
            display_mode=display_mode,
            started_at=started_at,
            status="failed",
            error="texmath timed out",
        )

    if process.returncode != 0:
        return _completed_result(
            backend=BACKEND_TEXMATH,
            raw_mathml=raw_mathml,
            display_mode=display_mode,
            started_at=started_at,
            status="failed",
            error=(process.stderr or process.stdout or f"texmath exited with {process.returncode}").strip(),
        )

    latex = normalize_latex(process.stdout)
    if latex.endswith("\\"):
        latex = latex[:-1].rstrip() + (r"\:" if "<mspace" in raw_mathml else "")
    if not latex:
        return _completed_result(
            backend=BACKEND_TEXMATH,
            raw_mathml=raw_mathml,
            display_mode=display_mode,
            started_at=started_at,
            status="failed",
            error="texmath returned empty output",
        )
    return _completed_result(
        backend=BACKEND_TEXMATH,
        raw_mathml=raw_mathml,
        display_mode=display_mode,
        started_at=started_at,
        latex=latex,
    )


def convert_with_mathml_to_latex(
    raw_mathml: str,
    *,
    display_mode: bool,
    env: Mapping[str, str] | None = None,
) -> FormulaConversionResult:
    runtime_env = dict(env or os.environ)
    node_bin = runtime_env.get("MATHML_TO_LATEX_NODE_BIN", "node").strip() or "node"
    script_path = runtime_env.get(
        "MATHML_TO_LATEX_SCRIPT",
        str(SCRIPT_DIR / "mathml_to_latex_cli.mjs"),
    )
    started_at = time.monotonic()

    if shutil.which(node_bin) is None and not Path(node_bin).exists():
        return _completed_result(
            backend=BACKEND_MATHML_TO_LATEX,
            raw_mathml=raw_mathml,
            display_mode=display_mode,
            started_at=started_at,
            status="failed",
            error=f"node executable not found: {node_bin}",
        )
    if not Path(script_path).exists():
        return _completed_result(
            backend=BACKEND_MATHML_TO_LATEX,
            raw_mathml=raw_mathml,
            display_mode=display_mode,
            started_at=started_at,
            status="failed",
            error=f"mathml-to-latex wrapper script not found: {script_path}",
        )

    args = [node_bin, script_path]
    try:
        process = _run_command(args, input_text=raw_mathml, env=runtime_env, cwd=ROOT_DIR)
    except subprocess.TimeoutExpired:
        return _completed_result(
            backend=BACKEND_MATHML_TO_LATEX,
            raw_mathml=raw_mathml,
            display_mode=display_mode,
            started_at=started_at,
            status="failed",
            error="mathml-to-latex timed out",
        )

    if process.returncode != 0:
        return _completed_result(
            backend=BACKEND_MATHML_TO_LATEX,
            raw_mathml=raw_mathml,
            display_mode=display_mode,
            started_at=started_at,
            status="failed",
            error=(process.stderr or process.stdout or f"mathml-to-latex exited with {process.returncode}").strip(),
        )

    latex = normalize_latex(process.stdout)
    if not latex:
        return _completed_result(
            backend=BACKEND_MATHML_TO_LATEX,
            raw_mathml=raw_mathml,
            display_mode=display_mode,
            started_at=started_at,
            status="failed",
            error="mathml-to-latex returned empty output",
        )
    return _completed_result(
        backend=BACKEND_MATHML_TO_LATEX,
        raw_mathml=raw_mathml,
        display_mode=display_mode,
        started_at=started_at,
        latex=latex,
    )


def convert_with_mml2tex(
    raw_mathml: str,
    *,
    display_mode: bool,
    env: Mapping[str, str] | None = None,
) -> FormulaConversionResult:
    runtime_env = dict(env or os.environ)
    java_bin = (
        runtime_env.get("MML2TEX_JAVA_BIN", "").strip()
        or first_existing_path(
            [
                FORMULA_TOOLS_BIN_DIR / "java",
            ]
        )
        or "java"
    )
    local_saxon_jar = first_existing_path([FORMULA_TOOLS_LIB_DIR / "Saxon-HE-12.5.jar"])
    local_xmlresolver_jar = first_existing_path([FORMULA_TOOLS_LIB_DIR / "xmlresolver-5.2.2.jar"])
    local_xmlresolver_data_jar = first_existing_path([FORMULA_TOOLS_LIB_DIR / "xmlresolver-5.2.2-data.jar"])
    local_stylesheet = first_existing_path([FORMULA_TOOLS_VENDOR_DIR / "mml2tex" / "xsl" / "invoke-mml2tex.xsl"])
    local_catalog = first_existing_path([FORMULA_TOOLS_DIR / "mml2tex.catalog.xml"])

    classpath = runtime_env.get("MML2TEX_CLASSPATH", "").strip()
    saxon_jar = runtime_env.get("MML2TEX_SAXON_JAR", "").strip() or local_saxon_jar
    xmlresolver_jar = runtime_env.get("MML2TEX_XMLRESOLVER_JAR", "").strip() or local_xmlresolver_jar
    xmlresolver_data_jar = runtime_env.get("MML2TEX_XMLRESOLVER_DATA_JAR", "").strip() or local_xmlresolver_data_jar
    stylesheet = runtime_env.get("MML2TEX_STYLESHEET", "").strip() or local_stylesheet
    catalog = runtime_env.get("MML2TEX_CATALOG", "").strip() or local_catalog
    started_at = time.monotonic()

    missing = []
    if shutil.which(java_bin) is None and not Path(java_bin).exists():
        missing.append(f"java executable not found: {java_bin}")
    if classpath:
        if not classpath_entries_exist(classpath):
            missing.append("mml2tex classpath contains missing jars")
    else:
        if not saxon_jar or not Path(saxon_jar).exists():
            missing.append(f"Saxon jar not found: {saxon_jar or '<unset>'}")
        if not xmlresolver_jar or not Path(xmlresolver_jar).exists():
            missing.append(f"xmlresolver jar not found: {xmlresolver_jar or '<unset>'}")
        if not xmlresolver_data_jar or not Path(xmlresolver_data_jar).exists():
            missing.append(f"xmlresolver data jar not found: {xmlresolver_data_jar or '<unset>'}")
    if not stylesheet or not Path(stylesheet).exists():
        missing.append(f"mml2tex stylesheet not found: {stylesheet or '<unset>'}")
    if not catalog or not Path(catalog).exists():
        missing.append(f"XML catalog not found: {catalog or '<unset>'}")
    if missing:
        return _completed_result(
            backend=BACKEND_MML2TEX,
            raw_mathml=raw_mathml,
            display_mode=display_mode,
            started_at=started_at,
            status="failed",
            error="; ".join(missing),
        )

    with tempfile.TemporaryDirectory(prefix="mml2tex-") as tmpdir:
        tmpdir_path = Path(tmpdir)
        input_path = tmpdir_path / "input.xml"
        input_path.write_text(raw_mathml, encoding="utf-8")
        java_classpath = classpath or os.pathsep.join(
            [
                saxon_jar,
                xmlresolver_jar,
                xmlresolver_data_jar,
            ]
        )
        args = [
            java_bin,
            "-cp",
            java_classpath,
            "net.sf.saxon.Transform",
            f"-catalog:{catalog}",
            f"-xsl:{stylesheet}",
            f"-s:{input_path}",
        ]
        try:
            process = _run_command(args, input_text="", env=runtime_env)
        except subprocess.TimeoutExpired:
            return _completed_result(
                backend=BACKEND_MML2TEX,
                raw_mathml=raw_mathml,
                display_mode=display_mode,
                started_at=started_at,
                status="failed",
                error="mml2tex timed out",
            )

    if process.returncode != 0:
        return _completed_result(
            backend=BACKEND_MML2TEX,
            raw_mathml=raw_mathml,
            display_mode=display_mode,
            started_at=started_at,
            status="failed",
            error=(process.stderr or process.stdout or f"mml2tex exited with {process.returncode}").strip(),
        )

    match = re.search(r"<\?mml2tex\s+(.*?)\?>", process.stdout, flags=re.S)
    latex = normalize_latex(match.group(1) if match else process.stdout)
    if not latex:
        return _completed_result(
            backend=BACKEND_MML2TEX,
            raw_mathml=raw_mathml,
            display_mode=display_mode,
            started_at=started_at,
            status="failed",
            error="mml2tex returned empty output",
        )
    return _completed_result(
        backend=BACKEND_MML2TEX,
        raw_mathml=raw_mathml,
        display_mode=display_mode,
        started_at=started_at,
        latex=latex,
    )


def convert_mathml_string(
    raw_mathml: str,
    *,
    display_mode: bool,
    env: Mapping[str, str] | None = None,
    backend: str | None = None,
) -> FormulaConversionResult:
    runtime_env = dict(env or os.environ)
    explicitly_selected = bool((backend or runtime_env.get("MATHML_CONVERTER_BACKEND") or "").strip())
    selected_backend = resolve_backend(env=env, backend=backend)
    if selected_backend == BACKEND_TEXMATH:
        result = convert_with_texmath(raw_mathml, display_mode=display_mode, env=runtime_env)
        if result.status == "ok" or explicitly_selected:
            return result
        fallback = convert_with_mathml_to_latex(raw_mathml, display_mode=display_mode, env=runtime_env)
        if fallback.status == "ok":
            return fallback
        return _completed_result(
            backend=BACKEND_TEXMATH,
            raw_mathml=raw_mathml,
            display_mode=display_mode,
            started_at=time.monotonic(),
            status="failed",
            error=f"texmath failed: {result.error}; mathml-to-latex fallback failed: {fallback.error}",
        )
    if selected_backend == BACKEND_MATHML_TO_LATEX:
        return convert_with_mathml_to_latex(raw_mathml, display_mode=display_mode, env=runtime_env)
    if selected_backend == BACKEND_MML2TEX:
        return convert_with_mml2tex(raw_mathml, display_mode=display_mode, env=runtime_env)
    if selected_backend == BACKEND_LEGACY:
        raise RuntimeError("Legacy conversion is not available through formula_conversion.py")
    if selected_backend == BACKEND_AUTO:
        for candidate in AUTO_BACKENDS:
            result = convert_mathml_string(raw_mathml, display_mode=display_mode, env=runtime_env, backend=candidate)
            if result.status == "ok":
                return result
        return _completed_result(
            backend=BACKEND_AUTO,
            raw_mathml=raw_mathml,
            display_mode=display_mode,
            started_at=time.monotonic(),
            status="failed",
            error="All external formula backends failed",
        )
    raise ValueError(f"Unsupported formula backend: {selected_backend}")


def convert_mathml_element_to_latex(
    element: ET.Element | str | None,
    *,
    display_mode: bool,
    env: Mapping[str, str] | None = None,
    backend: str | None = None,
) -> FormulaConversionResult:
    raw_mathml = stringify_mathml(element)
    if not raw_mathml:
        return FormulaConversionResult(
            backend=resolve_backend(env=env, backend=backend),
            status="failed",
            latex="",
            raw_mathml="",
            error="No MathML payload was provided",
            duration_ms=0,
            display_mode=display_mode,
        )
    return convert_mathml_string(raw_mathml, display_mode=display_mode, env=env, backend=backend)


def looks_like_mathml_element(element: ET.Element) -> bool:
    tag = element.tag if isinstance(element.tag, str) else ""
    return tag.rsplit("}", 1)[-1] == "math"


def infer_source_provider(root: ET.Element, xml_path: Path) -> str:
    root_name = xml_local_name(root.tag if isinstance(root.tag, str) else "")
    if root_name == "full-text-retrieval-response":
        return "elsevier"
    if root_name == "article":
        return "springer"
    lower_name = xml_path.name.lower()
    if "elsevier" in lower_name:
        return "elsevier"
    if "springer" in lower_name:
        return "springer"
    return "unknown"


def extract_formula_samples_from_xml(xml_path: Path, *, limit: int | None = None) -> list[FormulaSample]:
    try:
        root = ET.parse(xml_path).getroot()
    except ET.ParseError:
        return []

    samples: list[FormulaSample] = []
    seen: set[str] = set()
    counter = 0
    source_provider = infer_source_provider(root, xml_path)
    for node in root.iter():
        if not isinstance(node.tag, str) or not looks_like_mathml_element(node):
            continue
        raw_mathml = stringify_mathml(node)
        if not raw_mathml or raw_mathml in seen:
            continue
        seen.add(raw_mathml)
        display_attr = (node.get("display") or "").strip().lower()
        display_mode = display_attr == "block"
        samples.append(
            FormulaSample(
                sample_id=f"{xml_path.stem}:{counter}",
                source_path=str(xml_path),
                source_provider=source_provider,
                display_mode=display_mode,
                raw_mathml=raw_mathml,
            )
        )
        counter += 1
        if limit is not None and len(samples) >= limit:
            break
    return samples


def collect_formula_samples(
    xml_paths: Iterable[Path],
    *,
    per_file_limit: int | None = None,
) -> list[FormulaSample]:
    collected: list[FormulaSample] = []
    for xml_path in xml_paths:
        collected.extend(extract_formula_samples_from_xml(xml_path, limit=per_file_limit))
    return collected
