"""Tool registration, validation, and safe dispatch for FAULTLINE."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class RegisteredTool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., dict[str, Any]]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Callable[..., dict[str, Any]],
    ) -> None:
        self._tools[name] = RegisteredTool(name, description, parameters, handler)

    def openai_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in self._tools.values()
        ]

    def execute(self, name: str, raw_arguments: str | dict[str, Any]) -> dict[str, Any]:
        if name not in self._tools:
            return {"ok": False, "error": f"Unknown tool: {name}"}
        try:
            arguments = (
                raw_arguments
                if isinstance(raw_arguments, dict)
                else json.loads(raw_arguments or "{}")
            )
            if not isinstance(arguments, dict):
                return {"ok": False, "error": "Tool arguments must be a JSON object."}
        except (TypeError, json.JSONDecodeError) as exc:
            return {"ok": False, "error": f"Malformed tool arguments: {exc}"}

        try:
            result = self._tools[name].handler(**arguments)
            if not isinstance(result, dict):
                return {"ok": False, "error": "Tool returned a non-object result."}
            return result
        except TypeError as exc:
            return {"ok": False, "error": f"Invalid arguments for {name}: {exc}"}
        except Exception as exc:  # Tools must report failures back to the model.
            return {"ok": False, "error": f"{name} failed: {type(exc).__name__}: {exc}"}
