from dataclasses import dataclass, field


@dataclass
class FrontendApiCall:
    """Represents a single outgoing HTTP call found in the frontend codebase."""

    file: str
    method: str
    url: str
    line_number: int


@dataclass
class BackendEndpoint:
    """Represents a single HTTP endpoint defined in the backend codebase."""

    method: str
    path: str
    controller: str
    controller_method: str
    file: str
    service_calls: list[str] = field(default_factory=list)


@dataclass
class FlowMapping:
    """Represents an end-to-end flow from a frontend API call to a backend handler."""

    feature: str
    frontend_file: str
    api: str
    backend_controller: str
    backend_service: str
