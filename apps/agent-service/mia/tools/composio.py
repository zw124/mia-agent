import asyncio
import json
import shutil
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from mia.integrations.convex import ConvexClient


class ComposioSearchInput(BaseModel):
    query: str = Field(description="Natural language search query for a Composio tool slug.")
    toolkits: str = Field(default="", description="Optional comma-separated Composio toolkit filter.")


class ComposioExecuteInput(BaseModel):
    slug: str = Field(description="Composio tool slug, for example GITHUB_GET_THE_AUTHENTICATED_USER.")
    payload: dict[str, Any] = Field(default_factory=dict, description="JSON payload for the tool.")


class ComposioToolkitInput(BaseModel):
    toolkit: str = Field(description="Composio toolkit name, for example github, gmail, slack.")


class ComposioSchemaInput(BaseModel):
    slug: str = Field(description="Composio tool slug to inspect.")


class ComposioDryRunInput(BaseModel):
    slug: str = Field(description="Composio tool slug to dry-run.")
    payload: dict[str, Any] = Field(default_factory=dict, description="JSON payload to validate.")


class ComposioRunInput(BaseModel):
    script: str = Field(
        description=(
            "Inline JavaScript for `composio run`. Use execute(), search(), proxy(), and Promise.all "
            "for multi-step connected-app workflows."
        )
    )


async def _run_composio(args: list[str], *, timeout: int = 60) -> str:
    if not shutil.which("composio"):
        return "Composio CLI is not installed. Run `npm run mia:onboard` and enable Composio, or install/login with `composio login`."
    process = await asyncio.create_subprocess_exec(
        "composio",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        process.kill()
        await process.communicate()
        return "Composio command timed out."
    output = "\n".join(
        part.decode("utf-8", errors="replace").strip()
        for part in (stdout, stderr)
        if part.strip()
    ).strip()
    return output[:6000] if output else f"Composio exited with code {process.returncode}."


def build_composio_tools(
    convex: ConvexClient,
    *,
    requester_number: str,
    message_handle: str,
    enabled: bool,
) -> list[StructuredTool]:
    async def search_composio_tool(query: str, toolkits: str = "") -> str:
        if not enabled:
            return "Composio is disabled. Set COMPOSIO_ENABLED=true and run `composio login`."
        args = ["search", query]
        if toolkits.strip():
            args.extend(["--toolkits", toolkits.strip()])
        return await _run_composio(args, timeout=45)

    async def composio_whoami() -> str:
        if not enabled:
            return "Composio is disabled. Set COMPOSIO_ENABLED=true and run `composio login`."
        return await _run_composio(["whoami"], timeout=30)

    async def composio_link(toolkit: str) -> str:
        if not enabled:
            return "Composio is disabled. Set COMPOSIO_ENABLED=true and run `composio login`."
        return await _run_composio(["link", toolkit], timeout=120)

    async def composio_schema(slug: str) -> str:
        if not enabled:
            return "Composio is disabled. Set COMPOSIO_ENABLED=true and run `composio login`."
        return await _run_composio(["execute", slug, "--get-schema"], timeout=45)

    async def composio_dry_run(slug: str, payload: dict[str, Any] | None = None) -> str:
        if not enabled:
            return "Composio is disabled. Set COMPOSIO_ENABLED=true and run `composio login`."
        data = json.dumps(payload or {}, ensure_ascii=False)
        return await _run_composio(
            ["execute", slug, "--skip-connection-check", "--dry-run", "-d", data],
            timeout=45,
        )

    async def request_composio_execute(slug: str, payload: dict[str, Any] | None = None) -> str:
        if not enabled:
            return "Composio is disabled. Set COMPOSIO_ENABLED=true and run `composio login`."
        data = json.dumps(payload or {}, ensure_ascii=False)
        code = await convex.create_pending_action(
            requester_number=requester_number,
            source_message_handle=message_handle,
            kind="composio_execute",
            summary=f"Run Composio tool {slug} with payload:\n{data[:1200]}",
            payload={"slug": slug, "payload": payload or {}},
            risk="approval_required",
        )
        return f"Do you approve?\nRun Composio tool `{slug}`.\nReply approve to run it.\nApproval code: {code}"

    async def request_composio_run(script: str) -> str:
        if not enabled:
            return "Composio is disabled. Set COMPOSIO_ENABLED=true and run `composio login`."
        code = await convex.create_pending_action(
            requester_number=requester_number,
            source_message_handle=message_handle,
            kind="composio_run",
            summary=f"Run Composio script:\n{script[:1600]}",
            payload={"script": script},
            risk="approval_required",
        )
        return f"Do you approve?\nRun this Composio workflow script.\nReply approve to run it.\nApproval code: {code}"

    return [
        StructuredTool.from_function(
            coroutine=search_composio_tool,
            name="composio_search",
            description="Search Composio tool slugs. Use before executing when the exact slug is unknown.",
            args_schema=ComposioSearchInput,
        ),
        StructuredTool.from_function(
            coroutine=composio_whoami,
            name="composio_whoami",
            description="Check whether the Composio CLI is installed and authenticated.",
        ),
        StructuredTool.from_function(
            coroutine=composio_link,
            name="composio_link",
            description="Connect a Composio toolkit account, for example gmail, github, slack, or googlecalendar.",
            args_schema=ComposioToolkitInput,
        ),
        StructuredTool.from_function(
            coroutine=composio_schema,
            name="composio_schema",
            description="Inspect a Composio tool slug input schema before building a payload.",
            args_schema=ComposioSchemaInput,
        ),
        StructuredTool.from_function(
            coroutine=composio_dry_run,
            name="composio_dry_run",
            description="Preview a Composio tool execution payload without performing the external action.",
            args_schema=ComposioDryRunInput,
        ),
        StructuredTool.from_function(
            coroutine=request_composio_execute,
            name="composio_execute",
            description="Request approval to execute a Composio tool slug with JSON payload.",
            args_schema=ComposioExecuteInput,
        ),
        StructuredTool.from_function(
            coroutine=request_composio_run,
            name="composio_run",
            description="Request approval to run an inline Composio JavaScript workflow for multi-tool connected-app tasks.",
            args_schema=ComposioRunInput,
        ),
    ]


def execute_composio_pending_action(action: dict[str, Any]) -> str | None:
    if action.get("kind") == "composio_run":
        script = str((action.get("payload") or {}).get("script") or "").strip()
        if not script:
            raise ValueError("Missing Composio script")
        return asyncio.run(_run_composio(["run", script], timeout=180))
    if action.get("kind") != "composio_execute":
        return None
    payload = action.get("payload") or {}
    slug = str(payload.get("slug") or "").strip()
    data = json.dumps(payload.get("payload") or {}, ensure_ascii=False)
    if not slug:
        raise ValueError("Missing Composio slug")
    return asyncio.run(_run_composio(["execute", slug, "-d", data], timeout=120))
