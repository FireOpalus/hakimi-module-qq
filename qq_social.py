"""QQ social capability module (KR node, LOW attention)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from ..config import Settings
from ..hot_ring import HotRing
from ..thinking_policy import THINKING_LEVELS, ThinkingScene
from .actions import Action, DailyAction, DailyReceipt
from .base import AttentionLevel, BaseModule, GoalResult, NodeRegion
from .scheduling import ScheduleOptions


def register_qq_platform_hooks() -> None:
    """Register QQ / OneBot policy callbacks into the kernel platform hook registry."""
    from hakimi.modules.platforms.qq.chat_policy import (
        permits_chat_export as qq_permits_chat_export,
    )
    from hakimi.modules.platforms.qq.chat_policy import (
        permits_memory_mirror as qq_permits_memory_mirror,
    )
    from hakimi.modules.platforms.qq.chat_policy import qq_authorize
    from hakimi.platform_hooks import PlatformPolicyHooks, register_platform_hooks

    from .qq_audience import allowed_proactive_message

    hooks = PlatformPolicyHooks(
        authorize=qq_authorize,
        permits_export=qq_permits_chat_export,
        permits_memory_mirror=qq_permits_memory_mirror,
        allowed_proactive=allowed_proactive_message,
    )
    for platform in QQSocialModule.chat_platforms:
        register_platform_hooks(platform, hooks)


class QQSocialModule(BaseModule):
    """Summarizes active QQ transport and group ring activity without leaking private content."""

    module_id: str = "qq_social"
    thinking_scenes = (
        ThinkingScene(
            "fast_chat",
            "群聊与普通好友",
            "auto",
            ("auto", *THINKING_LEVELS),
            output_cap="chat_output_tokens",
        ),
        ThinkingScene(
            "owner_private",
            "Owner 私聊",
            "auto",
            ("auto", *THINKING_LEVELS),
            output_cap="owner_output_tokens",
        ),
        ThinkingScene("owner_digest", "Owner 每日汇报", output_tokens=4096),
        ThinkingScene("owner_companion", "日常陪伴", output_tokens=512),
    )
    chat_platforms = ("onebot", "qq")
    supports_voice = True
    preferred_voice_format = "mp3"
    supports_presence = True
    presence_platforms = ("onebot",)
    admin_panel = "qq"
    display_name = "QQ 社交"
    description = "OneBot 连接、群聊管理与主动私信"
    schedule_options = ScheduleOptions
    recipient_namespaces = ("owner", "onebot")
    node_region: NodeRegion = "KR"
    attention_level: AttentionLevel = "LOW"

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        hot_ring: HotRing | None = None,
        transport: Any = None,
        service: Any = None,
        speak: Any = None,
        digest: Any = None,
        preflight: Any = None,
        proactive=None,
        connected: Callable[[], bool] | None = None,
    ) -> None:
        super().__init__(settings)
        register_qq_platform_hooks()
        self._service = service
        self._hot_ring = hot_ring or getattr(service, "hot", None)
        self._transport = transport or getattr(getattr(service, "sender", None), "onebot", None)
        self.proactive = proactive or getattr(service, "proactive", None)
        self.connected = connected or (
            service.proactive.onebot_connected if service is not None else (lambda: False)
        )

    def chat_connected(self, platform: str) -> bool:
        return bool(self.inactive_reason is None and platform == "onebot" and self.connected())

    def presence_enabled(self) -> bool:
        if self.inactive_reason is not None:
            return False
        longnick = getattr(self._service, "longnick", None) if self._service is not None else None
        if longnick is None:
            return False
        mod_enabled = getattr(longnick, "module_enabled", None)
        if callable(mod_enabled) and not mod_enabled():
            return False
        return bool(getattr(getattr(longnick, "config", None), "enabled", False))

    async def apply_presence(
        self,
        mood_text: str,
        *,
        kind: Literal["life_block", "digest", "patrol", "chat"] = "life_block",
    ) -> dict[str, Any] | None:
        if self.inactive_reason is not None:
            return None
        longnick = getattr(self._service, "longnick", None) if self._service is not None else None
        if longnick is None:
            return None
        if kind == "digest":
            return await longnick.apply_digest(mood_text)
        if kind == "patrol":
            return await longnick.apply_patrol(mood_text)
        if kind == "life_block":
            if hasattr(longnick, "apply_life_block"):
                return await longnick.apply_life_block(mood_text)
            if hasattr(longnick, "apply_patrol"):
                return await longnick.apply_patrol(mood_text)
            return None
        if kind == "chat":
            return await longnick.update(mood_text, automatic=False)
        return None

    def authorize_chat(self, message, settings, *, bot_exempt=False):
        from hakimi.modules.platforms.qq.chat_policy import qq_authorize

        return qq_authorize(message, settings, _bot_exempt=bot_exempt)

    def permits_chat_export(self, message, consumer):
        from hakimi.modules.platforms.qq.chat_policy import permits_chat_export

        return permits_chat_export(message, consumer)

    def permits_memory_mirror(self, message, settings):
        from hakimi.modules.platforms.qq.chat_policy import permits_memory_mirror

        return permits_memory_mirror(message, settings)

    def admin_status(self, request):
        from ..admin_routes import onebot_connection

        return onebot_connection(request, request.app.state.service)

    async def on_switch(self, service):
        if not self.enabled:
            await service.store.cancel_platform_work(self.chat_platforms)
            await service.proactive._expire_and_disable()
        service.proactive.wakeup.set()

    def actions(self) -> tuple[Action, ...]:
        return ()

    async def daily_receipts(self):
        history = await self.proactive.digest_history()
        return [
            DailyReceipt(
                day=row["day"],
                stage=row["stage"],
                started=next(
                    (
                        row[k]
                        for k in ("generation_started_at", "generated_at", "queued_at")
                        if row.get(k) is not None
                    ),
                    None,
                ),
                confirmed=row.get("confirmed_at") if row["stage"] == "confirmed" else None,
            )
            for row in history
        ]

    def schedules(self) -> tuple[DailyAction, ...]:
        return ()

    def normalize_recipient(self, scope):
        if self.inactive_reason is not None or not self.settings:
            return None
        from .qq_audience import _normalize_target_scope

        return _normalize_target_scope(scope, self.settings)

    def permits_recipient(self, scope, config):
        if not scope.startswith("owner:"):
            return True
        if not self.settings or not self.settings.onebot_enabled or not self.settings.owner_qq_id:
            return False
        reg = getattr(self, "_registry", None)
        social_mod = reg.get("social_presence") if reg is not None else None
        if social_mod is not None:
            return bool(social_mod.scheduling(config).owner_delivery_enabled)
        return bool(
            getattr(self.settings, "proactive_dm_enabled", True)
            and getattr(config, "owner_delivery_enabled", True)
        )

    def proactive_groups(self) -> list[str]:
        if not self.settings or not self.settings.onebot_enabled:
            return []
        from .qq_audience import _allowlisted_groups

        return [f"onebot:{gid}" for gid in _allowlisted_groups(self.settings)[:20]]

    async def planning_context(self, service, config, now):
        if not self.settings or not self.settings.onebot_enabled:
            return {"available_groups": [], "owner_dm_available": False}
        from .qq_audience import _allowlisted_groups

        reg = getattr(self, "_registry", None)
        social_mod = reg.get("social_presence") if reg is not None else None
        if social_mod is not None:
            delivery_enabled = bool(social_mod.scheduling(config).owner_delivery_enabled)
        else:
            delivery_enabled = bool(
                getattr(self.settings, "proactive_dm_enabled", True)
                and getattr(config, "owner_delivery_enabled", True)
            )
        return {
            "available_groups": [
                "onebot:" + group for group in _allowlisted_groups(self.settings)[:20]
            ],
            "owner_dm_available": bool(delivery_enabled and self.settings.owner_qq_id),
        }

    def event_rules(self):
        return ()

    def _resolve_connection_label(self) -> str:
        transport = self._transport
        if transport is not None:
            status_fn = getattr(transport, "status", None)
            if callable(status_fn):
                status = status_fn()
                if isinstance(status, dict) and "online" in status:
                    return "在线" if status["online"] else "离线"
            ready = getattr(transport, "ready", None)
            is_set = getattr(ready, "is_set", None)
            if callable(is_set):
                return "在线" if is_set() else "离线"
            return "HTTP就绪"
        settings = self.settings
        if settings is not None:
            if getattr(settings, "onebot_enabled", False) or getattr(settings, "qq_enabled", False):
                return "已启用"
            return "未启用"
        return "待机"

    async def _raw_sensor_summary(self) -> str:
        conn_label = self._resolve_connection_label()
        hot_ring = self._hot_ring
        rings = getattr(hot_ring, "rings", {}) if hot_ring is not None else {}
        active_groups = 0
        group_buffered = 0
        for key, ring in rings.items():
            # Strictly aggregate group metadata only; never inspect or expose private owner chats.
            if isinstance(key, tuple) and len(key) >= 3 and key[2] == "group":
                active_groups += 1
                messages = getattr(ring, "messages", None)
                if messages is not None:
                    group_buffered += len(messages)
        parts = [f"QQ:{conn_label}", f"活跃群:{active_groups}", f"群缓冲:{group_buffered}"]
        if self.proactive_paused:
            parts.append("主动暂停")
        return " ".join(parts)

    async def dispatch_goal(self, ticket: dict[str, Any]) -> GoalResult:
        if not self.enabled:
            return GoalResult(ok=False, module_id=self.module_id, reason="module_disabled")
        action_type = str(ticket.get("action_type", "")).strip()
        if self.proactive_paused and action_type != "status":
            return GoalResult(
                ok=False,
                module_id=self.module_id,
                summary="QQ主动互动已因高专注锁定暂停",
                reason="proactive_paused",
            )
        summary = await self.get_sensor_summary()
        return GoalResult(
            ok=True,
            module_id=self.module_id,
            summary=summary,
            artifacts={"action_type": action_type[:64]},
        )
