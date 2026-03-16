"""Extracts Go const blocks, iota patterns, and status/enum maps from source files.

Supports:
  - Simple typed const groups:   const ( StatusPending OrderStatus = 1 )
  - Iota-based enums:            const ( Pending Status = iota )
  - Mapped string enums:         var statusNames = map[int]string{ 1: "Pending" }
  - Comment-annotated consts:    StatusActive = 2 // driver assigned

This is the highest-value extractor: it turns opaque integers (status=1, payCd=7)
into human-readable enum descriptions that the chatbot can look up at query time.
"""

import logging
import re
from pathlib import Path

from indexer.models import EnumGroup, EnumValue

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns for Go const/var extraction
# ---------------------------------------------------------------------------

# Matches a const block:  const ( ... )
_CONST_BLOCK_RE = re.compile(
    r"const\s*\((.*?)\)",
    re.DOTALL,
)

# Matches a single typed const line inside a const block:
#   StatusPending OrderStatus = 1    // awaiting driver
#   Pending = iota                   // first value
# Groups: (1) name, (2) optional type, (3) value, (4) optional comment
_CONST_LINE_RE = re.compile(
    r"^\s*(\w+)"                         # (1) const name
    r"(?:\s+(\w+))?"                     # (2) optional Go type
    r"\s*=\s*"                           # = sign
    r"(.*?)"                             # (3) value (non-greedy)
    r"\s*(?://\s*(.*))?$",               # (4) optional inline comment
    re.MULTILINE,
)

# Matches iota continuation lines (no explicit = iota):
#   Active     // driver assigned
_IOTA_CONT_RE = re.compile(
    r"^\s*(\w+)"                         # (1) const name
    r"\s*(?://\s*(.*))?$",               # (2) optional inline comment
    re.MULTILINE,
)

# Matches standalone typed const (outside a block):
#   const MaxRetries int = 3
_STANDALONE_CONST_RE = re.compile(
    r"^const\s+(\w+)\s+(\w+)\s*=\s*(.*?)(?:\s*//\s*(.*))?$",
    re.MULTILINE,
)

# Matches map literal for enum name translations:
#   var statusNames = map[int]string{ 1: "Pending", 2: "Active" }
# or:
#   statusNameMap := map[OrderStatus]string{
_MAP_LITERAL_RE = re.compile(
    r"(?:var\s+)?(\w+)\s*:?=\s*map\[(\w+)\]string\s*\{(.*?)\}",
    re.DOTALL,
)

# Matches entries inside a map literal:   1: "Pending",
_MAP_ENTRY_RE = re.compile(
    r'(\w+)\s*:\s*"([^"]+)"',
)

# Block comment before a const group
_BLOCK_COMMENT_RE = re.compile(
    r"((?://[^\n]*\n)+)\s*const\s*\(",
)

# ---------------------------------------------------------------------------
# Struct-literal enum patterns (very common in this Go codebase)
# ---------------------------------------------------------------------------

# Pattern 1: anonymous struct –
#   var StatusCD = struct { Assigned uint; ... }{ Assigned: 1, ... }
_ANON_STRUCT_ENUM_RE = re.compile(
    r"var\s+(\w+)\s*=\s*struct\s*\{[^}]*\}\s*\{(.*?)\}",
    re.DOTALL,
)

# Pattern 2: typed struct (with optional generics) –
#   var OrderRequestStatusCD OrderRequestStatus[uint] = OrderRequestStatus[uint]{ Pending: 1, ... }
#   var PayCDCode PayCDType[int] = PayCDType[int]{ Cash: 1, ... }
_TYPED_STRUCT_ENUM_RE = re.compile(
    r"var\s+(\w+)\s+(\w+)"       # (1) var name, (2) type name
    r"(?:\[[^\]]*\])?"            # optional [T] on declared type
    r"\s*=\s*"                    # =
    r"\w+(?:\[[^\]]*\])?"         # rhs type (with optional [T])
    r"\s*\{(.*?)\}",             # (3) initializer body
    re.DOTALL,
)

# Matches field: value inside a struct initializer
#   Pending: 1,     Cash: "cash",
_STRUCT_FIELD_RE = re.compile(
    r'(\w+)\s*:\s*("(?:[^"\\]|\\.)*"|\d+(?:\.\d+)?)',
)


def _extract_block_comment(content: str, block_start: int) -> str:
    """Look backwards from a const block to grab preceding // comments."""
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


def _parse_const_block(block_text: str, block_start: int,
                       content: str, file_path: str,
                       service: str) -> list[EnumGroup]:
    """Parse a single const( ... ) block into one or more EnumGroups."""
    groups: list[EnumGroup] = []
    block_comment = _extract_block_comment(content, block_start)

    # Try typed enum detection first
    current_type: str | None = None
    current_values: list[EnumValue] = []
    iota_counter = 0
    in_iota = False

    for line in block_text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue

        # Try explicit assignment:  Name Type = Value // comment
        m = _CONST_LINE_RE.match(stripped)
        if m:
            name, type_hint, value, comment = m.groups()
            value = value.strip()

            # Detect type change → flush previous group
            if type_hint and type_hint != current_type:
                if current_values and current_type:
                    groups.append(EnumGroup(
                        name=current_type,
                        type_name=current_type,
                        values=list(current_values),
                        file=file_path,
                        service=service,
                        comment=block_comment,
                    ))
                current_type = type_hint
                current_values = []
                iota_counter = 0
                in_iota = "iota" in value

            if "iota" in value:
                in_iota = True
                iota_counter = 0
                # Try to extract base offset: iota + 1 → start at 1
                offset_m = re.search(r"iota\s*\+\s*(\d+)", value)
                display_value = str(int(offset_m.group(1))) if offset_m else "0"
            elif in_iota:
                iota_counter += 1
                display_value = str(iota_counter)
            else:
                display_value = value
                in_iota = False

            current_values.append(EnumValue(
                name=name,
                value=display_value,
                comment=comment or "",
            ))
            continue

        # Iota continuation line (no =):  Active // driver assigned
        if in_iota:
            m2 = _IOTA_CONT_RE.match(stripped)
            if m2:
                iota_counter += 1
                current_values.append(EnumValue(
                    name=m2.group(1),
                    value=str(iota_counter),
                    comment=m2.group(2) or "",
                ))

    # Flush remaining
    if current_values:
        groups.append(EnumGroup(
            name=current_type or "unnamed",
            type_name=current_type or "int",
            values=current_values,
            file=file_path,
            service=service,
            comment=block_comment,
        ))

    return groups


def _extract_map_enums(content: str, file_path: str,
                       service: str) -> list[EnumGroup]:
    """Extract enum-like map[T]string definitions."""
    groups: list[EnumGroup] = []
    for m in _MAP_LITERAL_RE.finditer(content):
        var_name, key_type, body = m.groups()
        entries = _MAP_ENTRY_RE.findall(body)
        if not entries:
            continue
        values = [
            EnumValue(name=label, value=key, comment="")
            for key, label in entries
        ]
        groups.append(EnumGroup(
            name=var_name,
            type_name=key_type,
            values=values,
            file=file_path,
            service=service,
        ))
    return groups


def _extract_struct_literal_enums(content: str, file_path: str,
                                  service: str) -> list[EnumGroup]:
    """Extract enum-like Go struct literal initializers.

    Covers two patterns common in this codebase:
      var StatusCD = struct { ... }{ Field: value, ... }       (anonymous)
      var PayCDCode PayCDType[int] = PayCDType[int]{ ... }     (typed/generic)
    """
    groups: list[EnumGroup] = []
    seen_names: set[str] = set()

    # Pattern 1: anonymous struct
    for m in _ANON_STRUCT_ENUM_RE.finditer(content):
        var_name = m.group(1)
        body = m.group(2)
        entries = _STRUCT_FIELD_RE.findall(body)
        if not entries:
            continue
        values = [
            EnumValue(name=name, value=val.strip('"'), comment="")
            for name, val in entries
        ]
        groups.append(EnumGroup(
            name=var_name,
            type_name=var_name,
            values=values,
            file=file_path,
            service=service,
        ))
        seen_names.add(var_name)

    # Pattern 2: typed struct (with optional generics)
    for m in _TYPED_STRUCT_ENUM_RE.finditer(content):
        var_name = m.group(1)
        type_name = m.group(2)
        body = m.group(3)
        if var_name in seen_names:
            continue
        entries = _STRUCT_FIELD_RE.findall(body)
        if not entries:
            continue
        values = [
            EnumValue(name=name, value=val.strip('"'), comment="")
            for name, val in entries
        ]
        groups.append(EnumGroup(
            name=var_name,
            type_name=type_name,
            values=values,
            file=file_path,
            service=service,
        ))
        seen_names.add(var_name)

    return groups


def extract_enums_from_file(file_path: Path, repo_root: Path,
                            service: str) -> list[EnumGroup]:
    """Extract all enum/const groups from a single Go file."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    rel_path = str(file_path.relative_to(repo_root))
    groups: list[EnumGroup] = []

    # 1. Const blocks
    for m in _CONST_BLOCK_RE.finditer(content):
        block_groups = _parse_const_block(
            m.group(1), m.start(), content, rel_path, service
        )
        groups.extend(block_groups)

    # 2. Standalone consts
    for m in _STANDALONE_CONST_RE.finditer(content):
        name, type_name, value, comment = m.groups()
        groups.append(EnumGroup(
            name=name,
            type_name=type_name,
            values=[EnumValue(name=name, value=value.strip(), comment=comment or "")],
            file=rel_path,
            service=service,
        ))

    # 3. Map-based enum definitions
    groups.extend(_extract_map_enums(content, rel_path, service))

    # 4. Struct-literal enums (var Name = struct{...}{...} or var Name Type = Type{...})
    groups.extend(_extract_struct_literal_enums(content, rel_path, service))

    return groups


def extract_enums_from_repo(repo_path: str, service: str) -> list[EnumGroup]:
    """Walk a Go repository and extract all enum/const definitions.

    Args:
        repo_path: Path to the Go repository root.
        service: Service name to tag results with (e.g. "order-service").

    Returns:
        List of EnumGroup, each representing a set of related constants.
    """
    root = Path(repo_path).resolve()
    ignore_dirs = frozenset({".git", "vendor", "testdata", "test", "mocks", "node_modules"})
    all_groups: list[EnumGroup] = []

    for go_file in root.rglob("*.go"):
        if any(part in ignore_dirs for part in go_file.parts):
            continue
        if go_file.name.endswith("_test.go"):
            continue
        # Skip protobuf-generated files — they contain only boilerplate
        if go_file.name.endswith(".pb.go"):
            continue
        file_groups = extract_enums_from_file(go_file, root, service)
        all_groups.extend(file_groups)

    logger.info(
        "[EnumExtractor] Found %d enum groups across %s",
        len(all_groups), service,
    )
    return all_groups
