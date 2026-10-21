from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from backend.config import BLOCKED_INDICATORS
from backend.data_loader import DataBundle


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    message: str


def validate_bundle(bundle: DataBundle) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    if bundle.actuarial.duplicated(subset=["Plano / ponte", "Indicador"]).any():
        issues.append(ValidationIssue("erro", "ATU_DUP", "Há duplicidade plano/indicador na base atuarial."))

    if bundle.fiscal["Ano"].duplicated().any():
        issues.append(ValidationIssue("erro", "FIS_DUP", "Há exercício duplicado na matriz fiscal anual."))

    blocked = set(
        bundle.releases.loc[
            bundle.releases["Status de liberação"].astype(str).str.startswith("BLOQUEADO"), "Indicador"
        ].astype(str)
    )
    missing_blocked = BLOCKED_INDICATORS.difference(blocked)
    if missing_blocked:
        issues.append(
            ValidationIssue("erro", "GATE_MISSING", f"Bloqueios não encontrados na matriz: {sorted(missing_blocked)}")
        )

    mil_fin_2026 = bundle.flows.loc[
        (bundle.flows["Avaliação"] == 2026) & (bundle.flows["Dimensão"] == "Financeiro / Militar")
    ]
    if not mil_fin_2026.empty:
        issues.append(ValidationIssue("erro", "MIL_FIN_2026", "MIL FIN 2026 não pode ser materializado como série."))

    fiscal_2026 = bundle.fiscal.loc[bundle.fiscal["Ano"].eq(2026)]
    if fiscal_2026.empty or not fiscal_2026["Nota de comparabilidade"].astype(str).str.contains("Parcial", case=False).all():
        issues.append(ValidationIssue("erro", "FIS_2026", "2026 precisa permanecer explicitamente parcial."))

    if bundle.fiscal["Cobertura de insuficiências financeiras"].iloc[:3].notna().any():
        issues.append(ValidationIssue("erro", "NA_AS_ZERO", "N/A estrutural 2022–2024 foi preenchido indevidamente."))

    required_metadata = {
        "Ano", "Competência", "Periodicidade", "Poder", "Órgão", "Anexo",
        "Demonstrativo", "Indicador", "Unidade", "Fonte", "Status",
    }
    if required_metadata.difference(bundle.fiscal_series.columns):
        issues.append(ValidationIssue("erro", "FIS_META", "Metadados fiscais obrigatórios incompletos."))

    fiscal = bundle.fiscal.copy()
    composition_gap = (
        fiscal["Inativos e pensionistas — bruta"]
        - fiscal["Aposentadorias, reserva e reformas"]
        - fiscal["Pensões — RGF"]
    ).abs().max()
    if composition_gap >= 0.02:
        issues.append(ValidationIssue("erro", "FIS_COMP", "Aposentadorias e pensões não fecham o total bruto."))

    ratio_gap = (
        fiscal["DTP / RCL ajustada"]
        - fiscal["DTP"] / fiscal["RCL ajustada (pessoal)"] * 100
    ).abs().max()
    if ratio_gap >= 0.011:
        issues.append(ValidationIssue("erro", "FIS_RATIO", "DTP/RCL ajustada diverge além do arredondamento."))

    for fund in ("capitalização", "repartição"):
        gap = (
            fiscal[f"Receitas fundo em {fund}"]
            - fiscal[f"Despesas fundo em {fund}"]
            - fiscal[f"Resultado fundo em {fund}"]
        ).abs().max()
        if gap >= 0.02:
            issues.append(ValidationIssue("erro", "FIS_RESULT", f"Identidade do fundo em {fund} não fecha."))

    return issues
