"""Offline contracts only: fake HTTPS, mocked Docker, real local Python children.

No test invokes a real Docker executable or makes any network/token request.
"""
import contextlib
import copy
import datetime as dt
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import unittest
from unittest import mock

import environment_image_precheck as p

NOW = dt.datetime(2026, 10, 9, 21, 0, 0, tzinfo=dt.timezone.utc)
SECRET = "TEST_PRIVATE_BEARER_SHOULD_NEVER_APPEAR_4ad9"
RAW_SECRET = "203.0.113.99 PRIVATE_RAW_ERROR https://forbidden.invalid/secret"
CHALLENGE = 'Bearer realm="https://auth.docker.io/token",service="registry.docker.io",scope="repository:unityci/editor:pull"'
PASS_HEADERS = (("Docker-Content-Digest", p.DIGEST), ("RateLimit-Limit", "100;w=21600"), ("RateLimit-Remaining", "20;w=21600"))


class FakeRaw:
    def __init__(self, status, headers=(), body=b""):
        self.status, self.headers, self.body = status, tuple(headers), body
        self.reads = []

    def getheaders(self):
        return self.headers

    def read(self, amount):
        self.reads.append(amount)
        return self.body[:amount]


def raw_token(value=None, headers=None):
    value = {"token": SECRET, "expires_in": 300, "issued_at": "2026-10-09T21:00:00Z"} if value is None else value
    body = json.dumps(value).encode()
    headers = (("Content-Type", "application/json"), ("Content-Length", str(len(body)))) if headers is None else headers
    return FakeRaw(200, headers, body)


class Transport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls, self.connections = [], []

    def connect(self, host, **kwargs):
        outer = self
        outer.connections.append((host, kwargs))
        response = outer.responses.pop(0)
        if isinstance(response, BaseException):
            raise response

        class Connection:
            def request(self, method, path, body, headers):
                outer.calls.append((host, method, path, body, dict(headers)))

            def getresponse(self):
                if isinstance(response, BaseException):
                    raise response
                return response

            def close(self):
                pass
        return Connection()


class OfflineCase(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(socket, "create_connection", side_effect=AssertionError("NETWORK_FORBIDDEN")))
        self.stack.enter_context(mock.patch.object(p, "utc_now", return_value=NOW))
        self.stack.enter_context(mock.patch.dict(os.environ, {name: "" for name in p.BLOCKED_ENV}))
        self.stack.enter_context(mock.patch.object(p, "daemon_ready", return_value=True))
        # Tests must opt in to a controlled cache byte result or local fake process.
        self.stack.enter_context(mock.patch.object(p, "inspect_cache_bytes", return_value=None))

    def exercise(self, responses, *, cache=False, main=False, argv=None):
        transport = Transport(responses)
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(p, "cache_hit", return_value=cache), mock.patch.object(p.http.client, "HTTPSConnection", side_effect=transport.connect), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            if main:
                code = p.main([] if argv is None else argv)
                result = json.loads(out.getvalue())
                self.assertEqual(code, 0 if result["status"] == "PASS" else 2)
            else:
                result = p.probe()
        self.assertTrue(p.validate_report(result))
        self.assertEqual(err.getvalue(), "")
        self.assertNotIn(SECRET, out.getvalue())
        self.assertNotIn(RAW_SECRET, out.getvalue())
        self.assertNotIn(SECRET, json.dumps(result))
        return result, transport

    def auth_flow(self, final=None, token=None, challenge=CHALLENGE, main=False):
        return self.exercise([FakeRaw(401, (("WWW-Authenticate", challenge),), RAW_SECRET.encode()), raw_token() if token is None else token, FakeRaw(200, PASS_HEADERS) if final is None else final], main=main)


class CacheTests(OfflineCase):
    def hit(self, value):
        with mock.patch.object(p, "inspect_cache_bytes", return_value=value):
            return p.cache_hit()

    def test_exact_json_digest_hit(self):
        self.assertTrue(self.hit(json.dumps([p.IMAGE]).encode()))

    def test_only_repo_digests_array_is_accepted(self):
        candidates = [None, "", p.IMAGE, {"RepoDigests": [p.IMAGE]}, [{"RepoDigests": [p.IMAGE]}], [], [p.DIGEST], ["docker.io/" + p.IMAGE], [p.IMAGE + "evil"], [p.IMAGE.upper()], [p.IMAGE, 1], [p.IMAGE, p.IMAGE]]
        for value in candidates:
            with self.subTest(value_type=type(value).__name__):
                self.assertFalse(self.hit(json.dumps(value).encode()))

    def test_substrings_invalid_utf8_and_trailing_text_do_not_hit(self):
        for value in (b"not-json", b"\xff", json.dumps([p.IMAGE]).encode() + b"garbage", json.dumps(["prefix" + p.IMAGE]).encode()):
            self.assertFalse(self.hit(value))

    def test_cache_hit_skips_all_registry_requests(self):
        report, transport = self.exercise([], cache=True, main=True)
        self.assertEqual(report["status"], "PASS")
        self.assertTrue(report["cacheHit"])
        self.assertIsNone(report["httpStatus"])
        self.assertEqual(transport.calls, [])

    def test_other_digest_never_leaks(self):
        self.assertTrue(self.hit(json.dumps([p.IMAGE, "other/repo@sha256:" + "f" * 64]).encode()))

    def test_cache_exception_is_not_echoed(self):
        with mock.patch.object(p, "inspect_cache_bytes", side_effect=OSError(RAW_SECRET)):
            self.assertFalse(p.cache_hit())


class DaemonTests(unittest.TestCase):
    def check(self, payload):
        with mock.patch.object(p, "docker_bytes", return_value=payload) as command:
            result = p.daemon_ready()
        command.assert_called_once_with(p.DOCKER_INFO_COMMAND)
        return result

    def test_only_three_exact_true_booleans_are_ready(self):
        valid = {"httpProxyEmpty": True, "httpsProxyEmpty": True, "mirrorsEmpty": True}
        self.assertTrue(self.check(json.dumps(valid).encode()))
        for key in valid:
            for bad in (False, 1, "true", None, SECRET):
                self.assertFalse(self.check(json.dumps(dict(valid, **{key: bad})).encode()))
            missing = dict(valid)
            del missing[key]
            self.assertFalse(self.check(json.dumps(missing).encode()))
        self.assertFalse(self.check(json.dumps(dict(valid, extra=True)).encode()))

    def test_unknown_or_duplicate_daemon_data_is_not_ready(self):
        for payload in (None, b"", b"[]", b"null", b"\xff", b"{}", b'{"httpProxyEmpty":false,"httpProxyEmpty":true,"httpsProxyEmpty":true,"mirrorsEmpty":true}'):
            self.assertFalse(self.check(payload))

    def test_daemon_error_is_not_ready(self):
        with mock.patch.object(p, "docker_bytes", side_effect=OSError(RAW_SECRET)):
            self.assertFalse(p.daemon_ready())

    def test_unknown_daemon_stops_before_cache_and_network(self):
        with mock.patch.dict(os.environ, {name: "" for name in p.BLOCKED_ENV}), mock.patch.object(p, "daemon_ready", return_value=False), mock.patch.object(p, "cache_hit", side_effect=AssertionError("cache forbidden")) as cache, mock.patch.object(p.http.client, "HTTPSConnection", side_effect=AssertionError("network forbidden")) as network:
            report = p.probe()
        self.assertEqual(report["status"], "UNKNOWN")
        self.assertTrue(p.validate_report(report))
        cache.assert_not_called()
        network.assert_not_called()

    def test_command_only_formats_empty_booleans_with_missing_mirror_guard(self):
        self.assertEqual(p.DOCKER_INFO_COMMAND[:5], ("/usr/bin/docker", "--host=unix:///var/run/docker.sock", "info", "--format", p.DOCKER_INFO_FORMAT))
        self.assertIn('{{eq .HTTPProxy ""}}', p.DOCKER_INFO_FORMAT)
        self.assertIn('{{eq .HTTPSProxy ""}}', p.DOCKER_INFO_FORMAT)
        self.assertIn('{{if .RegistryConfig}}', p.DOCKER_INFO_FORMAT)
        self.assertIn('(eq (printf "%T" .RegistryConfig.Mirrors) "[]string")', p.DOCKER_INFO_FORMAT)
        self.assertIn('{{else}}false{{end}}', p.DOCKER_INFO_FORMAT)

    def test_arbitrary_command_rejected_before_process(self):
        with mock.patch.object(p.subprocess, "Popen", side_effect=AssertionError("process forbidden")) as spawn:
            self.assertIsNone(p.docker_bytes(("/bin/sh", "-c", "anything")))
        spawn.assert_not_called()


class ProtocolTests(OfflineCase):
    def test_daemon_cache_then_registry_order(self):
        calls = []
        class Client:
            def head(self, token=None):
                calls.append("head")
                return p.Response(200, PASS_HEADERS)
        with mock.patch.object(p, "daemon_ready", side_effect=lambda: calls.append("daemon") or True), mock.patch.object(p, "cache_hit", side_effect=lambda: calls.append("cache") or False), mock.patch.object(p, "RegistryClient", Client):
            report = p.probe()
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(calls, ["daemon", "cache", "head"])

    def test_exact_head_get_head_sequence_and_scope(self):
        report, transport = self.auth_flow(main=True)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["remaining"], 20)
        expected = [(p.REGISTRY_HOST, "HEAD", p.MANIFEST_PATH), (p.AUTH_HOST, "GET", p.TOKEN_PATH), (p.REGISTRY_HOST, "HEAD", p.MANIFEST_PATH)]
        self.assertEqual([call[:3] for call in transport.calls], expected)
        self.assertTrue(all(call[3] is None for call in transport.calls))
        self.assertEqual(transport.calls[0][4], {"Accept": p.ACCEPT})
        self.assertEqual(transport.calls[1][4], {"Accept": "application/json"})
        self.assertEqual(transport.calls[2][4], {"Accept": p.ACCEPT, "Authorization": "Bearer " + SECRET})
        self.assertEqual(transport.connections, [(p.REGISTRY_HOST, {"timeout": p.HTTP_TIMEOUT}), (p.AUTH_HOST, {"timeout": p.HTTP_TIMEOUT}), (p.REGISTRY_HOST, {"timeout": p.HTTP_TIMEOUT})])
        self.assertNotIn("offline", p.TOKEN_PATH)
        self.assertNotIn("account", p.TOKEN_PATH)

    def test_first_head_can_pass_without_token(self):
        report, transport = self.exercise([FakeRaw(200, PASS_HEADERS)])
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(len(transport.calls), 1)

    def test_head_bodies_never_read_even_errors(self):
        for status in (200, 401, 429, 500):
            response = FakeRaw(status, PASS_HEADERS, RAW_SECRET.encode())
            self.exercise([response])
            self.assertEqual(response.reads, [])

    def test_429_first_head_is_rate_limited_no_token(self):
        report, transport = self.exercise([FakeRaw(429, (("Retry-After", "60"),), RAW_SECRET.encode())], main=True)
        self.assertEqual(report["status"], "RATE_LIMITED")
        self.assertEqual(report["retryAfter"], {"seconds": 60})
        self.assertEqual(len(transport.calls), 1)

    def test_429_final_head_is_rate_limited(self):
        report, transport = self.auth_flow(FakeRaw(429, body=RAW_SECRET.encode()))
        self.assertEqual(report["status"], "RATE_LIMITED")
        self.assertEqual(len(transport.calls), 3)

    def test_429_token_endpoint_stops_without_second_head(self):
        report, transport = self.auth_flow(token=FakeRaw(429, (("Retry-After", "60"),), RAW_SECRET.encode()))
        self.assertEqual(report["status"], "RATE_LIMITED")
        self.assertEqual(len(transport.calls), 2)

    def test_second_401_never_retries_token(self):
        report, transport = self.auth_flow(FakeRaw(401, (("WWW-Authenticate", CHALLENGE),)))
        self.assertEqual(report["status"], "UNKNOWN")
        self.assertEqual(len(transport.calls), 3)

    def test_arbitrary_redirects_are_not_followed(self):
        for status in (301, 302, 303, 307, 308):
            for position in (0, 1, 2):
                with self.subTest(status=status, position=position):
                    redirect = FakeRaw(status, (("Location", "https://forbidden.invalid/" + SECRET),), SECRET.encode())
                    responses = [FakeRaw(401, (("WWW-Authenticate", CHALLENGE),)), raw_token(), FakeRaw(200, PASS_HEADERS)]
                    responses[position] = redirect
                    report, transport = self.exercise(responses, main=True)
                    self.assertEqual(report["status"], "UNKNOWN")
                    self.assertEqual(len(transport.calls), position + 1)
                    self.assertEqual(redirect.reads, [])

    def test_unknown_status_stops(self):
        for status in (204, 400, 403, 404, 500, 503):
            report, transport = self.exercise([FakeRaw(status, PASS_HEADERS)])
            self.assertEqual(report["status"], "UNKNOWN")
            self.assertEqual(len(transport.calls), 1)

    def test_network_exception_is_sanitized_no_retry(self):
        for error in (TimeoutError(SECRET), OSError(RAW_SECRET), ValueError(SECRET), http_client_error()):
            report, transport = self.exercise([error], main=True)
            self.assertEqual(report["status"], "UNKNOWN")
            self.assertEqual(len(transport.connections), 1)

    def test_final_head_error_never_echoes_bearer(self):
        report, transport = self.exercise([FakeRaw(401, (("WWW-Authenticate", CHALLENGE),)), raw_token(), OSError(SECRET + RAW_SECRET)], main=True)
        self.assertEqual(report["status"], "UNKNOWN")
        self.assertEqual(len(transport.connections), 3)

    def test_environment_cannot_change_urls_or_add_credentials(self):
        malicious = {"DOCKER_AUTH_CONFIG": SECRET, "UNITY_IMAGE": "other/image", "REGISTRY_HOST": "forbidden.invalid", "TOKEN_URL": "https://forbidden.invalid", "DOCKER_USERNAME": SECRET, "DOCKER_PASSWORD": SECRET}
        with mock.patch.dict(os.environ, malicious):
            _, transport = self.auth_flow()
        self.assertEqual([call[0] for call in transport.calls], [p.REGISTRY_HOST, p.AUTH_HOST, p.REGISTRY_HOST])
        self.assertNotIn(SECRET, json.dumps(p.DOCKER_ENV))

    def test_proxy_and_daemon_overrides_stop_before_cache_or_network(self):
        for name in p.BLOCKED_ENV:
            with self.subTest(name=name), mock.patch.dict(os.environ, {name: SECRET}), mock.patch.object(p, "cache_hit", side_effect=AssertionError("cache must not run")) as cache:
                report = p.probe()
                self.assertTrue(p.validate_report(report))
                self.assertEqual(report["status"], "UNKNOWN")
                self.assertIsNone(report["httpStatus"])
                self.assertNotIn(SECRET, json.dumps(report))
                cache.assert_not_called()


def http_client_error():
    return p.http.client.BadStatusLine(RAW_SECRET)


class ChallengeTests(OfflineCase):
    def test_valid_parameter_reordering(self):
        value = 'Bearer scope="repository:unityci/editor:pull", service="registry.docker.io", realm="https://auth.docker.io/token"'
        report, transport = self.auth_flow(challenge=value)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(len(transport.calls), 3)

    def test_malicious_or_ambiguous_challenges_are_rejected(self):
        values = [CHALLENGE.replace("auth.docker.io", "evil.invalid"), CHALLENGE.replace("https://", "http://"), CHALLENGE.replace("registry.docker.io", "evil.invalid"), CHALLENGE.replace(":pull\"", ":pull,push\""), CHALLENGE.replace("unityci/editor", "other/repo"), CHALLENGE + ',offline_token="true"', CHALLENGE + ',scope="repository:unityci/editor:pull"', CHALLENGE + ',Bearer realm="https://evil.invalid"', CHALLENGE.replace("Bearer ", "Basic "), CHALLENGE.replace('/token"', '/token?secret=x"'), CHALLENGE.replace('/token"', '/token/"'), CHALLENGE.replace('/token"', '/token#x"'), CHALLENGE.replace('scope=', 'realm='), CHALLENGE + "\r\nX-Leak: " + SECRET, CHALLENGE + " ", "", SECRET]
        for value in values:
            with self.subTest(case=values.index(value)):
                report, transport = self.auth_flow(challenge=value)
                self.assertEqual(report["status"], "UNKNOWN")
                self.assertEqual(len(transport.calls), 1)

    def test_duplicate_www_authenticate_rejected(self):
        report, transport = self.exercise([FakeRaw(401, (("WWW-Authenticate", CHALLENGE), ("www-authenticate", CHALLENGE)))])
        self.assertEqual(report["status"], "UNKNOWN")
        self.assertEqual(len(transport.calls), 1)


class QuotaTests(OfflineCase):
    def result(self, headers):
        return self.exercise([FakeRaw(200, headers)])[0]

    def test_every_required_header_is_required(self):
        for index in range(3):
            report = self.result(PASS_HEADERS[:index] + PASS_HEADERS[index + 1:])
            self.assertEqual(report["status"], "UNKNOWN")

    def test_unlimited_without_headers_is_unknown(self):
        self.assertEqual(self.result(PASS_HEADERS[:1])["status"], "UNKNOWN")

    def test_wrong_digest_is_unknown(self):
        for value in (p.DIGEST + "evil", p.DIGEST.upper(), p.IMAGE, "sha256:" + "0" * 64, " " + p.DIGEST):
            self.assertEqual(self.result((("Docker-Content-Digest", value),) + PASS_HEADERS[1:])["status"], "UNKNOWN")

    def test_unknown_quota_formats_rejected(self):
        invalid = ["20", "20;w=60", "20;w=21600, 10;w=60", "20; w=21600", "020;w=21600", "-1;w=21600", "2.0;w=21600", "1000000000;w=21600", "101;w=21600", "20;w=21600;other=x", "20;w=21600\r\nLeak: " + SECRET]
        for value in invalid:
            self.assertEqual(self.result(PASS_HEADERS[:2] + (("RateLimit-Remaining", value),))["status"], "UNKNOWN")

    def test_zero_remaining_is_rate_limited(self):
        report = self.result(PASS_HEADERS[:2] + (("RateLimit-Remaining", "0;w=21600"),))
        self.assertEqual(report["status"], "RATE_LIMITED")
        self.assertEqual(report["remaining"], 0)

    def test_429_retains_only_valid_unique_quota(self):
        for remaining in (0, 20):
            headers = PASS_HEADERS[:2] + (("RateLimit-Remaining", str(remaining) + ";w=21600"),)
            report, _ = self.exercise([FakeRaw(429, headers)])
            self.assertEqual(report["status"], "RATE_LIMITED")
            self.assertEqual((report["limit"], report["remaining"], report["windowSeconds"]), (100, remaining, 21600))
        report, _ = self.exercise([FakeRaw(429, PASS_HEADERS + (PASS_HEADERS[1],))])
        self.assertEqual(report["status"], "RATE_LIMITED")
        self.assertIsNone(report["limit"])

    def test_zero_limit_is_unknown(self):
        self.assertEqual(self.result((PASS_HEADERS[0], ("RateLimit-Limit", "0;w=21600"), ("RateLimit-Remaining", "0;w=21600")))["status"], "UNKNOWN")

    def test_different_windows_are_unknown(self):
        self.assertEqual(self.result((PASS_HEADERS[0], ("RateLimit-Limit", "100;w=60"), PASS_HEADERS[2]))["status"], "UNKNOWN")

    def test_case_insensitive_header_names(self):
        self.assertEqual(self.result(tuple((key.swapcase(), value) for key, value in PASS_HEADERS))["status"], "PASS")

    def test_duplicate_security_headers_never_pass(self):
        for key, value in PASS_HEADERS:
            self.assertEqual(self.result(PASS_HEADERS + ((key.lower(), value),))["status"], "UNKNOWN")
        for key in p.CRITICAL_HEADERS - {key.lower() for key, _ in PASS_HEADERS}:
            self.assertEqual(self.result(PASS_HEADERS + ((key, "0"), (key.upper(), "0")))["status"], "UNKNOWN")

    def test_ip_unknown_headers_and_body_not_in_report(self):
        report = self.result(PASS_HEADERS + (("docker-ratelimit-source", "203.0.113.99"), ("X-Private", RAW_SECRET)))
        self.assertEqual(report["status"], "PASS")
        self.assertNotIn("203.0.113.99", json.dumps(report))
        self.assertNotIn("X-Private", json.dumps(report))


class TokenTests(OfflineCase):
    def rejects(self, value):
        report, transport = self.auth_flow(token=raw_token(value), main=True)
        self.assertEqual(report["status"], "UNKNOWN")
        self.assertEqual(len(transport.calls), 2)

    def test_access_token_alias_accepted(self):
        report, _ = self.auth_flow(token=raw_token({"access_token": SECRET, "expires_in": 300}))
        self.assertEqual(report["status"], "PASS")

    def test_identical_aliases_accepted(self):
        report, _ = self.auth_flow(token=raw_token({"token": SECRET, "access_token": SECRET, "expires_in": 300}))
        self.assertEqual(report["status"], "PASS")

    def test_mismatched_token_aliases_rejected(self):
        self.rejects({"token": SECRET, "access_token": "different", "expires_in": 300})

    def test_token_must_be_bounded_bearer_characters(self):
        for token in (None, 1, [], "", "x" * (p.MAX_TOKEN_LENGTH + 1), SECRET + "\r\nX-Evil: 1", "token with spaces", "密钥", "prefix:token"):
            self.rejects({"token": token, "expires_in": 300})

    def test_explicit_short_lifetime_required(self):
        for lifetime in (None, True, "300", 0, -1, 59, 601, 300.0, 999999999999):
            self.rejects({"token": SECRET, "expires_in": lifetime})
        self.rejects({"token": SECRET})

    def test_short_lifetime_bounds(self):
        for lifetime in (60, 600):
            report, _ = self.auth_flow(token=raw_token({"token": SECRET, "expires_in": lifetime}))
            self.assertEqual(report["status"], "PASS")

    def test_refresh_offline_and_unknown_fields_rejected(self):
        for key in ("refresh_token", "offline_token", "account", "unexpected"):
            self.rejects({"token": SECRET, "expires_in": 300, key: SECRET})

    def test_issued_at_stale_future_or_malformed_rejected(self):
        for issued in ("2026-10-09T20:55:00Z", "2026-10-09T21:01:01Z", "2026-10-09T21:00:00+00:00", "2026-13-09T21:00:00Z", 1, None, SECRET):
            self.rejects({"token": SECRET, "expires_in": 300, "issued_at": issued})

    def test_fractional_issued_at_accepted(self):
        report, _ = self.auth_flow(token=raw_token({"token": SECRET, "expires_in": 300, "issued_at": "2026-10-09T21:00:00.123456789Z"}))
        self.assertEqual(report["status"], "PASS")

    def test_duplicate_json_fields_rejected(self):
        body = ('{"token":"' + SECRET + '","token":"evil","expires_in":300}').encode()
        report, transport = self.auth_flow(token=FakeRaw(200, (("Content-Type", "application/json"),), body))
        self.assertEqual(report["status"], "UNKNOWN")
        self.assertEqual(len(transport.calls), 2)

    def test_malformed_or_nonobject_json_rejected(self):
        for body in (b"not-json", b"\xff", b"[]", b"null", b"1", b"{\"token\": NaN}"):
            report, transport = self.auth_flow(token=FakeRaw(200, (("Content-Type", "application/json"),), body))
            self.assertEqual(report["status"], "UNKNOWN")
            self.assertEqual(len(transport.calls), 2)

    def test_body_is_bounded_even_without_content_length(self):
        raw = FakeRaw(200, (("Content-Type", "application/json"),), b"x" * (p.MAX_TOKEN_BODY + 200))
        report, _ = self.auth_flow(token=raw)
        self.assertEqual(raw.reads, [p.MAX_TOKEN_BODY + 1])
        self.assertEqual(report["status"], "UNKNOWN")

    def test_oversize_or_ambiguous_content_length_not_read(self):
        for length in (str(p.MAX_TOKEN_BODY + 1), "-1", "0001", "1, 2", RAW_SECRET):
            raw = FakeRaw(200, (("Content-Type", "application/json"), ("Content-Length", length)), SECRET.encode())
            report, _ = self.auth_flow(token=raw)
            self.assertEqual(report["status"], "UNKNOWN")
            self.assertEqual(raw.reads, [])

    def test_content_length_mismatch_rejected(self):
        raw = raw_token(headers=(("Content-Type", "application/json"), ("Content-Length", "1")))
        report, _ = self.auth_flow(token=raw)
        self.assertEqual(report["status"], "UNKNOWN")

    def test_duplicate_token_headers_rejected(self):
        for key in ("Content-Type", "Content-Length", "Content-Encoding", "Transfer-Encoding"):
            raw = raw_token()
            raw.headers += ((key, "x"), (key.lower(), "x"))
            report, _ = self.auth_flow(token=raw)
            self.assertEqual(report["status"], "UNKNOWN")
            self.assertEqual(raw.reads, [])

    def test_compressed_or_nonjson_token_body_rejected(self):
        for headers in ((), (("Content-Type", "text/plain"),), (("Content-Type", "application/json"), ("Content-Encoding", "gzip"))):
            report, _ = self.auth_flow(token=raw_token(headers=headers))
            self.assertEqual(report["status"], "UNKNOWN")

    def test_ambiguous_transfer_encoding_rejected(self):
        for headers in ((("Content-Type", "application/json"), ("Transfer-Encoding", "gzip")), (("Content-Type", "application/json"), ("Transfer-Encoding", "chunked"), ("Content-Length", "1"))):
            report, _ = self.auth_flow(token=raw_token(headers=headers))
            self.assertEqual(report["status"], "UNKNOWN")


class RetryTests(OfflineCase):
    def test_retry_after_utc_is_normalized(self):
        report, _ = self.exercise([FakeRaw(429, (("Retry-After", "Fri, 09 Oct 2026 21:01:00 GMT"),))])
        self.assertEqual(report["retryAfter"], {"utc": "2026-10-09T21:01:00Z"})

    def test_untrusted_retry_after_not_echoed(self):
        for value in (RAW_SECRET, SECRET, "-1", "01", "604801", "1.5", "Fri, 09 Oct 2026 20:59:00 GMT", "Sat, 09 Oct 2026 21:01:00 GMT", "Fri, 09 Oct 2026 21:01:00 PST"):
            report, _ = self.exercise([FakeRaw(429, (("Retry-After", value),))])
            self.assertEqual(report["status"], "RATE_LIMITED")
            self.assertIsNone(report["retryAfter"])

    def test_duplicate_retry_after_is_unknown_on_success(self):
        report, _ = self.exercise([FakeRaw(200, PASS_HEADERS + (("Retry-After", "1"), ("retry-after", "1")))])
        self.assertEqual(report["status"], "UNKNOWN")

    def test_duplicate_retry_after_on_429_retains_429_without_retry_data(self):
        report, _ = self.exercise([FakeRaw(429, (("Retry-After", "1"), ("retry-after", "1")))])
        self.assertEqual(report["status"], "RATE_LIMITED")
        self.assertIsNone(report["retryAfter"])


class ReportTests(OfflineCase):
    def test_schema_is_fixed(self):
        report, _ = self.exercise([FakeRaw(200, PASS_HEADERS)])
        self.assertEqual(set(report), p.REPORT_KEYS)
        self.assertEqual(report["checkedAt"], "2026-10-09T21:00:00Z")

    def test_report_validator_is_pure(self):
        report = p.blank_result()
        with mock.patch.object(p, "utc_now", side_effect=AssertionError("clock access")), mock.patch.object(p, "cache_hit", side_effect=AssertionError("cache access")):
            self.assertTrue(p.validate_report(report))

    def test_missing_and_extra_keys_rejected(self):
        report = p.blank_result()
        for key in p.REPORT_KEYS:
            bad = dict(report)
            del bad[key]
            self.assertFalse(p.validate_report(bad))
        report["raw"] = SECRET
        self.assertFalse(p.validate_report(report))

    def test_field_types_and_fixed_values_rejected(self):
        report = p.blank_result()
        bad_values = {"schemaVersion": [True, "1", 2], "image": [p.IMAGE + "evil", SECRET], "digest": [p.DIGEST.upper(), SECRET], "status": [SECRET, "pass"], "cacheHit": [1, None], "httpStatus": [True, "200", 99, 600], "checkedAt": [SECRET, "2026-10-09T21:00:00+00:00", "2026-13-09T21:00:00Z", "2026-10-09T21:00:00.00Z"], "limit": [0, True, 10], "remaining": [-1, True, 0], "windowSeconds": [0, "21600", 21600], "retryAfter": [SECRET, {"seconds": True}, {"raw": SECRET}]}
        for key, values in bad_values.items():
            for value in values:
                bad = dict(report, **{key: value})
                self.assertFalse(p.validate_report(bad), key)

    def test_status_consistency(self):
        for status in ("PASS", "RATE_LIMITED"):
            self.assertFalse(p.validate_report(dict(p.blank_result(), status=status)))
        self.assertFalse(p.validate_report(dict(p.blank_result(), cacheHit=True)))
        self.assertFalse(p.validate_report(dict(p.blank_result(), httpStatus=429)))
        report, _ = self.exercise([FakeRaw(200, PASS_HEADERS)])
        for updates in ({"status": "UNKNOWN"}, {"status": "RATE_LIMITED"}, {"cacheHit": True}, {"httpStatus": 201}, {"remaining": 0}, {"remaining": 101}, {"windowSeconds": 60}, {"limit": 1000000000}):
            self.assertFalse(p.validate_report(dict(report, **updates)))

    def test_report_input_remains_unchanged(self):
        report = dict(p.blank_result(), httpStatus=429, status="RATE_LIMITED", retryAfter={"seconds": 10})
        before = copy.deepcopy(report)
        self.assertTrue(p.validate_report(report))
        self.assertEqual(report, before)

    def test_no_cli_arguments_allowed_or_echoed(self):
        for args in (["--image", SECRET], ["--url", "https://forbidden.invalid/"], ["--docker", "evil"], ["--output", "/tmp/evil"], ["--help"]):
            report, transport = self.exercise([], main=True, argv=args)
            self.assertEqual(report["status"], "UNKNOWN")
            self.assertEqual(transport.calls, [])


class LocalProcessTests(unittest.TestCase):
    """Execute real Python children while forcibly denying all network/Docker I/O."""
    def local_inspect(self, code, timeout=None, command=None):
        real_popen = subprocess.Popen
        launched = []
        expected_command = p.DOCKER_COMMAND if command is None else command

        def spawn(command, **kwargs):
            self.assertEqual(command, expected_command)
            self.assertEqual(kwargs["env"], p.DOCKER_ENV)
            self.assertEqual(kwargs["stderr"], subprocess.DEVNULL)
            self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
            self.assertNotIn("shell", kwargs)
            child = real_popen([sys.executable, "-c", code], **kwargs)
            launched.append(child)
            return child

        with mock.patch.object(p.subprocess, "Popen", side_effect=spawn), mock.patch.object(p, "DOCKER_TIMEOUT", p.DOCKER_TIMEOUT if timeout is None else timeout):
            result = p.docker_bytes(expected_command)
        self.assertEqual(len(launched), 1)
        self.assertIsNotNone(launched[0].poll())
        return result

    def test_real_local_child_exact_cache_json(self):
        output = json.dumps([p.IMAGE]).encode() + b"\n"
        self.assertEqual(self.local_inspect("import sys; sys.stdout.buffer.write(" + repr(output) + ")"), output)

    def test_real_local_child_daemon_boolean_json(self):
        output = b'{"httpProxyEmpty":true,"httpsProxyEmpty":true,"mirrorsEmpty":true}\n'
        self.assertEqual(self.local_inspect("import sys; sys.stdout.buffer.write(" + repr(output) + ")", command=p.DOCKER_INFO_COMMAND), output)

    def test_real_local_child_failure_discards_stderr(self):
        self.assertIsNone(self.local_inspect("import sys; sys.stderr.write(" + repr(RAW_SECRET) + "); sys.exit(1)"))

    def test_real_local_child_oversized_output_is_killed(self):
        self.assertIsNone(self.local_inspect("import os,time; os.write(1,b'x'*1000000); time.sleep(10)"))

    def test_real_local_child_timeout_is_killed(self):
        self.assertIsNone(self.local_inspect("import time; time.sleep(10)", timeout=0.05))

    def run_cli_child(self, mode):
        script = r'''
import contextlib,datetime,importlib.util,io,json,os,socket,subprocess,sys,time
from unittest import mock
spec=importlib.util.spec_from_file_location("environment_image_precheck",sys.argv[1])
p=importlib.util.module_from_spec(spec);sys.modules[spec.name]=p;spec.loader.exec_module(p)
p.daemon_ready=lambda: True
def forbidden(*a,**k): raise AssertionError("NETWORK_OR_DOCKER_FORBIDDEN")
socket.create_connection=forbidden
subprocess.Popen=forbidden
secret="TEST_PRIVATE_BEARER_SHOULD_NEVER_APPEAR_4ad9"
mode=sys.argv[2]
if mode=="pass":
    p.cache_hit=lambda: True
elif mode=="error":
    p.cache_hit=lambda: False
    class Client:
        def head(self,*a): raise OSError(secret)
    p.RegistryClient=Client
elif mode=="alarm":
    p.TOTAL_TIMEOUT=0.05
    def blocked(): time.sleep(10)
    p.inspect_cache_bytes=blocked
elif mode=="bad-report":
    p.probe=lambda: dict(p.blank_result(),status="PASS",raw=secret)
elif mode=="exception":
    def broken(): raise RuntimeError(secret)
    p.probe=broken
elif mode.startswith("auth"):
    p.cache_hit=lambda: False
    class Client:
        def __init__(self): self.calls=0
        def head(self,token=None):
            self.calls+=1
            if self.calls==1:
                if token is not None: raise AssertionError("unexpected token")
                return p.Response(401,(("WWW-Authenticate",'Bearer realm="https://auth.docker.io/token",service="registry.docker.io",scope="repository:unityci/editor:pull"'),))
            if self.calls!=2 or token!=secret: raise AssertionError("invalid call count or token")
            if mode=="autherror": raise OSError(secret)
            if mode=="authredirect": return p.Response(307,(("Location","https://forbidden.invalid/"+secret),))
            return p.Response(200,(("Docker-Content-Digest",p.DIGEST),("RateLimit-Limit","100;w=21600"),("RateLimit-Remaining","1;w=21600")))
        def anonymous_token(self):
            return p.Response(200,(("Content-Type","application/json"),),json.dumps({"token":secret,"expires_in":300}).encode())
    p.RegistryClient=Client
else:
    p.cache_hit=lambda: False
    class Client:
        def head(self,*a): return p.Response(429,(("Retry-After","60"),))
    p.RegistryClient=Client
sys.exit(p.main([]))
'''
        return subprocess.run([sys.executable, "-c", script, str(Path(p.__file__)), mode], capture_output=True, text=True, timeout=5, env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent"})

    def test_real_cli_pass_and_nonpass_exit_and_json_contract(self):
        for mode in ("pass", "limited", "error", "bad-report", "exception", "alarm", "authpass", "autherror", "authredirect"):
            with self.subTest(mode=mode):
                result = self.run_cli_child(mode)
                self.assertEqual(result.returncode, 0 if mode in ("pass", "authpass") else 2)
                self.assertEqual(result.stderr, "")
                self.assertEqual(len(result.stdout.splitlines()), 1)
                self.assertNotIn(SECRET, result.stdout + result.stderr)
                self.assertNotIn(RAW_SECRET, result.stdout + result.stderr)
                report = json.loads(result.stdout)
                self.assertTrue(p.validate_report(report))
                self.assertEqual(report["status"], "PASS" if mode in ("pass", "authpass") else "RATE_LIMITED" if mode == "limited" else "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
