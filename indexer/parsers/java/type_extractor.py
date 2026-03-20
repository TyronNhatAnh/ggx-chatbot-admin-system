"""Extracts Java class/interface type definitions (DTOs, entities, request/response).

Supports:
  - Standard POJOs with field declarations
  - Lombok-annotated classes: @Data, @Getter, @Setter, @Builder, @Value
  - JPA entities: @Entity, @Table, @Column, @Id
  - Request/Response DTOs with @JsonProperty
  - Interfaces (used as type contracts)
  - Abstract classes
  - Inheritance detection (extends/implements)
"""

import logging
import re
from pathlib import Path

from indexer.models import StructDefinition, StructField

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Class/interface declaration:
#   public class OrderRequest { ... }
#   @Data public class OrderDTO extends BaseDTO implements Serializable { ... }
_CLASS_DEF_RE = re.compile(
    r"(?:public\s+)?(?:abstract\s+)?"
    r"(?:class|interface)\s+(\w+)"          # (1) class name
    r"(?:<[^>]+>)?"                          # optional generics <T>
    r"(?:\s+extends\s+([\w.<>,\s]+?))?"      # (2) optional extends
    r"(?:\s+implements\s+([\w.<>,\s]+?))?"   # (3) optional implements
    r"\s*\{",
)

# Field declaration:
#   private String orderId;
#   private Long id;
#   protected List<OrderItem> items;
_FIELD_RE = re.compile(
    r"^\s+(?:private|protected|public)\s+"   # access modifier (required for fields)
    r"(?!static\s+)"                         # exclude static fields (those go in enum extractor)
    r"(?!(?:abstract|final|synchronized|native|transient|volatile)\s+void\b)"
    r"([\w<>\[\]?,\s]+?)\s+"                 # (1) type (may include generics)
    r"(\w+)\s*"                              # (2) field name
    r"(?:=\s*[^;]+)?\s*;"                    # optional initializer
    r"\s*(?://\s*(.*))?$",                   # (3) optional inline comment
    re.MULTILINE,
)

# @JsonProperty annotation:  @JsonProperty("order_id")
_JSON_PROPERTY_RE = re.compile(
    r'@JsonProperty\s*\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']\s*\)',
)

# @Column annotation:  @Column(name = "status_cd")
_COLUMN_RE = re.compile(
    r'@Column\s*\([^)]*name\s*=\s*["\']([^"\']+)["\']',
)

# @SerializedName("field_name")  (Gson)
_SERIALIZED_NAME_RE = re.compile(
    r'@SerializedName\s*\(\s*["\']([^"\']+)["\']\s*\)',
)

# Lombok annotations on a class
_LOMBOK_CLASS_ANNOTATIONS = re.compile(
    r"@(Data|Value|Builder|Getter|Setter|AllArgsConstructor|NoArgsConstructor"
    r"|RequiredArgsConstructor|ToString|EqualsAndHashCode)\b"
)

# JPA annotations
_ENTITY_RE = re.compile(r"@Entity\b")
_TABLE_RE = re.compile(r'@Table\s*\([^)]*name\s*=\s*["\']([^"\']+)["\']')
_ID_RE = re.compile(r"@Id\b")

# @NotNull, @NotBlank, @NotEmpty — marks required fields
_REQUIRED_RE = re.compile(r"@(?:NotNull|NotBlank|NotEmpty)\b")

# @Nullable or Optional<T> — marks optional fields
_NULLABLE_RE = re.compile(r"@Nullable\b")
_OPTIONAL_TYPE_RE = re.compile(r"Optional<(.+)>")

# Annotations on a field line (annotation immediately before field)
_FIELD_ANNOTATION_RE = re.compile(
    r"^\s*@\w+(?:\([^)]*\))?\s*$",
    re.MULTILINE,
)


def _extract_balanced_brace(content: str, open_pos: int) -> str:
    """Extract text between { and matching } starting at open_pos."""
    depth = 0
    i = open_pos
    in_string = False
    string_char = ""
    while i < len(content):
        ch = content[i]
        if in_string:
            if ch == "\\":
                i += 2
                continue
            if ch == string_char:
                in_string = False
        else:
            if ch in ('"', "'"):
                in_string = True
                string_char = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return content[open_pos + 1:i]
        i += 1
    return ""


def _extract_javadoc_before(content: str, pos: int) -> str:
    """Extract Javadoc comment before a class declaration."""
    prefix = content[:pos].rstrip()
    jd_end = prefix.rfind("*/")
    if jd_end != -1 and jd_end > len(prefix) - 500:
        jd_start = prefix.rfind("/**", 0, jd_end)
        if jd_start != -1:
            raw = prefix[jd_start + 3:jd_end]
            lines = [
                ln.strip().lstrip("* ").strip()
                for ln in raw.split("\n")
                if ln.strip() and not ln.strip().startswith("@")
            ]
            return " ".join(lines)

    lines = prefix.split("\n")
    comment_lines: list[str] = []
    for line in reversed(lines):
        stripped = line.strip()
        if stripped.startswith("//"):
            comment_lines.append(stripped.lstrip("/ ").strip())
        elif stripped == "" or stripped.startswith("@"):
            continue
        else:
            break
    comment_lines.reverse()
    return " ".join(comment_lines)


def _extract_annotations_block(content: str, class_start: int) -> str:
    """Get annotation block before a class declaration."""
    prefix = content[:class_start]
    lines = prefix.rstrip().split("\n")
    ann_lines: list[str] = []
    for line in reversed(lines):
        stripped = line.strip()
        if stripped.startswith("@"):
            ann_lines.append(stripped)
        elif stripped == "" or stripped.startswith("//") or stripped.startswith("*"):
            continue
        else:
            break
    ann_lines.reverse()
    return "\n".join(ann_lines)


def _parse_fields(body: str) -> list[StructField]:
    """Parse field declarations from a Java class body.

    Handles annotations on the line above a field (e.g., @JsonProperty).
    """
    fields: list[StructField] = []
    lines = body.split("\n")
    pending_annotations: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Skip empty, comments, methods, inner classes
        if not stripped or stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            pending_annotations = []
            continue

        # Collect annotations above fields
        if stripped.startswith("@"):
            pending_annotations.append(stripped)
            continue

        # Try field match
        fm = _FIELD_RE.match(line)
        if fm:
            field_type = fm.group(1).strip()
            field_name = fm.group(2)
            inline_comment = fm.group(3) or ""

            # Determine JSON tag from annotations
            json_tag = ""
            is_pointer = False
            annotation_text = "\n".join(pending_annotations)

            jp = _JSON_PROPERTY_RE.search(annotation_text)
            if jp:
                json_tag = jp.group(1)

            sn = _SERIALIZED_NAME_RE.search(annotation_text)
            if sn and not json_tag:
                json_tag = sn.group(1)

            col = _COLUMN_RE.search(annotation_text)
            if col and not json_tag:
                json_tag = col.group(1)

            # Detect nullable/optional
            if _NULLABLE_RE.search(annotation_text):
                is_pointer = True
            om = _OPTIONAL_TYPE_RE.match(field_type)
            if om:
                field_type = om.group(1)
                is_pointer = True

            # Add annotation context to comment
            ann_tags: list[str] = []
            if _ID_RE.search(annotation_text):
                ann_tags.append("@Id")
            if _REQUIRED_RE.search(annotation_text):
                ann_tags.append("required")
            if ann_tags and inline_comment:
                inline_comment = f"[{', '.join(ann_tags)}] {inline_comment}"
            elif ann_tags:
                inline_comment = f"[{', '.join(ann_tags)}]"

            fields.append(StructField(
                name=field_name,
                type=field_type,
                json_tag=json_tag,
                comment=inline_comment,
                is_pointer=is_pointer,
            ))
            pending_annotations = []
            continue

        # Reset pending annotations if this line is not a field or annotation
        if not stripped.startswith("@"):
            pending_annotations = []

    return fields


def extract_types_from_file(file_path: Path, repo_root: Path,
                            service: str) -> list[StructDefinition]:
    """Extract all class/interface definitions from a single Java file."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    rel_path = str(file_path.relative_to(repo_root))
    structs: list[StructDefinition] = []

    for m in _CLASS_DEF_RE.finditer(content):
        class_name = m.group(1)
        extends_raw = m.group(2)
        implements_raw = m.group(3)

        brace_pos = content.find("{", m.start())
        if brace_pos == -1:
            continue

        body = _extract_balanced_brace(content, brace_pos)
        if not body:
            continue

        comment = _extract_javadoc_before(content, m.start())
        ann_block = _extract_annotations_block(content, m.start())

        # Classify the type via annotations
        type_tags: list[str] = []
        if _ENTITY_RE.search(ann_block):
            type_tags.append("entity")
        table_m = _TABLE_RE.search(ann_block)
        if table_m:
            type_tags.append(f"table:{table_m.group(1)}")
        if _LOMBOK_CLASS_ANNOTATIONS.search(ann_block):
            type_tags.append("lombok")
        if any(kw in class_name.lower() for kw in ("dto", "request", "response", "vo", "param")):
            type_tags.append("dto")

        if type_tags and comment:
            comment = f"[{', '.join(type_tags)}] {comment}"
        elif type_tags:
            comment = f"[{', '.join(type_tags)}]"

        # Collect embedded/parent types
        embedded: list[str] = []
        if extends_raw:
            for ext in extends_raw.split(","):
                ext = ext.strip().split("<")[0].strip()
                if ext:
                    embedded.append(ext)
        if implements_raw:
            for impl in implements_raw.split(","):
                impl = impl.strip().split("<")[0].strip()
                if impl and impl not in ("Serializable",):
                    embedded.append(impl)

        fields = _parse_fields(body)

        # Skip classes with no fields (likely interfaces/util classes)
        # but keep entities and DTOs even with few fields
        if not fields and not type_tags:
            continue

        structs.append(StructDefinition(
            name=class_name,
            fields=fields,
            file=rel_path,
            service=service,
            comment=comment,
            embedded_types=embedded,
        ))

    return structs


def extract_types_from_repo(repo_path: str, service: str) -> list[StructDefinition]:
    """Walk a Java repository and extract all class/interface definitions."""
    root = Path(repo_path).resolve()
    ignore_dirs = frozenset({
        ".git", "target", "build", ".gradle", ".idea", ".mvn",
        "test", "tests", "node_modules", "__pycache__",
    })
    all_structs: list[StructDefinition] = []

    for java_file in root.rglob("*.java"):
        if any(part in ignore_dirs for part in java_file.parts):
            continue
        if java_file.name.endswith("Test.java") or java_file.name.endswith("Tests.java"):
            continue
        file_structs = extract_types_from_file(java_file, root, service)
        all_structs.extend(file_structs)

    logger.info(
        "[Java TypeExtractor] Found %d type definitions across %s",
        len(all_structs), service,
    )
    return all_structs
