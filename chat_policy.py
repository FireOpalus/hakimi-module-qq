"""Admission for authenticated OneBot and official QQ messages."""

import re

from hakimi.security import bot_event_authorized, owner


def qq_authorize(message, settings, *, _bot_exempt=False):
    if message.platform == "onebot":
        enabled, bot, users, groups = (
            settings.onebot_enabled,
            settings.onebot_self_id,
            settings.onebot_allowed_users,
            settings.onebot_allowed_groups,
        )
    elif message.platform == "qq":
        enabled, bot, users, groups = (
            settings.qq_enabled,
            settings.qq_app_id,
            settings.qq_allowed_users,
            settings.qq_allowed_groups,
        )
    else:
        return False
    if not enabled or message.bot_id != bot or message.user_id == bot:
        return False
    if message.platform == "onebot":
        if not re.fullmatch(r"[0-9]{1,20}", message.user_id):
            return False
        real_owner = bool(settings.owner_qq_id and message.user_id == settings.owner_qq_id)
        if not real_owner and (
            (
                message.user_id in settings.bot_qq_ids
                and not _bot_exempt
                and not bot_event_authorized(message, settings)
            )
            or message.user_id in getattr(settings, "muted_user_ids", set())
        ):
            return False
        if message.kind == "private":
            return message.conversation_id == message.user_id and (
                real_owner
                or (
                    getattr(settings, "onebot_private_mode", "owner_only") == "owner_and_allowlist"
                    and message.user_id in users
                )
            )
    if message.kind == "private":
        trusted_user = owner(message, settings) or message.user_id in users
        return trusted_user and message.conversation_id == message.user_id
    # Group admission is controlled by the group list, never by the private-user list.
    # at_only/smart_reply still decide whether this admitted group message invites a reply.
    policy = settings.group_policies.get(f"{message.platform}:{message.conversation_id}", "at_only")
    return (
        message.conversation_id in groups
        and policy != "muted"
        and (message.invites_group_review or policy == "smart_reply")
    )


def permits_chat_export(message, consumer):
    return message.platform in {"onebot", "qq"} and consumer in {"bilibili_surf", "patrol_diary"}


def permits_memory_mirror(message, settings):
    if message.platform == "onebot":
        return (
            settings.onebot_enabled
            and message.bot_id == settings.onebot_self_id
            and message.conversation_id in settings.onebot_allowed_groups
        )
    return (
        message.platform == "qq"
        and settings.qq_enabled
        and message.bot_id == settings.qq_app_id
        and message.conversation_id in settings.qq_allowed_groups
    )
