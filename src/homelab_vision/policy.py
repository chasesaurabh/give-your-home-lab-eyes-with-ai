"""Default-deny boundaries for remote media and model-proposed actions."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from .contracts import ActionRequest


class PolicyViolation(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class EgressPolicy:
    allow_remote_media: bool = False
    allowed_hosts: frozenset[str] = field(default_factory=frozenset)

    def validate_media_url(self, url: str) -> None:
        if not self.allow_remote_media:
            raise PolicyViolation("remote media is disabled")

        parsed = urlsplit(url)
        if parsed.scheme not in {"https"} or not parsed.hostname:
            raise PolicyViolation("remote media requires an HTTPS URL with a hostname")
        if parsed.username or parsed.password:
            raise PolicyViolation("userinfo is not allowed in remote media URLs")

        hostname = parsed.hostname.rstrip(".").lower()
        if hostname not in {host.rstrip(".").lower() for host in self.allowed_hosts}:
            raise PolicyViolation("remote media host is not allowlisted")

        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            return
        if not address.is_global:
            raise PolicyViolation("non-global IP literals are not allowed")


@dataclass(frozen=True, slots=True)
class ActionPolicy:
    allowed_operations: dict[str, frozenset[str]] = field(default_factory=dict)

    def authorize(self, request: ActionRequest) -> None:
        operations = self.allowed_operations.get(request.tool)
        if operations is None or request.operation not in operations:
            raise PolicyViolation(
                f"operation {request.tool}.{request.operation} is not explicitly allowed"
            )
