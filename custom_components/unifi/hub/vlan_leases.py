"""DHCP lease counts of the networks of a UniFi site.

aiounifi has no handler for the controller's LAN overview, so it is requested here.
"""

from dataclasses import dataclass
import time
from typing import TYPE_CHECKING

from aiounifi.models.api import ApiRequestV2

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
    """Lease counts per network ID, refreshed at most every few seconds."""

    def __init__(self, api: Controller) -> None:
        """Initialize the cache."""
        self._api = api
        self._leases: dict[str, NetworkLeases] = {}
        self._updated = float("-inf")

    async def async_update(self) -> None:
        """Refresh the lease counts unless they were refreshed a moment ago."""
        if time.monotonic() - self._updated < CACHE_SECONDS:
            return
        self._updated = time.monotonic()

        response = await self._api.request(VlanLeaseRequest.create())
        leases: dict[str, NetworkLeases] = {}
        for item in response.get("data", []):
            statistics = item.get("statistics", {})
            network_id = item.get("configuration", {}).get("_id")
            if network_id is None or "dhcp_active_leases" not in statistics:
                continue
            leases[network_id] = NetworkLeases(
                active=statistics["dhcp_active_leases"],
                maximum=statistics.get("dhcp_max_leases", 0),
            )
        self._leases = leases

    def get(self, network_id: str) -> NetworkLeases | None:
        """Return the lease counts of a network, None if the controller has none."""
        return self._leases.get(network_id)
