from __future__ import annotations

import asyncio
import json
import os
import shutil
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    ClientSession = StdioServerParameters = stdio_client = None  # type: ignore


class McpDriveError(RuntimeError):
    """Falha segura ao chamar o conector Drive via MCP."""


class McpDriveClient:
    """Cliente síncrono mínimo para o servidor tools-mcp-drive via stdio."""

    def __init__(self, server_dir: str | Path, data_dir: str | Path = "data") -> None:
        if ClientSession is None:
            raise McpDriveError("Pacote 'mcp' não instalado. Instale via 'pip install mcp'.")
        self.server_dir = Path(server_dir).expanduser().resolve()
        self.data_dir = Path(data_dir).expanduser().resolve()
        if not self.server_dir.is_dir():
            raise McpDriveError(f"diretório tools-mcp não encontrado: {self.server_dir}")
        if not shutil.which("uv"):
            raise McpDriveError("uv não encontrado; instale o uv para iniciar o tools-mcp")

    @classmethod
    def from_env(cls) -> "McpDriveClient":
        default_dir = Path(__file__).resolve().parents[2] / "tools-mcp"
        server_dir = os.getenv("TOOLS_MCP_DIR", str(default_dir))
        data_dir = os.getenv(
            "TOOLS_MCP_DATA_DIR",
            str(Path(__file__).resolve().parents[1] / "data" / "tools_mcp"),
        )
        return cls(server_dir, data_dir)

    async def _call_async(self, operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
        env = os.environ.copy()
        env["TOOLS_MCP_DATA_DIR"] = str(self.data_dir)
        params = StdioServerParameters(
            command="uv",
            args=["run", "--directory", str(self.server_dir), "tools-mcp", "drive"],
            cwd=str(self.server_dir),
            env=env,
        )

        async with AsyncExitStack() as stack:
            read_stream, write_stream = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
            await session.initialize()
            result = await session.call_tool(operation, arguments)

        payload = getattr(result, "structuredContent", None) or getattr(
            result, "structured_content", None
        )
        if not isinstance(payload, dict):
            for block in getattr(result, "content", []) or []:
                text = getattr(block, "text", None)
                if not text:
                    continue
                try:
                    candidate = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if isinstance(candidate, dict):
                    payload = candidate
                    break
        if not isinstance(payload, dict):
            raise McpDriveError("tools-mcp retornou uma resposta sem envelope JSON")
        if payload.get("ok") is False:
            error = payload.get("error") or {}
            code = error.get("code", "connector_error")
            message = error.get("message_safe", "falha no conector Drive")
            raise McpDriveError(f"{code}: {message}")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise McpDriveError("tools-mcp retornou um envelope sem data")
        return data

    def call(self, operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return asyncio.run(self._call_async(operation, arguments))

    def list_files(
        self,
        *,
        folder_id: str,
        tenant_id: str,
        run_id: str,
        step_id: str,
        span_id: str,
    ) -> dict[str, Any]:
        return self.call(
            "drive_list_files",
            {
                "folder_id": folder_id,
                "tenant_id": tenant_id,
                "run_id": run_id,
                "step_id": step_id,
                "span_id": span_id,
            },
        )

    def select_files(
        self,
        *,
        folder_id: str,
        file_ids: list[str],
        tenant_id: str,
        run_id: str,
        step_id: str,
        span_id: str,
    ) -> dict[str, Any]:
        return self.call(
            "drive_select_files",
            {
                "folder_id": folder_id,
                "file_ids": file_ids,
                "tenant_id": tenant_id,
                "run_id": run_id,
                "step_id": step_id,
                "span_id": span_id,
            },
        )

    def download_file(
        self,
        *,
        file_id: str,
        tenant_id: str,
        run_id: str,
        step_id: str,
        span_id: str,
    ) -> dict[str, Any]:
        data = self.call(
            "drive_download_file",
            {
                "file_id": file_id,
                "tenant_id": tenant_id,
                "run_id": run_id,
                "step_id": step_id,
                "span_id": span_id,
            },
        )
        storage_ref = data.get("storage_ref")
        if not isinstance(storage_ref, str) or not storage_ref:
            raise McpDriveError("download do Drive não retornou storage_ref")
        artifact = (self.data_dir / storage_ref).resolve()
        if self.data_dir not in artifact.parents or not artifact.is_file():
            raise McpDriveError("storage_ref do Drive aponta para artefato inacessível")
        return {**data, "local_path": str(artifact)}
