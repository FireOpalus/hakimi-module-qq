"""QQ integration with the host's message transports."""

from hakimi.modules.adapters import Sender
from hakimi.modules.onebot_transport import HTTPTransport, WebSocketTransport
from hakimi.modules.qq_social import QQSocialModule


def create_module(service):
    module = QQSocialModule(service.s, service=service)
    service.longnick.module_enabled = lambda: module.inactive_reason is None
    if isinstance(service.sender, Sender):
        service.sender.module_enabled = service.longnick.module_enabled
        if isinstance(service.sender.onebot, (HTTPTransport, WebSocketTransport)):
            service.sender.onebot.module_enabled = service.sender.module_enabled
    return module
