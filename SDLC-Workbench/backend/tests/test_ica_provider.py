from __future__ import annotations

import json
import ssl

import httpx
import pytest

from app.llm.errors import (
    AuthenticationFailed,
    BadRequest,
    BadResponse,
    ContentFilterBlocked,
    ModelAccessDenied,
    ModelNotFound,
    TlsVerificationFailed,
    TransientProviderError,
)
from app.llm.providers.ica import (
    IcaConfigError,
    IcaProvider,
    build_messages,
    chat_url,
    error_text,
    parse_text,
    parse_usage,
)
from app.llm.types import LLMRequest, Message

pytestmark = pytest.mark.anyio

KEY = "sk-SECRET-123456"
ENDPOINT = "https://ica.example.invalid"
AGENT = "SDLC-test-agent/1.0"


def reply(content="ready", *, usage=None, finish="stop", **extra) -> dict:
    body = {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": finish}]}
    body["usage"] = usage if usage is not None else {"prompt_tokens": 12, "completion_tokens": 3}
    body.update(extra)
    return body


class Recorder:
    """A fake network. Records requests and answers from a queue of outcomes."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        outcome = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if isinstance(outcome, BaseException):
            raise outcome
        if isinstance(outcome, httpx.Response):
            return outcome
        return httpx.Response(200, json=outcome)

    @property
    def body(self) -> dict:
        return json.loads(self.requests[-1].content)


def make_provider(make_settings, *outcomes, **settings):
    fake = Recorder(*(outcomes or (reply(),)))
    base = dict(ibm_ica_endpoint=ENDPOINT, ibm_ica_api_key=KEY, ibm_ica_user_agent=AGENT)
    provider = IcaProvider(make_settings(**{**base, **settings}), transport=httpx.MockTransport(fake))
    return provider, fake


def ask(text="hi", **kw) -> LLMRequest:
    return LLMRequest.user("orchestrator", text, **kw)


# ---- url -------------------------------------------------------------------

@pytest.mark.parametrize(
    "endpoint, expected",
    [
        ("https://h.example", "https://h.example/v1/chat/completions"),
        ("https://h.example/", "https://h.example/v1/chat/completions"),
        ("  https://h.example/  ", "https://h.example/v1/chat/completions"),
        ("https://h.example/v1/chat/completions", "https://h.example/v1/chat/completions"),
        ("https://h.example/v1/chat/completions/", "https://h.example/v1/chat/completions"),
        ("https://h.example/v1", "https://h.example/v1/chat/completions"),
        ("https://h.example/gateway", "https://h.example/gateway/v1/chat/completions"),
    ],
)
def test_url_building(endpoint, expected):
    assert chat_url(endpoint) == expected


# ---- the request we send ---------------------------------------------------

async def test_wire_request(make_settings):
    provider, fake = make_provider(make_settings)
    await provider.complete("model-x", ask("hello", max_tokens=321))
    [req] = fake.requests
    assert req.method == "POST" and str(req.url) == ENDPOINT + "/v1/chat/completions"
    assert req.headers["authorization"] == f"Bearer {KEY}"
    assert req.headers["content-type"] == "application/json"
    assert req.headers["accept"] == "application/json"
    assert req.headers["user-agent"] == AGENT
    assert fake.body == {"model": "model-x", "messages": [{"role": "user", "content": "hello"}], "max_tokens": 321}
    assert "stream" not in fake.body and "temperature" not in fake.body


async def test_temperature_is_sent_only_when_set(make_settings):
    provider, fake = make_provider(make_settings)
    await provider.complete("m", ask(temperature=0.2))
    assert fake.body["temperature"] == 0.2
    await provider.complete("m", ask(temperature=0.0))  # zero is a real value, not "unset"
    assert fake.body["temperature"] == 0.0


def test_messages_put_system_first_and_keep_turn_order():
    request = LLMRequest(
        role="orchestrator", system="be brief",
        messages=(Message("user", "a"), Message("assistant", "b"), Message("user", "c")),
    )
    assert build_messages(request) == [
        {"role": "system", "content": "be brief"}, {"role": "user", "content": "a"},
        {"role": "assistant", "content": "b"}, {"role": "user", "content": "c"},
    ]
    assert build_messages(ask("x")) == [{"role": "user", "content": "x"}]


async def test_default_user_agent_is_the_sibling_apps_browser_label(make_settings):
    provider, fake = make_provider(make_settings, ibm_ica_user_agent=make_settings().ibm_ica_user_agent)
    await provider.complete("m", ask())
    assert fake.requests[0].headers["user-agent"].startswith("Mozilla/5.0")


# ---- parsing the reply -----------------------------------------------------

async def test_string_content_and_usage(make_settings):
    provider, _ = make_provider(make_settings, reply("  all good  \n", usage={"prompt_tokens": 40, "completion_tokens": 7}))
    out = await provider.complete("m", ask())
    assert out.text == "all good"
    assert (out.usage.tokens_in, out.usage.tokens_out) == (40, 7)
    assert out.finish_reason == "stop"


def test_content_part_lists_and_the_alternative_shape():
    assert parse_text(reply([{"type": "text", "text": "he"}, {"type": "text", "text": "llo"}, "junk", {"nope": 1}])) == "hello"
    assert parse_text({"content": [{"type": "text", "text": " alt "}]}) == "alt"
    assert parse_text({"choices": [{"message": {}}]}) == ""
    assert parse_text({}) == ""


@pytest.mark.parametrize(
    "usage, expected",
    [
        ({"prompt_tokens": 5, "completion_tokens": 6}, (5, 6)),
        ({"input_tokens": 7, "output_tokens": 8}, (7, 8)),
        ({"prompt_tokens": 5}, None),
        ({"prompt_tokens": "5", "completion_tokens": 6}, None),
        ({"prompt_tokens": 5.5, "completion_tokens": 6}, None),
        ({"prompt_tokens": -5, "completion_tokens": 6}, None),
        ({"prompt_tokens": True, "completion_tokens": 6}, None),
        ({}, None),
        ("many", None),
        (None, None),
    ],
)
def test_usage_parsing(usage, expected):
    data = {"choices": [], "usage": usage} if usage is not None else {"choices": []}
    got = parse_usage(data)
    assert (None if got is None else (got.tokens_in, got.tokens_out)) == expected


async def test_missing_usage_gives_none_not_a_guess(make_settings):
    body = {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]}
    provider, _ = make_provider(make_settings, body)
    assert (await provider.complete("m", ask())).usage is None


# ---- things that must be errors -------------------------------------------

async def test_content_filter_finish_reason_is_a_block(make_settings):
    provider, _ = make_provider(make_settings, reply("partial", finish="content_filter"))
    with pytest.raises(ContentFilterBlocked):
        await provider.complete("m", ask())


@pytest.mark.parametrize("content", ["", "   \n ", None, []])
async def test_empty_replies_are_errors(make_settings, content):
    provider, _ = make_provider(make_settings, reply(content, finish="stop"))
    with pytest.raises(BadResponse, match="empty reply.*stop"):
        await provider.complete("m", ask())


async def test_an_empty_reply_cut_off_by_length_hints_at_max_tokens(make_settings):
    provider, _ = make_provider(make_settings, reply("", finish="length"))
    with pytest.raises(BadResponse, match="raise max_tokens"):
        await provider.complete("m", ask())


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="<html>gateway welcome page</html>"),
        httpx.Response(200, json={"id": "x"}),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, json=["not", "a", "dict"]),
        httpx.Response(200, json={"choices": ["nope"]}),
    ],
)
async def test_bad_200s_are_bad_responses(make_settings, response):
    provider, _ = make_provider(make_settings, response)
    with pytest.raises(BadResponse):
        await provider.complete("m", ask())


# ---- status codes ----------------------------------------------------------

def err(status: int, **error) -> httpx.Response:
    return httpx.Response(status, json={"error": error} if error else {})


# The exact shape ICA returned on 2026-10-27 for a model this key may not use.
REAL_MODEL_ACCESS_DENIED = err(
    403, code="403", type="team_model_access_denied",
    message="The requested model 'gpt-5.6-sol' is not available for this API key, or the model name is invalid. "
            "Check the models available to you and try again.",
)


@pytest.mark.parametrize(
    "response, expected",
    [
        (REAL_MODEL_ACCESS_DENIED, ModelAccessDenied),
        (err(403, message="You are not authorized to use this model"), ModelAccessDenied),
        (err(403, code="model_access_denied", message="denied"), ModelAccessDenied),
        (err(401, message="bad key"), AuthenticationFailed),
        (err(401, message="Invalid API key provided"), AuthenticationFailed),
        # A 401 means the credentials were rejected, whatever else the message says. Only a 403 can mean
        # "this key is fine but may not use this model".
        (err(401, code="team_model_access_denied", message="The requested model 'x' is not available for this API key"),
         AuthenticationFailed),
        (err(401, message="You are not authorized to use this model"), AuthenticationFailed),
        (err(403, message="forbidden"), AuthenticationFailed),
        (err(403, message="Your IP is not allowed"), AuthenticationFailed),
        (err(400, message="invalid parameter"), BadRequest),
        (err(422, message="unprocessable"), BadRequest),
        (err(413, message="too big"), BadRequest),
        (err(404, message="no route"), ModelNotFound),
        (err(400, code="model_not_found", message="The model `x` does not exist"), ModelNotFound),
        (err(400, message="Unknown model: foo"), ModelNotFound),
        (err(400, code="content_filter", message="blocked by content filter"), ContentFilterBlocked),
        (err(400, message="Your request was rejected by the safety system"), ContentFilterBlocked),
        (err(408), TransientProviderError),
        (err(429, message="slow down"), TransientProviderError),
        (err(500), TransientProviderError),
        (err(502), TransientProviderError),
        (err(503), TransientProviderError),
        (err(504), TransientProviderError),
        (err(529), TransientProviderError),
        (err(599), TransientProviderError),
        (httpx.Response(502, text="<html>Bad gateway</html>"), TransientProviderError),
        (httpx.Response(400, text="plain text complaint"), BadRequest),
    ],
)
async def test_status_mapping(make_settings, response, expected):
    provider, _ = make_provider(make_settings, response)
    with pytest.raises(expected) as exc:
        await provider.complete("m", ask())
    assert type(exc.value) is expected


# ---- connection failures ---------------------------------------------------

@pytest.mark.parametrize(
    "failure",
    [
        httpx.ConnectError("refused"), httpx.ConnectTimeout("slow"), httpx.ReadTimeout("slow"),
        httpx.WriteTimeout("slow"), httpx.PoolTimeout("busy"), httpx.RemoteProtocolError("dropped"),
        httpx.ReadError("reset"),
    ],
)
async def test_network_trouble_is_transient(make_settings, failure):
    provider, _ = make_provider(make_settings, failure)
    with pytest.raises(TransientProviderError):
        await provider.complete("m", ask())


async def test_certificate_failure_is_its_own_error(make_settings):
    cause = ssl.SSLCertVerificationError("certificate verify failed: self signed certificate")
    failure = httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")
    failure.__cause__ = cause
    provider, _ = make_provider(make_settings, failure)
    with pytest.raises(TlsVerificationFailed):
        await provider.complete("m", ask())

    plain = httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")
    provider, _ = make_provider(make_settings, plain)
    with pytest.raises(TlsVerificationFailed):
        await provider.complete("m", ask())


# ---- error text never leaks ------------------------------------------------

def test_error_text_uses_only_parsed_fields_and_is_capped():
    response = httpx.Response(
        400, json={"error": {"code": "bad_thing", "type": "invalid", "message": "x" * 1000, "secret_extra": "LEAK"}},
    )
    text = error_text(response)
    assert text.startswith("HTTP 400: bad_thing - invalid - xxx") and len(text) <= 300
    assert "LEAK" not in text


def test_error_text_for_non_json_bodies_is_only_the_status():
    assert error_text(httpx.Response(502, text="<html>BODY-WITH-A-PROMPT</html>")) == "HTTP 502"
    assert error_text(httpx.Response(500, json={"unexpected": "shape"})) == "HTTP 500"
    assert error_text(httpx.Response(400, json={"error": "flat string error"})) == "HTTP 400: flat string error"
    assert error_text(httpx.Response(400, json={"message": "top-level message"})) == "HTTP 400: top-level message"


async def test_a_server_that_echoes_the_key_and_prompt_cannot_leak_through_a_non_json_body(make_settings):
    echo = httpx.Response(500, text=f"you sent {KEY} to {ENDPOINT} with PROMPT-SENTINEL")
    provider, _ = make_provider(make_settings, echo)
    with pytest.raises(TransientProviderError) as exc:
        await provider.complete("m", ask("PROMPT-SENTINEL"))
    for secret in (KEY, ENDPOINT, "PROMPT-SENTINEL"):
        assert secret not in str(exc.value)


async def test_connection_errors_do_not_expose_the_endpoint(make_settings):
    provider, _ = make_provider(make_settings, httpx.ConnectError(f"cannot reach {ENDPOINT} with {KEY}"))
    with pytest.raises(TransientProviderError) as exc:
        await provider.complete("m", ask())
    assert KEY not in str(exc.value) and ENDPOINT not in str(exc.value)
    assert exc.value.__cause__ is None  # the original message, which names the host, is not chained


# ---- the client ------------------------------------------------------------

async def test_one_shared_client_is_reused_and_closes_safely(make_settings):
    provider, fake = make_provider(make_settings)
    client = provider.client
    await provider.complete("m", ask())
    await provider.complete("m", ask())
    assert provider.client is client and len(fake.requests) == 2
    assert not client.is_closed
    await provider.aclose()
    assert client.is_closed
    await provider.aclose()  # closing twice is harmless


async def test_timeouts_are_applied(make_settings):
    provider, _ = make_provider(make_settings, llm_timeout_seconds=42)
    timeout = provider.client.timeout
    assert (timeout.read, timeout.write, timeout.pool, timeout.connect) == (42, 42, 42, 10.0)


async def test_the_real_connection_pool_allows_a_whole_phase_in_parallel(make_settings):
    # No transport override, so this is the pool a live run would use. Nothing is sent.
    provider = IcaProvider(make_settings(ibm_ica_endpoint=ENDPOINT, ibm_ica_api_key=KEY))
    try:
        pool = provider.client._transport._pool
        assert pool._max_connections == 20 and pool._max_keepalive_connections == 20
    finally:
        await provider.aclose()


def test_tls_verifies_by_default_and_the_switch_turns_it_off(make_settings):
    from app.llm.providers.ica import build_ssl_context

    default = build_ssl_context(False)
    assert isinstance(default, ssl.SSLContext) and default.verify_mode == ssl.CERT_REQUIRED
    assert build_ssl_context(True) is False
    assert make_settings().ibm_ica_insecure_tls is False
    assert make_settings(ibm_ica_insecure_tls=True).ibm_ica_insecure_tls is True


# ---- construction ----------------------------------------------------------

def test_building_a_provider_makes_no_network_call(make_settings):
    fake = Recorder(reply())
    IcaProvider(make_settings(ibm_ica_endpoint=ENDPOINT, ibm_ica_api_key=KEY), transport=httpx.MockTransport(fake))
    assert fake.requests == []


@pytest.mark.parametrize(
    "settings, variable",
    [
        ({"ibm_ica_api_key": KEY}, "IBM_ICA_ENDPOINT"),
        ({"ibm_ica_endpoint": ENDPOINT}, "IBM_ICA_API_KEY"),
        ({"ibm_ica_endpoint": "   ", "ibm_ica_api_key": KEY}, "IBM_ICA_ENDPOINT"),
    ],
)
def test_missing_credentials_name_the_variable(make_settings, settings, variable):
    with pytest.raises(IcaConfigError, match=variable):
        IcaProvider(make_settings(**settings))


def test_new_settings_read_from_a_dotenv_file(tmp_path):
    from app.config import Settings

    path = tmp_path / "t.env"
    path.write_text("IBM_ICA_INSECURE_TLS=true\nIBM_ICA_USER_AGENT=my-agent/2\n")
    s = Settings(_env_file=path)
    assert s.ibm_ica_insecure_tls is True and s.ibm_ica_user_agent == "my-agent/2"
