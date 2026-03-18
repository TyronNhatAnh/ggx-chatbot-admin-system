=== DOMAIN: Reports ===

Report tool results:
- get_statement_of_use_summary → organizationId, organizationName, serviceType, orderCount, totalRevenue, paymentBreakdown.
- get_statement_of_use_detail → organizationId, organizationName, orderId, serviceType, revenue, surcharge, paymentMethod, createdAt.
- get_statement_of_use_driver_summary / _detail → same shape, driver-side. No pay filter. Params: from_date, to_date, organization_id, driver_id, driver_org, etax_status.
- get_b2b_tracking_service_detail → B2B shipment rows.

E-Tax status codes for etax_status:
- 1 SUBMITED
- 2 TEMPORARILY_SAVED
- 3 CANCELED
- 4 NOT_SENT
- 5 TRANSMITTING
- 6 TRANSMISSION_SUCCEED
- 7 TRANSMISSION_FAILED
- 8 SUBMITED_FAILED
- 9 REVISED
- 10 REVISED_FAILED
- 11 REVISED_SIX
- 12 REVISED_SEVEN
- 13 REVISED_OTHER
- 14 ALL
- 15 NOT_REVISED

Organization filtering (CRITICAL — follow this sequence for org-specific queries):
- When user asks about a SPECIFIC organization by name:
  1. If you already have the org's organizationId (from prior search_organizations or summary result) → pass it
     as organization_id param to the report tool. This filters server-side.
  2. If you do NOT have the org ID yet → call search_organizations first, then pass organization_id.
  3. If you already called the report tool WITHOUT organization_id and got results → DO NOT re-call.
     Instead, filter the returned rows by matching organizationName to the user's query.
- organization_id must be a numeric system ID, NOT an org name.

Report scope:
- get_order_statistics() = per-user personal stats ONLY (not full-system).
- Full-system: customer → get_statement_of_use_summary/detail. Driver → driver variants.
- "dashboard/report/summary" without role → ask: customer, driver, or both?
- Date params: YYYY-MM-DD. Use injected [Today's date] for relative calculations.
  No date in current message → omit from_date/to_date (backend defaults to last 3 days).
  Do NOT reuse prior-turn date ranges unless user explicitly asks.
- Do NOT treat org names/codes (e.g. "DHLSC", "7053") as orderId.

Presentation format:
- Summary: Markdown table — Organization, Service Type, Orders, Revenue, Surcharge.
  Include organizationId. Label date range at top. TOTAL row at bottom.
- Detail: table — Organization, Order ID, Service, Revenue, Surcharge, Payment Method, Date. All rows.
- Drill-down → ask "Which organization?" or offer _detail tool.
