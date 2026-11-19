"""Sharing policy for the QQ channel."""

from hakimi.life_rules import Reaction, Rule
from hakimi.world_state import private_event_for_owner


def milestone_sharing(settings) -> Rule:
    from hakimi.modules.qq_audience import _allowlisted_groups

    def match(ev):
        if ev.importance != "high" or ev.event_type == "bili_mc_inspiration":
            return None
        if ev.event_type == "bili_video_watched" and not settings.owner_qq_id:
            return None
        if settings.owner_qq_id:
            recipient = "owner:" + settings.owner_qq_id
        else:
            groups = _allowlisted_groups(settings)
            recipient = "onebot:" + groups[0] if groups else ""
        if ev.payload.get("private_first") and not private_event_for_owner(
            ev.payload, recipient, settings
        ):
            return None
        if not recipient:
            return None
        return Reaction(
            "qq.speak",
            "刚遇到一件挺有意思的新动态，看气氛顺嘴跟群友或 BOISER 唠两句",
            recipient,
            delay=90,
            legacy_module=ev.source_module,
            legacy_verb=ev.source_module + "_milestone_share",
        )

    return Rule("social.milestone", match)
