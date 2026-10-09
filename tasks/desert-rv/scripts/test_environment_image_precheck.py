"""Offline HTTP contracts and real local Python child tests. No Docker/network I/O.

Each HTTP fixture goes through RegistryClient and its actual fixed request builder;
HTTPSConnection alone is substituted. Local children also forbid socket/Docker I/O.
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
REAL_CACHE_HIT = p.cache_hit

NOW = dt.datetime(2026, 10, 9, 21, 0, 0, tzinfo=p.UTC)
SECRET = "TEST_BEARER_TARGET_MUST_NOT_LEAK"
QUOTA_SECRET = "TEST_BEARER_PREVIEW_MUST_NOT_LEAK"
RAW_SECRET = "203.0.113.99 PRIVATE_ERROR https://forbidden.invalid/secret"
TARGET_HEADERS = (("Docker-Content-Digest", p.DIGEST),)
QUOTA_HEADERS = (("RateLimit-Limit", "100;w=21600"), ("RateLimit-Remaining", "20;w=21600"))


class Raw:
    def __init__(self, status, headers=(), body=b""):
        self.status, self.headers, self.body = status, tuple(headers), body
        self.reads = []
    def getheaders(self): return self.headers
    def read(self, amount):
        self.reads.append(amount)
        return self.body[:amount]


def challenge(route):
    return 'Bearer realm="https://auth.docker.io/token",service="registry.docker.io",scope="' + p.ROUTES[route][2] + '"'


def unauthorized(route):
    return Raw(401, (("WWW-Authenticate", challenge(route)),))


def token_response(token=SECRET, value=None, headers=None):
    payload = {"token": token, "expires_in": 3600} if value is None else value
    body = json.dumps(payload).encode()
    headers = (("Content-Type", "application/json"), ("Content-Length", str(len(body)))) if headers is None else headers
    return Raw(200, headers, body)


def target(): return Raw(200, TARGET_HEADERS)
def quota(): return Raw(200, QUOTA_HEADERS)


class Transport:
    def __init__(self, responses):
        self.responses, self.calls, self.connections = list(responses), [], []
    def connect(self, host, **kwargs):
        self.connections.append((host, kwargs))
        response = self.responses.pop(0)
        if callable(response): response = response()
        if isinstance(response, BaseException): raise response
        outer = self
        class Connection:
            def request(self, method, path, body, headers): outer.calls.append((host, method, path, body, dict(headers)))
            def getresponse(self): return response
            def close(self): pass
        return Connection()


class OfflineCase(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.clock = [NOW]
        self.stack.enter_context(mock.patch.object(socket, "create_connection", side_effect=AssertionError("NETWORK_FORBIDDEN")))
        self.stack.enter_context(mock.patch.object(p.subprocess, "Popen", side_effect=AssertionError("DOCKER_FORBIDDEN")))
        self.stack.enter_context(mock.patch.object(p, "utc_now", side_effect=lambda: self.clock[0]))
        self.stack.enter_context(mock.patch.dict(os.environ, {name: "" for name in p.BLOCKED_ENV}))
        self.stack.enter_context(mock.patch.object(p, "daemon_ready", return_value=True))
        self.stack.enter_context(mock.patch.object(p, "cache_hit", return_value=False))
        self.pull_mock = self.stack.enter_context(mock.patch.object(p, "run_fixed_pull", return_value=("NONZERO_EXIT", 1, "UNKNOWN_CLI_FAILURE")))

    def exercise(self, responses, main=False, argv=None, cache=False, cache_after_pull=False):
        transport, out, err = Transport(responses), io.StringIO(), io.StringIO()
        self.pull_mock.reset_mock()
        cache_values = iter((cache, cache_after_pull))
        def cache_check():
            value = next(cache_values)
            return value() if callable(value) else value
        with mock.patch.object(p, "cache_hit", side_effect=cache_check), mock.patch.object(p.http.client, "HTTPSConnection", side_effect=transport.connect), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            if main:
                code = p.main([] if argv is None else argv)
                report = json.loads(out.getvalue())
                self.assertEqual(code, 0 if report["status"] == "PASS" else 2)
            else:
                report = p.probe()
        self.assertTrue(p.validate_report(report), json.dumps(report))
        self.assertEqual(err.getvalue(), "")
        for secret in (SECRET, QUOTA_SECRET, RAW_SECRET):
            self.assertNotIn(secret, out.getvalue() + err.getvalue() + json.dumps(report))
        return report, transport

    def auth(self, target_response=None, quota_response=None, target_token=None, quota_token=None, main=False):
        return self.exercise([unauthorized(p.Route.TARGET), token_response() if target_token is None else target_token, target() if target_response is None else target_response, unauthorized(p.Route.QUOTA), token_response(QUOTA_SECRET) if quota_token is None else quota_token, quota() if quota_response is None else quota_response], main=main)


class FlowTests(OfflineCase):
    def test_target_without_quota_and_preview_positive_pass(self):
        report, transport = self.exercise([target(), quota()], main=True)
        self.assertEqual((report["status"], report["reason"]), ("PASS", "READY"))
        self.assertEqual(report["remaining"], 20)
        self.assertEqual(report["target"]["headers"]["limit"], "MISSING")
        self.assertEqual(len(transport.calls), 2)

    def test_exact_two_auth_routes_methods_and_tokens(self):
        report, transport = self.auth(main=True)
        self.assertEqual(report["status"], "PASS")
        expected = [(p.REGISTRY_HOST, "HEAD", p.ROUTES[p.Route.TARGET][0]), (p.AUTH_HOST, "GET", p.ROUTES[p.Route.TARGET][1]), (p.REGISTRY_HOST, "HEAD", p.ROUTES[p.Route.TARGET][0]), (p.REGISTRY_HOST, "HEAD", p.ROUTES[p.Route.QUOTA][0]), (p.AUTH_HOST, "GET", p.ROUTES[p.Route.QUOTA][1]), (p.REGISTRY_HOST, "HEAD", p.ROUTES[p.Route.QUOTA][0])]
        self.assertEqual([call[:3] for call in transport.calls], expected)
        for index, call in enumerate(transport.calls):
            self.assertIsNone(call[3])
            if index not in (2, 5): self.assertNotIn("Authorization", call[4])
        self.assertEqual(transport.calls[2][4]["Authorization"], "Bearer " + SECRET)
        self.assertEqual(transport.calls[5][4]["Authorization"], "Bearer " + QUOTA_SECRET)
        self.assertTrue(all(kwargs == {"timeout": p.HTTP_TIMEOUT} for _, kwargs in transport.connections))
        self.assertEqual(report["target"]["currentStage"], "AUTHENTICATED_HEAD")
        self.assertEqual(report["quota"]["currentStage"], "AUTHENTICATED_HEAD")

    def test_cache_hit_skips_both_routes(self):
        report, transport = self.exercise([], main=True, cache=True)
        self.assertEqual((report["status"], report["reason"]), ("PASS", "CACHE_HIT"))
        self.assertEqual(transport.calls, [])

    def test_daemon_cache_target_preview_order(self):
        calls = []
        class Client:
            def head(self, route, token=None):
                calls.append(route.value)
                return p.Response(200, TARGET_HEADERS if route is p.Route.TARGET else QUOTA_HEADERS)
        with mock.patch.object(p, "daemon_ready", side_effect=lambda: calls.append("daemon") or True), mock.patch.object(p, "cache_hit", side_effect=lambda: calls.append("cache") or False), mock.patch.object(p, "RegistryClient", Client):
            report = p.probe()
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(calls, ["daemon", "cache", "target", "quota"])

    def test_no_manifest_body_read(self):
        for status in (200, 401, 429, 500):
            raw = Raw(status, TARGET_HEADERS, RAW_SECRET.encode())
            self.exercise([raw, quota()])
            self.assertEqual(raw.reads, [])

    def test_no_redirect_follow_at_any_request(self):
        for code in (301, 302, 303, 307, 308):
            for position in range(6):
                with self.subTest(code=code, position=position):
                    fixtures = [unauthorized(p.Route.TARGET), token_response(), target(), unauthorized(p.Route.QUOTA), token_response(QUOTA_SECRET), quota()]
                    fixtures[position] = Raw(code, (("Location", "https://forbidden.invalid/" + SECRET),), SECRET.encode())
                    report, transport = self.exercise(fixtures, main=True)
                    self.assertEqual(report["status"], "UNKNOWN")
                    self.assertEqual(len(transport.calls), position + 1)
                    self.assertEqual(fixtures[position].reads, [])

    def test_transport_error_clears_token_200_in_target(self):
        report, _ = self.auth(target_response=TimeoutError(SECRET), main=True)
        self.assertEqual(report["reason"], "TARGET_TRANSPORT_ERROR")
        self.assertEqual(report["target"]["currentStage"], "AUTHENTICATED_HEAD")
        self.assertIsNone(report["target"]["httpStatus"])
        self.assertFalse(report["target"]["complete"])
        self.assertEqual(report["quota"]["currentStage"], "NOT_STARTED")

    def test_transport_error_clears_token_200_in_preview(self):
        report, _ = self.auth(quota_response=OSError(RAW_SECRET), main=True)
        self.assertEqual(report["reason"], "QUOTA_TRANSPORT_ERROR")
        self.assertIsNone(report["quota"]["httpStatus"])
        self.assertTrue(report["target"]["complete"])

    def test_initial_errors_report_correct_route(self):
        for fixtures, route in (([TimeoutError(SECRET)], "target"), ([target(), OSError(RAW_SECRET)], "quota")):
            report, _ = self.exercise(fixtures)
            self.assertEqual(report["reason"], route.upper() + "_TRANSPORT_ERROR")
            self.assertIsNone(report[route]["httpStatus"])

    def test_token_errors_clear_initial_401(self):
        for fixtures, route in (([unauthorized(p.Route.TARGET), TimeoutError(SECRET)], "target"), ([target(), unauthorized(p.Route.QUOTA), OSError(RAW_SECRET)], "quota")):
            report, _ = self.exercise(fixtures)
            self.assertEqual(report[route]["currentStage"], "TOKEN_GET")
            self.assertIsNone(report[route]["httpStatus"])
            self.assertFalse(report[route]["complete"])

    def test_second_401_is_auth_failure_without_loop(self):
        for route in p.Route:
            report, transport = self.auth(**({"target_response": unauthorized(route)} if route is p.Route.TARGET else {"quota_response": unauthorized(route)}))
            self.assertEqual(report["reason"], route.value.upper() + "_AUTH_FAILED")
            self.assertEqual(len(transport.calls), 3 if route is p.Route.TARGET else 6)

    def test_token_200_is_not_head_success(self):
        report, transport = self.auth(target_token=token_response(value={"expires_in": 3600}))
        self.assertEqual(report["reason"], "TARGET_AUTH_FAILED")
        self.assertEqual(report["target"]["httpStatus"], 200)
        self.assertEqual(report["target"]["currentStage"], "TOKEN_GET")
        self.assertFalse(report["target"]["complete"])
        self.assertEqual(len(transport.calls), 2)

    def test_arbitrary_route_is_rejected_before_connection(self):
        for route in ("target", "https://forbidden.invalid", None, True):
            with mock.patch.object(p.http.client, "HTTPSConnection") as connection, self.assertRaises(ValueError):
                p.RegistryClient().head(route)
            connection.assert_not_called()

    def test_environment_override_blocks_before_cache(self):
        for name in p.BLOCKED_ENV:
            with mock.patch.dict(os.environ, {name: SECRET}), mock.patch.object(p, "daemon_ready") as daemon, mock.patch.object(p, "cache_hit") as cache:
                report = p.probe()
            self.assertEqual(report["reason"], "ENVIRONMENT_OVERRIDE")
            daemon.assert_not_called(); cache.assert_not_called()
            self.assertTrue(p.validate_report(report))

    def test_unrelated_env_cannot_change_urls_or_auth(self):
        with mock.patch.dict(os.environ, {"TOKEN_URL": SECRET, "UNITY_IMAGE": SECRET, "REGISTRY_HOST": SECRET, "DOCKER_AUTH_CONFIG": SECRET}):
            report, transport = self.auth()
        self.assertEqual(report["status"], "PASS")
        self.assertNotIn(SECRET, json.dumps(p.DOCKER_ENV))


class HeadTests(OfflineCase):
    def test_target_missing_digest_blocks_preview(self):
        report, transport = self.exercise([Raw(200), quota()])
        self.assertEqual(report["reason"], "TARGET_DIGEST_UNVERIFIED")
        self.assertEqual(report["target"]["headers"]["digest"], "MISSING")
        self.assertEqual(len(transport.calls), 1)

    def test_target_wrong_digest_blocks_preview(self):
        for digest in (p.IMAGE, p.DIGEST.upper(), p.DIGEST + "evil", " " + p.DIGEST):
            report, _ = self.exercise([Raw(200, (("Docker-Content-Digest", digest),))])
            self.assertEqual(report["reason"], "TARGET_DIGEST_UNVERIFIED")
            self.assertEqual(report["target"]["headers"]["digest"], "MISMATCH")

    def test_target_duplicate_digest_rejected(self):
        report, _ = self.exercise([Raw(200, TARGET_HEADERS + TARGET_HEADERS)])
        self.assertEqual(report["target"]["headers"]["digest"], "DUPLICATE")
        self.assertEqual(report["status"], "UNKNOWN")

    def test_target_quota_cannot_substitute_preview(self):
        report, _ = self.exercise([Raw(200, TARGET_HEADERS + QUOTA_HEADERS), Raw(200)])
        self.assertEqual(report["status"], "UNKNOWN")
        self.assertEqual(report["reason"], "PULL_FAILED")
        self.assertIsNone(report["remaining"])

    def test_target_quota_zero_blocks_preview_and_pull(self):
        report, _ = self.exercise([Raw(200, TARGET_HEADERS + (("RateLimit-Limit", "100;w=21600"), ("RateLimit-Remaining", "0;w=21600"))), quota()])
        self.assertEqual(report["status"], "RATE_LIMITED")
        self.assertEqual(report["reason"], "TARGET_QUOTA_EXHAUSTED")
        self.assertIsNone(report["remaining"])
        self.pull_mock.assert_not_called()

    def test_preview_both_headers_absent_precisely_unknown(self):
        report, _ = self.exercise([target(), Raw(200)])
        self.assertEqual(report["quota"]["reason"], "QUOTA_HEADERS_ABSENT")
        self.assertEqual(report["quota"]["headers"]["limit"], "MISSING")
        self.assertEqual(report["quota"]["headers"]["remaining"], "MISSING")
        self.assertFalse(report["quota"]["complete"])

    def test_preview_one_missing_precisely_unknown(self):
        for header in QUOTA_HEADERS:
            report, _ = self.exercise([target(), Raw(200, (header,))])
            self.assertEqual(report["quota"]["reason"], "QUOTA_HEADER_PARTIAL")
            self.assertEqual(sum(report["quota"]["headers"][key] == "MISSING" for key in ("limit", "remaining")), 1)

    def test_preview_unknown_formats_and_windows_rejected(self):
        for value in ("20", "20;w=60", "20; w=21600", "020;w=21600", "-1;w=21600", "2.0;w=21600", "1000000000;w=21600", "101;w=21600", "20;w=21600, 10;w=60", "20;w=21600;other=x"):
            report, _ = self.exercise([target(), Raw(200, (QUOTA_HEADERS[0], ("RateLimit-Remaining", value)))])
            self.assertEqual(report["reason"], "QUOTA_INVALID")
            self.assertEqual(report["quota"]["headers"]["remaining"], "INVALID")

    def test_preview_zero_limit_rejected(self):
        report, _ = self.exercise([target(), Raw(200, (("RateLimit-Limit", "0;w=21600"), ("RateLimit-Remaining", "0;w=21600")))])
        self.assertEqual(report["reason"], "QUOTA_INVALID")

    def test_preview_zero_remaining_is_exhausted(self):
        report, _ = self.exercise([target(), Raw(200, (QUOTA_HEADERS[0], ("RateLimit-Remaining", "0;w=21600")))])
        self.assertEqual((report["status"], report["reason"]), ("RATE_LIMITED", "QUOTA_EXHAUSTED"))
        self.assertTrue(report["quota"]["complete"])
        self.assertEqual(report["remaining"], 0)

    def test_duplicate_quota_headers_rejected(self):
        for header in QUOTA_HEADERS:
            report, _ = self.exercise([target(), Raw(200, QUOTA_HEADERS + (header,))])
            self.assertEqual(report["status"], "UNKNOWN")
            self.assertIn("DUPLICATE", report["quota"]["headers"].values())

    def test_case_insensitive_names(self):
        report, _ = self.exercise([Raw(200, tuple((k.swapcase(), v) for k, v in TARGET_HEADERS)), Raw(200, tuple((k.swapcase(), v) for k, v in QUOTA_HEADERS))])
        self.assertEqual(report["status"], "PASS")

    def test_unknown_headers_ip_and_body_never_leak(self):
        report, _ = self.exercise([Raw(200, TARGET_HEADERS + (("docker-ratelimit-source", "203.0.113.99"),), RAW_SECRET.encode()), Raw(200, QUOTA_HEADERS + (("X-Private", RAW_SECRET),))])
        self.assertEqual(report["status"], "PASS")
        self.assertNotIn("203.0.113.99", json.dumps(report))

    def test_429_distinguishes_each_channel_and_stage(self):
        for position in range(6):
            fixtures = [unauthorized(p.Route.TARGET), token_response(), target(), unauthorized(p.Route.QUOTA), token_response(QUOTA_SECRET), quota()]
            fixtures[position] = Raw(429, (("Retry-After", "60"),), RAW_SECRET.encode())
            report, transport = self.exercise(fixtures)
            route = "target" if position < 3 else "quota"
            self.assertEqual((report["status"], report["reason"]), ("RATE_LIMITED", route.upper() + "_RATE_LIMITED"))
            self.assertEqual(report[route]["httpStatus"], 429)
            self.assertEqual(report["retryAfter"], {"seconds": 60})
            self.assertEqual(len(transport.calls), position + 1)

    def test_429_quota_retains_valid_values_only_from_preview_head(self):
        report, _ = self.exercise([target(), Raw(429, QUOTA_HEADERS)])
        self.assertEqual(report["remaining"], 20)
        self.assertEqual(report["status"], "RATE_LIMITED")
        report, _ = self.exercise([Raw(429, TARGET_HEADERS + QUOTA_HEADERS)])
        self.assertIsNone(report["remaining"])
        report, _ = self.auth(quota_token=Raw(429, QUOTA_HEADERS))
        self.assertIsNone(report["remaining"])

    def test_429_invalid_headers_retain_rate_limited_without_quota(self):
        report, _ = self.exercise([target(), Raw(429, QUOTA_HEADERS + (QUOTA_HEADERS[0],))])
        self.assertEqual(report["status"], "RATE_LIMITED")
        self.assertIsNone(report["remaining"])

    def test_non_200_statuses_never_pass(self):
        for status in (204, 400, 403, 404, 500, 503):
            for fixtures in ([Raw(status, TARGET_HEADERS)], [target(), Raw(status, QUOTA_HEADERS)]):
                report, _ = self.exercise(fixtures)
                self.assertEqual(report["status"], "UNKNOWN")

    def test_duplicate_or_malformed_transport_headers_never_pass(self):
        for headers in ((("Content-Length", "1"), ("content-length", "1")), (("Transfer-Encoding", "gzip"),), (("Transfer-Encoding", "chunked"), ("Content-Length", "1")), (("Retry-After", "a\r\nb"),), (("Content-Type", "x" * 4097),)):
            report, _ = self.exercise([Raw(200, TARGET_HEADERS + headers)])
            self.assertEqual(report["status"], "UNKNOWN")


class AuthTests(OfflineCase):
    def test_challenge_parameter_reordering(self):
        value = 'Bearer scope="repository:unityci/editor:pull", service="registry.docker.io", realm="https://auth.docker.io/token"'
        report, _ = self.exercise([Raw(401, (("WWW-Authenticate", value),)), token_response(), target(), quota()])
        self.assertEqual(report["status"], "PASS")

    def test_wrong_scope_and_malicious_challenges_rejected(self):
        base = challenge(p.Route.TARGET)
        values = [base.replace("auth.docker.io", "evil.invalid"), base.replace("https://", "http://"), base.replace("registry.docker.io", "evil.invalid"), base.replace(":pull\"", ":pull,push\""), challenge(p.Route.QUOTA), base + ',offline_token="true"', base + ',scope="repository:unityci/editor:pull"', base.replace("Bearer ", "Basic "), base.replace('/token"', '/token?secret=x"'), base.replace('/token"', '/token/"'), base.replace('/token"', '/token#x"'), base + "\r\n" + SECRET, ""]
        for value in values:
            report, transport = self.exercise([Raw(401, (("WWW-Authenticate", value),))])
            self.assertEqual(report["reason"], "TARGET_AUTH_FAILED")
            self.assertEqual(len(transport.calls), 1)

    def test_preview_scope_cannot_reuse_target_scope(self):
        report, transport = self.exercise([target(), unauthorized(p.Route.TARGET)])
        self.assertEqual(report["reason"], "QUOTA_AUTH_FAILED")
        self.assertEqual(len(transport.calls), 2)

    def test_duplicate_www_authenticate_rejected(self):
        report, _ = self.exercise([Raw(401, (("WWW-Authenticate", challenge(p.Route.TARGET)), ("www-authenticate", challenge(p.Route.TARGET))))])
        self.assertEqual(report["reason"], "TARGET_AUTH_FAILED")

    def token_check(self, payload, expected):
        report, transport = self.auth(target_token=token_response(value=payload))
        self.assertEqual(report["target"]["reason"], expected)
        self.assertEqual(report["reason"], "TARGET_AUTH_FAILED")
        self.assertEqual(len(transport.calls), 2)

    def test_omitted_expiry_and_issue_time_default_60(self):
        response = token_response(value={"token": SECRET})
        token, error = p.validated_token(p.Response(200, response.headers, response.body), NOW)
        self.assertIsNone(error)
        self.assertEqual(token.expires_at, NOW + dt.timedelta(seconds=60))
        report, _ = self.auth(target_token=response, quota_token=token_response(value={"access_token": QUOTA_SECRET}))
        self.assertEqual(report["status"], "PASS")

    def test_official_3600_lifetime_accepted(self):
        report, _ = self.auth(target_token=token_response(value={"token": SECRET, "expires_in": 3600, "issued_at": "2026-10-09T21:00:00Z"}))
        self.assertEqual(report["status"], "PASS")

    def test_token_aliases_identical_or_single_accepted(self):
        for payload in ({"access_token": SECRET}, {"token": SECRET, "access_token": SECRET}):
            report, _ = self.auth(target_token=token_response(value=payload))
            self.assertEqual(report["status"], "PASS")

    def test_inconsistent_aliases_rejected(self):
        self.token_check({"token": SECRET, "access_token": "different"}, "TOKEN_VALUE_INVALID")

    def test_refresh_offline_unknown_keys_rejected_without_echo(self):
        for key in ("refresh_token", "offline_token", "account", SECRET):
            self.token_check({"token": SECRET, key: RAW_SECRET}, "TOKEN_SCHEMA_INVALID")

    def test_lifetime_positive_integer_bounded(self):
        for value in (None, True, "3600", 0, -1, 3601, 1.5):
            self.token_check({"token": SECRET, "expires_in": value}, "TOKEN_LIFETIME_INVALID")

    def test_bearer_value_length_and_characters(self):
        for value in (None, 1, [], "", "x" * (p.MAX_TOKEN_LENGTH + 1), SECRET + "\r\nX:1", "spaces here", "密钥", "colon:token"):
            self.token_check({"token": value}, "TOKEN_VALUE_INVALID")

    def test_rfc3339_offsets_fractional_and_lowercase_accepted(self):
        for issued in ("2026-10-09T21:00:00+00:00", "2026-10-09T22:00:00+01:00", "2026-10-09T21:00:00.123456789Z", "2026-10-09t21:00:00z"):
            report, _ = self.auth(target_token=token_response(value={"token": SECRET, "issued_at": issued}))
            self.assertEqual(report["status"], "PASS")

    def test_malformed_or_excess_future_issue_time_rejected(self):
        for issued in (None, 1, SECRET, "2026-13-09T21:00:00Z", "2026-10-09T21:00:00", "2026-10-09T21:01:01Z"):
            self.token_check({"token": SECRET, "issued_at": issued}, "TOKEN_TIME_INVALID")

    def test_expired_token_never_reaches_authenticated_head(self):
        self.token_check({"token": SECRET, "issued_at": "2026-10-09T20:59:00Z"}, "TOKEN_EXPIRED")

    def test_token_expires_while_authenticated_head_in_flight(self):
        def late_head():
            self.clock[0] = NOW + dt.timedelta(seconds=60)
            return target()
        report, _ = self.exercise([unauthorized(p.Route.TARGET), token_response(value={"token": SECRET}), late_head])
        self.assertEqual(report["target"]["reason"], "TOKEN_EXPIRED")
        self.assertFalse(report["target"]["complete"])

    def test_target_token_expiry_during_preview_blocks_final_pass(self):
        def late_preview():
            self.clock[0] = NOW + dt.timedelta(seconds=60)
            return quota()
        report, _ = self.exercise([unauthorized(p.Route.TARGET), token_response(value={"token": SECRET}), target(), late_preview])
        self.assertEqual(report["reason"], "TARGET_AUTH_FAILED")
        self.assertEqual(report["target"]["reason"], "TOKEN_EXPIRED")
        self.assertEqual(report["remaining"], 20)
        self.assertEqual(report["status"], "UNKNOWN")

    def test_duplicate_json_keys_rejected(self):
        body = ('{"token":"' + SECRET + '","token":"evil"}').encode()
        report, _ = self.auth(target_token=Raw(200, (("Content-Type", "application/json"),), body))
        self.assertEqual(report["target"]["reason"], "TOKEN_BODY_INVALID")

    def test_bad_json_encoding_and_nonobject_body(self):
        for body, reason in ((b"not-json", "TOKEN_BODY_INVALID"), (b"\xff", "TOKEN_BODY_INVALID"), (b"[]", "TOKEN_SCHEMA_INVALID"), (b"null", "TOKEN_SCHEMA_INVALID"), (b"1", "TOKEN_SCHEMA_INVALID")):
            report, _ = self.auth(target_token=Raw(200, (("Content-Type", "application/json"),), body))
            self.assertEqual(report["target"]["reason"], reason)

    def test_token_body_bound_without_content_length(self):
        raw = Raw(200, (("Content-Type", "application/json"),), b"x" * (p.MAX_TOKEN_BODY + 200))
        report, _ = self.auth(target_token=raw)
        self.assertEqual(raw.reads, [p.MAX_TOKEN_BODY + 1])
        self.assertEqual(report["target"]["reason"], "TOKEN_BODY_INVALID")

    def test_invalid_or_oversized_content_length_not_read(self):
        for length in (str(p.MAX_TOKEN_BODY + 1), "-1", "0001", "1, 2", RAW_SECRET):
            raw = Raw(200, (("Content-Type", "application/json"), ("Content-Length", length)), SECRET.encode())
            report, _ = self.auth(target_token=raw)
            self.assertEqual(report["status"], "UNKNOWN")
            self.assertEqual(raw.reads, [])

    def test_content_length_mismatch_rejected(self):
        report, _ = self.auth(target_token=token_response(headers=(("Content-Type", "application/json"), ("Content-Length", "1"))))
        self.assertEqual(report["target"]["reason"], "TOKEN_BODY_INVALID")

    def test_compressed_or_nonjson_body_rejected(self):
        for headers in ((), (("Content-Type", "text/plain"),), (("Content-Type", "application/json"), ("Content-Encoding", "gzip"))):
            report, _ = self.auth(target_token=token_response(headers=headers))
            self.assertEqual(report["target"]["reason"], "TOKEN_HEADERS_INVALID")

    def test_duplicate_token_headers_no_body_read(self):
        for name in ("Content-Type", "Content-Length", "Content-Encoding", "Transfer-Encoding"):
            raw = token_response()
            raw.headers += ((name, "x"), (name.lower(), "x"))
            report, _ = self.auth(target_token=raw)
            self.assertEqual(report["status"], "UNKNOWN")
            self.assertEqual(raw.reads, [])


class RetryTests(OfflineCase):
    def test_retry_date_normalized(self):
        report, _ = self.exercise([Raw(429, (("Retry-After", "Fri, 09 Oct 2026 21:01:00 GMT"),))])
        self.assertEqual(report["retryAfter"], {"utc": "2026-10-09T21:01:00Z"})

    def test_invalid_retry_values_do_not_leak(self):
        for value in (RAW_SECRET, SECRET, "-1", "01", "604801", "1.5", "Fri, 09 Oct 2026 20:59:00 GMT", "Sat, 09 Oct 2026 21:01:00 GMT"):
            report, _ = self.exercise([Raw(429, (("Retry-After", value),))])
            self.assertEqual(report["status"], "RATE_LIMITED")
            self.assertIsNone(report["retryAfter"])

    def test_duplicate_retry_header_on_429_no_retry_data(self):
        report, _ = self.exercise([Raw(429, (("Retry-After", "1"), ("retry-after", "1")))])
        self.assertEqual(report["status"], "RATE_LIMITED")
        self.assertIsNone(report["retryAfter"])


class PullTests(OfflineCase):
    def test_both_absent_allows_exactly_one_pull_then_exact_cache(self):
        self.pull_mock.return_value = ("SUCCESS", 0, "NONE")
        with mock.patch.object(p, "inspect_cache_bytes", return_value=json.dumps([p.IMAGE]).encode()):
            report, transport = self.exercise([target(), Raw(200)], cache_after_pull=REAL_CACHE_HIT, main=True)
        self.assertEqual((report["status"], report["reason"]), ("PASS", "PULL_SUCCEEDED"))
        self.assertEqual(report["pull"], {"attempted": True, "currentStage": "COMPLETE", "outcome": "SUCCESS", "exitCode": 0, "cacheVerified": True, "failureClass": "NONE"})
        self.assertIsNone(report["remaining"])
        self.assertEqual(report["quota"]["reason"], "QUOTA_HEADERS_ABSENT")
        self.assertFalse(report["quota"]["complete"])
        self.pull_mock.assert_called_once_with()
        self.assertEqual(len(transport.calls), 2)

    def test_target_positive_quota_still_requires_preview_or_real_pull(self):
        self.pull_mock.return_value = ("SUCCESS", 0, "NONE")
        report, _ = self.exercise([Raw(200, TARGET_HEADERS + QUOTA_HEADERS), Raw(200)], cache_after_pull=True)
        self.assertEqual(report["reason"], "PULL_SUCCEEDED")
        self.assertIsNone(report["remaining"])
        self.pull_mock.assert_called_once_with()

    def test_pull_returncode_zero_wrong_digest_cannot_pass(self):
        self.pull_mock.return_value = ("SUCCESS", 0, "NONE")
        with mock.patch.object(p, "inspect_cache_bytes", return_value=json.dumps([p.IMAGE + "evil"]).encode()):
            report, _ = self.exercise([target(), Raw(200)], cache_after_pull=REAL_CACHE_HIT)
        self.assertEqual(report["reason"], "PULL_DIGEST_UNVERIFIED")
        self.assertEqual(report["pull"]["outcome"], "INSPECT_MISMATCH")
        self.assertFalse(report["pull"]["cacheVerified"])

    def test_pull_nonzero_never_inspects_for_success(self):
        def forbidden(): raise AssertionError("must not recheck after failure")
        report, _ = self.exercise([target(), Raw(200)], cache_after_pull=forbidden)
        self.assertEqual(report["reason"], "PULL_FAILED")
        self.assertEqual(report["pull"]["exitCode"], 1)
        self.pull_mock.assert_called_once_with()

    def test_pull_timeout_preserves_target_and_preview_observations(self):
        self.pull_mock.return_value = ("TIMEOUT", None, "NOT_CHECKED")
        report, _ = self.exercise([target(), Raw(200)], main=True)
        self.assertEqual(report["reason"], "PULL_TIMEOUT")
        self.assertTrue(report["target"]["complete"])
        self.assertEqual(report["quota"]["httpStatus"], 200)
        self.assertEqual(report["quota"]["headers"]["limit"], "MISSING")
        self.assertEqual(report["pull"]["currentStage"], "PULL")

    def test_pull_error_has_no_raw_text(self):
        self.pull_mock.return_value = ("ERROR", None, "UNKNOWN_CLI_FAILURE")
        report, _ = self.exercise([target(), Raw(200)], main=True)
        self.assertEqual(report["reason"], "PULL_ERROR")

    def test_recognized_pull_429_never_fabricates_http_429(self):
        self.pull_mock.return_value = ("NONZERO_EXIT", 1, "DOCKER_RATE_LIMITED")
        report, _ = self.exercise([target(), Raw(200)], main=True)
        self.assertEqual((report["status"], report["reason"]), ("RATE_LIMITED", "PULL_RATE_LIMITED"))
        self.assertEqual(report["pull"]["failureClass"], "DOCKER_RATE_LIMITED")
        self.assertEqual(report["target"]["httpStatus"], 200)
        self.assertEqual(report["quota"]["httpStatus"], 200)
        self.assertIsNone(report["remaining"])

    def test_stderr_cap_report_is_fixed_failure(self):
        self.pull_mock.return_value = ("STDERR_LIMIT_EXCEEDED", None, "STDERR_LIMIT_EXCEEDED")
        report, _ = self.exercise([target(), Raw(200)], main=True)
        self.assertEqual(report["reason"], "PULL_STDERR_LIMIT_EXCEEDED")
        self.assertEqual(report["status"], "UNKNOWN")

    def test_duplicate_both_preview_headers_never_count_as_absent(self):
        report, _ = self.exercise([target(), Raw(200, QUOTA_HEADERS + QUOTA_HEADERS)])
        self.assertEqual(report["quota"]["headers"]["limit"], "DUPLICATE")
        self.assertEqual(report["quota"]["headers"]["remaining"], "DUPLICATE")
        self.assertFalse(report["pull"]["attempted"])
        self.pull_mock.assert_not_called()

    def test_preview_partial_malformed_zero_and_bad_window_deny_pull(self):
        fixtures = [Raw(200, (QUOTA_HEADERS[0],)), Raw(200, (QUOTA_HEADERS[0], ("RateLimit-Remaining", "1;w=60"))), Raw(200, (QUOTA_HEADERS[0], ("RateLimit-Remaining", "0;w=21600"))), Raw(200, (QUOTA_HEADERS[0], ("RateLimit-Remaining", "101;w=21600"))), Raw(200, (QUOTA_HEADERS[0], ("RateLimit-Remaining", "unknown"))), Raw(401), Raw(429)]
        for fixture in fixtures:
            report, _ = self.exercise([target(), fixture])
            self.assertFalse(report["pull"]["attempted"])
            self.pull_mock.assert_not_called()

    def test_target_zero_duplicate_partial_malformed_window_deny_pull(self):
        invalid = [(("RateLimit-Limit", "100;w=21600"), ("RateLimit-Remaining", "0;w=21600")), QUOTA_HEADERS + QUOTA_HEADERS, (QUOTA_HEADERS[0],), (QUOTA_HEADERS[0], ("RateLimit-Remaining", "unknown")), (QUOTA_HEADERS[0], ("RateLimit-Remaining", "1;w=60")), (QUOTA_HEADERS[0], ("RateLimit-Remaining", "101;w=21600"))]
        for headers in invalid:
            report, transport = self.exercise([Raw(200, TARGET_HEADERS + headers), Raw(200)])
            self.assertFalse(report["pull"]["attempted"])
            self.assertEqual(len(transport.calls), 1)
            self.pull_mock.assert_not_called()

    def test_target_digest_mismatch_never_allows_pull(self):
        report, _ = self.exercise([Raw(200, (("Docker-Content-Digest", "sha256:" + "0" * 64),)), Raw(200)])
        self.assertFalse(report["pull"]["attempted"])
        self.pull_mock.assert_not_called()

    def test_expired_token_before_pull_denies_launch(self):
        def late_preview():
            self.clock[0] = NOW + dt.timedelta(seconds=60)
            return Raw(200)
        report, _ = self.exercise([unauthorized(p.Route.TARGET), token_response(value={"token": SECRET}), target(), late_preview])
        self.assertEqual(report["reason"], "TARGET_AUTH_FAILED")
        self.assertFalse(report["pull"]["attempted"])
        self.pull_mock.assert_not_called()

    def test_token_expiry_during_successful_pull_does_not_undo_cache(self):
        def pull():
            self.clock[0] = NOW + dt.timedelta(seconds=300)
            return "SUCCESS", 0, "NONE"
        self.pull_mock.side_effect = pull
        report, _ = self.exercise([unauthorized(p.Route.TARGET), token_response(value={"token": SECRET}), target(), Raw(200)], cache_after_pull=True)
        self.assertEqual((report["status"], report["reason"]), ("PASS", "PULL_SUCCEEDED"))
        self.assertTrue(report["pull"]["cacheVerified"])

    def test_readonly_positive_quota_does_not_pull(self):
        report, _ = self.auth()
        self.assertEqual(report["reason"], "READY")
        self.pull_mock.assert_not_called()


class CacheDaemonTests(unittest.TestCase):
    def cache(self, payload):
        with mock.patch.object(p, "inspect_cache_bytes", return_value=payload):
            return p.cache_hit()

    def daemon(self, payload):
        with mock.patch.object(p, "docker_bytes", return_value=payload) as command:
            result = p.daemon_ready()
        command.assert_called_once_with(p.DOCKER_INFO_COMMAND)
        return result

    def test_exact_digest_array_only(self):
        self.assertTrue(self.cache(json.dumps([p.IMAGE]).encode()))
        for value in (None, "", p.IMAGE, {"RepoDigests": [p.IMAGE]}, [{"RepoDigests": [p.IMAGE]}], [], [p.DIGEST], ["docker.io/" + p.IMAGE], [p.IMAGE + "evil"], [p.IMAGE, 1], [p.IMAGE, p.IMAGE]):
            self.assertFalse(self.cache(json.dumps(value).encode()))

    def test_cache_invalid_utf8_trailing_garbage_and_substring_rejected(self):
        for value in (b"not-json", b"\xff", json.dumps([p.IMAGE]).encode() + b"extra", json.dumps(["prefix" + p.IMAGE]).encode()):
            self.assertFalse(self.cache(value))

    def test_cache_other_digest_is_not_exported(self):
        self.assertTrue(self.cache(json.dumps([p.IMAGE, "other/repo@sha256:" + "f" * 64]).encode()))

    def test_cache_exceptions_fail_without_echo(self):
        with mock.patch.object(p, "inspect_cache_bytes", side_effect=OSError(RAW_SECRET)):
            self.assertFalse(p.cache_hit())

    def test_daemon_exact_true_boolean_schema(self):
        valid = {"httpProxyEmpty": True, "httpsProxyEmpty": True, "mirrorsEmpty": True}
        self.assertTrue(self.daemon(json.dumps(valid).encode()))
        for key in valid:
            for bad in (False, 1, "true", None, SECRET):
                self.assertFalse(self.daemon(json.dumps(dict(valid, **{key: bad})).encode()))
            missing = dict(valid); del missing[key]
            self.assertFalse(self.daemon(json.dumps(missing).encode()))
        self.assertFalse(self.daemon(json.dumps(dict(valid, extra=True)).encode()))

    def test_daemon_bad_duplicate_or_unknown_data_rejected(self):
        for value in (None, b"", b"[]", b"null", b"\xff", b"{}", b'{"httpProxyEmpty":false,"httpProxyEmpty":true,"httpsProxyEmpty":true,"mirrorsEmpty":true}'):
            self.assertFalse(self.daemon(value))

    def test_daemon_error_rejected(self):
        with mock.patch.object(p, "docker_bytes", side_effect=OSError(RAW_SECRET)):
            self.assertFalse(p.daemon_ready())

    def test_daemon_unknown_stops_before_cache_or_network(self):
        with mock.patch.dict(os.environ, {name: "" for name in p.BLOCKED_ENV}), mock.patch.object(p, "daemon_ready", return_value=False), mock.patch.object(p, "cache_hit") as cache, mock.patch.object(p.http.client, "HTTPSConnection") as network:
            report = p.probe()
        self.assertEqual(report["reason"], "DAEMON_UNVERIFIED")
        self.assertTrue(p.validate_report(report))
        cache.assert_not_called(); network.assert_not_called()

    def test_daemon_template_guards_missing_mirror_type(self):
        self.assertIn('{{eq .HTTPProxy ""}}', p.DOCKER_INFO_FORMAT)
        self.assertIn('{{eq .HTTPSProxy ""}}', p.DOCKER_INFO_FORMAT)
        self.assertIn('{{if .RegistryConfig}}', p.DOCKER_INFO_FORMAT)
        self.assertIn('(eq (printf "%T" .RegistryConfig.Mirrors) "[]string")', p.DOCKER_INFO_FORMAT)
        self.assertIn('{{else}}false{{end}}', p.DOCKER_INFO_FORMAT)

    def test_arbitrary_docker_commands_rejected(self):
        with mock.patch.object(p.subprocess, "Popen") as spawn:
            self.assertIsNone(p.docker_bytes(("/bin/sh", "-c", "anything")))
        spawn.assert_not_called()


class ReportTests(OfflineCase):
    def test_schema_fixed_and_validator_pure(self):
        report, _ = self.exercise([target(), quota()])
        self.assertEqual(set(report), p.REPORT_KEYS)
        self.assertEqual(report["schemaVersion"], 2)
        with mock.patch.object(p, "utc_now", side_effect=AssertionError("clock")), mock.patch.object(p, "cache_hit", side_effect=AssertionError("I/O")):
            self.assertTrue(p.validate_report(report))

    def test_extra_and_missing_keys_rejected_at_every_level(self):
        report, _ = self.exercise([target(), quota()])
        for path in ((), ("target",), ("quota",), ("target", "headers"), ("quota", "headers"), ("pull",)):
            original = report
            for key in path: original = original[key]
            for missing in list(original):
                bad = copy.deepcopy(report); node = bad
                for key in path: node = node[key]
                del node[missing]
                self.assertFalse(p.validate_report(bad))
            bad = copy.deepcopy(report); node = bad
            for key in path: node = node[key]
            node["extra"] = SECRET
            self.assertFalse(p.validate_report(bad))

    def test_fixed_literals_types_enums_and_dates_rejected(self):
        report = p.blank_result()
        invalid = {"schemaVersion": [True, 1, "2"], "image": [SECRET], "digest": [SECRET], "status": [SECRET], "reason": [SECRET], "cacheHit": [1, None], "checkedAt": [SECRET, "2026-13-09T21:00:00Z", "2026-10-09T21:00:00+00:00"], "remaining": [True, 0, -1], "limit": [0, True], "retryAfter": [SECRET, {"raw": SECRET}]}
        for key, values in invalid.items():
            for value in values: self.assertFalse(p.validate_report(dict(report, **{key: value})), key)

    def test_token_stage_cannot_be_forged_as_complete_pass(self):
        report, _ = self.auth()
        for route in ("target", "quota"):
            bad = copy.deepcopy(report); bad[route]["currentStage"] = "TOKEN_GET"
            self.assertFalse(p.validate_report(bad))
            bad = copy.deepcopy(report); bad[route]["httpStatus"] = 401
            self.assertFalse(p.validate_report(bad))
            bad = copy.deepcopy(report); bad[route]["complete"] = False
            self.assertFalse(p.validate_report(bad))

    def test_quota_must_belong_to_preview_head(self):
        report, _ = self.exercise([target(), quota()])
        for changes in ({"currentStage": "TOKEN_GET"}, {"httpStatus": 201}, {"reason": "QUOTA_EXHAUSTED"}):
            bad = copy.deepcopy(report); bad["quota"].update(changes)
            self.assertFalse(p.validate_report(bad))

    def test_pull_success_requires_exit_zero_exact_local_cache_and_missing_headers(self):
        self.pull_mock.return_value = ("SUCCESS", 0, "NONE")
        report, _ = self.exercise([target(), Raw(200)], cache_after_pull=True)
        for changes in ({"cacheVerified": False}, {"exitCode": 1}, {"attempted": False}, {"outcome": "TIMEOUT"}):
            bad = copy.deepcopy(report); bad["pull"].update(changes)
            self.assertFalse(p.validate_report(bad))
        for field in ("limit", "remaining"):
            bad = copy.deepcopy(report); bad["quota"]["headers"][field] = "DUPLICATE"
            self.assertFalse(p.validate_report(bad))

    def test_report_validation_does_not_mutate(self):
        report, _ = self.exercise([target(), quota()]); original = copy.deepcopy(report)
        self.assertTrue(p.validate_report(report)); self.assertEqual(report, original)

    def test_all_cli_arguments_rejected_without_execution_or_echo(self):
        for args in (["--image", SECRET], ["--url", "https://forbidden.invalid"], ["--docker", SECRET], ["--output", "/tmp/evil"], ["--help"]):
            report, transport = self.exercise([], main=True, argv=args)
            self.assertEqual(report["status"], "UNKNOWN"); self.assertEqual(transport.calls, [])
            self.pull_mock.assert_not_called()


class InterruptionTests(OfflineCase):
    def pull_report(self):
        self.pull_mock.return_value = ("SUCCESS", 0, "NONE")
        report, _ = self.exercise([target(), Raw(200)], cache_after_pull=True)
        return report

    def test_completed_pull_is_not_erased_by_late_alarm_or_interrupt(self):
        for timed_out in (True, False):
            report = self.pull_report()
            p.mark_interruption(report, timed_out)
            self.assertTrue(p.validate_report(report))
            self.assertEqual((report["status"], report["reason"]), ("PASS", "PULL_SUCCEEDED"))
            self.assertTrue(report["target"]["complete"])

    def test_verify_cache_alarm_and_keyboard_preserve_exit_zero(self):
        for timed_out in (True, False):
            report = self.pull_report()
            report.update(status="UNKNOWN", reason="NOT_STARTED")
            report["pull"].update(currentStage="VERIFY_CACHE", cacheVerified=False)
            p.mark_interruption(report, timed_out)
            self.assertTrue(p.validate_report(report))
            self.assertEqual(report["pull"]["exitCode"], 0)
            self.assertEqual(report["pull"]["currentStage"], "VERIFY_CACHE")
            self.assertEqual(report["reason"], "PULL_TIMEOUT" if timed_out else "PULL_INTERRUPTED")

    def test_interrupt_between_exit_zero_and_verify_stage_is_preserved(self):
        report = self.pull_report()
        report["pull"].update(currentStage="PULL", cacheVerified=False)
        p.mark_interruption(report, False)
        self.assertTrue(p.validate_report(report))
        self.assertEqual(report["pull"]["currentStage"], "VERIFY_CACHE")
        self.assertEqual(report["pull"]["exitCode"], 0)

    def test_already_observed_failure_is_not_replaced_by_late_interrupt(self):
        report, _ = self.exercise([target(), Raw(200)])
        p.mark_interruption(report, True)
        self.assertTrue(p.validate_report(report))
        self.assertEqual(report["reason"], "PULL_FAILED")
        self.assertEqual(report["pull"]["exitCode"], 1)

    def test_200_retry_date_ignored_before_long_pull(self):
        def pull():
            self.clock[0] = NOW + dt.timedelta(seconds=300)
            return "SUCCESS", 0, "NONE"
        self.pull_mock.side_effect = pull
        date = (("Retry-After", "Fri, 09 Oct 2026 21:01:00 GMT"),)
        report, _ = self.exercise([Raw(200, TARGET_HEADERS + date), Raw(200, date)], cache_after_pull=True, main=True)
        self.assertEqual(report["reason"], "PULL_SUCCEEDED")
        self.assertIsNone(report["retryAfter"])


class LocalProcessTests(unittest.TestCase):
    """Real local children implement fixed-command fixtures, never a Docker daemon."""
    def local_command(self, code, command, timeout=None):
        real_popen, launched = subprocess.Popen, []
        def spawn(actual, **kwargs):
            self.assertEqual(actual, command)
            self.assertEqual(kwargs["env"], p.DOCKER_ENV)
            self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
            self.assertEqual(kwargs["stderr"], subprocess.PIPE if command == p.PULL_COMMAND else subprocess.DEVNULL)
            self.assertNotIn("shell", kwargs)
            if command == p.PULL_COMMAND: self.assertEqual(kwargs["stdout"], subprocess.DEVNULL)
            child = real_popen([sys.executable, "-c", code], **kwargs)
            launched.append(child)
            return child
        with mock.patch.object(p.subprocess, "Popen", side_effect=spawn):
            if command == p.PULL_COMMAND:
                with mock.patch.object(p, "PULL_TIMEOUT", p.PULL_TIMEOUT if timeout is None else timeout): result = p.run_fixed_pull()
            else:
                with mock.patch.object(p, "DOCKER_TIMEOUT", p.DOCKER_TIMEOUT if timeout is None else timeout): result = p.docker_bytes(command)
        self.assertEqual(len(launched), 1)
        self.assertIsNotNone(launched[0].poll())
        return result

    def test_real_inspect_exact_json(self):
        output = json.dumps([p.IMAGE]).encode() + b"\n"
        self.assertEqual(self.local_command("import sys;sys.stdout.buffer.write(" + repr(output) + ")", p.DOCKER_COMMAND), output)

    def test_real_info_boolean_json(self):
        output = b'{"httpProxyEmpty":true,"httpsProxyEmpty":true,"mirrorsEmpty":true}\n'
        self.assertEqual(self.local_command("import sys;sys.stdout.buffer.write(" + repr(output) + ")", p.DOCKER_INFO_COMMAND), output)

    def test_real_inspect_stderr_and_nonzero_discarded(self):
        self.assertIsNone(self.local_command("import sys;sys.stderr.write(" + repr(RAW_SECRET) + ");sys.exit(1)", p.DOCKER_COMMAND))

    def test_real_inspect_oversized_stdout_is_bounded(self):
        self.assertIsNone(self.local_command("import os,time;os.write(1,b'x'*1000000);time.sleep(10)", p.DOCKER_COMMAND))

    def test_real_inspect_timeout_kills_child(self):
        self.assertIsNone(self.local_command("import time;time.sleep(10)", p.DOCKER_COMMAND, timeout=0.05))

    def test_real_pull_success_silences_both_streams(self):
        code = "import sys;sys.stdout.write(" + repr(SECRET) + ");sys.stderr.write(" + repr(RAW_SECRET) + ")"
        self.assertEqual(self.local_command(code, p.PULL_COMMAND), ("SUCCESS", 0, "NONE"))

    def test_real_pull_nonzero_does_not_retry(self):
        self.assertEqual(self.local_command("import sys;sys.exit(17)", p.PULL_COMMAND), ("NONZERO_EXIT", 17, "UNKNOWN_CLI_FAILURE"))

    def test_real_pull_official_rate_limit_phrases_classified_without_raw_output(self):
        phrases = ["toomanyrequests: You have reached your unauthenticated pull rate limit.", "You have reached your pull rate limit.", "429 Too Many Requests"]
        for phrase in phrases:
            code = "import sys;sys.stderr.write(" + repr(phrase + RAW_SECRET) + ");sys.exit(1)"
            self.assertEqual(self.local_command(code, p.PULL_COMMAND), ("NONZERO_EXIT", 1, "DOCKER_RATE_LIMITED"))

    def test_real_pull_arbitrary_sensitive_stderr_is_unknown_fixed_class(self):
        code = "import sys;sys.stderr.write(" + repr(SECRET + RAW_SECRET) + ");sys.exit(1)"
        self.assertEqual(self.local_command(code, p.PULL_COMMAND), ("NONZERO_EXIT", 1, "UNKNOWN_CLI_FAILURE"))

    def test_real_pull_stderr_hard_cap_is_failure(self):
        code = "import os,time;os.write(2,b'x'*1000000);time.sleep(10)"
        self.assertEqual(self.local_command(code, p.PULL_COMMAND), ("STDERR_LIMIT_EXCEEDED", None, "STDERR_LIMIT_EXCEEDED"))

    def test_pull_fixed_command_has_quiet_and_pinned_digest_only(self):
        self.assertEqual(p.PULL_COMMAND, ("/usr/bin/docker", "--host=unix:///var/run/docker.sock", "pull", "--quiet", p.IMAGE))

    def test_real_pull_timeout_is_bounded_not_claimed_daemon_stop(self):
        self.assertEqual(self.local_command("import time;time.sleep(10)", p.PULL_COMMAND, timeout=0.05), ("TIMEOUT", None, "NOT_CHECKED"))

    def test_real_pull_process_error_is_sanitized(self):
        with mock.patch.object(p.subprocess, "Popen", side_effect=OSError(RAW_SECRET)):
            self.assertEqual(p.run_fixed_pull(), ("ERROR", None, "UNKNOWN_CLI_FAILURE"))

    def cli_child(self, mode):
        script = r'''
import importlib.util,json,socket,subprocess,sys,time
spec=importlib.util.spec_from_file_location("environment_image_precheck",sys.argv[1]);p=importlib.util.module_from_spec(spec);sys.modules[spec.name]=p;spec.loader.exec_module(p)
def forbidden(*a,**k):raise AssertionError("NETWORK_OR_DOCKER_FORBIDDEN")
socket.create_connection=forbidden;subprocess.Popen=forbidden
p.daemon_ready=lambda:True
mode=sys.argv[2];count=[0]
def cache():
    count[0]+=1
    if mode=="cache":return True
    if count[0]==1:return False
    if mode=="verify-alarm":time.sleep(10)
    if mode=="verify-interrupt":raise KeyboardInterrupt()
    return mode!="wrong-digest"
p.cache_hit=cache
class Client:
    def head(self,route,token=None):
        if route is p.Route.TARGET:return p.Response(200,(("Docker-Content-Digest",p.DIGEST),))
        if mode=="read-alarm":time.sleep(10)
        if mode=="quota-pass":return p.Response(200,(("RateLimit-Limit","100;w=21600"),("RateLimit-Remaining","1;w=21600")))
        return p.Response(200,())
p.RegistryClient=Client
p.TOTAL_TIMEOUT=0.05 if mode=="read-alarm" else 2
p.PULL_PHASE_TIMEOUT=0.05 if mode in ("pull-alarm","verify-alarm") else 2
def pull():
    if mode=="pull-alarm":time.sleep(10)
    if mode=="pull-interrupt":raise KeyboardInterrupt()
    if mode=="pull-error":raise OSError("TEST_BEARER_TARGET_MUST_NOT_LEAK")
    if mode=="failure":return "NONZERO_EXIT",13,"UNKNOWN_CLI_FAILURE"
    return "SUCCESS",0,"NONE"
p.run_fixed_pull=pull
sys.exit(p.main([]))
'''
        return subprocess.run([sys.executable, "-c", script, str(Path(p.__file__)), mode], capture_output=True, text=True, timeout=5, env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent"})

    def test_real_cli_json_exit_secrets_and_phase_preservation(self):
        expected = {"cache": "CACHE_HIT", "quota-pass": "READY", "pull-pass": "PULL_SUCCEEDED", "failure": "PULL_FAILED", "wrong-digest": "PULL_DIGEST_UNVERIFIED", "read-alarm": "DEADLINE", "pull-alarm": "PULL_TIMEOUT", "verify-alarm": "PULL_TIMEOUT", "pull-interrupt": "PULL_INTERRUPTED", "verify-interrupt": "PULL_INTERRUPTED", "pull-error": "PULL_ERROR"}
        for mode, reason in expected.items():
            with self.subTest(mode=mode):
                child = self.cli_child(mode)
                self.assertEqual(child.stderr, "")
                self.assertEqual(len(child.stdout.splitlines()), 1)
                self.assertNotIn(SECRET, child.stdout + child.stderr)
                self.assertNotIn(RAW_SECRET, child.stdout + child.stderr)
                report = json.loads(child.stdout)
                self.assertTrue(p.validate_report(report))
                self.assertEqual(report["reason"], reason)
                self.assertEqual(child.returncode, 0 if mode in ("cache", "quota-pass", "pull-pass") else 2)
                if mode not in ("cache",):self.assertTrue(report["target"]["complete"])
                if mode.startswith("verify-"):
                    self.assertEqual(report["pull"]["currentStage"], "VERIFY_CACHE")
                    self.assertEqual(report["pull"]["exitCode"], 0)
                if mode.startswith("pull-") and mode not in ("pull-pass",):
                    self.assertEqual(report["pull"]["currentStage"], "PULL")
                if mode=="read-alarm":
                    self.assertEqual(report["quota"]["currentStage"], "INITIAL_HEAD")
                    self.assertEqual(report["quota"]["reason"], "DEADLINE")


if __name__ == "__main__":
    unittest.main()
