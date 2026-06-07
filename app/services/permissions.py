from app.models.user import User, UserRole


def is_admin(user: User) -> bool:
    return user.role == UserRole.ADMIN


def is_admin_assistant(user: User) -> bool:
    return user.role == UserRole.ADMIN_ASSISTANT


def can_create_users(user: User) -> bool:
    return is_admin(user) or (is_admin_assistant(user) and bool(user.can_create_users))


def can_manage_houses(user: User) -> bool:
    return (
        is_admin(user)
        or (user.role == UserRole.DISPATCHER and bool(user.can_manage_houses))
        or (is_admin_assistant(user) and bool(user.can_manage_houses))
    )


def can_ban_residents(user: User) -> bool:
    return (
        is_admin(user)
        or (user.role == UserRole.DISPATCHER and bool(user.can_ban_residents))
        or (is_admin_assistant(user) and bool(user.can_ban_residents))
    )


def can_manage_executor_schedules(user: User) -> bool:
    return is_admin(user) or (is_admin_assistant(user) and bool(user.can_manage_executor_schedules))


def can_manage_service_settings(user: User) -> bool:
    return is_admin(user) or (is_admin_assistant(user) and bool(user.can_manage_service_settings))


def can_manage_remarks(user: User) -> bool:
    return is_admin(user) or (is_admin_assistant(user) and bool(user.can_manage_remarks))


def can_manage_house_info(user: User) -> bool:
    return (
        is_admin(user)
        or (user.role == UserRole.DISPATCHER and bool(user.can_manage_houses))
        or (is_admin_assistant(user) and bool(user.can_manage_house_info))
    )


def can_manage_announcements(user: User) -> bool:
    return (
        is_admin(user)
        or user.role == UserRole.DISPATCHER
        or (is_admin_assistant(user) and bool(user.can_manage_announcements))
    )


def is_staff_like(user: User) -> bool:
    return user.role in [
        UserRole.ADMIN,
        UserRole.ADMIN_ASSISTANT,
        UserRole.DISPATCHER,
        UserRole.AUDITOR,
    ]
