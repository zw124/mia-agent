from __future__ import annotations

import argparse
import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path


ENV_KEYS = [
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "MODEL_NAME",
    "TRANSCRIPTION_MODEL",
    "CONVEX_SITE_URL",
    "AGENT_SERVICE_URL",
    "MIA_INTERNAL_SECRET",
    "SENDBLUE_API_KEY_ID",
    "SENDBLUE_API_SECRET_KEY",
    "SENDBLUE_FROM_NUMBER",
    "SENDBLUE_WEBHOOK_SECRET",
    "OWNER_PHONE_NUMBER",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_WEBHOOK_SECRET",
    "TELEGRAM_OWNER_CHAT_ID",
    "TELEGRAM_ALLOWED_CHAT_IDS",
    "SEARXNG_BASE_URL",
    "COMPOSIO_ENABLED",
]


def _env_path(path: str | None) -> Path:
    return Path(path or ".env.local").expanduser().resolve()


def _read_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def _write_env(path: Path, env: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key}={env.get(key, '')}" for key in ENV_KEYS]
    extras = [f"{key}={value}" for key, value in env.items() if key not in ENV_KEYS]
    path.write_text("\n".join([*lines, *extras]).strip() + "\n", encoding="utf-8")


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" ({default})" if default else ""
    answer = input(f"{prompt}{suffix}: ").strip()
    return answer or default


def _yes(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    answer = input(f"{prompt} [{hint}]: ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes", "是", "好", "可以"}


def onboard(args: argparse.Namespace) -> int:
    path = _env_path(args.env)
    env = {
        "OPENAI_BASE_URL": "https://api.openai.com/v1",
        "MODEL_NAME": "gpt-4o-mini",
        "TRANSCRIPTION_MODEL": "whisper-1",
        "AGENT_SERVICE_URL": f"http://localhost:{args.port}",
        "MIA_INTERNAL_SECRET": secrets.token_hex(24),
        "TELEGRAM_WEBHOOK_SECRET": secrets.token_hex(24),
        "COMPOSIO_ENABLED": "false",
        **_read_env(path),
    }

    print("Mia Agent Python onboard")
    print(f"Writing {path}\n")

    env["OPENAI_API_KEY"] = _ask("OpenAI-compatible API key", env.get("OPENAI_API_KEY", ""))
    env["OPENAI_BASE_URL"] = _ask("OpenAI-compatible base URL", env["OPENAI_BASE_URL"])
    env["MODEL_NAME"] = _ask("Model name", env["MODEL_NAME"])
    env["AGENT_SERVICE_URL"] = _ask("Public/local agent URL", env["AGENT_SERVICE_URL"])

    if _yes("Enable iMessage via SendBlue", bool(env.get("SENDBLUE_API_KEY_ID"))):
        env["SENDBLUE_API_KEY_ID"] = _ask("SendBlue API key id", env.get("SENDBLUE_API_KEY_ID", ""))
        env["SENDBLUE_API_SECRET_KEY"] = _ask(
            "SendBlue secret key",
            env.get("SENDBLUE_API_SECRET_KEY", ""),
        )
        env["SENDBLUE_FROM_NUMBER"] = _ask("SendBlue from number", env.get("SENDBLUE_FROM_NUMBER", ""))
        env["OWNER_PHONE_NUMBER"] = _ask("Owner phone number", env.get("OWNER_PHONE_NUMBER", ""))
        env["SENDBLUE_WEBHOOK_SECRET"] = _ask(
            "SendBlue webhook secret",
            env.get("SENDBLUE_WEBHOOK_SECRET", "") or secrets.token_hex(24),
        )

    if _yes("Enable Telegram bot", bool(env.get("TELEGRAM_BOT_TOKEN"))):
        env["TELEGRAM_BOT_TOKEN"] = _ask("Telegram bot token", env.get("TELEGRAM_BOT_TOKEN", ""))
        env["TELEGRAM_OWNER_CHAT_ID"] = _ask(
            "Telegram owner chat id",
            env.get("TELEGRAM_OWNER_CHAT_ID", ""),
        )
        env["TELEGRAM_ALLOWED_CHAT_IDS"] = _ask(
            "Allowed Telegram chat ids",
            env.get("TELEGRAM_ALLOWED_CHAT_IDS", "") or env.get("TELEGRAM_OWNER_CHAT_ID", ""),
        )
        env["TELEGRAM_WEBHOOK_SECRET"] = _ask(
            "Telegram webhook secret",
            env.get("TELEGRAM_WEBHOOK_SECRET", "") or secrets.token_hex(24),
        )

    env["COMPOSIO_ENABLED"] = "true" if _yes("Enable Composio CLI tools", env.get("COMPOSIO_ENABLED") == "true") else "false"

    _write_env(path, env)
    public_url = env["AGENT_SERVICE_URL"].rstrip("/")
    print(f"\nWrote {path}")
    print(f"Health:    {public_url}/health")
    print(f"SendBlue:  {public_url}/webhooks/sendblue/receive")
    print(f"Telegram:  {public_url}/webhooks/telegram/receive")
    print("\nRun: mia-agent serve --env " + str(path))
    return 0


def serve(args: argparse.Namespace) -> int:
    path = _env_path(args.env)
    if path.exists():
        for key, value in _read_env(path).items():
            os.environ.setdefault(key, value)
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "mia.main:app",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    if args.reload:
        command.append("--reload")
    return subprocess.call(command)


def doctor(args: argparse.Namespace) -> int:
    path = _env_path(args.env)
    env = {**os.environ, **_read_env(path)}
    checks = {
        "env file": path.exists(),
        "OPENAI_API_KEY": bool(env.get("OPENAI_API_KEY")),
        "OPENAI_BASE_URL": bool(env.get("OPENAI_BASE_URL")),
        "MODEL_NAME": bool(env.get("MODEL_NAME")),
        "SendBlue configured": bool(env.get("SENDBLUE_API_KEY_ID") and env.get("SENDBLUE_API_SECRET_KEY")),
        "Telegram configured": bool(env.get("TELEGRAM_BOT_TOKEN")),
        "Composio CLI": shutil.which("composio") is not None,
        "Composio enabled": env.get("COMPOSIO_ENABLED", "").lower() == "true",
    }
    for name, ok in checks.items():
        print(f"{'ok' if ok else 'missing'}  {name}")
    return 0 if all(checks[key] for key in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "MODEL_NAME")) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mia-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    onboard_parser = subparsers.add_parser("onboard", help="Interactive terminal setup")
    onboard_parser.add_argument("--env", default=".env.local")
    onboard_parser.add_argument("--port", type=int, default=8000)
    onboard_parser.set_defaults(func=onboard)

    serve_parser = subparsers.add_parser("serve", help="Run the FastAPI agent service")
    serve_parser.add_argument("--env", default=".env.local")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--reload", action="store_true")
    serve_parser.set_defaults(func=serve)

    doctor_parser = subparsers.add_parser("doctor", help="Check local configuration")
    doctor_parser.add_argument("--env", default=".env.local")
    doctor_parser.set_defaults(func=doctor)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
