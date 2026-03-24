"""Extracts Go const blocks, iota patterns, and status/enum maps from source files.

Uses tree-sitter for robust AST-based extraction when available, falling back
to regex for environments where tree-sitter is not installed.

Supports:
  - Simple typed const groups:   const ( StatusPending OrderStatus = 1 )
  - Iota-based enums:            const ( Pending Status = iota )
  - Mapped string enums:         var statusNames = map[int]string{ 1: "Pending" }
  - Struct-literal enums:        var StatusCD = struct{...}{...}
  - Comment-annotated consts:    StatusActive = 2 // driver assigned
"""

import logging
import re
from pathlib import Path

from indexer.models import EnumGroup, EnumValue
from indexer.parsers.ts_utils import (
    find_child,
    find_children,
    is_available as _ts_available,
    node_text,
    parse_go,
    preceding_comments,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared regex (used by both tree-sitter and fallback paths)
# ---------------------------------------------------------------------------

_MAP_ENTRY_RE = re.compile(r'(\w+)\s*:\s*"([^"]+)"')
_STRUCT_FIELD_RE = re.compile(r'(\w+)\s*:\s*("(?:[^"\\]|\\.)*"|\d+(?:\.\d+)?)')

_IGNORE_DIRS = frozenset({
    ".git", "vendor", "testdata", "test", "mocks", "node_modules",
})

# ---------------------------------------------------------------------------
# Tree-sitter extraction
# ---------------------------------------------------------------------------


def _ts_extract_enums_from_file(source: bytes, rel_path: str,
                                service: str) -> list[EnumGroup]:
    """Extract enums from a Go file using tree-sitter AST."""
    tree = parse_go(source)
    root = tree.root_node
    groups: list[EnumGroup] = []

    for node in root.children:
        if node.type == "const_declaration":
            groups.extend(_ts_parse_const_declaration(node, source, rel_path, service))
        elif node.type == "var_declaration":
            groups.extend(_ts_parse_var_declaration(node, source, rel_path, service))

    return groups


def _ts_parse_const_declaration(node, source: bytes, rel_path: str,
                                service: str) -> list[EnumGroup]:
    """Parse a const declaration (grouped or standalone) into EnumGroups."""
    groups: list[EnumGroup] = []
    block_comment = preceding_comments(node, source)

    specs = find_children(node, "const_spec")
    if not specs:
        return groups

    current_type: str | None = None
    current_values: list[EnumValue] = []
    iota_counter = 0
    in_iota = False

    for spec in specs:
        name_node = find_child(spec, "identifier")
        if not name_node:
            continue
        name = node_text(name_node)

        type_node = find_child(spec, "type_identifier")
        type_hint = node_text(type_node) if type_node else None

        expr_node = find_child(spec, "expression_list")
        value_text = node_text(expr_node).strip() if expr_node else ""

        # Inline comment: check siblings at the same line
        comment = _ts_inline_comment(spec)

        # Type change → flush previous group
        if type_hint and type_hint != current_type:
            if current_values and current_type:
                groups.append(EnumGroup(
                    name=current_type, type_name=current_type,
                    values=list(current_values), file=rel_path,
                    service=service, comment=block_comment,
                ))
            current_type = type_hint
            current_values = []
            iota_counter = 0
            in_iota = "iota" in value_text

        if value_text:
            if "iota" in value_text:
                in_iota = True
                iota_counter = 0
                offset_m = re.search(r"iota\s*\+\s*(\d+)", value_text)
                display_value = str(int(offset_m.group(1))) if offset_m else "0"
            elif in_iota:
                iota_counter += 1
                display_value = str(iota_counter)
            else:
                display_value = value_text
                in_iota = False
        elif in_iota:
            iota_counter += 1
            display_value = str(iota_counter)
        else:
            display_value = ""

        current_values.append(EnumValue(
            name=name, value=display_value, comment=comment,
        ))

    # Flush remaining
    if current_values:
        groups.append(EnumGroup(
            name=current_type or "unnamed",
            type_name=current_type or "int",
            values=current_values, file=rel_path,
            service=service, comment=block_comment,
        ))

    return groups


def _ts_inline_comment(spec_node) -> str:
    """Extract an inline comment on the same line as a const_spec."""
    row = spec_node.end_point.row
    parent = spec_node.parent
    if parent is None:
        return ""
    for child in parent.children:
        if child.type == "comment" and child.start_point.row == row:
            return node_text(child).lstrip("/ ")
    return ""


def _ts_parse_var_declaration(node, source: bytes, rel_path: str,
                              service: str) -> list[EnumGroup]:
    """Parse var declarations for map-based and struct-literal enums."""
    groups: list[EnumGroup] = []

    for spec in find_children(node, "var_spec"):
        name_node = find_child(spec, "identifier")
        if not name_node:
            continue
        var_name = node_text(name_node)

        expr_node = find_child(spec, "expression_list")
        if not expr_node:
            continue
        expr_text = node_text(expr_node)

        # Map-based enum: map[int]string{1: "Pending", 2: "Active"}
        if "map[" in expr_text and "]string{" in expr_text:
            map_m = re.search(r"map\[(\w+)\]string\{(.*)\}", expr_text, re.DOTALL)
            if map_m:
                key_type = map_m.group(1)
                entries = _MAP_ENTRY_RE.findall(map_m.group(2))
                if entries:
                    values = [EnumValue(name=label, value=key) for key, label in entries]
                    groups.append(EnumGroup(
                        name=var_name, type_name=key_type,
                        values=values, file=rel_path, service=service,
                    ))
            continue

        # Struct-literal enum: struct{...}{...} or TypeName{...}
        if "struct{" in expr_text.replace(" ", "") or re.search(r"\w+(?:\[[^\]]*\])?\s*\{", expr_text):
            brace_start = expr_text.rfind("{")
            if brace_start >= 0:
                body = expr_text[brace_start:]
                entries = _STRUCT_FIELD_RE.findall(body)
                if entries:
                    type_node = find_child(spec, "type_identifier")
                    type_name = node_text(type_node) if type_node else var_name
                    values = [
                        EnumValue(name=n, value=v.strip('"'))
                        for n, v in entries
                    ]
                    groups.append(EnumGroup(
                        name=var_name, type_name=type_name,
                        values=values, file=rel_path, service=service,
                    ))

    return groups


# ---------------------------------------------------------------------------
# Regex fallback (original implementation)
# ---------------------------------------------------------------------------

_CONST_BLOCK_RE = re.compile(r"const\s*\((.*?)\)", re.DOTALL)
_CONST_LINE_RE = re.compile(
    r"^\s*(\w+)(?:\s+(\w+))?\s*=\s*(.*?)\s*(?://\s*(.*))?$", re.MULTILINE,
)
_IOTA_CONT_RE = re.compile(r"^\s*(\w+)\s*(?://\s*(.*))?$", re.MULTILINE)
_STANDALONE_CONST_RE = re.compile(
    r"^const\s+(\w+)\s+(\w+)\s*=\s*(.*?)(?:\s*//\s*(.*))?$", re.MULTILINE,
)
_MAP_LITERAL_RE = re.compile(
    r"(?:var\s+)?(\w+)\s*:?=\s*map\[(\w+)\]string\s*\{(.*?)\}", re.DOTALL,
)
_ANON_STRUCT_ENUM_RE = re.compile(
    r"var\s+(\w+)\s*=\s*struct\s*\{[^}]*\}\s*\{(.*?)\}", re.DOTALL,
)
_TYPED_STRUCT_ENUM_RE = re.compile(
    r"var\s+(\w+)\s+(\w+)(?:\[[^\]]*\])?\s*=\s*\w+(?:\[[^\]]*\])?\s*\{(.*?)\}", re.DOTALL,
)


def _regex_extract_block_comment(content: str, block_start: int) -> str:
    prefix = content[:block_start]
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


def _regex_parse_const_block(block_text: str, block_start: int,
                             content: str, file_path: str,
                             service: str) -> list[EnumGroup]:
    groups: list[EnumGroup] = []
    block_comment = _regex_extract_block_comment(content, block_start)
    current_type: str | None = None
    current_values: list[EnumValue] = []
    iota_counter = 0
    in_iota = False

    for line in block_text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        m = _CONST_LINE_RE.match(stripped)
        if m:
            name, type_hint, value, comment = m.groups()
            value = value.strip()
            if type_hint and type_hint != current_type:
                if current_values and current_type:
                    groups.append(EnumGroup(
                        name=current_type, type_name=current_type,
                        values=list(current_values), file=file_path,
                        service=service, comment=block_comment,
                    ))
                current_type = type_hint
                current_values = []
                iota_counter = 0
                in_iota = "iota" in value
            if "iota" in value:
                in_iota = True
                iota_counter = 0
                offset_m = re.search(r"iota\s*\+\s*(\d+)", value)
                display_value = str(int(offset_m.group(1))) if offset_m else "0"
            elif in_iota:
                iota_counter += 1
                display_value = str(iota_counter)
            else:
                display_value = value
                in_iota = False
            current_values.append(EnumValue(name=name, value=display_value, comment=comment or ""))
            continue
        if in_iota:
            m2 = _IOTA_CONT_RE.match(stripped)
            if m2:
                iota_counter += 1
                current_values.append(EnumValue(
                    name=m2.group(1), value=str(iota_counter), comment=m2.group(2) or "",
                ))

    if current_values:
        groups.append(EnumGroup(
            name=current_type or "unnamed", type_name=current_type or "int",
            values=current_values, file=file_path,
            service=service, comment=block_comment,
        ))
    return groups


def _regex_extract_enums_from_file(content: str, rel_path: str,
                                   service: str) -> list[EnumGroup]:
    groups: list[EnumGroup] = []
    for m in _CONST_BLOCK_RE.finditer(content):
        groups.extend(_regex_parse_const_block(
            m.group(1), m.start(), content, rel_path, service,
        ))
    for m in _STANDALONE_CONST_RE.finditer(content):
        name, type_name, value, comment = m.groups()
        groups.append(EnumGroup(
            name=name, type_name=type_name,
            values=[EnumValue(name=name, value=value.strip(), comment=comment or "")],
            file=rel_path, service=service,
        ))
    for m in _MAP_LITERAL_RE.finditer(content):
        var_name, key_type, body = m.groups()
        entries = _MAP_ENTRY_RE.findall(body)
        if entries:
            values = [EnumValue(name=label, value=key) for key, label in entries]
            groups.append(EnumGroup(
                name=var_name, type_name=key_type, values=values,
                file=rel_path, service=service,
            ))
    seen_names: set[str] = {g.name for g in groups}
    for m in _ANON_STRUCT_ENUM_RE.finditer(content):
        var_name, body = m.group(1), m.group(2)
        entries = _STRUCT_FIELD_RE.findall(body)
        if entries:
            values = [EnumValue(name=n, value=v.strip('"')) for n, v in entries]
            groups.append(EnumGroup(
                name=var_name, type_name=var_name, values=values,
                file=rel_path, service=service,
            ))
            seen_names.add(var_name)
    for m in _TYPED_STRUCT_ENUM_RE.finditer(content):
        var_name, type_name, body = m.groups()
        if var_name in seen_names:
            continue
        entries = _STRUCT_FIELD_RE.findall(body)
        if entries:
            values = [EnumValue(name=n, value=v.strip('"')) for n, v in entries]
            groups.append(EnumGroup(
                name=var_name, type_name=type_name, values=values,
                file=rel_path, service=service,
            ))
    return groups


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_enums_from_file(file_path: Path, repo_root: Path,
                            service: str) -> list[EnumGroup]:
    """Extract all enum/const groups from a single Go file."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    rel_path = str(file_path.relative_to(repo_root))

    if _ts_available():
        return _ts_extract_enums_from_file(content.encode("utf-8"), rel_path, service)
    return _regex_extract_enums_from_file(content, rel_path, service)


def extract_enums_from_repo(repo_path: str, service: str) -> list[EnumGroup]:
    """Walk a Go repository and extract all enum/const definitions."""
    root = Path(repo_path).resolve()
    all_groups: list[EnumGroup] = []

    for go_file in root.rglob("*.go"):
        if any(part in _IGNORE_DIRS for part in go_file.parts):
            continue
        if go_file.name.endswith("_test.go") or go_file.name.endswith(".pb.go"):
            continue
        file_groups = extract_enums_from_file(go_file, root, service)
        all_groups.extend(file_groups)

    logger.info(
        "[EnumExtractor] Found %d enum groups across %s (tree-sitter=%s)",
        len(all_groups), service, _ts_available(),
    )
    return all_groups
