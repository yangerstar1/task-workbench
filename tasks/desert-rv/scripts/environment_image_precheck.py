#!/usr/bin/env python3
"""Fail-closed readiness check for one immutable Unity image.

Two fixed scopes: target digest existence and official rate-limit preview.
Two read-only HEAD channels; one bounded fixed-image Docker pull is permitted
only when target digest is verified and preview 200 has neither quota header.
No CLI parameters, credentials, Docker login, manifest GET, caller retries,
redirects, files, or persistent tokens. Call only after the workflow identity gate.
PASS is a point-in-time observation, never a reservation or a later-pull guarantee.
Docker must retain its original failure behavior if the subsequent pull fails.

Protocol sources (reviewed 2026-10-09):
https://docs.docker.com/docker-hub/usage/pulls/
https://docs.docker.com/reference/api/registry/latest/operations/HeadImageManifest/
https://docs.docker.com/reference/api/registry/auth/
https://docs.docker.com/reference/cli/docker/image/pull/
"""
import datetime as dt
import email.utils
import http.client
import hashlib
import json
import os
import re
import selectors
import signal
import subprocess
import sys
import time
from enum import Enum
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
# Official v28.5.1 sources: docker/cli cli/command/system/info.go embeds
# *system.Info and executes this struct as the template context; Moby
# api/types/system/info.go defines HTTPProxy/HTTPSProxy strings (JSON names
# differ) and RegistryConfig *registry.ServiceConfig; registry/registry.go
# defines Mirrors []string. Unsupported fields/errors remain UNKNOWN.
# https://raw.githubusercontent.com/docker/cli/v28.5.1/cli/command/system/info.go
# https://raw.githubusercontent.com/moby/moby/v28.5.1/api/types/system/info.go
# https://raw.githubusercontent.com/moby/moby/v28.5.1/api/types/registry/registry.go
DOCKER_INFO_FORMAT = '{"httpProxyEmpty":{{eq .HTTPProxy ""}},"httpsProxyEmpty":{{eq .HTTPSProxy ""}},"mirrorsEmpty":{{if .RegistryConfig}}{{and (eq (printf "%T" .RegistryConfig.Mirrors) "[]string") (not .RegistryConfig.Mirrors)}}{{else}}false{{end}}}'
DOCKER_INFO_COMMAND = ("/usr/bin/docker", "--host=unix:///var/run/docker.sock", "info", "--format", DOCKER_INFO_FORMAT)
PULL_COMMAND = ("/usr/bin/docker", "--host=unix:///var/run/docker.sock", "pull", "--quiet", IMAGE)
DOCKER_ENV = {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent"}
DOCKER_TIMEOUT = 5
HTTP_TIMEOUT = 8
TOTAL_TIMEOUT = 65
PULL_TIMEOUT = 600
PULL_PHASE_TIMEOUT = PULL_TIMEOUT + DOCKER_TIMEOUT + 5
MAX_TOKEN_BODY = 16384
MAX_TOKEN_LENGTH = 8192
MAX_CACHE_BODY = 16384
MAX_PULL_STDERR = 65536
WINDOW_SECONDS = 21600
MAX_RETRY_SECONDS = 604800
UTC = dt.timezone.utc
CRITICAL_HEADERS = frozenset(("docker-content-digest", "ratelimit-limit", "ratelimit-remaining", "retry-after", "www-authenticate", "content-type", "content-length", "content-encoding", "transfer-encoding", "location"))
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


# One hour is a local finite safety ceiling, not a Docker lifetime guarantee.
# It admits Docker's documented expires_in=3600 example; omission means 60.
MAX_TOKEN_LIFETIME = 3600
MAX_CLOCK_SKEW = 60


class Route(Enum):
    TARGET = "target"
    QUOTA = "quota"


ROUTES = {
    Route.TARGET: (MANIFEST_PATH, TOKEN_PATH, "repository:unityci/editor:pull"),
    Route.QUOTA: ("/v2/ratelimitpreview/test/manifests/latest", "/token?service=registry.docker.io&scope=repository%3Aratelimitpreview%2Ftest%3Apull", "repository:ratelimitpreview/test:pull"),
}
STAGES = frozenset(("NOT_STARTED", "INITIAL_HEAD", "TOKEN_GET", "AUTHENTICATED_HEAD"))
HEADER_STATES = frozenset(("NOT_CHECKED", "NOT_APPLICABLE", "VALID", "MISSING", "INVALID", "DUPLICATE", "MISMATCH"))
CHANNEL_REASONS = frozenset(("NOT_STARTED", "TARGET_VERIFIED", "QUOTA_AVAILABLE", "QUOTA_EXHAUSTED", "HEADERS_INVALID", "DIGEST_UNVERIFIED", "QUOTA_HEADERS_ABSENT", "QUOTA_HEADER_PARTIAL", "QUOTA_INVALID", "AUTH_CHALLENGE_INVALID", "TOKEN_HEADERS_INVALID", "TOKEN_BODY_INVALID", "TOKEN_SCHEMA_INVALID", "TOKEN_LIFETIME_INVALID", "TOKEN_VALUE_INVALID", "TOKEN_TIME_INVALID", "TOKEN_EXPIRED", "HTTP_UNEXPECTED", "HTTP_RATE_LIMITED", "TRANSPORT_ERROR", "DEADLINE"))
CHANNEL_REASONS = CHANNEL_REASONS | {"TARGET_QUOTA_EXHAUSTED"}
TOP_REASONS = frozenset(("NOT_STARTED", "ENVIRONMENT_OVERRIDE", "DAEMON_UNVERIFIED", "CACHE_HIT", "READY", "DEADLINE", "INTERNAL_ERROR", "TARGET_DIGEST_UNVERIFIED", "TARGET_AUTH_FAILED", "TARGET_TRANSPORT_ERROR", "TARGET_HEADERS_INVALID", "TARGET_HTTP_UNEXPECTED", "TARGET_RATE_LIMITED", "QUOTA_MISSING", "QUOTA_INVALID", "QUOTA_EXHAUSTED", "QUOTA_AUTH_FAILED", "QUOTA_TRANSPORT_ERROR", "QUOTA_HEADERS_INVALID", "QUOTA_HTTP_UNEXPECTED", "QUOTA_RATE_LIMITED", "PULL_SUCCEEDED", "PULL_FAILED", "PULL_TIMEOUT", "PULL_DIGEST_UNVERIFIED", "PULL_ERROR", "PULL_INTERRUPTED"))
TOP_REASONS = TOP_REASONS | {"TARGET_QUOTA_EXHAUSTED", "TARGET_QUOTA_INVALID", "PULL_RATE_LIMITED", "PULL_STDERR_LIMIT_EXCEEDED"}
HEADER_KEYS = frozenset(("safety", "digest", "limit", "remaining", "challenge"))
CHANNEL_KEYS = frozenset(("complete", "currentStage", "httpStatus", "reason", "headers", "rateDiagnostics"))
REPORT_KEYS = frozenset(("schemaVersion", "status", "reason", "image", "digest", "cacheHit", "limit", "remaining", "windowSeconds", "retryAfter", "checkedAt", "target", "quota", "pull"))
PULL_KEYS = frozenset(("attempted", "currentStage", "outcome", "exitCode", "cacheVerified", "failureClass"))
PULL_STAGES = frozenset(("NOT_STARTED", "PULL", "VERIFY_CACHE", "COMPLETE"))
PULL_OUTCOMES = frozenset(("NOT_ATTEMPTED", "SUCCESS", "NONZERO_EXIT", "TIMEOUT", "INSPECT_MISMATCH", "ERROR", "INTERRUPTED", "STDERR_LIMIT_EXCEEDED"))
PULL_FAILURE_CLASSES = frozenset(("NOT_CHECKED", "NONE", "DOCKER_RATE_LIMITED", "UNKNOWN_CLI_FAILURE", "STDERR_LIMIT_EXCEEDED"))


# Pure diagnostics only. These parsers NEVER decide PASS, routes or pull eligibility.
# Only these two HEAD headers may echo bounded printable ASCII, including
# unknown syntax. Obvious credentials/IPs are redacted; duplicates never merge.
MAX_NUMERIC_RAW = 256
MAX_SERIALIZED_REPORT_BYTES = 8192
MAX_NUMERIC_POLICIES = 4
POLICY_ATOM = r"[0-9]{1,10}(?:[ \t]*;[ \t]*w[ \t]*=[ \t]*[0-9]{1,10})?"
NUMERIC_POLICY = re.compile(r"[ \t]*" + POLICY_ATOM + r"(?:[ \t]*,[ \t]*" + POLICY_ATOM + r"){0,3}[ \t]*", re.ASCII)
DIAG_KEYS = frozenset(("occurrenceCount", "lengthBytes", "sha256", "format", "gateCompatibility", "boundedRaw", "policies"))
DIAG_FORMATS = frozenset(("NOT_OBSERVED", "MISSING", "DUPLICATE", "TOO_LONG", "NON_ASCII_OR_CONTROL", "REDACTED_SENSITIVE", "UNKNOWN_SYNTAX", "NUMERIC_SINGLE", "NUMERIC_MULTI"))
DIAG_COMPATIBILITY = frozenset(("NOT_EVALUATED", "MISSING", "DUPLICATE", "UNKNOWN_SYNTAX", "STRICT_FORMAT_MATCH", "WINDOW_MISSING", "WINDOW_NOT_21600", "MULTIPLE_POLICIES", "NONCANONICAL_NUMBER", "NONCANONICAL_SYNTAX"))
FAILED_PREDICATES = frozenset(("NOT_EVALUATED", "NONE", "HEADER_SAFETY", "TARGET_DIGEST_MATCH", "HTTP_STATUS_200", "HTTP_STATUS_429", "QUOTA_BOTH_HEADERS_MISSING", "LIMIT_MISSING", "REMAINING_MISSING", "LIMIT_HEADER_NOT_VALID", "REMAINING_HEADER_NOT_VALID", "LIMIT_STRICT_REGEX", "REMAINING_STRICT_REGEX", "LIMIT_NOT_POSITIVE", "REMAINING_GT_LIMIT", "REMAINING_NOT_POSITIVE"))


def blank_rate_header():
    return {"occurrenceCount": None, "lengthBytes": None, "sha256": None,
            "format": "NOT_OBSERVED", "gateCompatibility": "NOT_EVALUATED",
            "boundedRaw": None, "policies": []}


def blank_rate_diagnostics():
    return {"firstFailedPredicate": "NOT_EVALUATED", "limit": blank_rate_header(), "remaining": blank_rate_header()}


def sensitive_rate_text(value):
    patterns = (r"bearer", r"https?://", r"(?:[0-9]{1,3}\.){3}[0-9]{1,3}",
                r"(?:[0-9a-f]{0,4}:){2,}[0-9a-f:]*", r"[a-z0-9_-]{8,}\.[a-z0-9_-]{8,}\.[a-z0-9_-]{8,}",
                r"(?:token|password|secret|authorization|api[_-]?key)[ \t]*[:=]")
    return any(re.search(pattern, value, re.I | re.ASCII) for pattern in patterns)


def diagnose_rate_header(response, name):
    values = [value for key, value in response.headers if key.lower() == name]
    result = blank_rate_header()
    result["occurrenceCount"] = len(values)
    result["lengthBytes"] = sum(len(value.encode("utf-8", "surrogatepass")) for value in values)
    if not values:
        result.update(format="MISSING", gateCompatibility="MISSING")
        return result
    # Single occurrence hashes exact UTF-8 bytes; duplicate hash uses unambiguous
    # 8-byte lengths + UTF-8 values, in received order. No duplicate raw echo.
    digest = hashlib.sha256()
    for value in values:
        encoded = value.encode("utf-8", "surrogatepass")
        if len(values) > 1:
            digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    result["sha256"] = digest.hexdigest()
    if len(values) != 1:
        result.update(format="DUPLICATE", gateCompatibility="DUPLICATE")
        return result
    value = values[0]
    if len(value) > MAX_NUMERIC_RAW:
        result.update(format="TOO_LONG", gateCompatibility="UNKNOWN_SYNTAX")
        return result
    if any(ord(char) > 126 or ord(char) < 32 for char in value):
        result.update(format="NON_ASCII_OR_CONTROL", gateCompatibility="UNKNOWN_SYNTAX")
        return result
    if sensitive_rate_text(value):
        result.update(format="REDACTED_SENSITIVE", gateCompatibility="UNKNOWN_SYNTAX")
        return result
    result["boundedRaw"] = value
    if not NUMERIC_POLICY.fullmatch(value):
        result.update(format="UNKNOWN_SYNTAX", gateCompatibility="UNKNOWN_SYNTAX")
        return result
    policies = []
    for policy in value.split(","):
        parts = policy.strip(" \t").split(";")
        policies.append({"value": int(parts[0].strip(" \t")), "windowSeconds": int(parts[1].split("=", 1)[1].strip(" \t")) if len(parts) == 2 else None})
    result.update(format="NUMERIC_SINGLE" if len(policies) == 1 else "NUMERIC_MULTI", boundedRaw=value, policies=policies)
    if len(policies) != 1:
        compatibility = "MULTIPLE_POLICIES"
    elif policies[0]["windowSeconds"] is None:
        compatibility = "WINDOW_MISSING"
    elif policies[0]["windowSeconds"] != WINDOW_SECONDS:
        compatibility = "WINDOW_NOT_21600"
    elif re.fullmatch(r"(?:0|[1-9][0-9]{0,8});w=21600", value):
        compatibility = "STRICT_FORMAT_MATCH"
    elif not re.fullmatch(r"(?:0|[1-9][0-9]{0,8})", value.split(";", 1)[0].strip(" \t")):
        compatibility = "NONCANONICAL_NUMBER"
    else:
        compatibility = "NONCANONICAL_SYNTAX"
    result["gateCompatibility"] = compatibility
    return result


def observe_rate_diagnostics(response):
    return {"firstFailedPredicate": "NOT_EVALUATED",
            "limit": diagnose_rate_header(response, "ratelimit-limit"),
            "remaining": diagnose_rate_header(response, "ratelimit-remaining")}


def rate_predicate(record, predicate):
    record["rateDiagnostics"]["firstFailedPredicate"] = predicate


def blank_pull():
    return {"attempted": False, "currentStage": "NOT_STARTED", "outcome": "NOT_ATTEMPTED", "exitCode": None, "cacheVerified": False, "failureClass": "NOT_CHECKED"}


def blank_channel(route):
    return {"complete": False, "currentStage": "NOT_STARTED", "httpStatus": None,
            "reason": "NOT_STARTED", "headers": blank_headers(route), "rateDiagnostics": blank_rate_diagnostics()}


def blank_headers(route):
    return {"safety": "NOT_CHECKED", "digest": "NOT_CHECKED" if route is Route.TARGET else "NOT_APPLICABLE",
            "limit": "NOT_CHECKED", "remaining": "NOT_CHECKED", "challenge": "NOT_CHECKED"}


def blank_result():
    return {"schemaVersion": 3, "status": "UNKNOWN", "reason": "NOT_STARTED",
            "image": IMAGE, "digest": DIGEST, "cacheHit": False,
            "limit": None, "remaining": None, "windowSeconds": None,
            "retryAfter": None, "checkedAt": utc_text(utc_now()),
            "target": blank_channel(Route.TARGET), "quota": blank_channel(Route.QUOTA), "pull": blank_pull()}


def header(response, name):
    values = [value for key, value in response.headers if key.lower() == name.lower()]
    return values[0] if len(values) == 1 else None


def header_state(response, name):
    values = [value for key, value in response.headers if key.lower() == name.lower()]
    if not values:
        return "MISSING"
    if len(values) != 1:
        return "DUPLICATE"
    value = values[0]
    if type(value) is not str or len(value) > 4096 or any(ord(c) < 32 and c != "\t" or ord(c) > 126 for c in value):
        return "INVALID"
    return "VALID"


def safe_headers(response, route=None, is_token=False):
    # Target quota is a contradiction guard only, never preview quota evidence.
    ignored = {"ratelimit-limit", "ratelimit-remaining", "docker-content-digest"} if is_token else (set() if route is Route.TARGET else {"docker-content-digest"})
    for name in CRITICAL_HEADERS - ignored:
        if header_state(response, name) not in ("VALID", "MISSING"):
            return False
    encoding = header(response, "transfer-encoding")
    return encoding is None or (encoding.lower() == "chunked" and header(response, "content-length") is None)


def allowed_challenge(response, route):
    value = header(response, "www-authenticate")
    if value is None:
        return False
    matched = re.fullmatch(r'Bearer ([a-z]+="[^"\\\r\n]*"(?:[ \t]*,[ \t]*[a-z]+="[^"\\\r\n]*"){2})', value)
    if not matched:
        return False
    fields = re.findall(r'([a-z]+)="([^"\\]*)"', matched.group(1))
    expected = dict(AUTH_FIELDS, scope=ROUTES[route][2])
    return len({key for key, _ in fields}) == 3 and dict(fields) == expected


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
        if email.utils.format_datetime(date, usegmt=True) != value or not 0 <= (date - utc_now()).total_seconds() <= MAX_RETRY_SECONDS:
            return None
        return {"utc": utc_text(date)}
    except Exception:
        return None


@dataclass(repr=False)
class Token:
    value: str = field(repr=False)
    expires_at: dt.datetime = field(repr=False)

    def live(self):
        return utc_now() < self.expires_at


def validated_token(response, received_at):
    if not safe_headers(response, is_token=True) or header(response, "content-encoding") is not None:
        return None, "TOKEN_HEADERS_INVALID"
    content_type = header(response, "content-type")
    if content_type is None or not re.fullmatch(r"application/json(?:; ?charset=utf-8)?", content_type, re.I):
        return None, "TOKEN_HEADERS_INVALID"
    length = header(response, "content-length")
    if len(response.body) > MAX_TOKEN_BODY or (length is not None and (not re.fullmatch(r"(?:0|[1-9][0-9]{0,5})", length) or int(length) != len(response.body))):
        return None, "TOKEN_BODY_INVALID"
    try:
        value = json.loads(response.body.decode("utf-8"), object_pairs_hook=unique_object)
    except Exception:
        return None, "TOKEN_BODY_INVALID"
    if type(value) is not dict or not set(value) <= {"token", "access_token", "expires_in", "issued_at"}:
        return None, "TOKEN_SCHEMA_INVALID"
    lifetime = value.get("expires_in", 60)
    if type(lifetime) is not int or not 0 < lifetime <= MAX_TOKEN_LIFETIME:
        return None, "TOKEN_LIFETIME_INVALID"
    token = value.get("token", value.get("access_token"))
    if type(token) is not str or not 1 <= len(token) <= MAX_TOKEN_LENGTH or not re.fullmatch(r"[A-Za-z0-9._~+/-]+=*", token):
        return None, "TOKEN_VALUE_INVALID"
    if "access_token" in value and value["access_token"] != token:
        return None, "TOKEN_VALUE_INVALID"
    issued = received_at
    if "issued_at" in value:
        text = value["issued_at"]
        if type(text) is not str or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,9})?(?:[Zz]|[+-][0-9]{2}:[0-9]{2})", text):
            return None, "TOKEN_TIME_INVALID"
        try:
            issued = dt.datetime.fromisoformat(text.upper().replace("Z", "+00:00")).astimezone(UTC)
        except Exception:
            return None, "TOKEN_TIME_INVALID"
        if (issued - received_at).total_seconds() > MAX_CLOCK_SKEW:
            return None, "TOKEN_TIME_INVALID"
    # Do not let server clock skew extend the local lifetime beyond one hour.
    expiry = min(issued + dt.timedelta(seconds=lifetime), received_at + dt.timedelta(seconds=lifetime))
    if expiry <= received_at or expiry <= utc_now():
        return None, "TOKEN_EXPIRED"
    return Token(token, expiry), None


class RegistryClient:
    """No URLs from input, redirects, ambient auth, proxies or manifest GETs."""
    def _request(self, route, is_token, token=None):
        if type(route) is not Route or type(is_token) is not bool:
            raise ValueError("invalid fixed route")
        if is_token:
            host, path, method = AUTH_HOST, ROUTES[route][1], "GET"
            headers = {"Accept": "application/json"}
        else:
            host, path, method = REGISTRY_HOST, ROUTES[route][0], "HEAD"
            headers = {"Accept": ACCEPT}
            if token is not None:
                headers["Authorization"] = "Bearer " + token
        connection = http.client.HTTPSConnection(host, timeout=HTTP_TIMEOUT)
        try:
            connection.request(method, path, body=None, headers=headers)
            raw = connection.getresponse()
            response = Response(raw.status, tuple(raw.getheaders()))
            if is_token and raw.status == 200 and safe_headers(response, route, True):
                length = header(response, "content-length")
                if length is not None and (not re.fullmatch(r"(?:0|[1-9][0-9]{0,5})", length) or int(length) > MAX_TOKEN_BODY):
                    return response
                response.body = raw.read(MAX_TOKEN_BODY + 1)
            return response
        finally:
            connection.close()

    def head(self, route, token=None):
        return self._request(route, False, token)

    def anonymous_token(self, route):
        return self._request(route, True)


def start_request(record, route, stage):
    record.update(complete=False, currentStage=stage, httpStatus=None, reason="NOT_STARTED", headers=blank_headers(route), rateDiagnostics=blank_rate_diagnostics())


def accept_response(record, response, route, is_token=False):
    if type(response.status) is not int or not 100 <= response.status <= 599:
        record["reason"] = "HTTP_UNEXPECTED"
        return False
    record["httpStatus"] = response.status
    record["headers"]["safety"] = "VALID" if safe_headers(response, route, is_token) else "INVALID"
    if not is_token:
        record["rateDiagnostics"] = observe_rate_diagnostics(response)
        if route is Route.TARGET:
            record["headers"]["digest"] = header_state(response, "docker-content-digest")
        for key in ("limit", "remaining"):
            record["headers"][key] = header_state(response, "ratelimit-" + key)
    if response.status == 401:
        record["headers"]["challenge"] = header_state(response, "www-authenticate")
    return True


def quota_values(record, response):
    values = []
    missing = sum(record["headers"][key] == "MISSING" for key in ("limit", "remaining"))
    if missing:
        record["reason"] = "QUOTA_HEADERS_ABSENT" if missing == 2 else "QUOTA_HEADER_PARTIAL"
        rate_predicate(record, "QUOTA_BOTH_HEADERS_MISSING" if missing == 2 else "LIMIT_MISSING" if record["headers"]["limit"] == "MISSING" else "REMAINING_MISSING")
        return None
    for key in ("limit", "remaining"):
        state = record["headers"][key]
        value = header(response, "ratelimit-" + key)
        if state != "VALID" or value is None or not re.fullmatch(r"(?:0|[1-9][0-9]{0,8});w=21600", value):
            rate_predicate(record, key.upper() + ("_HEADER_NOT_VALID" if state != "VALID" or value is None else "_STRICT_REGEX"))
            if state == "VALID":
                record["headers"][key] = "INVALID"
            record["reason"] = "QUOTA_INVALID"
            return None
        values.append(int(value.split(";", 1)[0]))
    if values[0] <= 0 or values[1] > values[0]:
        rate_predicate(record, "LIMIT_NOT_POSITIVE" if values[0] <= 0 else "REMAINING_GT_LIMIT")
        record["headers"]["limit"] = record["headers"]["remaining"] = "INVALID"
        record["reason"] = "QUOTA_INVALID"
        return None
    rate_predicate(record, "NONE")
    return tuple(values)


def finish_head(result, record, response, route):
    # Only a 429 supplies a retry suggestion. A 200 Retry-After is not quota
    # evidence and must not become a stale timestamp after a long bounded pull.
    result["retryAfter"] = retry_after(response) if response.status == 429 else None
    if response.status == 429:
        record["reason"] = "HTTP_RATE_LIMITED"
        if route is Route.QUOTA and record["headers"]["safety"] == "VALID":
            values = quota_values(record, response)
            if values is not None:
                result["limit"], result["remaining"] = values
                result["windowSeconds"] = WINDOW_SECONDS
            record["reason"] = "HTTP_RATE_LIMITED"
        rate_predicate(record, "HTTP_STATUS_429")
        return False
    if record["headers"]["safety"] != "VALID":
        record["reason"] = "HEADERS_INVALID"
        rate_predicate(record, "HEADER_SAFETY")
        return False
    if response.status != 200:
        record["reason"] = "HTTP_UNEXPECTED"
        rate_predicate(record, "HTTP_STATUS_200")
        return False
    if route is Route.TARGET:
        if header(response, "docker-content-digest") != DIGEST:
            if record["headers"]["digest"] == "VALID":
                record["headers"]["digest"] = "MISMATCH"
            record["reason"] = "DIGEST_UNVERIFIED"
            rate_predicate(record, "TARGET_DIGEST_MATCH")
            return False
        if not all(record["headers"][key] == "MISSING" for key in ("limit", "remaining")):
            values = quota_values(record, response)
            if values is None:
                return False
            if values[1] == 0:
                record["reason"] = "TARGET_QUOTA_EXHAUSTED"
                rate_predicate(record, "REMAINING_NOT_POSITIVE")
                return False
        rate_predicate(record, "NONE")
        record.update(complete=True, reason="TARGET_VERIFIED")
        return True
    values = quota_values(record, response)
    if values is None:
        return False
    result["limit"], result["remaining"] = values
    result["windowSeconds"] = WINDOW_SECONDS
    rate_predicate(record, "NONE" if values[1] > 0 else "REMAINING_NOT_POSITIVE")
    record.update(complete=True, reason="QUOTA_AVAILABLE" if values[1] > 0 else "QUOTA_EXHAUSTED")
    return values[1] > 0


def channel(result, route, client):
    record = result[route.value]
    token = None
    try:
        start_request(record, route, "INITIAL_HEAD")
        result["retryAfter"] = None
        response = client.head(route)
        if not accept_response(record, response, route):
            return False, None
        if response.status == 401:
            if record["headers"]["safety"] != "VALID" or not allowed_challenge(response, route):
                record["reason"] = "AUTH_CHALLENGE_INVALID"
                if record["headers"]["challenge"] == "VALID":
                    record["headers"]["challenge"] = "MISMATCH"
                return False, None
            start_request(record, route, "TOKEN_GET")
            response = client.anonymous_token(route)
            received = utc_now()
            if not accept_response(record, response, route, True):
                return False, None
            result["retryAfter"] = retry_after(response) if response.status == 429 else None
            if response.status == 429:
                record["reason"] = "HTTP_RATE_LIMITED"
                return False, None
            if response.status != 200:
                record["reason"] = "HTTP_UNEXPECTED"
                return False, None
            token, error = validated_token(response, received)
            if error:
                record["reason"] = error
                return False, None
            start_request(record, route, "AUTHENTICATED_HEAD")
            result["retryAfter"] = None
            if not token.live():
                record["reason"] = "TOKEN_EXPIRED"
                return False, None
            response = client.head(route, token.value)
            if not accept_response(record, response, route):
                return False, None
            if not token.live():
                record["reason"] = "TOKEN_EXPIRED"
                return False, None
        return finish_head(result, record, response, route), token
    except Exception:
        record.update(complete=False, reason="TRANSPORT_ERROR")
        return False, None


def classify(result, route):
    reason = result[route.value]["reason"]
    prefix = route.value.upper()
    if reason == "HTTP_RATE_LIMITED":
        result.update(status="RATE_LIMITED", reason=prefix + "_RATE_LIMITED")
    elif reason == "QUOTA_EXHAUSTED":
        result.update(status="RATE_LIMITED", reason="QUOTA_EXHAUSTED")
    elif reason == "TARGET_QUOTA_EXHAUSTED":
        result.update(status="RATE_LIMITED", reason="TARGET_QUOTA_EXHAUSTED")
    elif (reason in ("AUTH_CHALLENGE_INVALID", "HTTP_UNEXPECTED") and result[route.value]["httpStatus"] in (401, 403)) or reason.startswith("TOKEN_"):
        result.update(status="UNKNOWN", reason=prefix + "_AUTH_FAILED")
    elif reason == "AUTH_CHALLENGE_INVALID" or result[route.value]["currentStage"] == "TOKEN_GET" and reason == "HTTP_UNEXPECTED":
        result.update(status="UNKNOWN", reason=prefix + "_AUTH_FAILED")
    else:
        mapped = {"DIGEST_UNVERIFIED": "TARGET_DIGEST_UNVERIFIED", "QUOTA_HEADERS_ABSENT": "QUOTA_MISSING", "QUOTA_HEADER_PARTIAL": "TARGET_QUOTA_INVALID" if route is Route.TARGET else "QUOTA_MISSING", "QUOTA_INVALID": "TARGET_QUOTA_INVALID" if route is Route.TARGET else "QUOTA_INVALID", "HEADERS_INVALID": prefix + "_HEADERS_INVALID", "TRANSPORT_ERROR": prefix + "_TRANSPORT_ERROR", "HTTP_UNEXPECTED": prefix + "_HTTP_UNEXPECTED"}
        result.update(status="UNKNOWN", reason=mapped.get(reason, "INTERNAL_ERROR"))


def pull_eligible(result):
    target, quota = result["target"], result["quota"]
    return (target["complete"] and target["httpStatus"] == 200 and target["reason"] == "TARGET_VERIFIED"
            and target["headers"]["digest"] == "VALID"
            and quota["httpStatus"] == 200 and quota["currentStage"] in ("INITIAL_HEAD", "AUTHENTICATED_HEAD")
            and quota["headers"]["safety"] == "VALID" and quota["reason"] == "QUOTA_HEADERS_ABSENT"
            and quota["headers"]["limit"] == quota["headers"]["remaining"] == "MISSING"
            and result["limit"] is None and result["remaining"] is None and result["windowSeconds"] is None)


def classify_pull_stderr(data):
    lowered = data.lower()
    known = (b"you have reached your unauthenticated pull rate limit", b"you have reached your pull rate limit", b"429 too many requests")
    return "DOCKER_RATE_LIMITED" if any(phrase in lowered for phrase in known) else "UNKNOWN_CLI_FAILURE"


def run_fixed_pull():
    """One CLI invocation; bounded private stderr, no stored/raw diagnostic text.

    Killing/timing out the CLI does NOT establish the daemon stopped pulling.
    """
    process = None
    try:
        process = subprocess.Popen(PULL_COMMAND, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                   env=DOCKER_ENV)
        deadline = time.monotonic() + PULL_TIMEOUT
        data = bytearray()
        with selectors.DefaultSelector() as selector:
            selector.register(process.stderr, selectors.EVENT_READ)
            while True:
                left = deadline - time.monotonic()
                if left <= 0 or not selector.select(left):
                    return "TIMEOUT", None, "NOT_CHECKED"
                chunk = os.read(process.stderr.fileno(), MAX_PULL_STDERR + 1 - len(data))
                if not chunk:
                    left = deadline - time.monotonic()
                    if left <= 0:
                        return "TIMEOUT", None, "NOT_CHECKED"
                    code = process.wait(timeout=left)
                    if type(code) is not int or not -128 <= code <= 255:
                        return "ERROR", None, "UNKNOWN_CLI_FAILURE"
                    if code == 0:
                        return "SUCCESS", 0, "NONE"
                    return "NONZERO_EXIT", code, classify_pull_stderr(data)
                data.extend(chunk)
                if len(data) > MAX_PULL_STDERR:
                    return "STDERR_LIMIT_EXCEEDED", None, "STDERR_LIMIT_EXCEEDED"
    except subprocess.TimeoutExpired:
        return "TIMEOUT", None, "NOT_CHECKED"
    except Exception:
        return "ERROR", None, "UNKNOWN_CLI_FAILURE"
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=DOCKER_TIMEOUT)
            process.stderr.close()


def bounded_pull(result, with_watchdog=False):
    pull = result["pull"]
    pull.update(attempted=True, currentStage="PULL")
    if with_watchdog:
        signal.setitimer(signal.ITIMER_REAL, PULL_PHASE_TIMEOUT)
    outcome, code, failure_class = run_fixed_pull()
    pull.update(outcome=outcome, exitCode=code, failureClass=failure_class)
    if outcome == "SUCCESS":
        pull["currentStage"] = "VERIFY_CACHE"
        if cache_hit():
            pull.update(currentStage="COMPLETE", cacheVerified=True)
            result.update(status="PASS", reason="PULL_SUCCEEDED")
            if with_watchdog:
                signal.setitimer(signal.ITIMER_REAL, 0)
            return
        pull["outcome"] = "INSPECT_MISMATCH"
        result.update(status="UNKNOWN", reason="PULL_DIGEST_UNVERIFIED")
    else:
        if outcome == "NONZERO_EXIT" and failure_class == "DOCKER_RATE_LIMITED":
            result.update(status="RATE_LIMITED", reason="PULL_RATE_LIMITED")
        else:
            result.update(status="UNKNOWN", reason={"NONZERO_EXIT": "PULL_FAILED", "TIMEOUT": "PULL_TIMEOUT", "ERROR": "PULL_ERROR", "STDERR_LIMIT_EXCEEDED": "PULL_STDERR_LIMIT_EXCEEDED"}.get(outcome, "PULL_ERROR"))


def expired_route(target_token, quota_token):
    return next((route for route, token in ((Route.TARGET, target_token), (Route.QUOTA, quota_token)) if token is not None and not token.live()), None)


def probe(result=None, with_watchdog=False):
    result = blank_result() if result is None else result
    try:
        if any(os.environ.get(name) for name in BLOCKED_ENV):
            result["reason"] = "ENVIRONMENT_OVERRIDE"
        elif not daemon_ready():
            result["reason"] = "DAEMON_UNVERIFIED"
        elif cache_hit():
            result.update(status="PASS", reason="CACHE_HIT", cacheHit=True)
        else:
            client = RegistryClient()
            target_ok, target_token = channel(result, Route.TARGET, client)
            if not target_ok:
                classify(result, Route.TARGET)
            else:
                quota_ok, quota_token = channel(result, Route.QUOTA, client)
                expired = expired_route(target_token, quota_token)
                if (quota_ok or pull_eligible(result)) and expired is not None:
                    result[expired.value].update(complete=False, reason="TOKEN_EXPIRED")
                    classify(result, expired)
                elif not quota_ok and pull_eligible(result):
                    # Tokens prove preconditions at launch. Their natural expiry
                    # during this longer pull does not negate a new local image.
                    bounded_pull(result, with_watchdog)
                elif not quota_ok:
                    classify(result, Route.QUOTA)
                else:
                    result.update(status="PASS", reason="READY")
    except Exception:
        if result["pull"]["attempted"]:
            result["pull"].update(outcome="ERROR", cacheVerified=False, failureClass="UNKNOWN_CLI_FAILURE")
            result.update(status="UNKNOWN", reason="PULL_ERROR")
        else:
            result.update(status="UNKNOWN", reason="INTERNAL_ERROR")
    result["checkedAt"] = utc_text(utc_now())
    return result


def parse_report_utc(value):
    if type(value) is not str or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if utc_text(parsed) == value else None
    except Exception:
        return None


def validate_rate_header(diagnostic):
    if type(diagnostic) is not dict or set(diagnostic) != DIAG_KEYS:
        return False
    if diagnostic == blank_rate_header():
        return True
    count, size, digest = (diagnostic[key] for key in ("occurrenceCount", "lengthBytes", "sha256"))
    if type(count) is not int or not 0 <= count <= 100 or type(size) is not int or not 0 <= size <= 16777216:
        return False
    if diagnostic["format"] not in DIAG_FORMATS or diagnostic["gateCompatibility"] not in DIAG_COMPATIBILITY:
        return False
    raw, policies = diagnostic["boundedRaw"], diagnostic["policies"]
    if type(policies) is not list or len(policies) > MAX_NUMERIC_POLICIES:
        return False
    for policy in policies:
        if type(policy) is not dict or set(policy) != {"value", "windowSeconds"} or type(policy["value"]) is not int or not 0 <= policy["value"] <= 9999999999:
            return False
        window = policy["windowSeconds"]
        if window is not None and (type(window) is not int or not 0 <= window <= 9999999999):
            return False
    if count == 0:
        return diagnostic == diagnose_rate_header(Response(200, ()), "ratelimit-limit")
    if type(digest) is not str or not re.fullmatch(r"[0-9a-f]{64}", digest):
        return False
    if count > 1:
        return raw is None and policies == [] and diagnostic["format"] == diagnostic["gateCompatibility"] == "DUPLICATE"
    if raw is not None:
        if type(raw) is not str or len(raw) > MAX_NUMERIC_RAW or any(ord(c) < 32 or ord(c) > 126 for c in raw) or sensitive_rate_text(raw):
            return False
        return diagnostic == diagnose_rate_header(Response(200, (("RateLimit-Limit", raw),)), "ratelimit-limit")
    if policies or diagnostic["gateCompatibility"] != "UNKNOWN_SYNTAX":
        return False
    if diagnostic["format"] == "TOO_LONG":
        return size > MAX_NUMERIC_RAW
    return diagnostic["format"] in ("NON_ASCII_OR_CONTROL", "REDACTED_SENSITIVE") and size > 0


def validate_rate_diagnostics(diagnostic):
    return (type(diagnostic) is dict and set(diagnostic) == {"firstFailedPredicate", "limit", "remaining"}
            and diagnostic["firstFailedPredicate"] in FAILED_PREDICATES
            and validate_rate_header(diagnostic["limit"]) and validate_rate_header(diagnostic["remaining"]))


def validate_channel(record, route):
    if type(record) is not dict or set(record) != CHANNEL_KEYS or type(record["complete"]) is not bool:
        return False
    if record["currentStage"] not in STAGES or record["reason"] not in CHANNEL_REASONS:
        return False
    if not validate_rate_diagnostics(record["rateDiagnostics"]):
        return False
    if record["currentStage"] == "TOKEN_GET" and record["rateDiagnostics"] != blank_rate_diagnostics():
        return False
    code = record["httpStatus"]
    if code is not None and (type(code) is not int or not 100 <= code <= 599):
        return False
    headers = record["headers"]
    if type(headers) is not dict or set(headers) != HEADER_KEYS or any(type(value) is not str or value not in HEADER_STATES for value in headers.values()):
        return False
    if headers["safety"] not in ("NOT_CHECKED", "VALID", "INVALID"):
        return False
    if headers["limit"] == "NOT_APPLICABLE" or headers["remaining"] == "NOT_APPLICABLE" or route is Route.QUOTA and headers["digest"] != "NOT_APPLICABLE":
        return False
    if record["currentStage"] == "NOT_STARTED":
        return record == blank_channel(route)
    if record["reason"] == "NOT_STARTED":
        return False
    if code is None and headers["safety"] != "NOT_CHECKED":
        return False
    if record["reason"] == "QUOTA_HEADERS_ABSENT":
        if route is not Route.QUOTA or code != 200 or record["currentStage"] not in ("INITIAL_HEAD", "AUTHENTICATED_HEAD") or headers["safety"] != "VALID" or headers["limit"] != "MISSING" or headers["remaining"] != "MISSING":
            return False
    if record["reason"] == "QUOTA_HEADER_PARTIAL" and sum(headers[key] == "MISSING" for key in ("limit", "remaining")) != 1:
        return False
    if record["complete"]:
        if code != 200 or record["currentStage"] not in ("INITIAL_HEAD", "AUTHENTICATED_HEAD") or headers["safety"] != "VALID":
            return False
        if route is Route.TARGET:
            return record["reason"] == "TARGET_VERIFIED" and headers["digest"] == "VALID" and ((headers["limit"] == headers["remaining"] == "MISSING") or (headers["limit"] == headers["remaining"] == "VALID"))
        return record["reason"] in ("QUOTA_AVAILABLE", "QUOTA_EXHAUSTED") and headers["limit"] == headers["remaining"] == "VALID"
    return record["reason"] not in ("TARGET_VERIFIED", "QUOTA_AVAILABLE", "QUOTA_EXHAUSTED")


def validate_report(report):
    """Pure fixed-schema/type/status consistency check; never performs I/O."""
    try:
        if type(report) is not dict or set(report) != REPORT_KEYS or type(report["schemaVersion"]) is not int or report["schemaVersion"] != 3:
            return False
        if len(json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")) + 1 > MAX_SERIALIZED_REPORT_BYTES:
            return False
        if report["image"] != IMAGE or report["digest"] != DIGEST or type(report["cacheHit"]) is not bool:
            return False
        if report["status"] not in ("PASS", "UNKNOWN", "RATE_LIMITED") or report["reason"] not in TOP_REASONS:
            return False
        checked = parse_report_utc(report["checkedAt"])
        if checked is None or any(not validate_channel(report[route.value], route) for route in Route):
            return False
        limit, remaining, window = (report[key] for key in ("limit", "remaining", "windowSeconds"))
        no_quota = limit is None and remaining is None and window is None
        valid_quota = type(limit) is int and type(remaining) is int and type(window) is int and 0 < limit <= 999999999 and 0 <= remaining <= limit and window == WINDOW_SECONDS
        if not no_quota and not valid_quota:
            return False
        target, quota = report["target"], report["quota"]
        pull = report["pull"]
        if type(pull) is not dict or set(pull) != PULL_KEYS or type(pull["attempted"]) is not bool or type(pull["cacheVerified"]) is not bool:
            return False
        if pull["currentStage"] not in PULL_STAGES or pull["outcome"] not in PULL_OUTCOMES or pull["failureClass"] not in PULL_FAILURE_CLASSES:
            return False
        code = pull["exitCode"]
        if code is not None and (type(code) is not int or not -128 <= code <= 255):
            return False
        if not pull["attempted"] and pull != blank_pull():
            return False
        if pull["attempted"]:
            if not pull_eligible(report):
                return False
            if pull["outcome"] == "SUCCESS":
                if pull["currentStage"] != "COMPLETE" or code != 0 or not pull["cacheVerified"] or report["reason"] != "PULL_SUCCEEDED" or report["status"] != "PASS" or pull["failureClass"] != "NONE":
                    return False
            elif pull["cacheVerified"]:
                return False
            elif pull["outcome"] == "NONZERO_EXIT":
                expected = "PULL_RATE_LIMITED" if pull["failureClass"] == "DOCKER_RATE_LIMITED" else "PULL_FAILED"
                if pull["currentStage"] != "PULL" or code is None or code == 0 or report["reason"] != expected or pull["failureClass"] not in ("DOCKER_RATE_LIMITED", "UNKNOWN_CLI_FAILURE"):
                    return False
            elif pull["outcome"] == "INSPECT_MISMATCH":
                if pull["currentStage"] != "VERIFY_CACHE" or code != 0 or report["reason"] != "PULL_DIGEST_UNVERIFIED" or pull["failureClass"] != "NONE":
                    return False
            elif pull["outcome"] == "STDERR_LIMIT_EXCEEDED":
                if pull["currentStage"] != "PULL" or code is not None or pull["failureClass"] != "STDERR_LIMIT_EXCEEDED" or report["reason"] != "PULL_STDERR_LIMIT_EXCEEDED":
                    return False
            elif pull["outcome"] in ("TIMEOUT", "ERROR", "INTERRUPTED"):
                expected = {"TIMEOUT": "PULL_TIMEOUT", "ERROR": "PULL_ERROR", "INTERRUPTED": "PULL_INTERRUPTED"}[pull["outcome"]]
                if pull["currentStage"] not in ("PULL", "VERIFY_CACHE") or report["reason"] != expected:
                    return False
                if pull["currentStage"] == "PULL" and code is not None or pull["currentStage"] == "VERIFY_CACHE" and code != 0:
                    return False
                expected_class = "UNKNOWN_CLI_FAILURE" if pull["outcome"] == "ERROR" else "NONE" if pull["currentStage"] == "VERIFY_CACHE" else "NOT_CHECKED"
                if pull["failureClass"] != expected_class:
                    return False
            else:
                return False
        elif report["reason"].startswith("PULL_"):
            return False
        if valid_quota and (quota["currentStage"] not in ("INITIAL_HEAD", "AUTHENTICATED_HEAD") or quota["httpStatus"] not in (200, 429) or quota["headers"]["limit"] != "VALID" or quota["headers"]["remaining"] != "VALID" or quota["headers"]["safety"] != "VALID"):
            return False
        if quota["complete"] and not valid_quota:
            return False
        if quota["reason"] == "QUOTA_AVAILABLE" and (not valid_quota or remaining <= 0) or quota["reason"] == "QUOTA_EXHAUSTED" and (not valid_quota or remaining != 0):
            return False
        retry = report["retryAfter"]
        if retry is not None:
            if type(retry) is not dict or all(record["httpStatus"] is None for record in (target, quota)):
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
        if report["cacheHit"]:
            return report["status"] == "PASS" and report["reason"] == "CACHE_HIT" and no_quota and retry is None and target == blank_channel(Route.TARGET) and quota == blank_channel(Route.QUOTA) and pull == blank_pull()
        if report["status"] == "PASS":
            if pull["attempted"]:
                return report["reason"] == "PULL_SUCCEEDED" and pull["outcome"] == "SUCCESS"
            return report["reason"] == "READY" and target["complete"] and quota["complete"] and valid_quota and remaining > 0
        if report["reason"] in ("CACHE_HIT", "READY"):
            return False
        if report["status"] == "RATE_LIMITED":
            if report["reason"] == "PULL_RATE_LIMITED":
                return pull["attempted"] and pull["outcome"] == "NONZERO_EXIT" and pull["failureClass"] == "DOCKER_RATE_LIMITED"
            if report["reason"] == "TARGET_QUOTA_EXHAUSTED":
                return target["httpStatus"] == 200 and target["reason"] == "TARGET_QUOTA_EXHAUSTED" and target["headers"]["limit"] == target["headers"]["remaining"] == "VALID" and no_quota and quota == blank_channel(Route.QUOTA)
            if report["reason"] == "QUOTA_EXHAUSTED":
                return target["complete"] and quota["complete"] and valid_quota and remaining == 0
            route = Route.TARGET if report["reason"] == "TARGET_RATE_LIMITED" else Route.QUOTA if report["reason"] == "QUOTA_RATE_LIMITED" else None
            return route is not None and report[route.value]["httpStatus"] == 429 and report[route.value]["reason"] == "HTTP_RATE_LIMITED"
        if report["reason"] in ("TARGET_RATE_LIMITED", "TARGET_QUOTA_EXHAUSTED", "QUOTA_RATE_LIMITED", "QUOTA_EXHAUSTED", "PULL_RATE_LIMITED"):
            return False
        return report["reason"] in ("DEADLINE", "INTERNAL_ERROR") or not (target["complete"] and quota["complete"])
    except Exception:
        return False


class DeadlineExpired(BaseException):
    pass


def alarm_expired(_signum, _frame):
    raise DeadlineExpired()


def mark_interruption(result, timed_out):
    result["status"] = "UNKNOWN"
    if result["pull"]["attempted"]:
        pull = result["pull"]
        if pull["currentStage"] == "COMPLETE" and pull["outcome"] == "SUCCESS" and pull["exitCode"] == 0 and pull["cacheVerified"]:
            result.update(status="PASS", reason="PULL_SUCCEEDED")
        elif pull["outcome"] in ("NONZERO_EXIT", "INSPECT_MISMATCH", "TIMEOUT", "ERROR", "STDERR_LIMIT_EXCEEDED"):
            result["reason"] = {"NONZERO_EXIT": "PULL_FAILED", "INSPECT_MISMATCH": "PULL_DIGEST_UNVERIFIED", "TIMEOUT": "PULL_TIMEOUT", "ERROR": "PULL_ERROR", "STDERR_LIMIT_EXCEEDED": "PULL_STDERR_LIMIT_EXCEEDED"}[pull["outcome"]]
            if pull["outcome"] == "NONZERO_EXIT" and pull["failureClass"] == "DOCKER_RATE_LIMITED":
                result.update(status="RATE_LIMITED", reason="PULL_RATE_LIMITED")
        else:
            if pull["exitCode"] == 0:
                pull["currentStage"] = "VERIFY_CACHE"
            pull.update(outcome="TIMEOUT" if timed_out else "INTERRUPTED", cacheVerified=False)
            result["reason"] = "PULL_TIMEOUT" if timed_out else "PULL_INTERRUPTED"
    else:
        result["reason"] = "DEADLINE" if timed_out else "INTERNAL_ERROR"
        for route in reversed(tuple(Route)):
            record = result[route.value]
            if record["currentStage"] != "NOT_STARTED" and record["reason"] == "NOT_STARTED":
                record.update(complete=False, reason="DEADLINE" if timed_out else "TRANSPORT_ERROR")
                break
    result["checkedAt"] = utc_text(utc_now())


def main(argv=None):
    result = blank_result()
    argv = sys.argv[1:] if argv is None else argv
    previous_handler, alarm_set = None, False
    try:
        if not argv:
            previous_handler = signal.signal(signal.SIGALRM, alarm_expired)
            signal.setitimer(signal.ITIMER_REAL, TOTAL_TIMEOUT)
            alarm_set = True
            result = probe(result, with_watchdog=True)
    except DeadlineExpired:
        mark_interruption(result, True)
    except KeyboardInterrupt:
        mark_interruption(result, False)
    except Exception:
        result = blank_result()
        result["reason"] = "INTERNAL_ERROR"
    finally:
        if alarm_set:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)
    if not validate_report(result):
        result = blank_result()
        result["reason"] = "INTERNAL_ERROR"
    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
