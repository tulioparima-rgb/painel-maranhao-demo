from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from io import StringIO
from pathlib import Path

import pandas as pd


PUBLIC_DATA_ROOT = Path(__file__).resolve().parents[1] / "public_data"


class DataLoadError(RuntimeError):
    """Erro contextualizado de leitura dos dados públicos sanitizados."""


@dataclass(frozen=True)
class DataBundle:
    actuarial: pd.DataFrame
    fiscal: pd.DataFrame
    fiscal_series: pd.DataFrame
    releases: pd.DataFrame
    flows: pd.DataFrame
    contribution_rates: pd.DataFrame
    fiscal_projections: pd.DataFrame
    fiscal_projection_assumptions: pd.DataFrame
    actuarial_balances: pd.DataFrame


def _read_table(name: str) -> pd.DataFrame:
    path = PUBLIC_DATA_ROOT / f"{name}.json"
    if not path.is_file():
        raise DataLoadError(f"Tabela pública não encontrada: {name}")
    try:
        return pd.read_json(StringIO(path.read_text(encoding="utf-8")), orient="table")
    except Exception:
        raise DataLoadError(f"Falha ao ler a tabela pública: {name}") from None


@lru_cache(maxsize=1)
def load_bundle() -> DataBundle:
    return DataBundle(
        actuarial=_read_table("actuarial"),
        fiscal=_read_table("fiscal"),
        fiscal_series=_read_table("fiscal_series"),
        releases=_read_table("releases"),
        flows=_read_table("flows"),
        contribution_rates=_read_table("contribution_rates"),
        fiscal_projections=_read_table("fiscal_projections"),
        fiscal_projection_assumptions=_read_table("fiscal_projection_assumptions"),
        actuarial_balances=_read_table("actuarial_balances"),
    )
