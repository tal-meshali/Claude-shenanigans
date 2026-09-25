"""Local mock portals + a shared mock card gateway, for demos and end-to-end tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from http.server import ThreadingHTTPServer
from typing import Callable

from .gateway import MockCardGateway
from .server import MockApp, serve
from .tanzania import MockTanzaniaPortal

# site key -> factory(gateway) -> portal app. Each country registers its mock here.
MOCK_PORTALS: dict[str, Callable[[MockCardGateway], MockApp]] = {
    "tanzania": MockTanzaniaPortal,
}


@dataclass
class MockEnvironment:
    portal: MockApp
    gateway: MockCardGateway
    _servers: list[ThreadingHTTPServer] = field(default_factory=list)

    @property
    def base_url(self) -> str:
        return self.portal.base_url

    def close(self) -> None:
        for server in self._servers:
            server.shutdown()
            server.server_close()

    def __enter__(self) -> "MockEnvironment":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def start_mock(site_key: str, *, port: int = 0, gateway_port: int = 0) -> MockEnvironment:
    """Start the gateway (as http://localhost:...) and the portal (as http://127.0.0.1:...).

    Different host names make the checkout a genuinely different origin, like a
    real payment provider.
    """
    if site_key not in MOCK_PORTALS:
        raise KeyError(f"no mock portal for {site_key!r}; available: {sorted(MOCK_PORTALS)}")
    gateway = MockCardGateway()
    servers = [serve(gateway, port=gateway_port, public_host="localhost")]
    portal = MOCK_PORTALS[site_key](gateway)
    servers.append(serve(portal, port=port))
    return MockEnvironment(portal, gateway, servers)
