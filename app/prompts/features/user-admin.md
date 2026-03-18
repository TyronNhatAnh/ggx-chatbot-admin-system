=== DOMAIN: Users & Admin ===

User tools:
- get_user_profile(user_id) / get_my_user_profile() → userId, name, phone, email, lastSignIn, lastAccessedAt.
- search_users(keyword, organization_id, branch_id) → matching users. keyword searches name/phone/email.
  Results paginated (default page_size=20). If user asks for more results, re-call with page_index=2, 3, etc.
- get_user_driver(user_id) → driver-linked profile.
- get_organization_by_id(id) → org detail.
- search_organizations(keyword, org_division) → org list with id/name. org_division: b2c, b2b, driver, customer.
  Results paginated — use page_index if the target org is not in the first page.
- get_branch_by_id(branch_id) / search_branches(keyword, organization_id) → branch records. Paginated.
- get_withdraw_reasons() / get_tos_contents() → reference data.
- Feature flags: get_feature_flags() system-wide; get_my_feature_flags() ONLY for "my flags" / permission audits.
- B2B: validate_b2c_org_code(org_code), verify_biz_registration_number(biz_number, user_id?) — user_id optional.
- verify_client_token(token) — security audits only.
- Admin: list_admin_roles(department_id?), list_admin_departments(), list_admin_menus(),
  get_admin_permissions(role_id), get_accessible_menu_tree(role_id).

Last-login policy:
- get_order_detail → extract userId → get_user_profile(userId).
- Prefer lastSignIn. Fallback: lastAccessedAt (label "last access"). Neither → unavailable.
