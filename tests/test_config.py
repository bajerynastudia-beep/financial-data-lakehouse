import copy

import pytest

from fin_lakehouse.config import ConfigError, get_secret, load_config, validate_config


def test_repo_config_is_valid(repo_root):
    cfg = load_config(repo_root)
    assert cfg.table("silver", "prices") == "workspace.fin_silver.prices"
    assert cfg.raw_volume_path == "/Volumes/workspace/fin_bronze/raw"
    assert abs(sum(cfg.portfolio_weights.values()) - 1) < 1e-9
    assert all(c["currency"] == "USD" for c in cfg.sec_companies)


def _broken(cfg, mutate):
    data = {"settings": copy.deepcopy(cfg.settings), "instruments": copy.deepcopy(cfg.instruments),
            "portfolio": copy.deepcopy(cfg.portfolio)}
    mutate(data)
    return type(cfg)(**data)


def test_weights_must_sum_to_one(repo_root):
    cfg = load_config(repo_root)
    bad = _broken(cfg, lambda d: d["portfolio"]["positions"][0].update(weight=0.5))
    with pytest.raises(ConfigError, match="sumują się"):
        validate_config(bad)


def test_portfolio_ticker_must_exist(repo_root):
    cfg = load_config(repo_root)
    bad = _broken(cfg, lambda d: d["portfolio"]["positions"][0].update(ticker="nieistnieje"))
    with pytest.raises(ConfigError, match="spoza instruments"):
        validate_config(bad)


def test_currency_needs_nbp_rate(repo_root):
    cfg = load_config(repo_root)
    bad = _broken(cfg, lambda d: d["settings"]["sources"]["nbp"].update(currencies=["USD"]))
    with pytest.raises(ConfigError, match="EUR"):
        validate_config(bad)


def test_secret_from_env_and_clear_error(repo_root, monkeypatch):
    cfg = load_config(repo_root)
    monkeypatch.setenv("STOOQ_API_KEY", "abc")
    assert get_secret(cfg, "stooq_api_key") == "abc"
    monkeypatch.delenv("STOOQ_API_KEY")
    with pytest.raises(ConfigError, match="fin-lakehouse"):
        get_secret(cfg, "stooq_api_key")


def test_secret_prefers_databricks_scope(repo_root):
    cfg = load_config(repo_root)

    class Secrets:
        @staticmethod
        def get(scope, key):
            assert (scope, key) == ("fin-lakehouse", "sec_user_agent")
            return "Fundusz Test test@example.com"

    class DbUtils:
        secrets = Secrets()

    assert get_secret(cfg, "sec_user_agent", DbUtils()) == "Fundusz Test test@example.com"
