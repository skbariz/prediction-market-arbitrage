from prediction_arb.cli import main


def test_check_config_masks_secrets(monkeypatch, capsys):
    monkeypatch.setenv("POLY_PRIVATE_KEY", "0xSUPER-SECRET-WALLET-KEY")
    assert main(["--env-file", "/nonexistent", "check-config"]) == 0
    out = capsys.readouterr().out
    assert "SUPER-SECRET" not in out
    assert "poly_private_key" in out and "<set>" in out


def test_live_mode_requires_explicit_flag_and_credentials(monkeypatch, capsys):
    monkeypatch.setenv("DRY_RUN", "false")
    assert main(["--env-file", "/nonexistent", "run", "--once"]) == 1
    err = capsys.readouterr().err
    assert "Refusing to start live trading" in err
    assert "--live" in err


def test_invalid_config_exits_nonzero(monkeypatch, capsys):
    monkeypatch.setenv("MAX_POSITION_USD", "0")
    assert main(["--env-file", "/nonexistent", "check-config"]) == 1
    assert "MAX_POSITION_USD" in capsys.readouterr().err
