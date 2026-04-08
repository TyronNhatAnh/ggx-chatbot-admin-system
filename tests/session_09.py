"""Session 09 — Admin Roles & Permissions."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _runner import run_session

QUESTIONS = [
    'List all admin roles in the system',
    'What permissions does role ID 3 have?',
    'List all admin departments',
    'What does the menu tree look like for role ID 5?',
    'List all available admin menus',
]

if __name__ == "__main__":
    run_session(9, "Admin Roles & Permissions (list_admin_roles, list_admin_departments, list_admin_menus, get_admin_permissions, get_accessible_menu_tree)", QUESTIONS)
