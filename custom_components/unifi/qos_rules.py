"""QoS rules of the UniFi Network Policy Engine.

UniFi Network moves the bandwidth limits of traffic rules ("throttle") into QoS
rules when a site is migrated to the Policy Engine. aiounifi has no handler for
them, so they are added here, in the same shape as its other v2 handlers.
"""

from copy import deepcopy
from dataclasses import dataclass
from typing import NotRequired, Self, TypedDict, cast

import aiounifi
from aiounifi.interfaces.api_handlers import APIHandler
from aiounifi.models.api import ApiItem, ApiRequestV2, TypedApiResponse
from aiounifi.models.configuration import Configuration


class TypedQosRule(TypedDict):
    """QoS rule as the controller lists it."""

    _id: str
    name: str
    enabled: bool
    objective: NotRequired[str]
    download_limit_kbps: NotRequired[int]
    upload_limit_kbps: NotRequired[int]


@dataclass
class QosRuleListRequest(ApiRequestV2):
    """Request object for the QoS rule list."""

    @classmethod
    def create(cls) -> Self:
        """Create QoS rule list request."""
        return cls(method="get", path="/qos-rules", data=None)


@dataclass
class QosRuleUpdateRequest(ApiRequestV2):
    """Request object to save a QoS rule; the controller wants the whole rule."""

    @classmethod
    def create(cls, rule: TypedQosRule) -> Self:
        """Create QoS rule update request."""
        return cls(method="put", path=f"/qos-rules/{rule['_id']}", data=rule)


class QosRule(ApiItem):
    """A QoS rule."""

    raw: TypedQosRule

    @property
    def id(self) -> str:
        """ID of the rule."""
        return self.raw["_id"]

    @property
    def name(self) -> str:
        """Name of the rule."""
        return self.raw.get("name", "")

    @property
    def enabled(self) -> bool:
        """Is the rule enabled."""
        return self.raw.get("enabled") is True


class QosRules(APIHandler[QosRule]):
    """QoS rules of the site."""

    obj_id_key = "_id"
    item_cls = QosRule
    api_request = QosRuleListRequest.create()

    async def enable(self, rule: QosRule, enabled: bool) -> TypedApiResponse:
        """Enable or disable a QoS rule."""
        raw = cast(TypedQosRule, deepcopy(dict(rule.raw)))
        raw["enabled"] = enabled
        response = await self.controller.request(QosRuleUpdateRequest.create(raw))
        self.process_raw(response.get("data", []))
        return response


class UnifiController(aiounifi.Controller):
    """aiounifi controller with the handlers aiounifi does not have yet."""

    def __init__(self, config: Configuration) -> None:
        """Set up the controller and the extra handlers."""
        super().__init__(config)
        self.qos_rules = QosRules(self)


def qos_rules(api: aiounifi.Controller) -> QosRules:
    """Return the QoS rules handler of the controller."""
    return cast(UnifiController, api).qos_rules
