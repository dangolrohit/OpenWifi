"""Role-based access control (RBAC) definitions."""
from enum import Enum

class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    VIEWER = "viewer"

ROLE_PERMISSIONS = {
    UserRole.SUPER_ADMIN: {
        "read:all", "write:all", "admin:users", "network:configure", "network:policy", "system:restart"
    },
    UserRole.ADMIN: {
        "read:all", "write:devices", "write:guests", "network:policy"
    },
    UserRole.VIEWER: {
        "read:all"
    }
}

def has_permission(role: str, permission: str) -> bool:
    """Check if a given role possesses a requested permission."""
    try:
        user_role = UserRole(role)
        perms = ROLE_PERMISSIONS.get(user_role, set())
        return "read:all" in perms if permission.startswith("read:") else permission in perms or "write:all" in perms
    except ValueError:
        return False

