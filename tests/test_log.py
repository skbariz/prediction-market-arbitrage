import os
import stat

from prediction_arb.log import configure_logging, logger


def _fail_with_secret_in_scope() -> None:
    secret = os.environ["TEST_SECRET_VALUE"]
    raise ValueError(f"failed after reading {len(secret)} characters")


def test_tracebacks_never_include_local_variable_values(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TEST_SECRET_VALUE", "do-not-log-this-private-key")
    log_file = tmp_path / "logs" / "bot.log"
    configure_logging("INFO", str(log_file))
    try:
        _fail_with_secret_in_scope()
    except ValueError:
        logger.exception("cycle failed")
    logger.complete()
    logger.remove()

    assert "do-not-log-this-private-key" not in capsys.readouterr().err
    assert "do-not-log-this-private-key" not in log_file.read_text()
    assert "ValueError" in log_file.read_text()


def test_log_file_is_private(tmp_path):
    log_file = tmp_path / "logs" / "bot.log"
    configure_logging("INFO", str(log_file))
    logger.info("hello")
    logger.complete()
    logger.remove()
    if os.name == "posix":
        assert stat.S_IMODE(log_file.stat().st_mode) == 0o600
