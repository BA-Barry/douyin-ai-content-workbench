"""Portable project paths and executable discovery; no downloads or credentials."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def project_root() -> Path:
    return Path(os.environ.get("DOUYIN_PROJECT_ROOT") or Path(__file__).resolve().parents[1]).expanduser().resolve()


def configured_path(variable: str, default: Path) -> Path:
    value = os.environ.get(variable)
    return Path(value).expanduser().resolve() if value else default.resolve()


def skills_root() -> Path:
    # The default is project-scoped: deleting a Skill in the UI must not remove
    # an unrelated user's global Codex installation.
    return configured_path("DOUYIN_SKILLS_DIR", project_root() / "skills")


def venv_python(folder: Path) -> Path:
    return folder / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def project_python(root: Path | None = None) -> Path:
    root = root or project_root()
    if os.environ.get("DOUYIN_PYTHON"):
        return Path(os.environ["DOUYIN_PYTHON"]).expanduser().resolve()
    candidates = [venv_python(root / ".venv"), venv_python(root / "envs/content")]
    return next((p for p in candidates if p.is_file()), Path(sys.executable).resolve())


def find_tool(name: str, root: Path | None = None) -> str | None:
    root = root or project_root()
    variable = "DOUYIN_FLOVA_CLI" if name == "flova" else f"PROJECT_{name.upper()}_EXE"
    explicit = os.environ.get(variable)
    if explicit:
        candidate = Path(explicit).expanduser()
        return str(candidate.resolve()) if candidate.is_file() else None
    executable = name + (".exe" if os.name == "nt" else "")
    if name == "flova":
        candidate = root / "envs/flova-cli" / executable
        if candidate.is_file():
            return str(candidate)
    folder = root / "tools" / ("ffmpeg" if name in {"ffmpeg", "ffprobe"} else name)
    if folder.is_dir():
        candidate = next(folder.rglob(executable), None)
        if candidate:
            return str(candidate)
    return shutil.which(name)


def runtime_environment(root: Path | None = None) -> dict[str, str]:
    root = root or project_root()
    cache = configured_path("DOUYIN_CACHE_DIR", root / "cache")
    models = configured_path("DOUYIN_MODELS_DIR", root / "models")
    paths = {
        "XDG_CACHE_HOME": cache, "PIP_CACHE_DIR": cache / "pip",
        "UV_CACHE_DIR": cache / "uv", "NPM_CONFIG_CACHE": cache / "npm",
        "PLAYWRIGHT_BROWSERS_PATH": cache / "playwright",
        "PUPPETEER_CACHE_DIR": cache / "puppeteer", "MPLCONFIGDIR": cache / "matplotlib",
        "NUMBA_CACHE_DIR": cache / "numba", "TEMP": cache / "temp", "TMP": cache / "temp",
        "HF_HOME": models / "huggingface", "HF_HUB_CACHE": models / "huggingface/hub",
        "HF_DATASETS_CACHE": models / "huggingface/datasets",
        "TORCH_HOME": models / "torch", "MODELSCOPE_CACHE": models / "modelscope",
    }
    env = dict(os.environ, DOUYIN_PROJECT_ROOT=str(root), PYTHONUTF8="1")
    for key, value in paths.items():
        value.mkdir(parents=True, exist_ok=True)
        env[key] = str(value)
    return env
