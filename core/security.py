import ipaddress
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

BLOCKED_HOSTS = frozenset(
    {
        "169.254.169.254",
        "metadata.google.internal",
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "[::1]",
        "::1",
    }
)

BLOCKED_NETS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fc00::/7"),
]


def is_safe_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return False

    hostname = hostname.strip("[]")

    if hostname in BLOCKED_HOSTS:
        logger.warning("Blocked internal hostname: %s", hostname)
        return False

    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            addr = ipaddress.ip_address(socket.gethostbyname(hostname))
        except (OSError, ValueError):
            return True

    for net in BLOCKED_NETS:
        if addr in net:
            logger.warning("Blocked private IP range %s for host %s", net, hostname)
            return False

    return True
