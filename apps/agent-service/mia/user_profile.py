from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
USER_PROFILE_PATHS = [
    PROJECT_ROOT / "user.local.md",
    PROJECT_ROOT / "user.md",
]
MAX_USER_PROFILE_CHARS = 8000


@lru_cache(maxsize=1)
def load_user_profile() -> str:
    profile_path = next((path for path in USER_PROFILE_PATHS if path.exists()), None)
    if profile_path is None:
        return "No local user.local.md profile found."
    content = profile_path.read_text(errors="replace").strip()
    if not content:
        return f"Local {profile_path.name} profile is empty."
    return content[:MAX_USER_PROFILE_CHARS]


def clear_user_profile_cache() -> None:
    load_user_profile.cache_clear()
