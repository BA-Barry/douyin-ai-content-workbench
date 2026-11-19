"""Test package that also exposes the source package modules during discovery."""

from pathlib import Path

_SOURCE_PACKAGE = Path(__file__).resolve().parents[2] / "src" / "pipeline_tools"
if str(_SOURCE_PACKAGE) not in __path__:
    __path__.append(str(_SOURCE_PACKAGE))
