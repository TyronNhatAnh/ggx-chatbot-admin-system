"""Extracts Java enum classes and static final constant groups.

Supports:
  - Java enum classes with constructor args:
        public enum OrderStatus { PENDING(1, "대기"), ACTIVE(2, "활성"); }
  - Simple Java enums (no args):
        public enum Color { RED, GREEN, BLUE }
  - static final constant fields grouped by enclosing class:
        public static final int PENDING = 1;
  - Interface-based constants (older Java pattern):
        public interface StatusCode { int PENDING = 1; }
"""

import logging
import re
from pathlib import Path

from indexer.models import EnumGroup, EnumValue

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Java enum class declaration:
#   public enum OrderStatus { ... }
_ENUM_CLASS_RE = re.compile(
    r"(?:public\s+)?enum\s+(\w+)"          # (1) enum name
    r"(?:\s+implements\s+[\w,\s<>]+)?"      # optional implements
    r"\s*\{",
)

# Enum constant with constructor args:
#   PENDING(1, "대기중"),  or  PENDING(1),
_ENUM_CONST_WITH_ARGS_RE = re.compile(
    r"^\s*(\w+)"                             # (1) constant name
    r"\s*\(\s*(.+?)\s*\)"                    # (2) constructor arguments
    r"\s*[,;]?"                              # trailing comma or semicolon
    r"\s*(?://\s*(.*))?$",                   # (3) optional inline comment
    re.MULTILINE,
)

# Simple enum constant (no args):   RED, GREEN, BLUE
_ENUM_CONST_SIMPLE_RE = re.compile(
    r"^\s*(\w+)"                             # (1) constant name
    r"\s*[,;]?"                              # trailing comma or semicolon
    r"\s*(?://\s*(.*))?$",                   # (2) optional inline comment
    re.MULTILINE,
)

# static final constant (inside a class):
#   public static final int PENDING = 1;  // awaiting
_STATIC_FINAL_RE = re.compile(
    r"^\s*(?:public|private|protected)?\s*"
    r"static\s+final\s+"
    r"(\w+)\s+"                              # (1) type (int, String, long, ...)
    r"(\w+)\s*=\s*"                          # (2) field name
    r"(.+?)\s*;\s*"                          # (3) value
    r"(?://\s*(.*))?$",                      # (4) optional comment
    re.MULTILINE,
)

# Interface constant:
#   int PENDING = 1;   (implicitly public static final)
_INTERFACE_CONST_RE = re.compile(
    r"^\s*(\w+)\s+"                          # (1) type
    r"(\w+)\s*=\s*"                          # (2) name
    r"(.+?)\s*;\s*"                          # (3) value
    r"(?://\s*(.*))?$",                      # (4) comment
    re.MULTILINE,
)

# Enclosing class/interface name
_CLASS_RE = re.compile(
    r"(?:public\s+)?(?:class|interface)\s+(\w+)",
)

# Javadoc or block comment before enum/class
_JAVADOC_RE = re.compile(
    r"/\*\*(.*?)\*/",
    re.DOTALL,
)

# Single-line comments above a declaration
_LINE_COMMENT_RE = re.compile(
    r"((?:\s*//[^\n]*\n)+)",
)


def _extract_javadoc_before(content: str, pos: int) -> str:
    """Extract Javadoc or line comments immediately before pos."""
    prefix = content[:pos].rstrip()
    # Try Javadoc /** ... */
    jd_end = prefix.rfind("*/")
    if jd_end != -1 and jd_end > len(prefix) - 200:
        jd_start = prefix.rfind("/**", 0, jd_end)
        if jd_start != -1:
            raw = prefix[jd_start + 3:jd_end]
            lines = [
                ln.strip().lstrip("* ").strip()
                for ln in raw.split("\n")
                if ln.strip() and not ln.strip().startswith("@")
            ]
            return " ".join(lines)

    # Try // line comments
    lines = prefix.split("\n")
    comment_lines: list[str] = []
    for line in reversed(lines):
        stripped = line.strip()
        if stripped.startswith("//"):
            comment_lines.append(stripped.lstrip("/ ").strip())
        elif stripped == "":
            continue
        else:
            break
    comment_lines.reverse()
    return " ".join(comment_lines)


def _extract_balanced_brace(content: str, open_pos: int) -> str:
    """Extract text between { and matching } starting at open_pos."""
    depth = 0
    i = open_pos
    while i < len(content):
        ch = content[i]
        if ch == '"':
            i += 1
            while i < len(content) and content[i] != '"':
                if content[i] == "\\":
                    i += 1
                i += 1
        elif ch == "'":
            i += 1
            while i < len(content) and content[i] != "'":
                if content[i] == "\\":
                    i += 1
                i += 1
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return content[open_pos + 1:i]
        i += 1
    return ""


def _parse_enum_body(body: str, enum_name: str, file_path: str,
                     service: str, comment: str) -> EnumGroup | None:
    """Parse the body of a Java enum class into an EnumGroup.

    The body contains enum constants first, then optionally fields/methods
    after a semicolon.
    """
    # Split at first semicolon that's not inside parens —
    # everything before is enum constants, after is fields/methods
    constants_section = body
    depth = 0
    for i, ch in enumerate(body):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif ch == ';' and depth == 0:
            constants_section = body[:i]
            break

    # Remove inner class / method blocks (anything with { })
    # Only keep lines that look like enum constants
    values: list[EnumValue] = []
    iota = 0

    for line in constants_section.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            continue

        # Skip annotation lines
        if stripped.startswith("@"):
            continue

        # Try constant with constructor args: PENDING(1, "대기"),
        m = _ENUM_CONST_WITH_ARGS_RE.match(stripped)
        if m:
            name = m.group(1)
            args_raw = m.group(2)
            inline_comment = m.group(3) or ""

            # Extract first arg as the "value" (usually the code/id)
            # Remove string quotes from arguments for display
            args = [a.strip().strip('"').strip("'") for a in args_raw.split(",")]
            value = args[0] if args else str(iota)

            # If there are multiple args, second is often a description
            desc_parts = []
            if len(args) > 1:
                desc_parts.append(args[1])
            if inline_comment:
                desc_parts.append(inline_comment)
            comment_str = " / ".join(desc_parts) if desc_parts else ""

            values.append(EnumValue(
                name=name, value=value, comment=comment_str,
            ))
            iota += 1
            continue

        # Try simple constant: RED, GREEN,
        m2 = _ENUM_CONST_SIMPLE_RE.match(stripped)
        if m2:
            name = m2.group(1)
            # Skip Java keywords that might match
            if name in {"private", "public", "protected", "static", "final",
                        "class", "interface", "enum", "abstract", "void",
                        "return", "int", "long", "String", "boolean"}:
                continue
            inline_comment = m2.group(2) or ""
            values.append(EnumValue(
                name=name, value=str(iota), comment=inline_comment,
            ))
            iota += 1
            continue

    if not values:
        return None

    return EnumGroup(
        name=enum_name,
        type_name=enum_name,
        values=values,
        file=file_path,
        service=service,
        comment=comment,
    )


def _extract_static_final_groups(content: str, file_path: str,
                                 service: str) -> list[EnumGroup]:
    """Extract static final constants grouped by enclosing class."""
    groups_by_class: dict[str, list[EnumValue]] = {}
    class_comments: dict[str, str] = {}

    # Find enclosing class name
    current_class = "Constants"
    for cm in _CLASS_RE.finditer(content):
        current_class = cm.group(1)
        class_comments[current_class] = _extract_javadoc_before(content, cm.start())
        break  # Use top-level class

    for m in _STATIC_FINAL_RE.finditer(content):
        type_name, field_name, value, comment = m.groups()
        value = value.strip().strip('"').strip("'")

        # Skip non-constant-looking fields (long strings, complex expressions)
        if len(value) > 100 or "new " in value or "(" in value:
            continue

        if current_class not in groups_by_class:
            groups_by_class[current_class] = []
        groups_by_class[current_class].append(EnumValue(
            name=field_name,
            value=value,
            comment=comment or "",
        ))

    result: list[EnumGroup] = []
    for cls_name, values in groups_by_class.items():
        if len(values) < 2:
            continue  # Single constant isn't an "enum group"
        result.append(EnumGroup(
            name=cls_name,
            type_name="static_final",
            values=values,
            file=file_path,
            service=service,
            comment=class_comments.get(cls_name, ""),
        ))
    return result


def extract_enums_from_file(file_path: Path, repo_root: Path,
                            service: str) -> list[EnumGroup]:
    """Extract all enum/constant groups from a single Java file."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    rel_path = str(file_path.relative_to(repo_root))
    groups: list[EnumGroup] = []

    # 1. Java enum classes
    for m in _ENUM_CLASS_RE.finditer(content):
        enum_name = m.group(1)
        brace_pos = content.find("{", m.start())
        if brace_pos == -1:
            continue
        body = _extract_balanced_brace(content, brace_pos)
        if not body:
            continue

        comment = _extract_javadoc_before(content, m.start())
        eg = _parse_enum_body(body, enum_name, rel_path, service, comment)
        if eg:
            groups.append(eg)

    # 2. static final constant groups
    groups.extend(_extract_static_final_groups(content, rel_path, service))

    return groups


def extract_enums_from_repo(repo_path: str, service: str) -> list[EnumGroup]:
    """Walk a Java repository and extract all enum/constant definitions."""
    root = Path(repo_path).resolve()
    ignore_dirs = frozenset({
        ".git", "target", "build", ".gradle", ".idea", ".mvn",
        "test", "tests", "node_modules", "__pycache__",
    })
    all_groups: list[EnumGroup] = []

    for java_file in root.rglob("*.java"):
        if any(part in ignore_dirs for part in java_file.parts):
            continue
        # Skip test files
        if java_file.name.endswith("Test.java") or java_file.name.endswith("Tests.java"):
            continue
        file_groups = extract_enums_from_file(java_file, root, service)
        all_groups.extend(file_groups)

    logger.info(
        "[Java EnumExtractor] Found %d enum groups across %s",
        len(all_groups), service,
    )
    return all_groups
