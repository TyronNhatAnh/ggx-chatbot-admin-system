"""Extracts Go struct definitions with fields, types, and JSON tags.

This gives the chatbot understanding of request/response shapes, domain models,
and the mapping between Go field names and JSON API field names.

Supports:
  - Named structs:  type Order struct { ... }
  - Embedded types: type B2COrder struct { Order; ExtraField string }
  - JSON tags:      Name string `json:"name,omitempty"`
  - Pointer fields: Driver *DriverInfo `json:"driver"`
"""

import logging
import re
from pathlib import Path

from indexer.models import StructDefinition, StructField

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Matches: type OrderDetail struct {
# Groups: (1) struct name
_STRUCT_DEF_RE = re.compile(
    r"type\s+(\w+)\s+struct\s*\{"
)

# Matches a struct field line:
#   Name   string       `json:"name,omitempty"`   // user-facing name
#   Driver *DriverInfo  `json:"driver"`
# Groups: (1) field name, (2) field type, (3) json tag content, (4) comment
_FIELD_RE = re.compile(
    r"^\s+(\w+)\s+"                        # (1) field name
    r"(\*?\[?\]?\*?\w+(?:\.\w+)?)"         # (2) type (with optional pointer/slice)
    r"(?:\s+`[^`]*json:\"([^\"]*?)\")?.*?" # (3) optional json tag
    r"(?://\s*(.*))?$",                     # (4) optional inline comment
    re.MULTILINE,
)

# Matches embedded type (no field name, just a type on its own line):
#   Order
#   *BaseModel
_EMBEDDED_RE = re.compile(
    r"^\s+(\*?\w+(?:\.\w+)?)\s*(?:`[^`]*`)?\s*(?://.*)?$",
    re.MULTILINE,
)

# Block comment above struct
_COMMENT_RE = re.compile(
    r"((?://[^\n]*\n)+)\s*type\s+\w+\s+struct"
)

_IGNORE_DIRS = frozenset({
    ".git", "vendor", "testdata", "test", "mocks", "__pycache__",
})


def _extract_struct_body(content: str, open_brace: int) -> str:
    """Extract the body between { and matching }."""
    depth = 0
    i = open_brace
    while i < len(content):
        ch = content[i]
        if ch == "`":
            i += 1
            while i < len(content) and content[i] != "`":
                i += 1
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return content[open_brace + 1:i]
        i += 1
    return ""


def _extract_block_comment(content: str, struct_start: int) -> str:
    """Get // comments immediately before a struct definition."""
    prefix = content[:struct_start]
    lines = prefix.rstrip().split("\n")
    comment_lines: list[str] = []
    for line in reversed(lines):
        stripped = line.strip()
        if stripped.startswith("//"):
            comment_lines.append(stripped.lstrip("/ "))
        else:
            break
    comment_lines.reverse()
    return " ".join(comment_lines)


def extract_structs_from_file(file_path: Path, repo_root: Path,
                               service: str) -> list[StructDefinition]:
    """Extract all struct definitions from a single Go file."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    rel_path = str(file_path.relative_to(repo_root))
    structs: list[StructDefinition] = []

    for m in _STRUCT_DEF_RE.finditer(content):
        struct_name = m.group(1)
        brace_idx = content.find("{", m.start())
        if brace_idx == -1:
            continue

        body = _extract_struct_body(content, brace_idx)
        if not body:
            continue

        comment = _extract_block_comment(content, m.start())

        fields: list[StructField] = []
        embedded: list[str] = []

        for line in body.split("\n"):
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue

            # Try field match
            fm = _FIELD_RE.match(line)
            if fm:
                fname, ftype, json_tag, fcomment = fm.groups()
                is_ptr = ftype.startswith("*")
                fields.append(StructField(
                    name=fname,
                    type=ftype.lstrip("*"),
                    json_tag=json_tag or "",
                    comment=fcomment or "",
                    is_pointer=is_ptr,
                ))
                continue

            # Try embedded type match
            em = _EMBEDDED_RE.match(line)
            if em:
                embedded_type = em.group(1).lstrip("*")
                # Skip if it looks like a method receiver or tag
                if not embedded_type[0].isupper():
                    continue
                embedded.append(embedded_type)

        structs.append(StructDefinition(
            name=struct_name,
            fields=fields,
            file=rel_path,
            service=service,
            comment=comment,
            embedded_types=embedded,
        ))

    return structs


def extract_structs_from_repo(repo_path: str, service: str) -> list[StructDefinition]:
    """Walk a Go repository and extract all struct definitions.

    Args:
        repo_path: Path to the Go repository root.
        service: Service name (e.g. "order-service").

    Returns:
        List of StructDefinition.
    """
    root = Path(repo_path).resolve()
    all_structs: list[StructDefinition] = []

    for go_file in root.rglob("*.go"):
        if any(part in _IGNORE_DIRS for part in go_file.parts):
            continue
        if go_file.name.endswith("_test.go"):
            continue
        file_structs = extract_structs_from_file(go_file, root, service)
        all_structs.extend(file_structs)

    logger.info(
        "[TypeExtractor] Found %d struct definitions across %s",
        len(all_structs), service,
    )
    return all_structs
