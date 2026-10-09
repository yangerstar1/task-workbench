#!/usr/bin/env python3
"""Fail-closed, read-only availability snapshot for one immutable Unity image.

No CLI parameters, registry credentials, Docker login/pull, manifest GET, retries,
redirects, files, or persistent tokens. Call only after the workflow identity gate.
PASS is a point-in-time observation, never a reservation or a later-pull guarantee.
Docker must retain its original failure behavior if the subsequent pull fails.

Protocol sources (reviewed 2026-10-09):
https://docs.docker.com/docker-hub/usage/pulls/
https://docs.docker.com/reference/api/registry/latest/operations/HeadImageManifest/
https://docs.docker.com/reference/api/registry/auth/
"""
import datetime as dt
import email.utils
import http.client
import json
import os
import re
import selectors
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field

DIGEST = "sha256:17406791cf1e438bea2dac20671668e05d83db5ed38c916744815db4584a8264"
IMAGE = "unityci/editor@" + DIGEST
REGISTRY_HOST = "registry-1.docker.io"
MANIFEST_PATH = "/v2/unityci/editor/manifests/" + DIGEST
AUTH_HOST = "auth.docker.io"
TOKEN_PATH = "/token?service=registry.docker.io&scope=repository%3Aunityci%2Feditor%3Apull"
AUTH_FIELDS = {"realm": "https://auth.docker.io/token", "service": "registry.docker.io", "scope": "repository:unityci/editor:pull"}
ACCEPT = ", ".join(("application/vnd.docker.distribution.manifest.v2+json", "application/vnd.docker.distribution.manifest.list.v2+json", "application/vnd.oci.image.manifest.v1+json", "application/vnd.oci.image.index.v1+json"))
DOCKER_COMMAND = ("/usr/bin/docker", "--host=unix:///var/run/docker.sock", "image", "inspect", "--format", "{{json .RepoDigests}}", IMAGE)
# Only booleans leave the daemon. Explicit type/parent checks keep missing
# mirror metadata from looking like a verified empty mirror configuration.
DOCKER_INFO_FORMAT = '{"httpProxyEmpty":{{eq .HTTPProxy ""}},"httpsProxyEmpty":{{eq .HTTPSProxy ""}},"mirrorsEmpty":{{if .RegistryConfig}}{{and (eq (printf "%T" .RegistryConfig.Mirrors) "[]string") (not .RegistryConfig.Mirrors)}}{{else}}false{{end}}}'
DOCKER_INFO_COMMAND = ("/usr/bin/docker", "--host=unix:///var/run/docker.sock", "info", "--format", DOCKER_INFO_FORMAT)
DOCKER_ENV = {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent"}
DOCKER_TIMEOUT = 5
HTTP_TIMEOUT = 8
TOTAL_TIMEOUT = 35
MAX_TOKEN_BODY = 16384
MAX_TOKEN_LENGTH = 8192
MAX_CACHE_BODY = 16384
WINDOW_SECONDS = 21600
MAX_RETRY_SECONDS = 604800
UTC = dt.timezone.utc
CRITICAL_HEADERS = frozenset(("docker-content-digest", "ratelimit-limit", "ratelimit-remaining", "retry-after", "www-authenticate", "content-type", "content-length", "content-encoding", "transfer-encoding", "location"))
REPORT_KEYS = frozenset(("schemaVersion", "status", "image", "digest", "httpStatus", "cacheHit", "limit", "remaining", "windowSeconds", "retryAfter", "checkedAt"))
BLOCKED_ENV = ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH", "DOCKER_CONFIG", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")


@dataclass(repr=False)
class Response:
    status: int
    headers: tuple = field(repr=False)
    body: bytes = field(default=b"", repr=False)


def utc_now():
    return dt.datetime.now(UTC)


def utc_text(value):
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def blank_result():
    return {"schemaVersion": 1, "status": "UNKNOWN", "image": IMAGE,
            "digest": DIGEST, "httpStatus": None, "cacheHit": False,
            "limit": None, "remaining": None, "windowSeconds": None,
            "retryAfter": None, "checkedAt": utc_text(utc_now())}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("invalid JSON")
        result[key] = value
    return result


def cache_hit():
    """Inspect only the fixed local daemon; never consult CLI contexts or auth."""
    try:
        # Inspect has no registry I/O. stderr is discarded, never interpolated.
        output = inspect_cache_bytes()
        if output is None:
            return False
        digests = json.loads(output.decode("utf-8"), object_pairs_hook=unique_object)
        return (isinstance(digests, list) and 0 < len(digests) <= 64
                and all(type(item) is str and len(item) <= 512 for item in digests)
                and len(set(digests)) == len(digests) and IMAGE in digests)
    except Exception:
        return False


def inspect_cache_bytes():
    return docker_bytes(DOCKER_COMMAND)


def daemon_ready():
    """Observe only proxy/mirror absence; never claim to establish future NAT."""
    try:
        output = docker_bytes(DOCKER_INFO_COMMAND)
        if output is None:
            return False
        value = json.loads(output.decode("utf-8"), object_pairs_hook=unique_object)
        return (type(value) is dict and set(value) == {"httpProxyEmpty", "httpsProxyEmpty", "mirrorsEmpty"}
                and all(item is True for item in value.values()))
    except Exception:
        return False


def docker_bytes(command):
    """Bound both elapsed time and stdout memory even if the local CLI is broken."""
    if command not in (DOCKER_COMMAND, DOCKER_INFO_COMMAND):
        return None
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               env=DOCKER_ENV)
    deadline = time.monotonic() + DOCKER_TIMEOUT
    data = bytearray()
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                left = deadline - time.monotonic()
                if left <= 0 or not selector.select(left):
                    return None
                chunk = os.read(process.stdout.fileno(), MAX_CACHE_BODY + 1 - len(data))
                if not chunk:
                    left = deadline - time.monotonic()
                    if left <= 0 or process.wait(timeout=left) != 0:
                        return None
                    return bytes(data)
                data.extend(chunk)
                if len(data) > MAX_CACHE_BODY:
                    return None
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=DOCKER_TIMEOUT)
        process.stdout.close()


def header(response, name):
    values = [value for key, value in response.headers if key.lower() == name.lower()]
    return values[0] if len(values) == 1 else None


def safe_headers(response):
    seen = set()
    for key, value in response.headers:
        name = key.lower()
        if name in CRITICAL_HEADERS:
            if name in seen or not isinstance(value, str) or len(value) > 4096:
                return False
            if any(ord(c) < 32 and c != "\t" or ord(c) > 126 for c in value):
                return False
            seen.add(name)
    encoding = header(response, "transfer-encoding")
    if encoding is not None and (encoding.lower() != "chunked" or header(response, "content-length") is not None):
        return False
    return True


def allowed_challenge(response):
    value = header(response, "www-authenticate")
    if not safe_headers(response) or value is None or not value.startswith("Bearer "):
        return False
    # Only three quoted, unescaped fixed parameters, in any order. Unknown,
    # repeated parameters, multiple schemes and different scopes fail closed.
    pairs = re.fullmatch(r'Bearer ([a-z]+="[^"\\\r\n]*"(?:[ \t]*,[ \t]*[a-z]+="[^"\\\r\n]*"){2})', value)
    if not pairs:
        return False
    fields = re.findall(r'([a-z]+)="([^"\\]*)"', pairs.group(1))
    return len({key for key, _ in fields}) == 3 and dict(fields) == AUTH_FIELDS


def retry_after(response):
    value = header(response, "retry-after")
    if value is None:
        return None
    if re.fullmatch(r"(?:0|[1-9][0-9]{0,5})", value):
        seconds = int(value)
        return {"seconds": seconds} if seconds <= MAX_RETRY_SECONDS else None
    if not re.fullmatch(r"[A-Z][a-z]{2}, [0-9]{2} [A-Z][a-z]{2} [0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2} GMT", value):
        return None
    try:
        date = email.utils.parsedate_to_datetime(value)
        if email.utils.format_datetime(date, usegmt=True) != value:
            return None
        if not 0 <= (date - utc_now()).total_seconds() <= MAX_RETRY_SECONDS:
            return None
        return {"utc": utc_text(date)}
    except Exception:
        return None


def quota(response):
    parsed = []
    for name in ("ratelimit-limit", "ratelimit-remaining"):
        value = header(response, name)
        if value is None or not re.fullmatch(r"(?:0|[1-9][0-9]{0,8});w=21600", value):
            return None
        parsed.append(int(value.split(";", 1)[0]))
    limit, remaining = parsed
    return (limit, remaining) if limit > 0 and remaining <= limit else None


def validated_token(response):
    if not safe_headers(response) or len(response.body) > MAX_TOKEN_BODY:
        return None
    if header(response, "content-encoding") is not None:
        return None
    content_type = header(response, "content-type")
    if content_type is None or not re.fullmatch(r"application/json(?:; ?charset=utf-8)?", content_type, re.I):
        return None
    length = header(response, "content-length")
    if length is not None and (not re.fullmatch(r"(?:0|[1-9][0-9]{0,5})", length) or int(length) != len(response.body)):
        return None
    value = json.loads(response.body.decode("utf-8"), object_pairs_hook=unique_object)
    if not isinstance(value, dict) or not set(value) <= {"token", "access_token", "expires_in", "issued_at"}:
        return None  # Includes explicit rejection of refresh/offline tokens.
    lifetime = value.get("expires_in")
    if type(lifetime) is not int or not 60 <= lifetime <= 600:
        return None
    token = value.get("token", value.get("access_token"))
    if not isinstance(token, str) or not 1 <= len(token) <= MAX_TOKEN_LENGTH:
        return None
    if not re.fullmatch(r"[A-Za-z0-9._~+/-]+=*", token):
        return None
    if "access_token" in value and value["access_token"] != token:
        return None
    issued_at = value.get("issued_at")
    if "issued_at" in value:
        if not isinstance(issued_at, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,9})?Z", issued_at):
            return None
        age = (utc_now() - dt.datetime.fromisoformat(issued_at.replace("Z", "+00:00"))).total_seconds()
        if age < -60 or age >= lifetime:
            return None
    return token


class RegistryClient:
    """HTTPS with normal certificate verification, no proxy/auth config or redirects."""
    def _request(self, is_token, token=None):
        if is_token:
            host, path, method = AUTH_HOST, TOKEN_PATH, "GET"
            headers = {"Accept": "application/json"}
        else:
            host, path, method = REGISTRY_HOST, MANIFEST_PATH, "HEAD"
            headers = {"Accept": ACCEPT}
            if token is not None:
                headers["Authorization"] = "Bearer " + token
        connection = http.client.HTTPSConnection(host, timeout=HTTP_TIMEOUT)
        try:
            connection.request(method, path, body=None, headers=headers)
            raw = connection.getresponse()
            response = Response(raw.status, tuple(raw.getheaders()))
            # HEAD never reads a body. Redirects and error bodies are never read.
            if is_token and raw.status == 200 and safe_headers(response):
                length = header(response, "content-length")
                if length is not None and (not re.fullmatch(r"(?:0|[1-9][0-9]{0,5})", length) or int(length) > MAX_TOKEN_BODY):
                    return response
                response.body = raw.read(MAX_TOKEN_BODY + 1)
            return response
        finally:
            connection.close()

    def head(self, token=None):
        return self._request(False, token)

    def anonymous_token(self):
        return self._request(True)


def inspect_response(result, response):
    if type(response.status) is not int or not 100 <= response.status <= 599:
        return False
    result["httpStatus"] = response.status
    result["retryAfter"] = retry_after(response)
    if response.status == 429:
        result["status"] = "RATE_LIMITED"
        values = quota(response) if safe_headers(response) else None
        if values is not None:
            result["limit"], result["remaining"] = values
            result["windowSeconds"] = WINDOW_SECONDS
        return False
    if not safe_headers(response):
        return False
    if response.status == 200 and header(response, "docker-content-digest") == DIGEST:
        values = quota(response)
        if values is not None:
            result["limit"], result["remaining"] = values
            result["windowSeconds"] = WINDOW_SECONDS
            result["status"] = "PASS" if values[1] > 0 else "RATE_LIMITED"
    return True


def probe():
    result = blank_result()
    try:
        # Refuse alternate daemons/proxies rather than silently checking a
        # different target from the later Docker build. Never print their values.
        if any(os.environ.get(name) for name in BLOCKED_ENV):
            return result
        if not daemon_ready():
            return result
        if cache_hit():
            result.update(status="PASS", cacheHit=True)
        else:
            client = RegistryClient()
            response = client.head()
            if inspect_response(result, response) and response.status == 401 and allowed_challenge(response):
                response = client.anonymous_token()
                result["httpStatus"] = response.status if type(response.status) is int and 100 <= response.status <= 599 else None
                result["retryAfter"] = retry_after(response)
                if response.status == 429:
                    inspect_response(result, response)
                elif response.status == 200:
                    token = validated_token(response)
                    if token is not None:
                        response = client.head(token)
                        token = None
                        inspect_response(result, response)
    except Exception:
        # No raw exception, HTTP payload/header, token, IP or Docker output escapes.
        result["status"] = "UNKNOWN"
    result["checkedAt"] = utc_text(utc_now())
    return result


def validate_report(report):
    """Pure allowlist validator for the one safe, uploadable report; no I/O."""
    try:
        if type(report) is not dict or set(report) != REPORT_KEYS:
            return False
        if type(report["schemaVersion"]) is not int or report["schemaVersion"] != 1:
            return False
        if report["image"] != IMAGE or report["digest"] != DIGEST:
            return False
        if report["status"] not in ("PASS", "RATE_LIMITED", "UNKNOWN") or type(report["cacheHit"]) is not bool:
            return False
        checked = parse_report_utc(report["checkedAt"])
        if checked is None:
            return False
        code = report["httpStatus"]
        if code is not None and (type(code) is not int or not 100 <= code <= 599):
            return False
        retry = report["retryAfter"]
        if retry is not None:
            if type(retry) is not dict or code is None:
                return False
            if set(retry) == {"seconds"}:
                if type(retry["seconds"]) is not int or not 0 <= retry["seconds"] <= MAX_RETRY_SECONDS:
                    return False
            elif set(retry) == {"utc"}:
                date = parse_report_utc(retry["utc"])
                if date is None or not 0 <= (date - checked).total_seconds() <= MAX_RETRY_SECONDS + 1:
                    return False
            else:
                return False
        limit, remaining, window = (report[name] for name in ("limit", "remaining", "windowSeconds"))
        no_quota = limit is None and remaining is None and window is None
        valid_quota = (type(limit) is int and type(remaining) is int and type(window) is int
                       and 0 < limit <= 999999999 and 0 <= remaining <= limit and window == WINDOW_SECONDS)
        if not no_quota and not valid_quota:
            return False
        if report["cacheHit"]:
            return report["status"] == "PASS" and code is None and no_quota and retry is None
        if report["status"] == "PASS":
            return code == 200 and valid_quota and remaining > 0
        if report["status"] == "RATE_LIMITED":
            return (code == 429 and (no_quota or valid_quota)) or (code == 200 and valid_quota and remaining == 0)
        return no_quota and code != 429
    except Exception:
        return False


def parse_report_utc(value):
    if type(value) is not str or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if utc_text(parsed) == value else None
    except Exception:
        return None


class DeadlineExpired(BaseException):
    """Must not be swallowed by a cache/network fallback's Exception handler."""


def alarm_expired(_signum, _frame):
    raise DeadlineExpired()


def main(argv=None):
    result = blank_result()
    argv = sys.argv[1:] if argv is None else argv
    previous_handler = None
    alarm_set = False
    try:
        if not argv:
            # Linux hosted runner contract: this also bounds DNS/slow responses.
            previous_handler = signal.signal(signal.SIGALRM, alarm_expired)
            signal.setitimer(signal.ITIMER_REAL, TOTAL_TIMEOUT)
            alarm_set = True
            result = probe()
    except (Exception, KeyboardInterrupt, DeadlineExpired):
        result = blank_result()
    finally:
        if alarm_set:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)
    if not validate_report(result):
        result = blank_result()
    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
