"""Bounded AI source policy. This is a guardrail, not a Python sandbox or SQL parser."""

from __future__ import annotations

import ast
import re
from pathlib import Path

NETWORK = ("requests", "httpx", "socket", "urllib.request", "sawakli.connectors")
SENSITIVE = {"users", "oauth_connections", "connector_tokens", "raw_api_responses"}
SYMBOLS = (
    SENSITIVE | {f"{name}_table" for name in SENSITIVE} | {"User", "OAuthConnection"}
)
SQL_TABLE = re.compile(
    r'\b(?:from|join|update|into)\s+(?:"?\w+"?\.)?"?(\w+)"?', re.IGNORECASE
)


def inspect_source(source: str) -> list[tuple[int, str]]:
    """Return line/rule pairs for explicit forbidden imports, symbols and SQL literals."""
    violations: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imports = [item.name for item in node.names]
        elif isinstance(node, ast.ImportFrom):
            imports = [node.module or ""] + [
                f"{node.module}.{item.name}" for item in node.names
            ]
            if any(item.name in SYMBOLS for item in node.names):
                violations.append((node.lineno, "sensitive import"))
        else:
            imports = []
        if any(
            name == prefix or name.startswith(prefix + ".")
            for name in imports
            for prefix in NETWORK
        ):
            violations.append((node.lineno, "network/provider import"))
        if any(name.startswith("sawakli.db.models.user") for name in imports):
            violations.append((node.lineno, "user model import"))
        if isinstance(node, ast.Name) and node.id in SYMBOLS:
            violations.append((node.lineno, "sensitive symbol"))
        if isinstance(node, ast.Attribute) and node.attr in SYMBOLS:
            violations.append((node.lineno, "sensitive attribute"))
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if any(
                table.lower() in SENSITIVE for table in SQL_TABLE.findall(node.value)
            ):
                violations.append((node.lineno, "sensitive SQL literal"))
    return sorted(set(violations))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    failures = 0
    for path in sorted((root / "apps/backend/src/sawakli/ai").rglob("*.py")):
        for line, rule in inspect_source(path.read_text()):
            print(f"{path.relative_to(root)}:{line}: {rule}")
            failures += 1
    print(f"AI source boundary: {failures} violation(s)")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
