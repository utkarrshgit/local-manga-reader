"""
providers/security.py - HTTPS-only request validation and connection-level SSRF protection.

Architecture & Security Design:
------------------------------
1. Limitations of requests / urllib3 for Connection-Level SSRF Protection:
   - In urllib3 and requests, connections are managed by PoolManager, which creates
     HTTPConnectionPool and HTTPSConnectionPool instances keyed by (scheme, host, port).
   - Intercepting the actual socket connection to verify the connected IP requires
     subclassing HTTPConnectionPool / HTTPSConnectionPool and overriding the private
     internal `_new_conn()` method.
   - In urllib3 v2.x, internal connection creation, ALPN, and pool management mechanisms
     were significantly refactored. Hooking custom connection classes into `requests`
     relies on private attributes (such as `requests.adapters.HTTPAdapter.init_poolmanager`
     and `self.poolmanager.pool_classes_by_scheme`), which are undocumented and fragile
     across library versions.
   - Furthermore, adding `requests` introduces multiple third-party dependencies
     (requests, urllib3, certifi, idna, charset-normalizer) into a project designed to be
     zero-dependency.

2. Safer Standard-Library Architecture (http.client.HTTPSConnection):
   - Standard library `http.client.HTTPSConnection` provides a clean, stable, documented
     inheritance interface via `connect()`.
   - By subclassing `http.client.HTTPSConnection` (`SSRFProtectedHTTPSConnection`), we
     control the entire socket lifecycle:
     a. Hostname is resolved via `socket.getaddrinfo`.
     b. Every candidate IP address is validated against strict SSRF rules (rejecting
        loopback, private, link-local, carrier-grade NAT, multicast, reserved,
        documentation, and IPv4-mapped IPv6 non-global addresses).
     c. The raw socket connects directly to the pre-approved IP.
     d. Immediately after connection, `sock.getpeername()` is re-checked on the active
        socket to ensure the connected endpoint is genuinely approved.
     e. The already-connected socket is passed to `ssl_context.wrap_socket`, with
        `server_hostname=self.host`.
     f. TLS SNI (Server Name Indication) extension and certificate verification
        (with check_hostname=True and verify_mode=ssl.CERT_REQUIRED) are strictly
        preserved against the intended hostname.
     g. No secondary DNS lookup occurs between validation and TLS handshake, eliminating
        Time-of-Check to Time-of-Use (TOCTOU) DNS rebinding attacks entirely.
     h. All of this is accomplished with zero external dependencies.

3. URL & Redirect Validation:
   - HTTPS-only scheme enforcement (HTTP, file, ftp, gopher, javascript are rejected).
   - Strict hostname boundary validation (wildcards require explicit pattern matching;
     partial domain suffixes such as `badexample.com` or `example.com.evil.com` are rejected).
   - URLs with embedded credentials (e.g. `user:pass@host`) are rejected.
   - Automatic redirects are disabled. Every redirect destination is validated against
     the HTTPS scheme and the provider's allowed hosts list before following.
   - Strict hop limits and loop detection prevent infinite redirect chains.
   - Arbitrary browser-supplied URLs are never allowed to become outbound proxy targets.
"""

from __future__ import annotations

import errno
import http.client
import ipaddress
import socket
import ssl
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union
from urllib.parse import urljoin, urlsplit, SplitResult


# ---------------------------------------------------------------------------
# Blocked Network Definitions (RFC Standards)
# ---------------------------------------------------------------------------

BLOCKED_IPV4_NETWORKS = (
    ipaddress.ip_network("0.0.0.0/8"),         # "This host on this network" (RFC 1122)
    ipaddress.ip_network("10.0.0.0/8"),        # Private-Use (RFC 1918)
    ipaddress.ip_network("100.64.0.0/10"),     # Shared Address Space / Carrier-Grade NAT (RFC 6598)
    ipaddress.ip_network("127.0.0.0/8"),       # Loopback (RFC 1122)
    ipaddress.ip_network("169.254.0.0/16"),    # Link-Local (RFC 3927) - AWS/GCP/Azure metadata services
    ipaddress.ip_network("172.16.0.0/12"),     # Private-Use (RFC 1918)
    ipaddress.ip_network("192.0.0.0/24"),      # IETF Protocol Assignments (RFC 6890)
    ipaddress.ip_network("192.0.2.0/24"),      # Documentation TEST-NET-1 (RFC 5737)
    ipaddress.ip_network("192.88.99.0/24"),    # 6to4 Relay Anycast (RFC 7526)
    ipaddress.ip_network("192.168.0.0/16"),    # Private-Use (RFC 1918)
    ipaddress.ip_network("198.18.0.0/15"),     # Benchmarking (RFC 2544)
    ipaddress.ip_network("198.51.100.0/24"),   # Documentation TEST-NET-2 (RFC 5737)
    ipaddress.ip_network("203.0.113.0/24"),    # Documentation TEST-NET-3 (RFC 5737)
    ipaddress.ip_network("224.0.0.0/4"),       # Multicast (RFC 5771)
    ipaddress.ip_network("240.0.0.0/4"),       # Reserved for future use (RFC 1112)
    ipaddress.ip_network("255.255.255.255/32"),# Limited Broadcast (RFC 919)
)

BLOCKED_IPV6_NETWORKS = (
    ipaddress.ip_network("::1/128"),           # Loopback (RFC 4291)
    ipaddress.ip_network("::/128"),            # Unspecified (RFC 4291)
    ipaddress.ip_network("::/96"),             # Deprecated IPv4-Compatible IPv6 (RFC 4291)
    ipaddress.ip_network("::ffff:0:0:0/96"),   # SIIT IPv4-Translated (RFC 2765)
    ipaddress.ip_network("64:ff9b::/96"),      # IPv4/IPv6 translation (RFC 6052)
    ipaddress.ip_network("64:ff9b:1::/48"),    # Local IPv4/IPv6 translation (RFC 8215)
    ipaddress.ip_network("100::/64"),          # Discard-Only (RFC 6666)
    ipaddress.ip_network("2001::/23"),         # IETF Protocol Assignments
    ipaddress.ip_network("2001:db8::/32"),     # Documentation (RFC 3849)
    ipaddress.ip_network("2002::/16"),         # 6to4 (RFC 3056, deprecated RFC 7526)
    ipaddress.ip_network("fc00::/7"),          # Unique Local Address ULA (RFC 4193)
    ipaddress.ip_network("fe80::/10"),         # Link-Local Unicast (RFC 4291)
    ipaddress.ip_network("ff00::/8"),          # Multicast (RFC 4291)
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SSRFSecurityError(Exception):
    """Base exception for all SSRF and outbound security violations."""
    pass


class InvalidSchemeError(SSRFSecurityError):
    """Raised when an outbound URL does not use the HTTPS scheme."""
    pass


class DisallowedHostError(SSRFSecurityError):
    """Raised when an outbound URL target host is not in the provider allowlist."""
    pass


class BlockedIPError(SSRFSecurityError):
    """Raised when a resolved IP address belongs to a private, loopback, or reserved range."""
    pass


class RedirectSecurityError(SSRFSecurityError):
    """Raised when a redirect target violates security policies or forms a loop."""
    pass


class MaxRedirectsExceededError(RedirectSecurityError):
    """Raised when the number of redirects exceeds the configured hop limit."""
    pass


# ---------------------------------------------------------------------------
# IP Address Validation
# ---------------------------------------------------------------------------

def is_safe_ip(
    ip: Union[str, int, ipaddress.IPv4Address, ipaddress.IPv6Address],
    allow_localhost: bool = False,
) -> bool:
    """
    Validate that an IP address is a safe, publicly routable global address.

    Rejects:
    - Loopback (127.0.0.0/8, ::1)
    - Private networks (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, fc00::/7)
    - Link-local (169.254.0.0/16, fe80::/10) - cloud metadata services
    - Carrier-grade NAT (100.64.0.0/10)
    - Multicast (224.0.0.0/4, ff00::/8)
    - Reserved / unspecified (0.0.0.0/8, 240.0.0.0/4, ::)
    - IPv4-mapped IPv6 (::ffff:x.x.x.x) mapped to any disallowed IPv4
    - Deprecated IPv4-compatible IPv6 (::/96)
    - SIIT IPv4-translated (::ffff:0:0:0/96)
    - 6to4 (2002::/16) mapped to any disallowed IPv4
    - Documentation subnets (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24, 2001:db8::/32)
    - Any non-global address (ip.is_global is False)

    Args:
        ip: String IP address, integer, or ipaddress object.
        allow_localhost: If True, loopback addresses are permitted (controlled test only).
    """
    if isinstance(ip, str):
        try:
            parsed_ip = ipaddress.ip_address(ip.strip())
        except (ValueError, AttributeError):
            return False
    elif isinstance(ip, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
        parsed_ip = ip
    elif isinstance(ip, int):
        try:
            parsed_ip = ipaddress.ip_address(ip)
        except (ValueError, OverflowError):
            return False
    else:
        return False

    # Handle IPv6 unwrapping for mapped or transition addresses
    if isinstance(parsed_ip, ipaddress.IPv6Address):
        # IPv4-mapped IPv6 address (::ffff:x.x.x.x)
        if parsed_ip.ipv4_mapped is not None:
            parsed_ip = parsed_ip.ipv4_mapped
        # 6to4 address embedding IPv4
        elif parsed_ip.sixtofour is not None:
            parsed_ip = parsed_ip.sixtofour

    # Controlled local test override
    if allow_localhost and parsed_ip.is_loopback:
        return True

    # Standard property checks
    if (
        parsed_ip.is_loopback
        or parsed_ip.is_private
        or parsed_ip.is_link_local
        or parsed_ip.is_multicast
        or parsed_ip.is_reserved
        or parsed_ip.is_unspecified
        or not parsed_ip.is_global
    ):
        return False

    # Explicit network blocklist checks
    if isinstance(parsed_ip, ipaddress.IPv4Address):
        for net in BLOCKED_IPV4_NETWORKS:
            if parsed_ip in net:
                return False
    elif isinstance(parsed_ip, ipaddress.IPv6Address):
        for net in BLOCKED_IPV6_NETWORKS:
            if parsed_ip in net:
                return False

    return True


# ---------------------------------------------------------------------------
# Security Policy & Hostname Matching
# ---------------------------------------------------------------------------

class SecurityPolicy:
    """
    Outbound request security policy enforcing host allowlisting, HTTPS,
    and connection-level SSRF defenses.
    """

    def __init__(
        self,
        allowed_hosts: Iterable[str] = (),
        allow_localhost: bool = False,
        allowed_ports: Optional[Iterable[int]] = None,
        max_redirects: int = 5,
        max_response_bytes: int = 25 * 1024 * 1024,  # 25 MB
    ) -> None:
        self.allowed_hosts: Set[str] = {h.strip().lower() for h in allowed_hosts if h and h.strip()}
        self.allow_localhost: bool = bool(allow_localhost)
        self.allowed_ports: Set[int] = set(allowed_ports) if allowed_ports is not None else {443}
        self.max_redirects: int = max(0, int(max_redirects))
        self.max_response_bytes: int = max(1024, int(max_response_bytes))

    def match_hostname(self, hostname: str) -> bool:
        """
        Check if hostname matches the allowed hosts with exact boundaries.

        Rules:
        - If allow_localhost is True and host is 'localhost' or '127.0.0.1': matches.
        - Exact match: 'example.com' matches 'example.com'.
        - Wildcard match: '*.example.com' matches 'sub.example.com' and 'a.b.example.com'.
        - Subdomain boundary: 'badexample.com' does NOT match 'example.com'.
        - Suffix boundary: 'example.com.evil.com' does NOT match 'example.com'.
        """
        host = hostname.strip().lower().rstrip(".")
        if not host:
            return False

        if self.allow_localhost and host in {"localhost", "127.0.0.1", "::1"}:
            return True

        for pattern in self.allowed_hosts:
            pat = pattern.strip().lower().rstrip(".")
            if pat.startswith("*."):
                suffix = pat[2:]
                # Suffix must contain at least one dot (prevent TLD-level wildcard like *.com)
                if "." not in suffix:
                    continue
                if host == suffix or host.endswith("." + suffix):
                    return True
            else:
                if host == pat:
                    return True

        return False

    def validate_url(self, url: str) -> SplitResult:
        """
        Validate URL against scheme, host boundary, and credential rules.

        Returns:
            urllib.parse.SplitResult if valid.

        Raises:
            InvalidSchemeError: If scheme is not HTTPS.
            SSRFSecurityError: If URL contains user credentials or is malformed.
            DisallowedHostError: If hostname is not in the allowlist or port is disallowed.
        """
        if not url or not isinstance(url, str):
            raise SSRFSecurityError("URL must be a non-empty string.")

        # Reject control characters or null bytes in URL
        if any(ord(c) < 32 or ord(c) == 127 for c in url):
            raise SSRFSecurityError("URL contains illegal control characters or whitespace.")

        parsed = urlsplit(url)

        if parsed.scheme.lower() != "https":
            raise InvalidSchemeError(
                f"URL scheme '{parsed.scheme}' is prohibited. Only HTTPS is allowed: {url}"
            )

        if parsed.username or parsed.password:
            raise SSRFSecurityError("URLs containing userinfo / credentials are prohibited.")

        hostname = (parsed.hostname or "").strip().lower().rstrip(".")
        if not hostname:
            raise DisallowedHostError(f"URL is missing a valid hostname: {url}")

        # Check raw IP as hostname: disallow direct raw IPs unless allow_localhost in test
        try:
            ipaddress.ip_address(hostname)
            is_ip = True
        except ValueError:
            is_ip = False

        if is_ip:
            if not (self.allow_localhost and hostname in {"127.0.0.1", "::1"}):
                raise DisallowedHostError(
                    f"Direct IP address '{hostname}' is not permitted as a remote provider hostname."
                )

        if not self.match_hostname(hostname):
            raise DisallowedHostError(
                f"Hostname '{hostname}' is not in the authorized provider allowlist: {sorted(self.allowed_hosts)}"
            )

        try:
            port = parsed.port if parsed.port is not None else 443
        except ValueError as e:
            raise SSRFSecurityError(f"Invalid URL port: {e}") from e

        if port <= 0 or port > 65535:
            raise SSRFSecurityError(f"URL port {port} is outside valid range (1-65535).")

        if port not in self.allowed_ports:
            raise DisallowedHostError(
                f"Port {port} is not in the authorized ports list: {sorted(self.allowed_ports)}"
            )

        return parsed

    def is_ip_allowed(self, ip_str: str) -> bool:
        """Validate an IP string against SSRF rules under this policy."""
        return is_safe_ip(ip_str, allow_localhost=self.allow_localhost)


# ---------------------------------------------------------------------------
# Custom Transport: SSRFProtectedHTTPSConnection
# ---------------------------------------------------------------------------

class SSRFProtectedHTTPSConnection(http.client.HTTPSConnection):
    """
    Standard-library HTTPSConnection subclass providing connection-level SSRF protection.

    Guarantees:
    - Resolves hostname directly and validates every candidate IP address before socket connect.
    - Connects directly to a validated safe IP, preventing DNS rebinding TOCTOU attacks.
    - Verifies socket peer name (sock.getpeername()) immediately after connection.
    - Passes the connected socket to SSLContext.wrap_socket with server_hostname=self.host,
      preserving TLS SNI and standard certificate verification.
    """

    def __init__(
        self,
        host: str,
        port: Optional[int] = None,
        timeout: float = 10.0,
        security_policy: Optional[SecurityPolicy] = None,
        context: Optional[ssl.SSLContext] = None,
        check_hostname: bool = True,
        **kwargs: Any,
    ) -> None:
        if context is None:
            context = ssl.create_default_context()
            context.check_hostname = check_hostname
            context.verify_mode = ssl.CERT_REQUIRED
        elif hasattr(context, "check_hostname"):
            context.check_hostname = check_hostname

        super().__init__(
            host=host,
            port=port,
            timeout=timeout,
            context=context,
            **kwargs,
        )
        self.security_policy = security_policy or SecurityPolicy()

    def connect(self) -> None:
        """
        Connect to host on the given port with connection-level SSRF verification.
        """
        target_port = self.port or 443

        # Resolve hostname to candidate addresses
        try:
            addr_info = socket.getaddrinfo(
                self.host,
                target_port,
                family=socket.AF_UNSPEC,
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror as e:
            raise SSRFSecurityError(f"DNS resolution failed for '{self.host}': {e}") from e

        if not addr_info:
            raise SSRFSecurityError(f"No IP addresses resolved for '{self.host}'")

        # Validate each resolved candidate IP address
        valid_candidates: List[Tuple[Any, Any, Any, Any, Any]] = []
        for family, socktype, proto, canonname, sockaddr in addr_info:
            ip_str = sockaddr[0]
            if not self.security_policy.is_ip_allowed(ip_str):
                # Immediate rejection if any resolved IP violates the security policy
                raise BlockedIPError(
                    f"Resolved IP address '{ip_str}' for host '{self.host}' is blocked by security policy."
                )
            valid_candidates.append((family, socktype, proto, canonname, sockaddr))

        if not valid_candidates:
            raise BlockedIPError(f"No authorized IP addresses available for host '{self.host}'")

        # Connect raw TCP socket to the first approved candidate
        last_error: Optional[Exception] = None
        connected_sock: Optional[socket.socket] = None

        for family, socktype, proto, _, sockaddr in valid_candidates:
            sock: Optional[socket.socket] = None
            try:
                sock = socket.socket(family, socktype, proto)
                sock.settimeout(self.timeout)
                sock.connect(sockaddr)

                # Post-connect verification: verify actual connected peer IP
                peer_ip = sock.getpeername()[0]
                if not self.security_policy.is_ip_allowed(peer_ip):
                    sock.close()
                    sock = None
                    raise BlockedIPError(
                        f"Connected socket peer IP '{peer_ip}' violates security policy."
                    )

                connected_sock = sock
                break
            except SSRFSecurityError:
                # Security violation on connected socket must never be ignored or retried
                if sock is not None:
                    try:
                        sock.close()
                    except Exception:
                        pass
                raise
            except Exception as e:
                if sock is not None:
                    try:
                        sock.close()
                    except Exception:
                        pass
                last_error = e

        if connected_sock is None:
            if isinstance(last_error, SSRFSecurityError):
                raise last_error
            raise SSRFSecurityError(
                f"Failed to connect to host '{self.host}:{target_port}': {last_error}"
            ) from last_error

        # Set TCP_NODELAY if supported
        try:
            connected_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError as e:
            if e.errno != errno.ENOPROTOOPT:
                pass

        # Wrap connected socket with TLS, preserving SNI and cert verification
        server_hostname = self._tunnel_host or self.host
        try:
            self.sock = self._context.wrap_socket(
                connected_sock,
                server_hostname=server_hostname,
            )
        except Exception:
            try:
                connected_sock.close()
            except Exception:
                pass
            raise


# ---------------------------------------------------------------------------
# Secure HTTP Client
# ---------------------------------------------------------------------------

class SecureResponse:
    """Represents an HTTP response received from SecureHttpClient."""

    def __init__(
        self,
        status_code: int,
        headers: Dict[str, str],
        body: bytes,
        url: str,
    ) -> None:
        self.status_code = int(status_code)
        self.headers = {k.lower(): v for k, v in headers.items()}
        self.body = bytes(body)
        self.url = str(url)

    def text(self, encoding: str = "utf-8", errors: str = "replace") -> str:
        """Decode response body as string."""
        return self.body.decode(encoding, errors=errors)


class SecureHttpClient:
    """
    SSRF-protected HTTP client that disables automatic redirects,
    validates every redirect destination, enforces hop limits,
    and uses SSRFProtectedHTTPSConnection.
    """

    def __init__(
        self,
        policy: SecurityPolicy,
        ssl_context: Optional[ssl.SSLContext] = None,
        timeout: float = 10.0,
    ) -> None:
        self.policy = policy
        self.ssl_context = ssl_context
        self.timeout = float(timeout)

    def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
    ) -> SecureResponse:
        """Perform a GET request with redirect and SSRF validation."""
        return self.request("GET", url, headers=headers)

    def request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[bytes] = None,
    ) -> SecureResponse:
        """
        Execute an HTTP request with strict validation.

        - Validates initial URL against SecurityPolicy.
        - Disables automatic redirects; intercepts redirect responses (301, 302, 303, 307, 308).
        - Validates redirect target URL before following.
        - Enforces redirect loop detection and max redirect hops limit.
        - Protects against oversized response payloads.
        """
        current_url = url
        visited_urls: Set[str] = set()
        hops = 0
        req_method = method.upper()
        req_body = body
        req_headers = dict(headers or {})

        while True:
            if hops > self.policy.max_redirects:
                raise MaxRedirectsExceededError(
                    f"Redirect limit of {self.policy.max_redirects} exceeded."
                )

            # Validate URL with policy before connecting
            parsed = self.policy.validate_url(current_url)
            visited_urls.add(current_url)

            port = parsed.port if parsed.port is not None else 443
            hostname = parsed.hostname or ""

            # Establish SSRF-protected connection
            conn = SSRFProtectedHTTPSConnection(
                host=hostname,
                port=port,
                timeout=self.timeout,
                security_policy=self.policy,
                context=self.ssl_context,
            )

            request_path = parsed.path or "/"
            if parsed.query:
                request_path += f"?{parsed.query}"

            # Ensure Host header accurately reflects destination host
            req_headers["Host"] = hostname if port == 443 else f"{hostname}:{port}"

            try:
                conn.request(req_method, request_path, body=req_body, headers=req_headers)
                resp = conn.getresponse()

                # Check for redirects
                if resp.status in (301, 302, 303, 307, 308):
                    location = resp.getheader("Location")
                    if not location:
                        # Redirect without Location header, return as-is
                        data = self._read_response_body(resp)
                        return SecureResponse(
                            status_code=resp.status,
                            headers=dict(resp.getheaders()),
                            body=data,
                            url=current_url,
                        )

                    # Check for CRLF injection in Location header
                    if any(c in location for c in ("\r", "\n", "\0")):
                        raise RedirectSecurityError(
                            "Location header contains illegal control characters."
                        )

                    next_url = urljoin(current_url, location)

                    # Check redirect loop
                    if next_url in visited_urls:
                        raise RedirectSecurityError(
                            f"Redirect loop detected: '{next_url}' was already visited."
                        )

                    # Validate redirect target URL BEFORE opening any new connection
                    parsed_next = self.policy.validate_url(next_url)

                    # Strip sensitive authorization headers if redirect changes host (RFC 7235 / 9110)
                    next_hostname = (parsed_next.hostname or "").lower()
                    if next_hostname != hostname.lower():
                        req_headers = {
                            k: v for k, v in req_headers.items()
                            if k.lower() not in {"authorization", "proxy-authorization", "cookie"}
                        }

                    # Adjust method and body for standard HTTP redirect semantics
                    if resp.status in (301, 302, 303) and req_method != "GET":
                        req_method = "GET"
                        req_body = None

                    current_url = next_url
                    hops += 1
                    continue

                # Read body with response size limit
                data = self._read_response_body(resp)
                return SecureResponse(
                    status_code=resp.status,
                    headers=dict(resp.getheaders()),
                    body=data,
                    url=current_url,
                )
            finally:
                conn.close()

    def _read_response_body(self, resp: http.client.HTTPResponse) -> bytes:
        """Read response body while enforcing maximum payload size."""
        chunks: List[bytes] = []
        total_read = 0
        chunk_size = 64 * 1024

        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            chunks.append(chunk)
            total_read += len(chunk)
            if total_read > self.policy.max_response_bytes:
                raise SSRFSecurityError(
                    f"Response payload size exceeded limit ({self.policy.max_response_bytes} bytes)."
                )

        return b"".join(chunks)


# ---------------------------------------------------------------------------
# Browser Target URL Validation Helper
# ---------------------------------------------------------------------------

def validate_provider_target_url(url: str, allowed_hosts: Iterable[str]) -> str:
    """
    Validate that an incoming target URL is strictly valid for the given allowed hosts.

    Ensures arbitrary browser-supplied URLs never become outbound proxy targets.
    """
    policy = SecurityPolicy(allowed_hosts=allowed_hosts)
    policy.validate_url(url)
    return url
