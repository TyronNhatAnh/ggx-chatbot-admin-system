"""Java language parser — extracts enums, types, and service flows from Java repos.

Supports Java 8 Spring Boot codebases including:
  - Enum classes and static final constants
  - DTOs, entities, request/response classes (with Lombok / JPA support)
  - Controller → Service → Repository flows (REST and non-REST)
  - Scheduled tasks, event listeners, internal service methods
  - Spring DI graph edges (@Autowired, constructor injection)
"""

from indexer.parsers.java.parser import JavaParser
from indexer.parsers.registry import register

register(JavaParser)

__all__ = ["JavaParser"]
