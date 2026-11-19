"""DHCP lease counts of the networks of a UniFi site.

aiounifi has no handler for the controller's LAN overview, so it is requested here.
"""

import asyncio
from dataclasses import dataclass
import time
from typing import TYPE_CHECKING

from aiounifi.models.api import ApiRequestV2

from ..entity import get_network_config_vlan

if TYPE_CHECKING:
    from aiounifi import Controller

CACHE_SECONDS = 20
"""Every VLAN sensor asks for the lease counts, so share one request between them."""


@dataclass
class VlanLeaseRequest(ApiRequestV2):
    """Request object for the LAN overview with DHCP statistics."""

    @classmethod
    def create(cls) -> "VlanLeaseRequest":
        """Create LAN overview request."""
        return cls(method="get", path="/lan/enriched-configuration")


@dataclass(frozen=True)
class NetworkLeases:
    """DHCP leases of a network."""

    active: int
    maximum: int


class VlanLeases:
    """Lease counts per VLAN key, refreshed at most every few seconds.

    Keyed by VLAN rather than network ID: the overview carries the network
    configuration, so it does not depend on the networks handler having the
    same IDs (UniFi Network can change every network ID in an update).
    """

    def __init__(self, api: Controller) -> None:
        """Initialize the cache."""
        self._api = api
        self._leases: dict[str, NetworkLeases] = {}
        self._updated = float("-inf")
        self._lock = asyncio.Lock()

    async def async_update(self) -> None:
        """Refresh the lease counts unless they were refreshed a moment ago."""
        # Sensors update at the same time: the others wait for the request in flight
        async with self._lock:
            if time.monotonic() - self._updated < CACHE_SECONDS:
                return

            response = await self._api.request(VlanLeaseRequest.create())
            leases: dict[str, NetworkLeases] = {}
            for item in response.get("data", []):
                statistics = item.get("statistics") or {}
                configuration = item.get("configuration") or {}
                if (
                    configuration.get("enabled") is False
                    or "dhcp_active_leases" not in statistics
                    or (vlan := get_network_config_vlan(configuration)) is None
                ):
                    continue
                leases.setdefault(
                    vlan,
                    NetworkLeases(
                        active=statistics["dhcp_active_leases"],
                        maximum=statistics.get("dhcp_max_leases", 0),
                    ),
                )
            self._leases = leases
            self._updated = time.monotonic()

    def get(self, vlan: str) -> NetworkLeases | None:
        """Return the lease counts of a VLAN, None if the controller has none."""
        return self._leases.get(vlan)
