=== DOMAIN: Knowledge & Code ===

Knowledge tools (indexed codebase):
- explain_status(code) → decoded status across all enums. ONE call, answer immediately.
- lookup_enum(enum_name) → all enum values. Partial names OK.
- trace_service_flow(handler_name) → handler → service → repo call chain.
- get_struct_definition(struct_name) → Go struct fields + JSON tags.
- search_codebase(query) → semantic + full-text code search.
- get_knowledge_stats() → check what's indexed.

Graph tools:
- traverse_graph(name, edge_types, direction, max_depth) — multi-hop (1-5 hops).
- find_api_consumers(endpoint) — React components calling a backend endpoint.
- trace_full_stack(endpoint) — end-to-end: React → API → Go handler → services.

Doc tools:
- list_available_docs() — call FIRST if unsure what's indexed.
- search_endpoints(keyword) — find routes by method/path/handler.
- get_handler_context(handler_name) — full handler source + service calls.

Tool priority for code questions (lightest first):
  1. explain_status / lookup_enum
  2. trace_service_flow / get_struct_definition
  3. traverse_graph / find_api_consumers / trace_full_stack
  4. search_codebase
  5. search_endpoints / get_handler_context
