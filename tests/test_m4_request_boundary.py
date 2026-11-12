"""M4: inspect actual ASGI receive calls, not just post-parse validation responses."""

import asyncio
import json

import pytest
from sqlalchemy import select
from starlette.requests import Request

from studio_manager.agent_models import StudioAgent, StudioAgentVersion, StudioSkill, StudioSkillVersion
from studio_manager.models import AuditEvent

EXPECTED_LIMIT = 1024 * 1024
BODY = b'{"code":"boundary_agent","name":"Boundary","role":"QA"}'


def headers(client, *, authenticated=True):
    result = [(b"host", b"testserver"), (b"x-studio-request", b"1"), (b"content-type", b"application/json")]
    if authenticated:
        result.append((b"authorization", ("Bearer " + client.app.state.settings.api_token).encode()))
    return result


def snapshot(client):
    with client.app.state.engine.connect() as connection:
        return {
            model.__tablename__: [dict(row) for row in connection.execute(
                select(model.__table__).order_by(model.__table__.c.id)
            ).mappings()]
            for model in (StudioAgent, StudioAgentVersion, StudioSkill, StudioSkillVersion, AuditEvent)
        }


def invoke(app, supplied_headers, chunks, *, path="/api/v1/agents", method="POST", root_path=""):
    async def run():
        sent = []
        consumed = 0
        completed = asyncio.Event()
        events = [chunk if isinstance(chunk, dict) else
                  {"type": "http.request", "body": chunk, "more_body": index < len(chunks) - 1}
                  for index, chunk in enumerate(chunks)]
        if not events:
            events = [{"type": "http.request", "body": b"", "more_body": False}]

        async def receive():
            nonlocal consumed
            if consumed < len(events):
                event = events[consumed]
                consumed += 1
                return event
            await completed.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            sent.append(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                completed.set()

        scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
                 "http_version": "1.1", "method": method, "scheme": "http", "path": path,
                 "raw_path": path.encode(), "root_path": root_path, "query_string": b"", "headers": supplied_headers,
                 "client": ("127.0.0.1", 12345), "server": ("testserver", 80)}
        await app(scope, receive, send)
        start = next(message for message in sent if message["type"] == "http.response.start")
        body = b"".join(message.get("body", b"") for message in sent if message["type"] == "http.response.body")
        return start["status"], consumed, body, dict(start["headers"])

    return asyncio.run(run())


@pytest.mark.parametrize("credential", [None, "Bearer incorrect", "Basic invalid"])
def test_unauthorized_registry_request_is_rejected_before_body_read(client, credential, monkeypatch):
    before = snapshot(client)
    supplied = headers(client, authenticated=False)
    if credential is not None:
        supplied.append((b"authorization", credential.encode()))
    parsed = []
    original = Request.json

    async def tracked_json(self):
        parsed.append(True)
        return await original(self)

    monkeypatch.setattr(Request, "json", tracked_json)
    status, consumed, body, response_headers = invoke(client.app, supplied, [b'{"private-data":'])
    print(json.dumps({"http": status, "receive_calls": consumed, "json_calls": len(parsed)}))
    assert status == 401
    assert consumed == 0 and parsed == []
    assert response_headers[b"www-authenticate"] == b"Bearer"
    assert b"content-security-policy" in response_headers
    assert b"private-data" not in body
    assert snapshot(client) == before


def test_declared_oversize_is_rejected_without_receiving_body(client):
    before = snapshot(client)
    supplied = headers(client) + [(b"content-length", str(EXPECTED_LIMIT + 1).encode())]
    status, consumed, body, _ = invoke(client.app, supplied, [BODY.ljust(EXPECTED_LIMIT + 1, b" ")])
    print(json.dumps({"http": status, "receive_calls": consumed}))
    assert status == 413 and consumed == 0
    assert b"boundary_agent" not in body
    assert snapshot(client) == before


@pytest.mark.parametrize("length", [EXPECTED_LIMIT - 1, EXPECTED_LIMIT])
def test_below_and_exact_limit_preserve_valid_registry_requests(client, length):
    data = BODY.ljust(length, b" ")
    result = invoke(client.app, headers(client) + [(b"content-length", str(length).encode())], [data])
    assert result[0] == 201
    assert result[1] == 1
    assert json.loads(result[2])["enabled"] is False


@pytest.mark.parametrize("chunked", [False, True], ids=["missing-length", "chunked"])
def test_unknown_length_stream_is_bounded_and_stops_at_overflow(client, chunked, monkeypatch):
    before = snapshot(client)
    supplied = headers(client)
    if chunked:
        supplied.append((b"transfer-encoding", b"chunked"))
    calls = []
    original = Request.json

    async def tracked_json(self):
        calls.append(True)
        return await original(self)

    monkeypatch.setattr(Request, "json", tracked_json)
    chunks = [b" " * (EXPECTED_LIMIT // 2), b" " * (EXPECTED_LIMIT // 2), b"x", b"UNREAD"]
    status, consumed, _, _ = invoke(client.app, supplied, chunks)
    assert status == 413 and consumed == 3
    assert calls == []
    assert snapshot(client) == before


@pytest.mark.parametrize("chunked", [False, True])
def test_valid_stream_without_length_preserves_utf8_json(client, chunked):
    supplied = headers(client) + ([(b"transfer-encoding", b"chunked")] if chunked else [])
    data = json.dumps({"code": "unicode_stream", "name": "لومڑی 🦊", "role": "QA"}, ensure_ascii=False).encode()
    chunks = [data[index:index + 5] for index in range(0, len(data), 5)]
    status, consumed, body, _ = invoke(client.app, supplied, chunks)
    assert status == 201 and consumed == len(chunks)
    assert json.loads(body)["name"] == "لومڑی 🦊"


@pytest.mark.parametrize("declared", [b"-1", b"abc", b"1,1", b"\xa01\xa0"])
def test_invalid_content_length_is_safe_400_before_read(client, declared):
    before = snapshot(client)
    status, consumed, _, _ = invoke(client.app, headers(client) + [(b"content-length", declared)], [BODY])
    assert status == 400 and consumed == 0
    assert snapshot(client) == before


@pytest.mark.parametrize("framing", ["duplicate-length", "length-and-chunked", "length-mismatch", "truncated"])
def test_ambiguous_or_mismatched_framing_never_writes(client, framing):
    before = snapshot(client)
    extra = [(b"content-length", str(len(BODY)).encode())]
    if framing == "duplicate-length":
        extra *= 2
    elif framing == "length-and-chunked":
        extra.append((b"transfer-encoding", b"chunked"))
    elif framing == "truncated":
        extra = [(b"content-length", str(len(BODY) + 5).encode())]
    else:
        extra = [(b"content-length", b"1")]
    status, consumed, _, _ = invoke(client.app, headers(client) + extra, [BODY])
    assert status == 400
    assert consumed == (1 if framing in {"length-mismatch", "truncated"} else 0)
    assert snapshot(client) == before


def test_understated_length_cannot_bypass_stream_limit(client):
    before = snapshot(client)
    status, consumed, _, _ = invoke(
        client.app, headers(client) + [(b"content-length", b"1")], [b" " * EXPECTED_LIMIT, b"x"],
    )
    assert status == 413 and consumed == 2
    assert snapshot(client) == before


def test_duplicate_authorization_is_rejected_before_read(client):
    before = snapshot(client)
    status, consumed, _, _ = invoke(client.app, headers(client) + [(b"authorization", b"Bearer invalid")], [BODY])
    assert status == 401 and consumed == 0
    assert snapshot(client) == before


@pytest.mark.parametrize("depth", [13, 100, 1100])
def test_authenticated_deep_json_is_bounded_and_controlled(client, depth):
    created = client.post("/api/v1/agents", headers={
        "Authorization": "Bearer " + client.app.state.settings.api_token, "X-Studio-Request": "1",
    }, json={"code": "deep_agent", "name": "Deep", "role": "QA"})
    assert created.status_code == 201
    before = snapshot(client)
    data = b'{"instruction":"Plan","config":' + b'{"n":' * depth + b'{}' + b'}' * depth + b'}'
    status, _, body, _ = invoke(
        client.app, headers(client), [data], path=f"/api/v1/agents/{created.json()['id']}/versions",
    )
    assert status in {400, 422}
    assert b"Plan" not in body
    assert snapshot(client) == before


def test_authenticated_malformed_json_keeps_safe_validation_behavior(client):
    before = snapshot(client)
    status, consumed, body, _ = invoke(client.app, headers(client), [b'{"private-data":'])
    assert status == 422 and consumed == 1
    assert b"private-data" not in body
    assert snapshot(client) == before


def test_existing_intent_and_host_checks_still_run_before_body_reads(client):
    supplied = [item for item in headers(client) if item[0] != b"x-studio-request"]
    assert invoke(client.app, supplied, [BODY])[:2] == (403, 0)
    supplied = [(key, b"untrusted.example" if key == b"host" else value) for key, value in headers(client)]
    assert invoke(client.app, supplied, [BODY])[:2] == (400, 0)


def test_nonregistry_api_is_not_subject_to_registry_boundary(client):
    before = snapshot(client)
    status, consumed, _, _ = invoke(
        client.app, headers(client, authenticated=False), [b'{"private-data":'], path="/api/v1/projects",
    )
    assert status == 422 and consumed == 1  # Existing nonregistry behavior, intentionally not expanded here.
    assert snapshot(client) == before


def test_default_limit_supports_max_length_escaped_emoji_instruction(client):
    created = client.post("/api/v1/agents", headers={
        "Authorization": "Bearer " + client.app.state.settings.api_token, "X-Studio-Request": "1",
    }, json={"code": "emoji_agent", "name": "Emoji", "role": "QA"})
    assert created.status_code == 201
    instruction = "🦊" * 50000
    data = json.dumps({"instruction": instruction}).encode()
    assert len(data) < EXPECTED_LIMIT
    status, _, body, _ = invoke(
        client.app, headers(client) + [(b"content-length", str(len(data)).encode())], [data],
        path=f"/api/v1/agents/{created.json()['id']}/versions",
    )
    assert status == 201
    assert json.loads(body)["instruction"] == instruction


def test_unauthenticated_deep_stream_never_reaches_body_or_parser(client):
    before = snapshot(client)
    data = b'{"n":' * 1100 + b'{}' + b'}' * 1100
    result = invoke(client.app, headers(client, authenticated=False), [data[:100], data[100:]])
    assert result[:2] == (401, 0)
    assert snapshot(client) == before


def test_empty_chunks_do_not_change_valid_streamed_payload(client):
    result = invoke(client.app, headers(client), [b"", BODY[:10], b"", BODY[10:]])
    assert result[0] == 201 and result[1] == 4


def test_huge_numeric_content_length_does_not_require_big_integer_conversion(client):
    before = snapshot(client)
    result = invoke(client.app, headers(client) + [(b"content-length", b"9" * 1000)], [BODY])
    assert result[:2] == (413, 0)
    assert snapshot(client) == before


def test_valid_leading_zero_length_is_not_rejected(client):
    declared = b"0" * 100 + str(len(BODY)).encode()
    result = invoke(client.app, headers(client) + [(b"content-length", declared)], [BODY])
    assert result[0] == 201


def test_disconnected_stream_does_not_write(client):
    before = snapshot(client)
    result = invoke(client.app, headers(client), [{"type": "http.disconnect"}])
    assert result[:2] == (400, 1)
    assert snapshot(client) == before


def test_middleware_order_and_documented_default(client):
    from studio_manager.registry_boundary import REGISTRY_MAX_BODY_BYTES

    assert REGISTRY_MAX_BODY_BYTES == EXPECTED_LIMIT
    assert [m.cls.__name__ for m in client.app.user_middleware] == [
        "BaseHTTPMiddleware", "TrustedHostMiddleware", "RegistryRequestBoundary",
    ]
    assert client.app.user_middleware[-1].kwargs["max_body_bytes"] == EXPECTED_LIMIT


def test_invalid_configured_limit_is_rejected():
    from studio_manager.registry_boundary import RegistryRequestBoundary

    with pytest.raises(ValueError, match="positive"):
        RegistryRequestBoundary(None, max_body_bytes=0)


def test_replay_delivers_body_once_then_preserves_disconnect(client):
    from studio_manager.registry_boundary import RegistryRequestBoundary

    async def run():
        source = iter([{"type": "http.request", "body": b"{}", "more_body": False}, {"type": "http.disconnect"}])
        delivered, sent = [], []

        async def receive():
            return next(source)

        async def send(message):
            sent.append(message)

        async def downstream(scope, receive, send):
            delivered.append(await receive())
            delivered.append(await receive())
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"{}"})

        scope = {"type": "http", "method": "POST", "path": "/api/v1/agents",
                 "headers": headers(client), "app": client.app}
        await RegistryRequestBoundary(downstream, max_body_bytes=64)(scope, receive, send)
        assert delivered == [{"type": "http.request", "body": b"{}", "more_body": False},
                             {"type": "http.disconnect"}]
        assert sent[0]["status"] == 200

    asyncio.run(run())


def test_root_path_registry_is_protected_before_parsing(client):
    before = snapshot(client)
    result = invoke(
        client.app, headers(client, authenticated=False), [b'{"private-data":'],
        path="/mounted/api/v1/agents", root_path="/mounted",
    )
    assert result[:2] == (401, 0)
    assert snapshot(client) == before


def test_root_path_preserves_valid_authenticated_registry_request(client):
    result = invoke(
        client.app, headers(client), [BODY], path="/mounted/api/v1/agents", root_path="/mounted",
    )
    assert result[0] == 201
