"""Wczytywanie i walidacja konfiguracji (config/*.yml) oraz odczyt sekretów."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Błąd konfiguracji – zatrzymuje potok, zanim cokolwiek zostanie pobrane."""


@dataclass(frozen=True)
class Config:
    settings: dict[str, Any]
    instruments: list[dict[str, Any]]
    portfolio: dict[str, Any]

    # ---- nazwy obiektów w Unity Catalog -------------------------------------------------
    @property
    def catalog(self) -> str:
        return self.settings["catalog"]

    def schema(self, layer: str) -> str:
        return f"{self.catalog}.{self.settings['schemas'][layer]}"

    def table(self, layer: str, name: str) -> str:
        """Pełna nazwa tabeli, np. table('silver', 'fx_rates') -> workspace.fin_silver.fx_rates."""
        return f"{self.schema(layer)}.{name}"

    @property
    def raw_volume_path(self) -> str:
        s = self.settings
        return f"/Volumes/{s['catalog']}/{s['schemas']['bronze']}/{s['raw_volume']}"

    # ---- instrumenty ---------------------------------------------------------------------
    @property
    def tickers(self) -> list[str]:
        return [i["ticker"] for i in self.instruments]

    @property
    def sec_companies(self) -> list[dict[str, Any]]:
        """Spółki, dla których pobieramy dane finansowe z SEC (mają sec_cik)."""
        return [i for i in self.instruments if i.get("sec_cik")]

    @property
    def portfolio_weights(self) -> dict[str, float]:
        return {p["ticker"]: float(p["weight"]) for p in self.portfolio["positions"]}


def _read_yaml(path: Path) -> Any:
    if not path.exists():
        raise ConfigError(f"Brak pliku konfiguracyjnego: {path}")
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_config(repo_root: str | os.PathLike) -> Config:
    """Wczytuje config/settings.yml, config/instruments.yml i config/portfolio.yml."""
    root = Path(repo_root)
    cfg = Config(
        settings=_read_yaml(root / "config" / "settings.yml"),
        instruments=_read_yaml(root / "config" / "instruments.yml")["instruments"],
        portfolio=_read_yaml(root / "config" / "portfolio.yml"),
    )
    validate_config(cfg)
    return cfg


ALLOWED_CURRENCIES = {"PLN", "USD", "EUR"}
ALLOWED_TYPES = {"stock", "index"}


def validate_config(cfg: Config) -> None:
    """Reguły poprawności konfiguracji. Każde naruszenie -> ConfigError z opisem."""
    errors: list[str] = []

    tickers = [i.get("ticker") for i in cfg.instruments]
    if len(tickers) != len(set(tickers)):
        errors.append("Zduplikowane tickery w instruments.yml")
    for inst in cfg.instruments:
        for field in ("ticker", "name", "market", "currency", "type"):
            if not inst.get(field):
                errors.append(f"Instrument {inst} nie ma pola '{field}'")
        if inst.get("currency") not in ALLOWED_CURRENCIES:
            errors.append(f"{inst.get('ticker')}: niedozwolona waluta {inst.get('currency')}")
        if inst.get("type") not in ALLOWED_TYPES:
            errors.append(f"{inst.get('ticker')}: niedozwolony typ {inst.get('type')}")

    fx_needed = {i["currency"] for i in cfg.instruments if i.get("currency")} - {"PLN"}
    fx_configured = set(cfg.settings["sources"]["nbp"]["currencies"])
    if not fx_needed <= fx_configured:
        errors.append(f"Brak kursów NBP dla walut: {sorted(fx_needed - fx_configured)}")

    positions = cfg.portfolio.get("positions", [])
    weights = [float(p.get("weight", 0)) for p in positions]
    if not positions:
        errors.append("Portfel nie ma pozycji")
    if any(w <= 0 for w in weights):
        errors.append("Wagi w portfelu muszą być dodatnie")
    if abs(sum(weights) - 1.0) > 1e-6:
        errors.append(f"Wagi w portfelu sumują się do {sum(weights):.4f}, a powinny do 1")
    unknown = {p.get("ticker") for p in positions} - set(tickers)
    if unknown:
        errors.append(f"Pozycje portfela spoza instruments.yml: {sorted(unknown)}")
    if float(cfg.portfolio.get("initial_capital_pln", 0)) <= 0:
        errors.append("initial_capital_pln musi być dodatni")

    if errors:
        raise ConfigError("Niepoprawna konfiguracja:\n- " + "\n- ".join(errors))


def get_secret(cfg: Config, name: str, dbutils: Any = None) -> str:
    """Zwraca sekret: najpierw Databricks secret scope, potem zmienna środowiskowa.

    name: klucz z settings.yml -> secrets.keys (np. 'stooq_api_key').
    Zmienna środowiskowa ma nazwę wielkimi literami (np. STOOQ_API_KEY).
    """
    scope = cfg.settings["secrets"]["scope"]
    key = cfg.settings["secrets"]["keys"][name]
    if dbutils is not None:
        try:
            value = dbutils.secrets.get(scope=scope, key=key)
            if value:
                return value
        except Exception:  # brak scope/klucza – próbujemy dalej
            pass
    value = os.environ.get(name.upper())
    if value:
        return value
    raise ConfigError(
        f"Brak sekretu '{name}'. Dodaj go do Databricks secret scope '{scope}' (klucz '{key}') "
        f"albo ustaw zmienną środowiskową {name.upper()} – instrukcja w README.md."
    )
