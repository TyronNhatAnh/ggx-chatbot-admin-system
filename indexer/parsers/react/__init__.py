"""React/Next.js/TypeScript parser — indexes frontend repositories.

Extracts:
  - Enums (TS enums, const-object enumerations)
  - Types (TS interfaces, type aliases)
  - Routes (Next.js Pages Router, React Router)
  - Components (React function/const components)
  - API calls (axios clients, API modules, SWR, Redux thunks)
  - Flows (component → API call → backend endpoint)
"""

from indexer.parsers.react.parser import ReactParser
from indexer.parsers.registry import register

register(ReactParser)

__all__ = ["ReactParser"]
