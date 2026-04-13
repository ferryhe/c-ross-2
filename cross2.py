from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


TARGET_MODULE = Path(__file__).resolve().parent / "AI_Agent" / "scripts" / "cross2.py"


def _load_target_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ai_agent_scripts_cross2", TARGET_MODULE)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {TARGET_MODULE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


main = _load_target_module().main


if __name__ == "__main__":
    raise SystemExit(main())
