"""MathML formula conversion adapters and benchmark helpers."""

from __future__ import annotations

import os
import atexit
from contextlib import contextmanager
from contextvars import ContextVar
import json
import re
import select
import shutil
import subprocess
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from copy import deepcopy
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Callable, Iterable, Iterator, Mapping

from cachetools import LRUCache

from .paths import (
    formula_tools_subpaths,
    mathml_to_latex_script_candidates,
    mathml_to_latex_worker_script_candidates,
)

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
DEFAULT_CONVERSION_CACHE_SIZE = 1024
MATHML_NS = "http://www.w3.org/1998/Math/MathML"
ET.register_namespace("", MATHML_NS)
_CONVERSION_CACHE: LRUCache[tuple[object, ...], FormulaConversionResult] | None = None
_CONVERSION_CACHE_LOCK = threading.RLock()
_MATHML_WORKERS: dict[tuple[str, str], "MathMLToLatexWorker"] = {}
_MATHML_WORKERS_LOCK = threading.Lock()
_FORMULA_TIMING_COLLECTOR: ContextVar[Callable[[float], None] | None] = ContextVar(
    "paper_fetch_formula_timing_collector",
    default=None,
)
_FORMULA_TIMING_DEPTH: ContextVar[int] = ContextVar("paper_fetch_formula_timing_depth", default=0)


def _stop_mathml_workers() -> None:
    with _MATHML_WORKERS_LOCK:
        workers = list(_MATHML_WORKERS.values())
        _MATHML_WORKERS.clear()
    for worker in workers:
        worker.stop()


atexit.register(_stop_mathml_workers)

UPGREEK_LATEX_ALIASES = {
    "upalpha": "alpha",
    "upbeta": "beta",
    "upgamma": "gamma",
    "updelta": "delta",
    "upepsilon": "epsilon",
    "upvarepsilon": "varepsilon",
    "upzeta": "zeta",
    "upeta": "eta",
    "uptheta": "theta",
    "upvartheta": "vartheta",
    "upiota": "iota",
    "upkappa": "kappa",
    "uplambda": "lambda",
    "upmu": "mu",
    "upnu": "nu",
    "upxi": "xi",
    "uppi": "pi",
    "upvarpi": "varpi",
    "uprho": "rho",
    "upvarrho": "varrho",
    "upsigma": "sigma",
    "upvarsigma": "varsigma",
    "uptau": "tau",
    "upupsilon": "upsilon",
    "upphi": "phi",
    "upvarphi": "varphi",
    "upchi": "chi",
    "uppsi": "psi",
    "upomega": "omega",
    "upGamma": "Gamma",
    "upDelta": "Delta",
    "upTheta": "Theta",
    "upLambda": "Lambda",
    "upXi": "Xi",
    "upPi": "Pi",
    "upSigma": "Sigma",
    "upUpsilon": "Upsilon",
    "upPhi": "Phi",
    "upPsi": "Psi",
    "upOmega": "Omega",
}
UPGREEK_LATEX_ALIAS_NAMES = "|".join(
    re.escape(name) for name in sorted(UPGREEK_LATEX_ALIASES, key=len, reverse=True)
)
UPGREEK_LATEX_ALIAS_PATTERN = re.compile(r"\\(" + UPGREEK_LATEX_ALIAS_NAMES + r")(?![A-Za-z])")
LATEX_MSPACE_MU_PATTERN = re.compile(
    r"\\mspace\s*\{\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*mu\s*\}"
)


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


def _env_config_value(env: Mapping[str, str], name: str) -> str:
    return str(env.get(name, "")).strip()


def _env_signature(env: Mapping[str, str], names: Iterable[str]) -> tuple[tuple[str, str], ...]:
    return tuple((name, _env_config_value(env, name)) for name in names)


def _cache_size(env: Mapping[str, str]) -> int:
    raw_value = _env_config_value(env, "MATHML_CONVERSION_CACHE_SIZE")
    if not raw_value:
        return DEFAULT_CONVERSION_CACHE_SIZE
    try:
        return max(0, int(raw_value))
    except ValueError:
        return DEFAULT_CONVERSION_CACHE_SIZE


def clear_conversion_cache() -> None:
    with _CONVERSION_CACHE_LOCK:
        global _CONVERSION_CACHE
        _CONVERSION_CACHE = None


@contextmanager
def formula_timing_collector(collector: Callable[[float], None] | None) -> Iterator[None]:
    """Collect wall-clock seconds spent in top-level MathML conversion calls."""

    token = _FORMULA_TIMING_COLLECTOR.set(collector)
    try:
        yield
    finally:
        _FORMULA_TIMING_COLLECTOR.reset(token)


def _record_formula_timing(started_at: float) -> None:
    collector = _FORMULA_TIMING_COLLECTOR.get()
    if collector is None:
        return
    try:
        collector(max(0.0, time.monotonic() - started_at))
    except Exception:
        pass


def _conversion_cache_for(env: Mapping[str, str]) -> LRUCache[tuple[object, ...], FormulaConversionResult] | None:
    size = _cache_size(env)
    if size <= 0:
        return None
    with _CONVERSION_CACHE_LOCK:
        global _CONVERSION_CACHE
        if _CONVERSION_CACHE is None or _CONVERSION_CACHE.maxsize != size:
            _CONVERSION_CACHE = LRUCache(maxsize=size)
        return _CONVERSION_CACHE


def _cached_result(key: tuple[object, ...], env: Mapping[str, str]) -> FormulaConversionResult | None:
    cache = _conversion_cache_for(env)
    if cache is None:
        return None
    with _CONVERSION_CACHE_LOCK:
        result = cache.get(key)
    return replace(result, duration_ms=0) if result is not None else None


def _store_result(key: tuple[object, ...], env: Mapping[str, str], result: FormulaConversionResult) -> FormulaConversionResult:
    cache = _conversion_cache_for(env)
    if cache is not None:
        with _CONVERSION_CACHE_LOCK:
            cache[key] = replace(result)
    return result


@lru_cache(maxsize=256)
def _first_existing_path_cached(candidates: tuple[str, ...]) -> str:
    return first_existing_path(candidates)


def _path_candidates_signature(candidates: Iterable[str | Path | None]) -> tuple[str, ...]:
    return tuple(str(candidate) for candidate in candidates if candidate)


def _formula_cache_key(
    *,
    backend: str,
    raw_mathml: str,
    display_mode: bool,
    env: Mapping[str, str],
) -> tuple[object, ...]:
    config_names = (
        "MATHML_CONVERTER_BACKEND",
        "PAPER_FETCH_FORMULA_TOOLS_DIR",
        "TEXMATH_BIN",
        "MATHML_TO_LATEX_NODE_BIN",
        "MATHML_TO_LATEX_SCRIPT",
        "MATHML_TO_LATEX_WORKER",
        "MATHML_TO_LATEX_WORKER_SCRIPT",
        "MML2TEX_JAVA_BIN",
        "MML2TEX_CLASSPATH",
        "MML2TEX_SAXON_JAR",
        "MML2TEX_XMLRESOLVER_JAR",
        "MML2TEX_XMLRESOLVER_DATA_JAR",
        "MML2TEX_STYLESHEET",
        "MML2TEX_CATALOG",
    )
    return (
        backend,
        display_mode,
        raw_mathml,
        _env_signature(env, config_names),
        _path_candidates_signature(mathml_to_latex_script_candidates(env)),
        _path_candidates_signature(mathml_to_latex_worker_script_candidates(env)),
    )


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


def normalize_latex_macros(value: str | None) -> str:
    text = value or ""
    if not text:
        return ""

    def replace_alias(match: re.Match[str]) -> str:
        return "\\" + UPGREEK_LATEX_ALIASES[match.group(1)]

    def replace_mspace(match: re.Match[str]) -> str:
        following = match.string[match.end() : match.end() + 1]
        suffix = " " if following and following.isalnum() else ""
        return rf"\mkern{match.group(1)}mu{suffix}"

    text = UPGREEK_LATEX_ALIAS_PATTERN.sub(replace_alias, text)
    return LATEX_MSPACE_MU_PATTERN.sub(replace_mspace, text)


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
    text = re.sub(r"(?<=[A-Za-z0-9])\\textbackslash\\_(?=[A-Za-z0-9])", r"\\_", text)
    text = normalize_latex_macros(text)
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


def subprocess_env(overrides: Mapping[str, str] | None = None) -> Mapping[str, str]:
    if not overrides:
        return os.environ
    merged = dict(os.environ)
    merged.update({key: str(value) for key, value in overrides.items()})
    return merged


def first_existing_path(candidates: Iterable[str | Path | None]) -> str:
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists():
            return str(path)
    return ""


def first_existing_path_cached(candidates: Iterable[str | Path | None]) -> str:
    return _first_existing_path_cached(_path_candidates_signature(candidates))


def split_classpath(value: str | None) -> list[str]:
    return [item for item in (value or "").split(os.pathsep) if item]


def classpath_entries_exist(value: str | None) -> bool:
    entries = split_classpath(value)
    return bool(entries) and all(Path(entry).exists() for entry in entries)


def _worker_enabled(env: Mapping[str, str]) -> bool:
    return _env_config_value(env, "MATHML_TO_LATEX_WORKER").lower() not in {"0", "false", "no", "off"}


def _compact_error_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _resolve_mathml_to_latex_command(runtime_env: Mapping[str, str]) -> tuple[str, str, Path | None, str | None]:
    node_bin = _env_config_value(runtime_env, "MATHML_TO_LATEX_NODE_BIN") or "node"
    configured_script = _env_config_value(runtime_env, "MATHML_TO_LATEX_SCRIPT")
    script_candidates = mathml_to_latex_script_candidates(runtime_env)
    script_path = configured_script or first_existing_path_cached(script_candidates)
    if not script_path and script_candidates:
        script_path = str(script_candidates[0])

    if shutil.which(node_bin) is None and not Path(node_bin).exists():
        return node_bin, script_path, None, f"node executable not found: {node_bin}"
    if not Path(script_path).exists():
        return node_bin, script_path, None, f"mathml-to-latex wrapper script not found: {script_path}"
    return node_bin, script_path, Path(script_path).resolve().parent, None


def _resolve_mathml_to_latex_worker_command(runtime_env: Mapping[str, str]) -> tuple[str, str, Path | None, str | None]:
    node_bin = _env_config_value(runtime_env, "MATHML_TO_LATEX_NODE_BIN") or "node"
    configured_script = _env_config_value(runtime_env, "MATHML_TO_LATEX_WORKER_SCRIPT")
    script_candidates = mathml_to_latex_worker_script_candidates(runtime_env)
    script_path = configured_script or first_existing_path_cached(script_candidates)
    if not script_path and script_candidates:
        script_path = str(script_candidates[0])

    if shutil.which(node_bin) is None and not Path(node_bin).exists():
        return node_bin, script_path, None, f"node executable not found: {node_bin}"
    if not Path(script_path).exists():
        return node_bin, script_path, None, f"mathml-to-latex worker script not found: {script_path}"
    return node_bin, script_path, Path(script_path).resolve().parent, None


class MathMLToLatexWorker:
    def __init__(
        self,
        *,
        node_bin: str,
        script_path: str,
        cwd: Path | None,
        env: Mapping[str, str],
    ) -> None:
        self.node_bin = node_bin
        self.script_path = script_path
        self.cwd = cwd
        self.env = dict(env)
        self._lock = threading.Lock()
        self._next_id = 0
        self._process: subprocess.Popen[str] | None = None

    def _ensure_process(self) -> subprocess.Popen[str]:
        process = self._process
        if process is not None and process.poll() is None and process.stdin is not None and process.stdout is not None:
            return process
        self._process = subprocess.Popen(
            [self.node_bin, self.script_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(self.cwd) if self.cwd else None,
            env=subprocess_env(self.env),
        )
        return self._process

    def stop(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return
        try:
            process.terminate()
            process.wait(timeout=0.5)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

    def convert(self, raw_mathml: str, *, timeout_seconds: float) -> str:
        with self._lock:
            process = self._ensure_process()
            if process.stdin is None or process.stdout is None:
                self.stop()
                raise RuntimeError("mathml-to-latex worker pipes were not available")
            self._next_id += 1
            request_id = self._next_id
            process.stdin.write(json.dumps({"id": request_id, "mathml": raw_mathml}, ensure_ascii=False) + "\n")
            process.stdin.flush()
            ready, _, _ = select.select([process.stdout], [], [], timeout_seconds)
            if not ready:
                self.stop()
                raise subprocess.TimeoutExpired([self.node_bin, self.script_path], timeout_seconds)
            line = process.stdout.readline()
            if not line:
                stderr = process.stderr.read() if process.stderr is not None else ""
                self.stop()
                raise RuntimeError(_compact_error_text(stderr) or "mathml-to-latex worker exited without output")
            payload = json.loads(line)
            if payload.get("id") != request_id:
                self.stop()
                raise RuntimeError("mathml-to-latex worker returned an out-of-order response")
            if not payload.get("ok"):
                raise RuntimeError(_compact_error_text(payload.get("error")) or "mathml-to-latex worker conversion failed")
            return str(payload.get("latex") or "")


def _mathml_worker_for(
    *,
    node_bin: str,
    script_path: str,
    cwd: Path | None,
    env: Mapping[str, str],
) -> MathMLToLatexWorker:
    key = (node_bin, script_path)
    with _MATHML_WORKERS_LOCK:
        worker = _MATHML_WORKERS.get(key)
        if worker is None:
            worker = MathMLToLatexWorker(node_bin=node_bin, script_path=script_path, cwd=cwd, env=env)
            _MATHML_WORKERS[key] = worker
        return worker


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
        or first_existing_path_cached(formula_tools_subpaths(Path("bin") / "texmath", runtime_env))
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
    started_at = time.monotonic()
    node_bin, script_path, script_cwd, command_error = _resolve_mathml_to_latex_command(runtime_env)

    if command_error:
        return _completed_result(
            backend=BACKEND_MATHML_TO_LATEX,
            raw_mathml=raw_mathml,
            display_mode=display_mode,
            started_at=started_at,
            status="failed",
            error=command_error,
        )

    worker_error: str | None = None
    if _worker_enabled(runtime_env):
        worker_node, worker_script, worker_cwd, worker_command_error = _resolve_mathml_to_latex_worker_command(runtime_env)
        if worker_command_error is None:
            worker = _mathml_worker_for(
                node_bin=worker_node,
                script_path=worker_script,
                cwd=worker_cwd,
                env=runtime_env,
            )
            try:
                latex = normalize_latex(worker.convert(raw_mathml, timeout_seconds=DEFAULT_TIMEOUT_SECONDS))
                if latex:
                    return _completed_result(
                        backend=BACKEND_MATHML_TO_LATEX,
                        raw_mathml=raw_mathml,
                        display_mode=display_mode,
                        started_at=started_at,
                        latex=latex,
                    )
                worker_error = "mathml-to-latex worker returned empty output"
            except (subprocess.TimeoutExpired, RuntimeError, json.JSONDecodeError, OSError) as exc:
                worker_error = str(exc)
        else:
            worker_error = worker_command_error

    args = [node_bin, script_path]
    try:
        process = _run_command(args, input_text=raw_mathml, env=runtime_env, cwd=script_cwd)
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
        error = (process.stderr or process.stdout or f"mathml-to-latex exited with {process.returncode}").strip()
        if worker_error:
            error = f"worker failed: {worker_error}; CLI failed: {error}"
        return _completed_result(
            backend=BACKEND_MATHML_TO_LATEX,
            raw_mathml=raw_mathml,
            display_mode=display_mode,
            started_at=started_at,
            status="failed",
            error=error,
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
        or first_existing_path_cached(formula_tools_subpaths(Path("bin") / "java", runtime_env))
        or "java"
    )
    local_saxon_jar = first_existing_path_cached(formula_tools_subpaths(Path("lib") / "Saxon-HE-12.5.jar", runtime_env))
    local_xmlresolver_jar = first_existing_path_cached(formula_tools_subpaths(Path("lib") / "xmlresolver-5.2.2.jar", runtime_env))
    local_xmlresolver_data_jar = first_existing_path_cached(
        formula_tools_subpaths(Path("lib") / "xmlresolver-5.2.2-data.jar", runtime_env)
    )
    local_stylesheet = first_existing_path_cached(
        formula_tools_subpaths(Path("vendor") / "mml2tex" / "xsl" / "invoke-mml2tex.xsl", runtime_env)
    )
    local_catalog = first_existing_path_cached(formula_tools_subpaths("mml2tex.catalog.xml", runtime_env))

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
    started_at = time.monotonic()
    depth = _FORMULA_TIMING_DEPTH.get()
    depth_token = _FORMULA_TIMING_DEPTH.set(depth + 1)
    try:
        runtime_env = dict(env or os.environ)
        explicitly_selected = bool((backend or runtime_env.get("MATHML_CONVERTER_BACKEND") or "").strip())
        selected_backend = resolve_backend(env=env, backend=backend)
        cache_key = _formula_cache_key(
            backend=selected_backend,
            raw_mathml=raw_mathml,
            display_mode=display_mode,
            env=runtime_env,
        )
        cached = _cached_result(cache_key, runtime_env)
        if cached is not None:
            return cached
        return _store_result(
            cache_key,
            runtime_env,
            _convert_mathml_string_uncached(
                raw_mathml,
                display_mode=display_mode,
                env=runtime_env,
                backend=selected_backend,
                explicitly_selected=explicitly_selected,
            ),
        )
    finally:
        _FORMULA_TIMING_DEPTH.reset(depth_token)
        if depth == 0:
            _record_formula_timing(started_at)


def _convert_mathml_string_uncached(
    raw_mathml: str,
    *,
    display_mode: bool,
    env: Mapping[str, str],
    backend: str,
    explicitly_selected: bool,
) -> FormulaConversionResult:
    runtime_env = dict(env)
    selected_backend = resolve_backend(env=runtime_env, backend=backend)
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
