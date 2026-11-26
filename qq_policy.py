"""Compatibility shim exporting QQPolicy and DESKTOP_CONTEXT_HINT via SocialProactivePolicy."""

from __future__ import annotations

from ..social_policy import (
    DESKTOP_CONTEXT_HINT,
    SocialProactivePolicy,
    _desktop_latest_activity,
)


class QQPolicy(SocialProactivePolicy):
    def __init__(self, service):
        super().__init__(
            service,
            "onebot",
            lambda: getattr(service.s, "onebot_self_id", ""),
        )


__all__ = ["DESKTOP_CONTEXT_HINT", "QQPolicy", "_desktop_latest_activity"]
