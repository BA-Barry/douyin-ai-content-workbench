"""Zero-dependency local setup and launch: python manage.py --help."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from project_runtime import find_tool, project_python, project_root, runtime_environment, skills_root


def initialize(root: Path) -> list[str]:
    written = []
    for name in ("data", "content", "research", "workspace", "assets/library", "skills"):
        (root / name).mkdir(parents=True, exist_ok=True)
    for source in (root / "examples/data").glob("*.example.*"):
        target = root / "data" / source.name.replace(".example", "")
        if not target.exists():
            shutil.copy2(source, target)
            written.append(target.name)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Portable local workbench setup and launch")
    actions = parser.add_subparsers(dest="action", required=True)
    init = actions.add_parser("init", help="Initialize missing local data; never overwrite existing files")
    init.add_argument("--venv", action="store_true", help="Create .venv using the current Python")
    serve = actions.add_parser("serve", help="Run foreground server on loopback")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--offline", action="store_true")
    actions.add_parser("doctor", help="Show configuration and optional executable availability")
    args = parser.parse_args()
    root = project_root()
    if not (root / "workbench/server.py").is_file():
        parser.error("DOUYIN_PROJECT_ROOT must point to a complete workbench checkout")
    if args.action == "init":
        written = initialize(root)
        if args.venv and not (root / ".venv/pyvenv.cfg").exists():
            env = runtime_environment(root)
            os.environ.update(env)
            venv.EnvBuilder(with_pip=True).create(root / ".venv")
        print(json.dumps({"root": str(root), "created": written, "python": str(project_python(root))}, ensure_ascii=False, indent=2))
        return 0
    if args.action == "doctor":
        print(json.dumps({"root": str(root), "python": str(project_python(root)), "skills": str(skills_root()),
                          "data_initialized": (root / "data/content_registry.csv").is_file(),
                          "tools": {name: find_tool(name, root) for name in ("ffmpeg", "ffprobe", "flova")}}, ensure_ascii=False, indent=2))
        return 0
    if not 1 <= args.port <= 65535:
        parser.error("port must be in 1..65535")
    initialize(root)
    command = [str(project_python(root)), "-u", str(root / "workbench/server.py"), "--port", str(args.port)]
    if args.offline:
        command.append("--offline")
    try:
        return subprocess.call(command, cwd=root, env=runtime_environment(root))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
