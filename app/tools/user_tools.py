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
