=== DOMAIN: Users & Admin ===

User tools:
- search_users(keyword, organization_id, branch_id) → matching users. keyword searches name/phone/email/ID.
  Results paginated (default page_size=5, max 5 per call). If user asks for more results, re-call with page_index=2, 3, etc.
- get_organization_by_id(id) → org detail.
- search_organizations(keyword, org_division) → org list with id/name. org_division: b2c, b2b, driver, customer.
  Results paginated — use page_index if the target org is not in the first page.
- get_branch_by_id(branch_id) / search_branches(keyword, organization_id) → branch records. Paginated.
- verify_biz_registration_number(biz_number, user_id?) — compliance: validate tax/business registration. user_id optional.
- Admin roles & permissions:
  - list_admin_departments() → all departments. Use first to get department_id before listing roles by dept.
  - list_admin_roles(department_id?) → roles, optionally filtered by department. Omit department_id for all roles.
  - list_admin_menus() → all menu items (full menu tree nodes). Use to identify menu_id values.
  - get_admin_permissions(role_id) → all permissions assigned to a specific role (requires role_id from list_admin_roles).
  - get_accessible_menu_tree(role_id) → the filtered menu tree a role can access (requires role_id). Use when user asks what menus/features a role can see.

  Typical flow for "what can role X do?": list_admin_roles() → find role_id → get_accessible_menu_tree(role_id) + get_admin_permissions(role_id).

Last-login policy:
- To find a user's last login: resolve the userId first using whichever identifier is available:
  - If an order ID is known: get_order_detail(order_id) → extract userId from the owner field.
  - If a name/phone/email is known: search_users(keyword) → pick the matching user → use their userId.
  - If userId is already known: search_users(keyword=userId) → match by exact userId.
- Prefer lastSignIn. Fallback: lastAccessedAt (label "last access"). Neither → unavailable.