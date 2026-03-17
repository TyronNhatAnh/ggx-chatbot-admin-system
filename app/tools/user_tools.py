"""User tools exposed to the Gemini AI model.

Read-only wrappers around UserServiceClient.
"""

from app.services.user_service_client import get_user_client


def get_withdraw_reasons() -> dict:
    """Get withdrawal reason list (GET /withdraw-reasons)."""
    return get_user_client().get_withdraw_reasons()


def get_tos_contents() -> dict:
    """Get guest terms-of-service contents (GET /guest/tos-contents)."""
    return get_user_client().get_tos_contents()


def get_feature_flags() -> dict:
    """Get global feature flags (GET /feature/flag)."""
    return get_user_client().get_feature_flags()


def get_my_feature_flags() -> dict:
    """Get feature flags for current authenticated user (GET /auth/feature/flag)."""
    return get_user_client().get_my_feature_flags()


def get_user_profile(user_id: int) -> dict:
    """Get user profile by user ID (GET /users?id=). Includes lastSignIn and lastAccessedAt when available."""
    return get_user_client().get_user_profile(user_id)


def get_my_user_profile() -> dict:
    """Get current authenticated user profile (GET /users/me). Includes lastSignIn and lastAccessedAt when available."""
    return get_user_client().get_my_user_profile()


def search_users(
    name: str = "",
    phone_number: str = "",
    email: str = "",
    page_index: int = 1,
    page_size: int = 20,
) -> dict:
    """Search users (GET /users/search). Read-only lookup by name/phone/email with paging."""
    return get_user_client().search_users(
        name=name or None,
        phone_number=phone_number or None,
        email=email or None,
        page_index=page_index,
        page_size=page_size,
    )


def get_user_driver(user_id: int) -> dict:
    """Get driver-related user profile (GET /user-driver?id=)."""
    return get_user_client().get_user_driver(user_id)


def get_branch_by_id(branch_id: int) -> dict:
    """Get branch by ID (GET /branch?id=)."""
    return get_user_client().get_branch_by_id(branch_id)


def search_branches(
    org_name: str = "",
    branch_name: str = "",
    page_index: int = 1,
    page_size: int = 20,
) -> dict:
    """Search branches (GET /branch/search)."""
    return get_user_client().search_branches(
        org_name=org_name or None,
        branch_name=branch_name or None,
        page_index=page_index,
        page_size=page_size,
    )


def get_organization_by_id(organization_id: int) -> dict:
    """Get organization by ID (GET /organization?id=)."""
    return get_user_client().get_organization_by_id(organization_id)


def search_organizations(
    organization_name: str = "",
    division: str = "",
    page_index: int = 1,
    page_size: int = 20,
) -> dict:
    """Search organizations (GET /organization/search)."""
    return get_user_client().search_organizations(
        organization_name=organization_name or None,
        division=division or None,
        page_index=page_index,
        page_size=page_size,
    )


def verify_client_token(token: str) -> dict:
    """Verify client token (GET /auth/client-token/verify?token=...)."""
    return get_user_client().verify_client_token(token)


def list_admin_roles(department_id: int = 0) -> dict:
    """List admin roles (GET /admin/roles). Optional filter: department_id."""
    return get_user_client().list_admin_roles(department_id if department_id > 0 else None)


def list_admin_departments() -> dict:
    """List admin departments (GET /admin/departments)."""
    return get_user_client().list_admin_departments()


def list_admin_menus() -> dict:
    """List admin menus (GET /admin/menus)."""
    return get_user_client().list_admin_menus()


def get_admin_permissions(role_id: int) -> dict:
    """Get role permissions (GET /admin/permissions?roleId=)."""
    return get_user_client().get_admin_permissions(role_id)


def get_accessible_menu_tree(role_id: int) -> dict:
    """Get accessible menu tree by role (GET /admin/permissions/menus?roleId=)."""
    return get_user_client().get_accessible_menu_tree(role_id)


def validate_b2c_org_code(org_code: str) -> dict:
    """Validate B2C organization code (GET /auth/b2c/org-code/validate?orgCode=).
    Use for B2B admin workflows: check if an org code is valid before assignment."""
    return get_user_client().validate_b2c_org_code(org_code)


def verify_biz_registration_number(biz_number: str, user_id: int = 0) -> dict:
    """Verify business registration number (GET /guest/etax/verify_biz_registration_number/{biz_number}).
    Use for compliance audits: validate tax/business registration. Optional user_id context."""
    return get_user_client().verify_biz_registration_number(biz_number, user_id if user_id > 0 else None)
