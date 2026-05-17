from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DESIGN_CONTEXT_PATH = PROJECT_ROOT / "DESIGN.md"
MAX_DESIGN_CONTEXT_CHARS = 12000


@lru_cache(maxsize=1)
def load_design_context() -> str:
    if not DESIGN_CONTEXT_PATH.exists():
        return "No DESIGN.md found."
    content = DESIGN_CONTEXT_PATH.read_text(encoding="utf-8").strip()
    if len(content) > MAX_DESIGN_CONTEXT_CHARS:
        return content[:MAX_DESIGN_CONTEXT_CHARS].rstrip() + "\n\n[DESIGN.md truncated]"
    return content


def clear_design_context_cache() -> None:
    load_design_context.cache_clear()
