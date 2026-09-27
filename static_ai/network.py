"""Public-web GET client: DNS pinning, redirect validation, bounded downloads."""

import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import httpx


async def public_address(url: str):
    u = urlsplit(url)
    if u.scheme not in ("http", "https") or not u.hostname or u.username or u.password:
        raise ValueError("Only public HTTP(S) URLs without credentials are allowed")
    if u.port not in (None, 80, 443):
        raise ValueError("Web access is restricted to ports 80 and 443")
    if u.hostname.lower() in ("localhost", "metadata.google.internal"):
        raise ValueError("Private network URLs are blocked")
    records = await asyncio.get_running_loop().getaddrinfo(
        u.hostname, u.port or (443 if u.scheme == "https" else 80), type=socket.SOCK_STREAM
    )
    ips = list(dict.fromkeys(r[4][0] for r in records))
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise ValueError("Private, reserved, and link-local addresses are blocked")
    return u, ips[0]


async def fetch_public(url: str, limit=2_000_000):
    async with httpx.AsyncClient(timeout=25, follow_redirects=False, trust_env=False) as client:
        for _ in range(6):
            parts, address = await public_address(url)
            # Connect to the validated IP; retain the original Host and TLS server name.
            pinned = httpx.URL(url).copy_with(host=address)
            headers = {
                "Host": parts.netloc,
                "User-Agent": "Static/0.1 (+local personal research)",
                "Accept-Encoding": "identity",
            }
            async with client.stream(
                "GET", pinned, headers=headers, extensions={"sni_hostname": parts.hostname}
            ) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    if "location" not in response.headers:
                        raise ValueError("Redirect has no destination")
                    url = urljoin(url, response.headers["location"])
                    continue
                response.raise_for_status()
                if int(response.headers.get("content-length", 0)) > limit:
                    raise ValueError("Download exceeds the size limit")
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > limit:
                        raise ValueError("Download exceeds the size limit")
                return (
                    url,
                    bytes(data),
                    response.headers.get("content-type", "application/octet-stream"),
                )
        raise ValueError("Too many redirects")
