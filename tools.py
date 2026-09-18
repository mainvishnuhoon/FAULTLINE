"""Constrained filesystem and test tools exposed to the debugging agent."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class DemoTools:
    MAX_READ_BYTES = 50_000
    MAX_TEST_OUTPUT = 12_000

    def __init__(self, repo_root: str | Path) -> None:
        self.repo_root = Path(repo_root).resolve()
        if not self.repo_root.is_dir():
            raise ValueError(f"Repository does not exist: {self.repo_root}")

    def _safe_path(self, path: str, *, must_exist: bool = False) -> Path:
        if not isinstance(path, str) or not path.strip():
            raise ValueError("path must be a non-empty string")
        candidate = Path(path)
        resolved = (candidate if candidate.is_absolute() else self.repo_root / candidate).resolve()
        try:
            resolved.relative_to(self.repo_root)
        except ValueError as exc:
            raise ValueError("path is outside the repository workspace") from exc
        if must_exist and not resolved.exists():
            raise FileNotFoundError(f"file does not exist: {path}")
        return resolved

    def inspect_repo(self, action: str = "list", path: str = "") -> dict[str, Any]:
        if action not in {"list", "read"}:
            return {"ok": False, "error": "action must be 'list' or 'read'"}
        if action == "list":
            files = []
            for item in sorted(self.repo_root.rglob("*")):
                if not item.is_file():
                    continue
                relative = item.relative_to(self.repo_root).as_posix()
                if any(part in {".git", ".faultline_backups", "__pycache__"} for part in item.parts):
                    continue
                files.append(relative)
            return {"ok": True, "action": "list", "root": str(self.repo_root), "files": files}

        target = self._safe_path(path, must_exist=True)
        if not target.is_file():
            return {"ok": False, "error": f"not a file: {path}"}
        if target.stat().st_size > self.MAX_READ_BYTES:
            return {"ok": False, "error": f"file is larger than {self.MAX_READ_BYTES} bytes"}
        return {
            "ok": True,
            "action": "read",
            "path": target.relative_to(self.repo_root).as_posix(),
            "content": target.read_text(encoding="utf-8"),
        }

    def run_tests(self) -> dict[str, Any]:
        command = [sys.executable, "-m", "unittest", "discover", "-v"]
        try:
            completed = subprocess.run(
                command,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
            output = (completed.stdout + "\n" + completed.stderr).strip()
            if len(output) > self.MAX_TEST_OUTPUT:
                output = output[-self.MAX_TEST_OUTPUT :]
            return {
                "ok": True,
                "passed": completed.returncode == 0,
                "exit_code": completed.returncode,
                "command": "python -m unittest discover -v",
                "output": output,
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "ok": False,
                "passed": False,
                "error": "test command timed out after 30 seconds",
                "output": (exc.stdout or "")[-self.MAX_TEST_OUTPUT :],
            }

    def edit_file(self, path: str, content: str) -> dict[str, Any]:
        target = self._safe_path(path, must_exist=True)
        if not target.is_file():
            return {"ok": False, "error": f"not a file: {path}"}
        if not isinstance(content, str):
            return {"ok": False, "error": "content must be a string"}
        if target.suffix != ".py":
            return {"ok": False, "error": "only existing Python files may be edited"}
        if target.name.startswith("test_") or target.parent.name == "tests":
            return {"ok": False, "error": "tests are protected; edit implementation files only"}

        backup_root = self.repo_root / ".faultline_backups"
        backup_root.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = backup_root / f"{stamp}_{target.name}.bak"
        shutil.copy2(target, backup)
        target.write_text(content, encoding="utf-8")
        return {
            "ok": True,
            "path": target.relative_to(self.repo_root).as_posix(),
            "backup": backup.relative_to(self.repo_root).as_posix(),
            "message": "file updated; original saved in the backup directory",
        }
