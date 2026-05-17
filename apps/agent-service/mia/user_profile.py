from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
USER_PROFILE_PATH = PROJECT_ROOT / "user.md"
MAX_USER_PROFILE_CHARS = 8000


@lru_cache(maxsize=1)
def load_user_profile() -> str:
    if not USER_PROFILE_PATH.exists():
        return "No local user.md profile found."
    content = USER_PROFILE_PATH.read_text(errors="replace").strip()
    if not content:
        return "Local user.md profile is empty."
    return content[:MAX_USER_PROFILE_CHARS]


def clear_user_profile_cache() -> None:
    load_user_profile.cache_clear()
