"""Networks (VLANs) of a UniFi site.

Written in the style of aiounifi (model, request and handler) so that it can be
moved into the library, which has no handler for ``rest/networkconf`` yet.
"""

from dataclasses import dataclass
from typing import NotRequired, Self, TypedDict

from aiounifi.interfaces.api_handlers import APIHandler
from aiounifi.models.api import ApiItem, ApiRequest
from aiounifi.models.message import MessageKey

from ..const import VLAN_NATIVE

LAN_PURPOSES = ("corporate", "guest", "vlan-only")
"""Purposes of networks that clients can connect to (not WAN or VPN)."""


class TypedNetwork(TypedDict):
    """Network type definition, only the fields that are used."""

    _id: str
    name: str
    purpose: str
    enabled: NotRequired[bool]
    vlan: NotRequired[int | str]
    vlan_enabled: NotRequired[bool]


@dataclass
class NetworkListRequest(ApiRequest):
    """Request object for network list."""

    @classmethod
    def create(cls) -> Self:
        """Create network list request."""
        return cls(method="get", path="/rest/networkconf")


class Network(ApiItem):
    """Represent a network configuration."""

    raw: TypedNetwork

    @property
    def id(self) -> str:
        """ID of the network."""
        return self.raw["_id"]

    @property
    def name(self) -> str:
        """Name of the network."""
        return self.raw["name"]

    @property
    def purpose(self) -> str:
        """Purpose of the network, for example corporate, guest, wan or vpn-client."""
        return self.raw["purpose"]

    @property
    def enabled(self) -> bool:
        """Is the network enabled."""
        return self.raw.get("enabled", True)

    @property
    def vlan(self) -> int | None:
        """VLAN ID of the network, None if the network is not tagged."""
        if not self.raw.get("vlan_enabled"):
            return None
        try:
            return int(self.raw["vlan"])
        except KeyError, ValueError:
            return None

    @property
    def vlan_key(self) -> str | None:
        """Key clients on this network have: the VLAN ID, or native if untagged.

        None for networks clients cannot connect to, such as WAN and VPN.
        """
        if self.raw.get("vlan_enabled"):
            return None if self.vlan is None else str(self.vlan)
        if self.purpose in LAN_PURPOSES:
            return VLAN_NATIVE
        return None


class Networks(APIHandler[Network]):
    """Represent network configurations."""

    obj_id_key = "_id"
    item_cls = Network
    process_messages = (MessageKey.NETWORK_CONF_UPDATED,)
    api_request = NetworkListRequest.create()

    def get_by_vlan_key(self, vlan_key: str) -> Network | None:
        """Return the enabled network with this VLAN key."""
        return next(
            (
                network
                for network in self.values()
                if network.enabled and network.vlan_key == vlan_key
            ),
            None,
        )
