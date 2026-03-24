"""Extracts Go struct definitions with fields, types, and JSON tags.

Uses tree-sitter for robust AST-based struct parsing when available,
falling back to regex for environments where tree-sitter is not installed.

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
from indexer.parsers.ts_utils import (
    find_child,
    find_children,
    is_available as _ts_available,
    node_text,
    parse_go,
    preceding_comments,
)

logger = logging.getLogger(__name__)

_IGNORE_DIRS = frozenset({
    ".git", "vendor", "testdata", "test", "mocks", "__pycache__",
})

_JSON_TAG_RE = re.compile(r'json:"([^"]*)"')

# ---------------------------------------------------------------------------
# Tree-sitter extraction
# ---------------------------------------------------------------------------


def _ts_extract_structs_from_file(source: bytes, rel_path: str,
                                  service: str) -> list[StructDefinition]:
    """Extract struct definitions using tree-sitter AST."""
    tree = parse_go(source)
    root = tree.root_node
    structs: list[StructDefinition] = []

    for node in root.children:
        if node.type != "type_declaration":
            continue
        for spec in find_children(node, "type_spec"):
            name_node = find_child(spec, "type_identifier")
            struct_node = find_child(spec, "struct_type")
            if not name_node or not struct_node:
                continue

            struct_name = node_text(name_node)
            comment = preceding_comments(node, source)

            field_list = find_child(struct_node, "field_declaration_list")
            fields: list[StructField] = []
            embedded: list[str] = []

            if field_list:
                for fdecl in find_children(field_list, "field_declaration"):
                    _ts_parse_field(fdecl, fields, embedded)

            structs.append(StructDefinition(
                name=struct_name,
                fields=fields,
                file=rel_path,
                service=service,
                comment=comment,
                embedded_types=embedded,
            ))

    return structs


def _ts_parse_field(fdecl, fields: list[StructField], embedded: list[str]) -> None:
    """Parse a single field_declaration node into a StructField or embedded type."""
    field_id = find_child(fdecl, "field_identifier")

    if field_id:
        # Named field
        fname = node_text(field_id)
        ftype = _ts_field_type(fdecl)
        is_ptr = find_child(fdecl, "pointer_type") is not None

        # JSON tag from raw_string_literal
        json_tag = ""
        tag_node = find_child(fdecl, "raw_string_literal")
        if tag_node:
            tag_text = node_text(tag_node)
            m = _JSON_TAG_RE.search(tag_text)
            if m:
                json_tag = m.group(1).split(",")[0]

        # Inline comment
        comment = ""
        cnode = find_child(fdecl, "comment")
        if cnode:
            comment = node_text(cnode).lstrip("/ ")

        fields.append(StructField(
            name=fname,
            type=ftype.lstrip("*"),
            json_tag=json_tag,
            comment=comment,
            is_pointer=is_ptr,
        ))
    else:
        # Embedded type (no field name)
        etype = _ts_field_type(fdecl)
        if etype and etype[0].isupper():
            embedded.append(etype.lstrip("*"))


def _ts_field_type(fdecl) -> str:
    """Extract the type string from a field_declaration."""
    for child in fdecl.children:
        if child.type in (
            "type_identifier", "pointer_type", "slice_type",
            "array_type", "map_type", "qualified_type",
            "interface_type", "struct_type", "channel_type",
            "function_type", "generic_type",
        ):
            return node_text(child)
    return ""


# ---------------------------------------------------------------------------
# Regex fallback (original implementation)
# ---------------------------------------------------------------------------

_STRUCT_DEF_RE = re.compile(r"type\s+(\w+)\s+struct\s*\{")

_FIELD_RE = re.compile(
    r"^\s+(\w+)\s+"
    r"(\*?\[?\]?\*?\w+(?:\.\w+)?)"
    r"(?:\s+`[^`]*json:\"([^\"]*?)\")?.*?"
    r"(?://\s*(.*))?$",
    re.MULTILINE,
)

_EMBEDDED_RE = re.compile(
    r"^\s+(\*?\w+(?:\.\w+)?)\s*(?:`[^`]*`)?\s*(?://.*)?$",
    re.MULTILINE,
)


def _regex_extract_struct_body(content: str, open_brace: int) -> str:
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


def _regex_extract_block_comment(content: str, struct_start: int) -> str:
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


def _regex_extract_structs_from_file(content: str, rel_path: str,
                                     service: str) -> list[StructDefinition]:
    structs: list[StructDefinition] = []
    for m in _STRUCT_DEF_RE.finditer(content):
        struct_name = m.group(1)
        brace_idx = content.find("{", m.start())
        if brace_idx == -1:
            continue
        body = _regex_extract_struct_body(content, brace_idx)
        if not body:
            continue
        comment = _regex_extract_block_comment(content, m.start())
        fields: list[StructField] = []
        embedded: list[str] = []
        for line in body.split("\n"):
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue
            fm = _FIELD_RE.match(line)
            if fm:
                fname, ftype, json_tag, fcomment = fm.groups()
                is_ptr = ftype.startswith("*")
                fields.append(StructField(
                    name=fname, type=ftype.lstrip("*"),
                    json_tag=json_tag or "", comment=fcomment or "",
                    is_pointer=is_ptr,
                ))
                continue
            em = _EMBEDDED_RE.match(line)
            if em:
                embedded_type = em.group(1).lstrip("*")
                if embedded_type[0].isupper():
                    embedded.append(embedded_type)
        structs.append(StructDefinition(
            name=struct_name, fields=fields, file=rel_path,
            service=service, comment=comment, embedded_types=embedded,
        ))
    return structs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_structs_from_file(file_path: Path, repo_root: Path,
                              service: str) -> list[StructDefinition]:
    """Extract all struct definitions from a single Go file."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    rel_path = str(file_path.relative_to(repo_root))

    if _ts_available():
        return _ts_extract_structs_from_file(content.encode("utf-8"), rel_path, service)
    return _regex_extract_structs_from_file(content, rel_path, service)


def extract_structs_from_repo(repo_path: str, service: str) -> list[StructDefinition]:
    """Walk a Go repository and extract all struct definitions."""
    root = Path(repo_path).resolve()
    all_structs: list[StructDefinition] = []

    for go_file in root.rglob("*.go"):
        if any(part in _IGNORE_DIRS for part in go_file.parts):
            continue
        if go_file.name.endswith("_test.go") or go_file.name.endswith(".pb.go"):
            continue
        file_structs = extract_structs_from_file(go_file, root, service)
        all_structs.extend(file_structs)

    logger.info(
        "[TypeExtractor] Found %d struct definitions across %s (tree-sitter=%s)",
        len(all_structs), service, _ts_available(),
    )
    return all_structs
