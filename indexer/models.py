"""Data models for indexed codebase entities."""

from dataclasses import dataclass, field


@dataclass
class EnumValue:
    """A single constant within a Go const block."""
    name: str
    value: str            # literal value or iota expression
    comment: str = ""     # inline comment explaining the value
    persona: str = ""     # perspective: "customer", "driver", "admin", or "" (all)


@dataclass
class EnumGroup:
    """A group of related constants (one Go const block or typed const group)."""
    name: str                           # e.g. "OrderStatusCd", "PayCd"
    type_name: str                      # Go type, e.g. "int", "string", "OrderStatus"
    values: list[EnumValue] = field(default_factory=list)
    file: str = ""                      # relative path in the repo
    service: str = ""                   # service name, e.g. "order-service"
    comment: str = ""                   # block-level comment


@dataclass
class StructField:
    """A single field inside a Go struct."""
    name: str
    type: str
    json_tag: str = ""
    comment: str = ""
    is_pointer: bool = False


@dataclass
class StructDefinition:
    """A Go struct with its fields and metadata."""
    name: str
    fields: list[StructField] = field(default_factory=list)
    file: str = ""
    service: str = ""
    comment: str = ""
    embedded_types: list[str] = field(default_factory=list)


@dataclass
class ServiceCall:
    """A detected service/repository call within a function body."""
    receiver: str           # e.g. "orderService", "orderRepo"
    method: str             # e.g. "CreateOrder", "FindByID"
    file: str = ""
    line: int = 0


@dataclass
class ServiceFlow:
    """A traced execution path: handler → service → repository."""
    handler_name: str                              # e.g. "GetOrderDetail"
    handler_file: str = ""
    endpoint: str = ""                             # e.g. "GET /api/v1/orders/:id"
    service_calls: list[ServiceCall] = field(default_factory=list)
    repository_calls: list[ServiceCall] = field(default_factory=list)
    description: str = ""
    service: str = ""


@dataclass
class CodeChunk:
    """An indexed code fragment for vector search."""
    qualified_name: str     # e.g. "order-service.OrderHandler.GetOrderDetail"
    content: str            # source code or summarized text
    chunk_type: str         # "function", "struct", "enum", "handler", "flow"
    file: str = ""
    service: str = ""
    start_line: int = 0
    end_line: int = 0
    metadata: dict = field(default_factory=dict)
