=== DOMAIN: Reports (Statement of Use / 이용내역ᆞ정산) ===

Four endpoints cover customer and driver Statement-of-Use reports:

## Customer Reports

- get_customer_statement_summary(from_date, to_date, pay, org_id?, businessline_cd?, branch?)
  → GET /admin/report/statement-of-use/summary
  Returns ONE ROW PER ORG/BUSINESS-LINE with aggregated order counts and fares.
  Use for: "customer usage summary", "order count by org", "total fare per org", "monthly statement overview".
  Result: StatementOfUseDataSummary rows + meta.additionalData (totalCustomerFare, totalOrderCount).
  Note: Summary returns ALL matching rows — pagination params are ignored.

- get_customer_statement_detail(from_date, to_date, pay, org_id?, businessline_cd?, page_size?, page_index?)
  → GET /admin/report/statement-of-use/detail
  Returns ONE ROW PER ORDER with full fare breakdown and driver info.
  Use for: "customer usage detail", "order-level billing", "individual order fare breakdown".
  Default: page_size=10, page_index=1.

## Driver Reports

- get_driver_statement_summary(from_date, to_date, driver_type, org_id?, driver_id?, driver_org?, tax_player_cd?, e_tax_status?, is_revised?)
  → GET /admin/report/statement-of-use-driver/summary
  Returns ONE ROW PER DRIVER with aggregated settlement data for the period.
  Use for: "driver settlement summary", "driver payout report", "기사 정산 요약".
  Result: DriverDataSummary rows + meta.additionalData.totalDriverCount.
  Note: Summary returns ALL matching rows — pagination params are ignored.

- get_driver_statement_detail(from_date, to_date, driver_type, org_id?, driver_id?, driver_org?, tax_player_cd?, e_tax_status?, is_revised?, page_size?, page_index?)
  → GET /admin/report/statement-of-use-driver/detail
  Returns ONE ROW PER ORDER PER DRIVER — most granular view with full financial and e-tax fields.
  Use for: "driver settlement detail", "per-order driver payout", "기사 정산 상세".
  Default: page_size=10, page_index=1.

## Required Parameters — Ask if Missing

Customer endpoints (get_customer_statement_summary, get_customer_statement_detail):
- from_date, to_date: YYYY-MM-DD format. Ask the user if not provided.
- pay: Required. Valid values: "Credit" (후불/credit account), "Cash" (현금).
  If the user does not specify, use ["Credit", "Cash"] to include all payment types.

Driver endpoints (get_driver_statement_summary, get_driver_statement_detail):
- from_date, to_date: YYYY-MM-DD format. Ask the user if not provided.
- driver_type: Always pass "normalDriver" — it is the only supported value. Never ask the user about this.

## Pagination Discipline

- Call Detail tools EXACTLY ONCE per user turn — never auto-paginate.
- Pass the exact page_index the user requested (default: page_index=1, page_size=10 unless user specified).
- When the user says "page 2", "next page", etc. → pass that page_index in ONE call, then stop.
- After any Detail call: render the result and show "Page X of N (Y total rows)" — do NOT call again.
- If the user says "show all rows": tell them the API is paginated and ask which pages they want.

## Tool Selection Rules

- Aggregated view (totals per org or driver) → use Summary tool
- Row-level view (per-order breakdown) → use Detail tool
- Start with Summary ONLY for aggregation/overview requests. NOT for "which order had highest X" type questions.
- "Which order had the highest/lowest X?" → go directly to Detail with page_size=50. Do NOT call Summary first.
- Do NOT call both Summary and Detail in the same turn unless explicitly requested.
- If user asks for a single driver's report → pass driver_id filter; if for a single org → pass org_id filter.
- Comparative / ranking questions across orgs ("which org had the highest X?", "top org by fare", etc.):
  Do NOT call search_organizations. Call the summary tool without org_id to get ALL orgs,
  then rank/compare from the returned data[] rows.

## Rendering Rules

- Render all numeric columns as a table with a TOTAL row at the bottom.
- Customer summary TOTAL row: use meta.additionalData.totalCustomerFare and meta.additionalData.totalOrderCount.
- Driver summary TOTAL row: use meta.additionalData.totalDriverCount for distinct driver count.
- For paginated (detail) results: show "Page X of N (total Y rows)" below the table.
  Use meta.numPage for total pages; meta.additionalData.totalCount for total row count.
- If data[] is null or empty, say "No records found for the selected period and filters."

## Nullable Field Format

Fields typed null.Float, null.String, null.Time in the response serialize as JSON objects:
  {"Float64": <value>, "Valid": <bool>}  or  {"String": <value>, "Valid": <bool>}

- When Valid=false → treat as null/absent (omit from table cell or show "—").
- When Valid=true → use the inner value (Float64, String, or Time field).

## Filter Parameter Usage

- e_tax_status: pass as the Korean string directly (e.g. `"발급완료"`). Do NOT call lookup_enum or explain_status first.
  Valid values include: `"발급완료"` (issued), `"미발급"` (not issued), `"발급대기"` (pending).
- tax_player_cd: pass as integer list (e.g. `[1]` for 일반과세자법인). Do NOT look up enum codes first.

## Known Data Inconsistencies

- DriverDataDetail: the incentive field has JSON key "CustomerFare" (capital C) — this is a known
  naming inconsistency in the source service. Label it "Incentive" in user-facing responses.
- residentRegistrationNumber and phoneNumber in all driver report rows are masked (***) in API
  responses. Full values are only available in Excel exports — tell the user if they ask.
