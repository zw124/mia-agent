from mia.user_profile import clear_user_profile_cache, load_user_profile


def test_load_user_profile_reads_root_user_md() -> None:
    clear_user_profile_cache()

    profile = load_user_profile()

    assert profile == "No local user.local.md profile found."
