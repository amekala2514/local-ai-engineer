"""URL validation for the fetch_url endpoint.

This module rejects URLs that would be unsafe to fetch:
- Non-HTTP(S) schemes (file, ftp, gopher, javascript, data, ...)
- URLs pointing to localhost or private network ranges (SSRF defense)
- URLs that resolve to private IPs (DNS rebinding defense)

The validator is intentionally strict. False positives (rejecting a
URL we could have safely fetched) are acceptable; false negatives
(allowing a URL we shouldn't fetch) are not.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse


ALLOWED_SCHEMES = frozenset(["http", "https"])

# Hostnames we explicitly reject (catches common metadata/internal aliases)
DENY_HOSTNAMES = frozenset([
    "localhost",
    "metadata.google.internal",
    "metadata.aws",
    "instance-data",
])

# Maximum URL length
MAX_URL_LENGTH = 2048


@dataclass
class ValidationResult:
    valid: bool
    reason: str | None = None
    resolved_ip: str | None = None


def _is_private_ip(ip_str: str) -> bool:
    """Return True if the IP is private, loopback, link-local, multicast,
    reserved, or unspecified."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_url(url: str, resolve_dns: bool = True) -> ValidationResult:
    """Validate a URL for safe fetching.

    Args:
        url: the URL string to validate
        resolve_dns: if True, resolve the hostname and reject private IPs.
            Set to False only when DNS resolution is impractical (offline
            tests). The fetcher should always pass resolve_dns=True.

    Returns:
        ValidationResult with valid=True if safe to fetch, or valid=False
        plus a reason if rejected.
    """
    if not url or not isinstance(url, str):
        return ValidationResult(False, "URL is empty or not a string")

    if len(url) > MAX_URL_LENGTH:
        return ValidationResult(False, f"URL exceeds max length ({MAX_URL_LENGTH})")

    try:
        parsed = urlparse(url)
    except Exception as e:
        return ValidationResult(False, f"URL could not be parsed: {e}")

    if parsed.scheme not in ALLOWED_SCHEMES:
        return ValidationResult(
            False,
            f"Scheme '{parsed.scheme}' not allowed. Use http or https.",
        )

    if not parsed.hostname:
        return ValidationResult(False, "URL has no hostname")

    hostname = parsed.hostname.lower()

    # Reject explicit deny-listed hostnames
    if hostname in DENY_HOSTNAMES:
        return ValidationResult(False, f"Hostname '{hostname}' is not allowed")

    # If the hostname is an IP literal, check it directly
    try:
        ip = ipaddress.ip_address(hostname)
        if _is_private_ip(str(ip)):
            return ValidationResult(
                False,
                f"IP {ip} is in a private/reserved range",
            )
        # Public IP literal is allowed
        return ValidationResult(True, resolved_ip=str(ip))
    except ValueError:
        # Not an IP literal, continue to DNS resolution
        pass

    if not resolve_dns:
        return ValidationResult(True)

    # Resolve and check the IP. We reject if any A/AAAA record is private,
    # to defend against DNS rebinding (where the same hostname resolves to
    # public IPs for the validator but private IPs at fetch time, or has
    # both public and private records).
    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except (socket.gaierror, socket.herror) as e:
        return ValidationResult(False, f"DNS resolution failed: {e}")

    if not addr_info:
        return ValidationResult(False, "DNS resolution returned no addresses")

    resolved_ips = []
    for entry in addr_info:
        # entry = (family, type, proto, canonname, sockaddr)
        sockaddr = entry[4]
        ip_str = sockaddr[0]
        resolved_ips.append(ip_str)
        if _is_private_ip(ip_str):
            return ValidationResult(
                False,
                f"Hostname '{hostname}' resolves to private IP {ip_str}",
            )

    return ValidationResult(True, resolved_ip=resolved_ips[0])
