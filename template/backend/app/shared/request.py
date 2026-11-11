import ipaddress

from fastapi import Request
from fastapi.routing import iter_route_contexts
from starlette.requests import HTTPConnection
from starlette.routing import Match

UNKNOWN_CLIENT_IP_ADDRESS = "unknown"
FORWARDED_CLIENT_ADDRESS_HEADER = "x-real-ip"


def find_peer_address(connection: HTTPConnection) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(connection.client.host if connection.client is not None else "")
    except ValueError:
        return None


def is_trusted_proxy(
    peer_address: ipaddress.IPv4Address | ipaddress.IPv6Address,
    *,
    trusted_proxy_networks: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...],
) -> bool:
    return any(peer_address in trusted_proxy_network for trusted_proxy_network in trusted_proxy_networks)


def read_client_ip_address(
    connection: HTTPConnection,
    *,
    trusted_proxy_networks: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...],
) -> str:
    peer_address = find_peer_address(connection)
    if peer_address is None:
        return UNKNOWN_CLIENT_IP_ADDRESS
    forwarded_address = connection.headers.get(FORWARDED_CLIENT_ADDRESS_HEADER)
    if forwarded_address is None or not is_trusted_proxy(peer_address, trusted_proxy_networks=trusted_proxy_networks):
        return str(peer_address)
    try:
        return str(ipaddress.ip_address(forwarded_address.strip()))
    except ValueError:
        return str(peer_address)


def find_untrusted_proxy_address(
    connection: HTTPConnection,
    *,
    trusted_proxy_networks: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...],
) -> str | None:
    peer_address = find_peer_address(connection)
    if (
        peer_address is None
        or not peer_address.is_private
        or FORWARDED_CLIENT_ADDRESS_HEADER not in connection.headers
        or is_trusted_proxy(peer_address, trusted_proxy_networks=trusted_proxy_networks)
    ):
        return None
    return str(peer_address)


def read_route_template(request: Request) -> str:
    route = request.scope.get("route")
    if route is not None:
        return route.path
    for route_context in iter_route_contexts(request.app.router.routes) if "app" in request.scope else ():
        if route_context.path is not None and route_context.matches(request.scope)[0] == Match.FULL:
            return route_context.path
    return f"{request.method} (unrouted)"
