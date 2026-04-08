"""User tools exposed to the Gemini AI model.

Read-only wrappers around UserServiceClient.
"""

from app.services.user_service_client import get_user_client

from app.limits import MAX_LIST_RESULTS


def search_users(
    keyword: str = "",
    organization_id: int = 0,
    branch_id: int = 0,
    page_index: int = 1,
    page_size: int = MAX_LIST_RESULTS,
) -> dict:
    """Search users (GET /users/search). Searches by keyword (matches name/phone/email), with optional org/branch filter."""
    return get_user_client().search_users(
        keyword=keyword or None,
        organization_id=organization_id if organization_id > 0 else None,
        branch_id=branch_id if branch_id > 0 else None,
        page_index=page_index,
        page_size=page_size,
    )


def search_branches(
    keyword: str = "",
    organization_id: int = 0,
    page_index: int = 1,
    page_size: int = MAX_LIST_RESULTS,
) -> dict:
    """Search branches (GET /branch/search). Searches by keyword (branch name), with optional organization_id filter."""
    return get_user_client().search_branches(
        keyword=keyword or None,
        organization_id=organization_id if organization_id > 0 else None,
        page_index=page_index,
        page_size=page_size,
    )


def search_organizations(
    keyword: str = "",
    org_division: str = "",
    page_index: int = 1,
    page_size: int = MAX_LIST_RESULTS,
) -> dict:
    """Search organizations (GET /organization/search). Searches by keyword (org name). Optional org_division filter: b2c, b2b, driver, customer."""
    return get_user_client().search_organizations(
        keyword=keyword or None,
        org_division=org_division or None,
        page_index=page_index,
        page_size=page_size,
    )


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


def verify_biz_registration_number(biz_number: str, user_id: int = 0) -> dict:
    """Verify business registration number (GET /guest/etax/verify_biz_registration_number/{biz_number}).
    Use for compliance audits: validate tax/business registration. Optional user_id context."""
    return get_user_client().verify_biz_registration_number(biz_number, user_id if user_id > 0 else None)
