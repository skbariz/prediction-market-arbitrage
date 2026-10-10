import base64
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from aiohttp import web
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, padding, rsa

from prediction_arb.clients.kalshi import (
    KalshiAuthError,
    KalshiClient,
    load_private_key,
    parse_market,
)
from prediction_arb.config import Settings
from prediction_arb.models import Side

RAW_MARKET = {
    "ticker": "KXNBA-27-NYK",
    "title": "Will New York win the 2027 Pro Basketball Finals?",
    "market_type": "binary",
    "status": "active",
    "close_time": "2099-07-30T14:00:00Z",
    "expected_expiration_time": "2097-07-31T14:00:00Z",
    "yes_ask_dollars": "0.0900",
    "no_ask_dollars": "0.9200",
    "volume_fp": "1051618.21",
}


def _rsa_pem() -> tuple[rsa.RSAPrivateKey, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()
    return key, pem


def test_parse_market():
    market = parse_market(RAW_MARKET)
    assert market.market_id == "KXNBA-27-NYK"
    assert (market.price.yes, market.price.no) == (0.09, 0.92)
    assert market.volume == pytest.approx(1051618.21)
    assert market.resolves_at.year == 2097  # expected resolution, not the worst-case close
    assert market.is_active


@pytest.mark.parametrize(
    "override",
    [
        {"close_time": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()},
        {"yes_ask_dollars": None},
        {"market_type": "scalar"},
        {"yes_ask_dollars": "not-a-number"},
    ],
)
def test_parse_market_skips_unusable(override):
    assert parse_market({**RAW_MARKET, **override}) is None


def test_rsa_signature_is_pss_over_timestamp_method_and_full_path():
    key, pem = _rsa_pem()
    client = KalshiClient(Settings(kalshi_api_key_id="key-id", kalshi_private_key=pem))
    headers = client.auth_headers("POST", "/portfolio/orders")

    message = f"{headers['KALSHI-ACCESS-TIMESTAMP']}POST/trade-api/v2/portfolio/orders".encode()
    key.public_key().verify(
        base64.b64decode(headers["KALSHI-ACCESS-SIGNATURE"]),
        message,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256(),
    )
    assert headers["KALSHI-ACCESS-KEY"] == "key-id"


def test_ed25519_keys_are_supported(tmp_path):
    key = ed25519.Ed25519PrivateKey.generate()
    path = tmp_path / "kalshi.pem"
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    client = KalshiClient(Settings(kalshi_api_key_id="id", kalshi_private_key_path=str(path)))
    headers = client.auth_headers("GET", "/portfolio/balance")
    message = f"{headers['KALSHI-ACCESS-TIMESTAMP']}GET/trade-api/v2/portfolio/balance".encode()
    key.public_key().verify(base64.b64decode(headers["KALSHI-ACCESS-SIGNATURE"]), message)


def test_single_line_env_key_is_unescaped(monkeypatch):
    _, pem = _rsa_pem()
    monkeypatch.setenv("KALSHI_PRIVATE_KEY", pem.replace("\n", "\\n"))
    assert load_private_key(Settings.from_env(env_file=None)) is not None


def test_bad_key_error_does_not_leak_key_material():
    label = "RSA " + "PRIVATE KEY"  # split so secret scanners do not flag this fake key
    secret = f"-----BEGIN {label}-----\nTOP-SECRET-VALUE\n-----END {label}-----"
    with pytest.raises(KalshiAuthError) as exc:
        load_private_key(Settings(kalshi_private_key=secret))
    assert "TOP-SECRET-VALUE" not in str(exc.value)


def test_no_auth_headers_without_credentials():
    assert KalshiClient(Settings()).auth_headers("GET", "/markets") == {}


async def test_place_order_without_credentials_fails_safely():
    async with KalshiClient(Settings()) as client:
        result = await client.place_order("T", Side.YES, 0.5, 10)
    assert not result.ok
    assert "credentials" in result.error


@pytest.fixture
async def fake_kalshi(aiohttp_unused_port):
    received: list[dict] = []

    async def create_order(request: web.Request) -> web.Response:
        body = await request.json()
        received.append({"body": body, "headers": dict(request.headers)})
        status = "executed" if body["count"] < 100 else "canceled"
        return web.json_response({"order": {"order_id": "ord-123", "status": status}}, status=201)

    app = web.Application()
    app.router.add_post("/trade-api/v2/portfolio/orders", create_order)
    runner = web.AppRunner(app)
    await runner.setup()
    port = aiohttp_unused_port()
    await web.TCPSite(runner, "127.0.0.1", port).start()
    yield f"http://127.0.0.1:{port}/trade-api/v2", received
    await runner.cleanup()


@pytest.fixture
def aiohttp_unused_port():
    from aiohttp.test_utils import unused_port

    return unused_port


async def test_place_order_sends_fill_or_kill_limit_buy(fake_kalshi):
    base_url, received = fake_kalshi
    _, pem = _rsa_pem()
    settings = Settings(kalshi_api_key_id="id", kalshi_private_key=pem, kalshi_base_url=base_url)

    async with KalshiClient(settings) as client:
        filled = await client.place_order("KXNBA-27-NYK", Side.NO, 0.92, 54)
        killed = await client.place_order("KXNBA-27-NYK", Side.NO, 0.92, 500)

    assert filled.ok and filled.order_id == "ord-123"
    assert not killed.ok and killed.status == "canceled"
    body = received[0]["body"]
    assert body["action"] == "buy"
    assert body["side"] == "no"
    assert body["no_price"] == 92
    assert "yes_price" not in body
    assert body["count"] == 54
    assert body["time_in_force"] == "fill_or_kill"
    assert body["client_order_id"]
    assert received[0]["headers"]["KALSHI-ACCESS-KEY"] == "id"


async def test_place_order_rejects_out_of_range_price(fake_kalshi):
    base_url, received = fake_kalshi
    _, pem = _rsa_pem()
    settings = replace(
        Settings(kalshi_api_key_id="id", kalshi_private_key=pem), kalshi_base_url=base_url
    )
    async with KalshiClient(settings) as client:
        result = await client.place_order("T", Side.YES, 0.999, 1)
    assert not result.ok
    assert received == []


@pytest.mark.parametrize("value", ["nan", "inf"])
def test_parse_market_rejects_non_finite_prices(value):
    assert parse_market({**RAW_MARKET, "yes_ask_dollars": value}) is None


def test_warns_when_key_file_is_readable_by_others(tmp_path):
    import os

    from prediction_arb.log import logger

    _, pem = _rsa_pem()
    path = tmp_path / "kalshi.pem"
    path.write_text(pem)
    path.chmod(0o644)
    messages: list[str] = []
    sink = logger.add(messages.append, level="WARNING")
    try:
        load_private_key(Settings(kalshi_private_key_path=str(path)))
    finally:
        logger.remove(sink)
    if os.name == "posix":
        assert any("chmod 600" in m for m in messages)


async def test_place_order_does_not_follow_redirects(aiohttp_unused_port):
    hits = {"redirect_target": 0}

    async def redirect(request: web.Request) -> web.Response:
        raise web.HTTPTemporaryRedirect(f"http://127.0.0.1:{port}/elsewhere")

    async def elsewhere(request: web.Request) -> web.Response:
        hits["redirect_target"] += 1
        return web.json_response({"order": {"order_id": "x", "status": "executed"}})

    app = web.Application()
    app.router.add_post("/trade-api/v2/portfolio/orders", redirect)
    app.router.add_post("/elsewhere", elsewhere)
    runner = web.AppRunner(app)
    await runner.setup()
    port = aiohttp_unused_port()
    await web.TCPSite(runner, "127.0.0.1", port).start()
    try:
        _, pem = _rsa_pem()
        settings = Settings(
            kalshi_api_key_id="id",
            kalshi_private_key=pem,
            kalshi_base_url=f"http://127.0.0.1:{port}/trade-api/v2",
        )
        async with KalshiClient(settings) as client:
            result = await client.place_order("T", Side.YES, 0.5, 1)
    finally:
        await runner.cleanup()
    assert not result.ok
    assert hits["redirect_target"] == 0
