import pytest

from prediction_arb.config import DEFAULT_KALSHI_SERIES, ConfigError, Settings


def test_defaults_are_safe():
    settings = Settings.from_env(env_file=None)
    assert settings.dry_run is True
    assert settings.kalshi_series == DEFAULT_KALSHI_SERIES
    assert not settings.has_kalshi_credentials
    assert not settings.has_polymarket_credentials


def test_reads_environment(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("MAX_POSITION_USD", "25.5")
    monkeypatch.setenv("KALSHI_SERIES", "kxnba, kxnhl")
    monkeypatch.setenv("KALSHI_BASE_URL", "https://demo-api.kalshi.co/trade-api/v2/")
    settings = Settings.from_env(env_file=None)
    assert settings.dry_run is False
    assert settings.max_position_usd == 25.5
    assert settings.kalshi_series == ("KXNBA", "KXNHL")
    assert settings.kalshi_base_url == "https://demo-api.kalshi.co/trade-api/v2"


def test_reads_dotenv_file(tmp_path):
    env = tmp_path / ".env"
    env.write_text("MIN_PROFIT_PCT=0.05\n")
    assert Settings.from_env(env).min_profit_pct == 0.05


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("DRY_RUN", "maybe"),
        ("MAX_POSITION_USD", "-1"),
        ("MIN_PROFIT_PCT", "2"),
        ("POLL_INTERVAL_SEC", "1"),
        ("KALSHI_BASE_URL", "http://insecure.example"),
        ("POLY_SIGNATURE_TYPE", "7"),
        ("MAX_OPEN_POSITIONS", "abc"),
        ("KALSHI_FEE_RATE", "-0.1"),
        ("POLY_DEFAULT_FEE_RATE", "2"),
    ],
)
def test_rejects_invalid_values(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ConfigError):
        Settings.from_env(env_file=None)


@pytest.mark.parametrize(
    ("name", "url"),
    [
        ("KALSHI_BASE_URL", "https://evil.example/trade-api/v2"),
        ("KALSHI_BASE_URL", "https://api.kalshi.com@evil.example/trade-api/v2"),
        ("KALSHI_BASE_URL", "https://kalshi.com.evil.example/trade-api/v2"),
        ("KALSHI_BASE_URL", "https://evilkalshi.com/trade-api/v2"),
        ("KALSHI_BASE_URL", "https://api.kalshi.com:8443/trade-api/v2"),
        ("KALSHI_BASE_URL", "https://api.kalshi.com:bad/trade-api/v2"),
        ("POLY_CLOB_URL", "https://clob.polymarket.com.evil.example"),
        ("POLY_GAMMA_URL", "http://gamma-api.polymarket.com"),
    ],
)
def test_api_urls_must_point_at_the_exchanges(monkeypatch, name, url):
    monkeypatch.setenv(name, url)
    with pytest.raises(ConfigError, match=name):
        Settings.from_env(env_file=None)


def test_official_and_demo_hosts_are_allowed(monkeypatch):
    monkeypatch.setenv("KALSHI_BASE_URL", "https://demo-api.kalshi.co/trade-api/v2")
    monkeypatch.setenv("POLY_CLOB_URL", "https://clob.polymarket.com")
    assert Settings.from_env(env_file=None).kalshi_base_url.startswith("https://demo-api")


@pytest.mark.parametrize("value", ["inf", "nan", "-inf"])
def test_rejects_non_finite_numbers(monkeypatch, value):
    monkeypatch.setenv("MAX_POSITION_USD", value)
    with pytest.raises(ConfigError):
        Settings.from_env(env_file=None)


def test_repr_never_contains_secrets_or_account_identifiers():
    settings = Settings(
        kalshi_api_key_id="KALSHI-KEY-ID",
        kalshi_private_key="KALSHI-SECRET",
        poly_private_key="POLY-SECRET",
        poly_funder_address="0xFUNDER",
        poly_api_secret="API-SECRET",
        poly_passphrase="PASSPHRASE",
        poly_api_key="API-KEY",
    )
    text = repr(settings)
    for secret in (
        "KALSHI-KEY-ID", "KALSHI-SECRET", "POLY-SECRET", "0xFUNDER", "API-SECRET", "PASSPHRASE", "API-KEY",
    ):  # fmt: skip
        assert secret not in text


def test_live_trading_problems():
    assert len(Settings().live_trading_problems()) == 2
    ready = Settings(kalshi_api_key_id="id", kalshi_private_key="k", poly_private_key="p")
    assert ready.live_trading_problems() == []
    proxy = Settings(
        kalshi_api_key_id="id", kalshi_private_key="k", poly_private_key="p", poly_signature_type=2
    )
    assert any("POLY_FUNDER_ADDRESS" in p for p in proxy.live_trading_problems())
