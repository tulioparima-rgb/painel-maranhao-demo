from __future__ import annotations

import math
import re
from typing import Iterable

import pandas as pd


IPCA_FACTOR = 1.1435259627

FLOW_COLORS = {
    "Previdenciário / Civil": "#17534D",
    "Financeiro / Civil": "#C3A35F",
    "Previdenciário / Militar": "#3C91A8",
    "Financeiro / Militar": "#A63D40",
    "Total compatível": "#6B5B95",
}

ARIMA_COLORS = {
    "Receita": "#17534D",
    "Despesa": "#A65A46",
    "Resultado anual": "#C3A35F",
}


ACTUARIAL_COLUMNS = {
    "2022 nominal": "Valor original 2022",
    "2022 em R$ de 2025": "2022 atualizado a dez/2025",
    "2025 observado": "Valor observado 2025",
}

EXECUTIVE_PLAN_MAP = {
    "Previdenciário / Civil": "FEPA — Civil",
    "Financeiro / Civil": "Tesouro — Civil",
    "Previdenciário / Militar": "Militares — ponte 2022/SPSM 2025",
}


def brl(value: object, compact: bool = False) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    number = float(value)
    if compact:
        magnitude = abs(number)
        if magnitude >= 1_000_000_000:
            return f"R$ {number / 1_000_000_000:,.2f} bi".replace(",", "X").replace(".", ",").replace("X", ".")
        if magnitude >= 1_000_000:
            return f"R$ {number / 1_000_000:,.1f} mi".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def integer(value: object) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{int(round(float(value))):,}".replace(",", ".")


def percent(value: object, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):.{digits}f}%".replace(".", ",")


def actuarial_total(frame: pd.DataFrame, indicator: str, column: str) -> float:
    matching = frame.loc[frame["Indicador"].eq(indicator)].copy()
    consolidated = matching.loc[matching["Plano / ponte"].astype(str).str.startswith("Sistema")]
    subset = consolidated[column] if not consolidated.empty else matching[column]
    numeric = pd.to_numeric(subset, errors="coerce")
    return float(numeric.sum(min_count=1))


def actuarial_kpis(frame: pd.DataFrame) -> dict[str, float]:
    result_2022 = actuarial_total(frame, "Resultado atuarial", "Valor original 2022")
    result_2022_real = actuarial_total(frame, "Resultado atuarial", "2022 atualizado a dez/2025")
    result_2025 = actuarial_total(frame, "Resultado atuarial", "Valor observado 2025")
    return {
        "resultado_2022": result_2022,
        "resultado_2022_real": result_2022_real,
        "resultado_2025": result_2025,
        "variacao_nominal": result_2025 - result_2022,
        "variacao_real": result_2025 - result_2022_real,
        "ativos_garantidores_2025": actuarial_total(frame, "Ativos garantidores", "Valor observado 2025"),
        "provisoes_2025": actuarial_total(frame, "Provisões matemáticas", "Valor observado 2025"),
        "populacao_2025": sum(
            actuarial_total(frame, indicator, "Valor observado 2025")
            for indicator in ("Ativos", "Aposentados", "Pensionistas")
        ),
    }


def actuarial_chart(frame: pd.DataFrame, indicators: Iterable[str], plans: Iterable[str]) -> pd.DataFrame:
    subset = frame.loc[frame["Indicador"].isin(indicators) & frame["Plano / ponte"].isin(plans)].copy()
    melted = subset.melt(
        id_vars=["Plano / ponte", "Indicador", "Unidade"],
        value_vars=list(ACTUARIAL_COLUMNS.values()),
        var_name="Comparação",
        value_name="Valor",
    )
    reverse = {value: key for key, value in ACTUARIAL_COLUMNS.items()}
    melted["Comparação"] = melted["Comparação"].map(reverse)
    melted["Valor"] = pd.to_numeric(melted["Valor"], errors="coerce")
    return melted.dropna(subset=["Valor"])


def demographic_summary(frame: pd.DataFrame, plans: Iterable[str] | None = None) -> pd.DataFrame:
    source = frame if plans is None else frame.loc[frame["Plano / ponte"].isin(plans)]
    rows: list[dict[str, object]] = []
    for indicator in ("Ativos", "Aposentados", "Pensionistas"):
        initial = actuarial_total(source, indicator, "Valor original 2022")
        final = actuarial_total(source, indicator, "Valor observado 2025")
        rows.append({"Grupo": indicator, "2022": initial, "2025": final, "Variação": final - initial})
    return pd.DataFrame(rows)


def flow_compatibility(frame: pd.DataFrame, evaluation: int, dimensions: Iterable[str]) -> dict[str, object]:
    """Valida o recorte anual; taxas distintas são metadado, não bloqueio de soma."""
    selected = list(dict.fromkeys(dimensions))
    subset = frame.loc[frame["Avaliação"].eq(evaluation) & frame["Dimensão"].isin(selected)]
    if len(selected) < 2:
        return {"compatible": False, "reason": "Selecione ao menos duas dimensões para avaliar uma soma.", "rate": None}
    present = set(subset["Dimensão"].dropna().astype(str))
    if present != set(selected):
        return {"compatible": False, "reason": "Há dimensão sem série publicada; N/A não pode compor total.", "rate": None}
    methods = subset["Método"].dropna().unique()
    if len(methods) != 1:
        return {
            "compatible": False,
            "reason": "Soma bloqueada: o recorte mistura métodos ou avaliações.",
            "rate": None,
        }
    rates = sorted(pd.to_numeric(subset["Taxa de juros (%)"], errors="coerce").dropna().unique().tolist())
    return {
        "compatible": True,
        "reason": "Agregação anual autorizada: mesma avaliação, método, exercício e unidade. Taxas distintas são preservadas como premissas e não são combinadas.",
        "rate": float(rates[0]) if len(rates) == 1 else None,
        "rates": rates,
    }


def aggregate_actuarial_flows(
    frame: pd.DataFrame,
    evaluation: int,
    dimensions: Iterable[str],
    years: tuple[int, int],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Soma fluxos financeiros por exercício e produz as três séries mandatórias."""
    selected = list(dict.fromkeys(dimensions))
    if not 1 <= len(selected) <= 3:
        raise ValueError("Selecione de um a três planos.")
    status = flow_compatibility(frame, evaluation, selected)
    if len(selected) > 1 and not status["compatible"]:
        raise ValueError(str(status["reason"]))
    subset = frame.loc[
        frame["Avaliação"].eq(evaluation)
        & frame["Dimensão"].isin(selected)
        & frame["Exercício"].between(years[0], years[1]),
        ["Exercício", "Dimensão", "Receitas", "Despesas"],
    ].copy()
    if subset.empty or set(subset["Dimensão"].unique()) != set(selected):
        raise ValueError("Há plano selecionado sem série publicada no recorte.")
    grouped = subset.groupby("Exercício", as_index=False)[["Receitas", "Despesas"]].sum(min_count=1)
    grouped["Resultado anual"] = grouped["Receitas"] - grouped["Despesas"]
    table = grouped.rename(
        columns={
            "Exercício": "Ano",
            "Receitas": "Receita agregada",
            "Despesas": "Despesa agregada",
            "Resultado anual": "Resultado anual agregado",
        }
    )
    long = table.melt(
        id_vars="Ano",
        value_vars=["Receita agregada", "Despesa agregada", "Resultado anual agregado"],
        var_name="Série",
        value_name="Valor",
    )
    long["Série"] = long["Série"].map(
        {
            "Receita agregada": "Receita",
            "Despesa agregada": "Despesa",
            "Resultado anual agregado": "Resultado anual",
        }
    )
    return table, long


def implicit_flow_rates(frame: pd.DataFrame, dimensions: Iterable[str]) -> pd.DataFrame:
    """Calcula alíquotas implícitas de 2026 pela razão entre somas, nunca pela média de taxas."""
    selected = list(dict.fromkeys(dimensions))
    subset = frame.loc[
        frame["Avaliação"].eq(2026)
        & frame["Exercício"].eq(2026)
        & frame["Dimensão"].isin(selected),
        [
            "Dimensão",
            "Base de cálculo da contribuição normal",
            "Contribuição do ente — benefícios a conceder",
            "Contribuição dos segurados ativos — benefícios a conceder",
        ],
    ].drop_duplicates("Dimensão")
    rows: list[dict[str, object]] = []
    for label, contribution in (
        ("Ente", "Contribuição do ente — benefícios a conceder"),
        ("Segurados ativos", "Contribuição dos segurados ativos — benefícios a conceder"),
    ):
        base = pd.to_numeric(subset["Base de cálculo da contribuição normal"], errors="coerce").sum(min_count=1)
        amount = pd.to_numeric(subset[contribution], errors="coerce").sum(min_count=1)
        rate = None if pd.isna(base) or math.isclose(float(base), 0.0) else abs(float(amount)) / abs(float(base)) * 100
        rows.append(
            {
                "Componente": label,
                "Contribuição no fluxo": amount,
                "Base de cálculo": base,
                "Alíquota implícita (%)": rate,
                "Fórmula": "Σ contribuições ÷ Σ bases × 100",
                "Competência": "Fluxo atuarial 2026",
            }
        )
    return pd.DataFrame(rows)


def flow_multiplan_long(
    frame: pd.DataFrame,
    evaluation: int,
    dimensions: Iterable[str],
    indicator: str,
    years: tuple[int, int],
    include_total: bool = False,
) -> pd.DataFrame:
    """Monta séries multiplano sem misturar indicadores nem preencher ausências."""
    selected = list(dict.fromkeys(dimensions))
    subset = frame.loc[
        frame["Avaliação"].eq(evaluation)
        & frame["Dimensão"].isin(selected)
        & frame["Exercício"].between(years[0], years[1]),
        ["Avaliação", "Exercício", "Dimensão", "Taxa de juros (%)", "Método", indicator],
    ].copy()
    subset = subset.rename(columns={indicator: "Valor"}).dropna(subset=["Valor"])
    subset["Indicador"] = indicator
    if include_total:
        status = flow_compatibility(frame, evaluation, selected)
        if not status["compatible"]:
            raise ValueError(str(status["reason"]))
        totals = subset.groupby(["Avaliação", "Exercício", "Indicador", "Método"], as_index=False)["Valor"].sum(min_count=1)
        totals["Dimensão"] = "Total compatível"
        totals["Taxa de juros (%)"] = status["rate"]
        subset = pd.concat([subset, totals[subset.columns]], ignore_index=True)
    return subset.sort_values(["Dimensão", "Exercício"]).reset_index(drop=True)


def plan_executive_snapshots(frame: pd.DataFrame) -> dict[str, dict[str, object]]:
    """Consolida a leitura 2025 por plano sem transformar ausência em zero."""
    result: dict[str, dict[str, object]] = {}
    payroll_by_group = {
        "Ativos": "Folha mensal de ativos",
        "Aposentados": "Folha mensal de aposentados",
        "Pensionistas": "Folha mensal de pensionistas",
    }
    for public_name, source_name in EXECUTIVE_PLAN_MAP.items():
        subset = frame.loc[frame["Plano / ponte"].eq(source_name)].copy()
        indexed = subset.set_index("Indicador") if not subset.empty else pd.DataFrame()

        def observed(indicator: str) -> float | None:
            if indexed.empty or indicator not in indexed.index:
                return None
            value = pd.to_numeric(indexed.loc[indicator, "Valor observado 2025"], errors="coerce")
            if isinstance(value, pd.Series):
                value = value.iloc[0]
            return None if pd.isna(value) else float(value)

        populations = {
            group: {"quantity": observed(group), "payroll": observed(payroll)}
            for group, payroll in payroll_by_group.items()
        }
        result[public_name] = {
            "source_name": source_name,
            "populations": populations,
            "actuarial_result": observed("Resultado atuarial"),
            "provisions": observed("Provisões matemáticas"),
            "guarantee_assets": observed("Ativos garantidores"),
            "base_date": "31/12/2025",
            "competence": "Avaliação atuarial 2026 · posição em 31/12/2025",
            "status": "DISPONÍVEL COM RESSALVAS",
            "reservation": (
                "Ponte metodológica agregada; não demonstra continuidade plano a plano."
                if "Militar" in public_name
                else "Leitura observada da avaliação atuarial; sem projeção ou inferência normativa."
            ),
        }
    return result


def executive_selection_summary(
    actuarial: pd.DataFrame,
    flows: pd.DataFrame,
    plans: Iterable[str],
) -> dict[str, object]:
    """Agrega somente linhas próprias dos planos escolhidos, sem incluir o consolidado de controle."""
    selected = list(dict.fromkeys(plans))
    if not 1 <= len(selected) <= 3:
        raise ValueError("Selecione de um a três planos.")
    source_names = [EXECUTIVE_PLAN_MAP[name] for name in selected]
    subset = actuarial.loc[actuarial["Plano / ponte"].isin(source_names)].copy()

    def total(indicator: str) -> float | None:
        values = pd.to_numeric(
            subset.loc[subset["Indicador"].eq(indicator), "Valor observado 2025"],
            errors="coerce",
        )
        value = values.sum(min_count=1)
        return None if pd.isna(value) else float(value)

    populations = {}
    for group, payroll in {
        "Ativos": "Folha mensal de ativos",
        "Aposentados": "Folha mensal de aposentados",
        "Pensionistas": "Folha mensal de pensionistas",
    }.items():
        populations[group] = {"quantity": total(group), "payroll": total(payroll)}
    return {
        "plans": selected,
        "populations": populations,
        "actuarial_result": total("Resultado atuarial"),
        "provisions": total("Provisões matemáticas"),
        "guarantee_assets": total("Ativos garantidores"),
        "implicit_rates": implicit_flow_rates(flows, selected),
        "competence": "Avaliação atuarial 2026 · posição em 31/12/2025; fluxo atuarial de 2026",
        "status": "DISPONÍVEL COM RESSALVAS",
        "reservation": "Agregação restrita aos planos selecionados; taxas implícitas calculadas pela razão entre somas.",
    }


ACTUARIAL_DEFINITIONS = {
    "Ativos": ("Participantes ativos da massa", "Contagem observada na data-base"),
    "Aposentados": ("Beneficiários aposentados", "Contagem observada na data-base"),
    "Pensionistas": ("Beneficiários pensionistas", "Contagem observada na data-base"),
    "Folha mensal de ativos": ("Folha mensal dos participantes ativos", "Valor mensal observado"),
    "Folha mensal de aposentados": ("Folha mensal de aposentadorias", "Valor mensal observado"),
    "Folha mensal de pensionistas": ("Folha mensal de pensões", "Valor mensal observado"),
    "Provisões matemáticas": ("Obrigação atuarial registrada", "PMBC + PMBaC, conforme fonte"),
    "Ativos garantidores": ("Ativos informados para cobertura", "Estoque observado publicado"),
    "Resultado atuarial": ("Diferença atuarial publicada entre ativos e obrigações", "Valor consolidado publicado; sinal original preservado"),
}


def _coverage_classification(ratio: float | None) -> str:
    if ratio is None:
        return "N/A — denominador igual a zero"
    if ratio >= 0.95:
        return "Excelente"
    if ratio >= 0.70:
        return "Adequado"
    if ratio >= 0.50:
        return "Atenção"
    return "Crítico"


def _ima_classification(ratio: float | None) -> str:
    if ratio is None:
        return "N/A — denominador igual a zero"
    if ratio >= 0.75:
        return "Maturidade muito elevada"
    if ratio >= 0.50:
        return "Maturidade elevada"
    if ratio >= 0.25:
        return "Maturidade intermediária"
    return "Baixa maturidade"


def _ipa_classification(ratio: float | None) -> str:
    if ratio is None:
        return "N/A — denominador igual a zero"
    if ratio >= 0.50:
        return "Dependência crítica"
    if ratio >= 0.25:
        return "Dependência elevada"
    if ratio >= 0.10:
        return "Dependência moderada"
    return "Baixa dependência"


def actuarial_2026_indicator_catalog(
    actuarial: pd.DataFrame,
    balances: pd.DataFrame,
    public_plan: str,
) -> pd.DataFrame:
    """Calcula os oito indicadores pontuais do catálogo ARIMA, sem série histórica."""
    source_plan = EXECUTIVE_PLAN_MAP[public_plan]
    official = actuarial.loc[actuarial["Plano / ponte"].eq(source_plan)].copy()
    balance_rows = balances.loc[balances["Dimensão"].eq(public_plan)]
    if balance_rows.empty:
        return pd.DataFrame()
    balance = balance_rows.iloc[0]

    def official_value(indicator: str) -> float | None:
        values = pd.to_numeric(
            official.loc[official["Indicador"].eq(indicator), "Valor observado 2025"],
            errors="coerce",
        )
        value = values.sum(min_count=1)
        return None if pd.isna(value) else float(value)

    assets = official_value("Ativos garantidores")
    provision = official_value("Provisões matemáticas")
    rap = official_value("Resultado atuarial")
    ativo_bc = float(balance["Ativo BC"])
    ativo_bac = float(balance["Ativo BaC"])
    passivo_bc = float(balance["Passivo BC"])
    passivo_bac = float(balance["Passivo BaC"])
    plan = float(balance["Plano de amortização"])
    assets_value = 0.0 if assets is None else assets
    deficit = max((0.0 if provision is None else provision) - assets_value, 0.0)
    excess_after_bc = max(assets_value - passivo_bc, 0.0)
    provision_bc = passivo_bc - ativo_bc
    calculated_provision = float(balance["Provisão calculada DRAA"])
    residual = None if provision is None else provision - calculated_provision
    residual_pct = None if not provision else residual / provision * 100

    def ratio(numerator: float, denominator: float | None) -> float | None:
        return None if denominator is None or denominator == 0 else numerator / denominator

    icbc = ratio(assets_value, passivo_bc)
    icp = ratio(assets_value, provision)
    icn = ratio(assets_value + plan, provision)
    ipa = ratio(plan, provision) if deficit > 0 else None
    ima = ratio(provision_bc, provision)
    iepa = None if deficit <= 0 else ratio(plan, deficit)
    icbac = ratio(ativo_bac + excess_after_bc, passivo_bac)
    common_source = "Base Comparativa Atuarial MA v0.3 + fluxo atuarial DRAA 2026.xlsx"
    competence = "Avaliação 2026 · data-base 31/12/2025"
    reconciliation = (
        "Sem resíduo calculável."
        if residual is None
        else f"Resíduo entre a provisão oficial e a recomposição por fatores do DRAA: R$ {residual:,.2f} ({residual_pct:.4f}%)."
    )

    rows = [
        ("ICBC", "Índice de Cobertura dos Benefícios Concedidos", "Solvência", icbc, "%", "Ativos Garantidores / Passivo Atuarial dos Benefícios Concedidos", f"Ativos garantidores={assets_value:.2f}; Passivo BC={passivo_bc:.2f}", _coverage_classification(icbc), "Mede a suficiência patrimonial diante dos benefícios já concedidos.", "Faixas ARIMA: crítico <50%; atenção 50%–<70%; adequado 70%–<95%; excelente ≥95%.", "O passivo BC é recomposto do fluxo descontado."),
        ("ICP", "Índice de Cobertura Primária", "Solvência", icp, "%", "Ativos Garantidores / Provisão Matemática", f"Ativos garantidores={assets_value:.2f}; Provisão oficial={provision}", _coverage_classification(icp), "Mede a parcela da provisão coberta pelo patrimônio já constituído.", "Faixas ARIMA de cobertura.", "Usa provisão oficial; a decomposição DRAA possui resíduo de arredondamento."),
        ("ICN", "Índice de Cobertura Nominal", "Solvência", icn, "%", "(Ativos Garantidores + Plano de Amortização) / Provisão Matemática", f"Ativos={assets_value:.2f}; Plano de amortização={plan:.2f}; Provisão oficial={provision}", _coverage_classification(icn), "Inclui o valor presente do plano de amortização na cobertura nominal.", "Faixas ARIMA de cobertura.", "Plano de amortização igual a zero conforme a planilha DRAA disponibilizada."),
        ("IPA", "Índice de Participação do Plano de Amortização", "Estrutura Atuarial", ipa, "%", "Plano de Amortização / Provisão Matemática", f"Plano de amortização={plan:.2f}; Provisão oficial={provision}", _ipa_classification(ipa), "Mede quanto da provisão está associado ao equacionamento futuro.", "Faixas ARIMA: baixa dependência <10%; dependência moderada 10%–<25%; dependência elevada 25%–<50%; dependência crítica ≥50%.", "Aplicável quando há déficit primário; valor zero decorre de plano não mensurado no DRAA."),
        ("IMA", "Índice de Maturidade Atuarial", "Estrutura Atuarial", ima, "%", "Provisão Matemática dos Benefícios Concedidos / Provisão Matemática Total", f"Provisão BC líquida={provision_bc:.2f}; Provisão oficial={provision}", _ima_classification(ima), "Mede a participação das obrigações líquidas dos benefícios concedidos.", "Faixas efetivas ARIMA: baixa maturidade <25%; maturidade intermediária 25%–<50%; maturidade elevada 50%–<75%; maturidade muito elevada ≥75%.", "A provisão BC líquida é recomposta do fluxo descontado."),
        ("IEPA", "Índice de Eficiência do Plano de Amortização", "Estrutura Atuarial", iepa, "%", "Plano de Amortização / Déficit Atuarial Primário", f"Plano de amortização={plan:.2f}; Déficit primário={deficit:.2f}", "N/A — sem déficit primário" if iepa is None else ("Superior ao déficit" if iepa > 1 else "Suficiente" if iepa >= 0.90 else "Insuficiente" if iepa >= 0.70 else "Crítico"), "Mede a proporção do déficit primário coberta pelo plano de amortização.", "ARIMA: crítico <70%; insuficiente 70%–<90%; suficiente 90%–100%; superior >100%.", "Valor zero indica déficit sem plano de amortização mensurado."),
        ("ICBAC", "Índice de Cobertura dos Benefícios a Conceder", "Solvência", icbac, "%", "(Ativo BaC + Excedente dos Ativos após BC) / Passivo BaC", f"Ativo BaC={ativo_bac:.2f}; Excedente após BC={excess_after_bc:.2f}; Passivo BaC={passivo_bac:.2f}", _coverage_classification(icbac), "Mede a cobertura das obrigações de benefícios a conceder.", "Faixas ARIMA de cobertura.", "N/A quando o passivo BaC é zero; não substitui ausência por zero."),
        ("RAP", "Resultado Atuarial Primário", "Resultado Atuarial", rap, "R$", "Ativos Garantidores - Provisão Matemática", f"Ativos garantidores={assets_value:.2f}; Provisão oficial={provision}", "Superávit atuarial primário" if rap is not None and rap > 0 else "Equilíbrio atuarial primário" if rap == 0 else "Déficit atuarial primário", "Expressa a posição atuarial primária na data-base.", "Sinal positivo: superávit; zero: equilíbrio; negativo: déficit.", "Leitura pontual; não constitui tendência ou conclusão causal."),
    ]
    definitions = {
        "ICBC": "Relação entre o patrimônio garantidor e as obrigações líquidas relativas aos benefícios já concedidos.",
        "ICP": "Relação entre os ativos garantidores e a provisão matemática oficial do plano.",
        "ICN": "Relação entre a cobertura patrimonial acrescida do plano de amortização e a provisão matemática.",
        "IPA": "Participação do plano de amortização na provisão matemática quando existe déficit primário.",
        "IMA": "Participação da provisão líquida dos benefícios concedidos na provisão matemática total.",
        "IEPA": "Proporção do déficit atuarial primário coberta pelo plano de amortização mensurado.",
        "ICBAC": "Relação entre os recursos atribuíveis aos benefícios a conceder e seu passivo atuarial.",
        "RAP": "Diferença pontual entre ativos garantidores e provisão matemática na data-base.",
    }
    records = []
    for code, name, group, raw_value, unit, formula, components, classification, interpretation, criterion, limitation in rows:
        display_value = raw_value if unit == "R$" or raw_value is None else raw_value * 100
        records.append(
            {
                "Sigla": code,
                "Indicador": name,
                "Definição": definitions[code],
                "Objetivo": interpretation,
                "Grupo": group,
                "Valor": display_value,
                "Unidade": unit,
                "Fórmula": formula,
                "Componentes": components,
                "Plano / massa": public_plan,
                "Fonte": common_source,
                "Competência": competence,
                "Interpretação": interpretation,
                "Classificação": classification,
                "Critério": criterion,
                "Condição de uso": "LIBERADO COM RESSALVAS — avaliação 2026 exclusivamente.",
                "Limitação": f"{limitation} {reconciliation}",
                "Comparação": None,
                "Justificativa da comparação": "Oculta: não há base externa homogênea e validada para comparação entre RPPS neste pacote.",
                "Disponibilidade": "DISPONÍVEL" if raw_value is not None else "N/A ESTRUTURAL",
                "Implementação": "IMPLEMENTADO",
                "Liberação": "LIBERADO COM RESSALVAS",
                "Justificativa de ausência": "Não se aplica; valor calculado." if raw_value is not None else limitation,
                "Resíduo de reconciliação": residual,
                "Resíduo (%)": residual_pct,
            }
        )
    return pd.DataFrame.from_records(records)


def fiscal_management_breakdown(actuarial: pd.DataFrame, flows: pd.DataFrame) -> pd.DataFrame:
    """Decompõe apenas componentes demonstráveis, sem criar resíduo de 'outros'."""
    snapshots = plan_executive_snapshots(actuarial)
    rates = implicit_flow_rates(flows, ["Previdenciário / Civil", "Previdenciário / Militar"])
    employer_flow = rates.loc[rates["Componente"].eq("Ente"), "Contribuição no fluxo"].iloc[0]
    civil = snapshots["Previdenciário / Civil"]["populations"]
    military = snapshots["Previdenciário / Militar"]["populations"]
    rows = [
        ("Efetivos civis", civil["Ativos"]["payroll"], civil["Ativos"]["payroll"] * 13, None, "Folha mensal × 13; encargo patronal legal depende da distribuição individual por faixas."),
        ("Militares ativos", military["Ativos"]["payroll"], military["Ativos"]["payroll"] * 13, None, "Folha mensal × 13; alíquota patronal militar autônoma não localizada."),
        ("Outros vínculos", None, None, None, "N/A — taxonomia contábil ainda não demonstrada."),
        ("Aposentados e pensionistas civis", civil["Aposentados"]["payroll"] + civil["Pensionistas"]["payroll"], (civil["Aposentados"]["payroll"] + civil["Pensionistas"]["payroll"]) * 13, None, "Componente previdenciário; não integra o custo dos efetivos."),
        ("Reserva, reformas e pensionistas militares", military["Aposentados"]["payroll"] + military["Pensionistas"]["payroll"], (military["Aposentados"]["payroll"] + military["Pensionistas"]["payroll"]) * 13, None, "Componente previdenciário militar; não integra o custo dos ativos."),
        ("Contribuição do ente no fluxo atuarial", None, None, employer_flow, "Fluxo atuarial 2026; não é alíquota legal nem dedução da DTP."),
        ("Deduções legais", None, None, None, "N/A — detalhamento não homologado."),
    ]
    return pd.DataFrame(rows, columns=["Componente", "Folha mensal", "Folha anualizada (×13)", "Contribuição / encargo demonstrável", "Base e limitação"])


def fiscal_insufficiency_scenario(
    flows: pd.DataFrame,
    evaluation: int = 2026,
    year: int = 2026,
) -> dict[str, object]:
    """Calcula um cenário gerencial por plano, sem compensação cruzada.

    O resultado usa fluxos atuariais projetados e não representa aporte
    oficial, despesa liquidada ou autorização de transferência entre planos.
    """
    dimensions = [
        "Financeiro / Civil",
        "Previdenciário / Civil",
        "Previdenciário / Militar",
    ]
    selected = flows.loc[
        flows["Avaliação"].eq(evaluation)
        & flows["Exercício"].eq(year)
        & flows["Dimensão"].isin(dimensions)
    ].copy()
    selected["Receitas"] = pd.to_numeric(selected["Receitas"], errors="coerce")
    selected["Despesas"] = pd.to_numeric(selected["Despesas"], errors="coerce")
    selected["Insuficiência gerencial"] = (
        selected["Despesas"] - selected["Receitas"]
    ).clip(lower=0)
    selected = selected[["Dimensão", "Receitas", "Despesas", "Insuficiência gerencial", "Fonte", "Competência"]]
    selected = selected.set_index("Dimensão").reindex(dimensions).reset_index()
    complete = bool(
        selected[["Receitas", "Despesas"]].notna().all().all()
        and set(selected["Dimensão"]) == set(dimensions)
    )
    value = (
        float(selected["Insuficiência gerencial"].sum(min_count=len(dimensions)))
        if complete
        else None
    )
    return {
        "value": value,
        "components": selected,
        "formula": "Σ por plano de máx(0; despesas projetadas − receitas projetadas)",
        "status": "CENÁRIO GERENCIAL CONDICIONADO",
        "validated": False,
        "limitation": (
            "Fluxo DRAA 2026 projetado; sem compensação entre planos. "
            "Depende de validação atuarial e fiscal/contábil e não constitui aporte oficial."
        ),
    }


def fiscal_annual_cost_breakdown(actuarial: pd.DataFrame, flows: pd.DataFrame) -> pd.DataFrame:
    """Organiza as sete linhas executivas da MVP-04.R1 e preserva ausências materiais."""
    snapshots = plan_executive_snapshots(actuarial)
    civil = snapshots["Previdenciário / Civil"]["populations"]["Ativos"]
    military = snapshots["Previdenciário / Militar"]["populations"]["Ativos"]
    civil_annual = float(civil["payroll"]) * 13
    military_annual = float(military["payroll"]) * 13

    civil_rates = implicit_flow_rates(flows, ["Previdenciário / Civil"])
    employer = civil_rates.loc[civil_rates["Componente"].eq("Ente")]
    employer_rate = None if employer.empty else float(employer.iloc[0]["Alíquota implícita (%)"])
    contributive_base = None if employer.empty else float(employer.iloc[0]["Base de cálculo"])
    employer_contribution = (
        None
        if employer_rate is None or contributive_base is None
        else contributive_base * employer_rate / 100
    )
    known_active_subtotal = civil_annual + military_annual + float(employer_contribution)
    base_share = contributive_base / civil_annual * 100 if civil_annual else None
    insufficiency = fiscal_insufficiency_scenario(flows)

    rows = [
        (
            "ATIVOS CIVIS",
            civil_annual,
            "Folha mensal × 13; aproximação gerencial, não despesa oficial liquidada.",
            "Avaliação Atuarial 2026 · data-base 31/12/2025 · DISPONÍVEL COM RESSALVAS.",
        ),
        (
            "CONTRIBUIÇÃO ENTE CIVIL",
            employer_contribution,
            (
                f"Alíquota implícita de {employer_rate:.4f}% × base contributiva anual; "
                f"a base equivale a {base_share:.2f}% da folha anual e não foi presumida como folha integral."
            ).replace(".", ","),
            "Fluxo atuarial DRAA 2026 · razão de somas · CENÁRIO GERENCIAL CONDICIONADO.",
        ),
        (
            "ATIVOS MILITARES",
            military_annual,
            "Folha mensal × 13; aproximação gerencial, não despesa oficial liquidada.",
            "Avaliação Atuarial 2026 · ponte SPSM 2025 · DISPONÍVEL COM RESSALVAS.",
        ),
        (
            "CONTRIBUIÇÃO ENTE MILITAR",
            None,
            "N/A — contribuição de 10,5% dos segurados não é patronal.",
            "Alíquota patronal militar autônoma não comprovada · DEPENDENTE DE VALIDAÇÃO.",
        ),
        (
            "TOTAL DOS ATIVOS",
            known_active_subtotal,
            "Soma dos componentes conhecidos; não converte a contribuição militar ausente em zero.",
            "SUBTOTAL CONHECIDO — TOTAL COMPLETO CONDICIONADO.",
        ),
        (
            "APORTE DE INSUFICIÊNCIA",
            insufficiency["value"],
            str(insufficiency["formula"]),
            f"{insufficiency['status']} · {insufficiency['limitation']}",
        ),
        (
            "TOTAL DOS ATIVOS COM INSUFICIÊNCIA",
            known_active_subtotal + float(insufficiency["value"]),
            "Subtotal conhecido dos ativos + insuficiência gerencial por plano; sem compensação cruzada.",
            (
                "CENÁRIO GERENCIAL CONDICIONADO — NÃO REPRESENTA DTP OFICIAL. "
                "A contribuição patronal militar permanece N/A."
            ),
        ),
    ]
    return pd.DataFrame(
        rows,
        columns=["Componente", "Valor anual", "Critério de cálculo", "Fonte e situação"],
    )


def fiscal_management_commitment(
    fiscal: pd.DataFrame,
    annual_costs: pd.DataFrame,
) -> dict[str, object]:
    """Calcula o comprometimento gerencial sem substituir a razão oficial DTP/RCL."""
    latest = fiscal.sort_values("Ano").iloc[-1]
    indexed = annual_costs.set_index("Componente")
    active_subtotal = float(indexed.loc["TOTAL DOS ATIVOS", "Valor anual"])
    insufficiency = float(indexed.loc["APORTE DE INSUFICIÊNCIA", "Valor anual"])
    total_with_insufficiency = float(
        indexed.loc["TOTAL DOS ATIVOS COM INSUFICIÊNCIA", "Valor anual"]
    )
    rcl = float(latest["RCL ajustada (pessoal)"])
    return {
        "exercise": int(latest["Ano"]),
        "active_subtotal": active_subtotal,
        "insufficiency": insufficiency,
        "total_with_insufficiency": total_with_insufficiency,
        "rcl": rcl,
        "management_commitment": total_with_insufficiency / rcl * 100 if rcl else None,
        "official_dtp": float(latest["DTP"]),
        "official_dtp_rcl": float(latest["DTP / RCL ajustada"]),
        "status": "CENÁRIO GERENCIAL CONDICIONADO — NÃO REPRESENTA DTP OFICIAL",
        "limitation": (
            "O subtotal ativo não inclui contribuição patronal militar. "
            "A insuficiência vem dos fluxos DRAA e não foi conciliada como aporte ou parcela da DTP."
        ),
    }


def fiscal_simulator_defaults(
    fiscal_projections: pd.DataFrame,
    assumptions: pd.DataFrame,
) -> dict[str, object]:
    """Obtém os valores iniciais exclusivamente das premissas oficiais do projeto."""
    projection = fiscal_projections.loc[fiscal_projections["Ano"].between(2026, 2035)].copy()
    scenario_a = projection.loc[projection["Cenário"].eq("A")].sort_values("Ano")
    rcl_2026 = float(scenario_a.loc[scenario_a["Ano"].eq(2026), "RCL nominal"].iloc[0])
    rcl_2035 = float(scenario_a.loc[scenario_a["Ano"].eq(2035), "RCL nominal"].iloc[0])
    rcl_years = 2035 - 2026
    rcl_cagr = ((rcl_2035 / rcl_2026) ** (1 / rcl_years) - 1) * 100

    scenario_growth: dict[str, float] = {}
    for scenario in ("A", "B", "C"):
        rows = projection.loc[
            projection["Cenário"].eq(scenario)
            & projection["Ano"].between(2027, 2035)
        ]
        scenario_growth[scenario] = float(
            pd.to_numeric(rows["Cresc. real folha"], errors="coerce").dropna().iloc[0]
        ) * 100

    approved_real = assumptions.loc[assumptions["ID"].eq("P13"), "Valor"]
    return {
        "scenario": "A",
        "rcl_growth_percent": rcl_cagr,
        "salary_growth_percent": scenario_growth["A"],
        "scenario_salary_growth_percent": scenario_growth,
        "approved_long_term_real_growth_percent": (
            float(approved_real.iloc[0]) * 100 if not approved_real.empty else None
        ),
        "basis": (
            "CAGR nominal da trajetória de RCL 2026–2035 e crescimentos reais "
            "A/B/C das premissas públicas da projeção."
        ),
    }


def fiscal_pressure_simulation(
    annual_costs: pd.DataFrame,
    flows: pd.DataFrame,
    fiscal_projections: pd.DataFrame,
    scenario: str,
    rcl_growth_percent: float,
    salary_growth_percent: float,
) -> pd.DataFrame:
    """Simula 2027–2035 com Opção A: crescimento salarial apenas na folha ativa."""
    if scenario not in {"A", "B", "C"}:
        raise ValueError("Cenário deve ser A, B ou C.")
    if rcl_growth_percent <= -100 or salary_growth_percent <= -100:
        raise ValueError("Taxas anuais devem ser superiores a -100%.")

    indexed = annual_costs.set_index("Componente")
    civil_payroll = float(indexed.loc["ATIVOS CIVIS", "Valor anual"])
    military_payroll = float(indexed.loc["ATIVOS MILITARES", "Valor anual"])
    civil_employer = float(indexed.loc["CONTRIBUIÇÃO ENTE CIVIL", "Valor anual"])

    projection = fiscal_projections.loc[
        fiscal_projections["Cenário"].eq(scenario)
        & fiscal_projections["Ano"].between(2026, 2035)
    ].sort_values("Ano")
    if projection.empty:
        raise ValueError("Trajetória-base do cenário não localizada.")

    ipca_by_year = projection.set_index("Ano")["IPCA"].apply(pd.to_numeric, errors="coerce")
    rcl_2026 = float(projection.loc[projection["Ano"].eq(2026), "RCL nominal"].iloc[0])
    salary_growth = float(salary_growth_percent) / 100
    rcl_growth = float(rcl_growth_percent) / 100

    dimensions = [
        "Financeiro / Civil",
        "Previdenciário / Civil",
        "Previdenciário / Militar",
    ]
    original_flows = flows.loc[
        flows["Avaliação"].eq(2026)
        & flows["Exercício"].between(2027, 2035)
        & flows["Dimensão"].isin(dimensions)
    ].copy()
    original_flows["Receitas"] = pd.to_numeric(original_flows["Receitas"], errors="coerce")
    original_flows["Despesas"] = pd.to_numeric(original_flows["Despesas"], errors="coerce")
    original_flows["Insuficiência"] = (
        original_flows["Despesas"] - original_flows["Receitas"]
    ).clip(lower=0)
    shortfalls = original_flows.pivot_table(
        index="Exercício",
        columns="Dimensão",
        values="Insuficiência",
        aggfunc="first",
    ).reindex(columns=dimensions)

    rows: list[dict[str, object]] = []
    rcl = rcl_2026
    for year in range(2026, 2036):
        ipca = float(ipca_by_year.loc[year])
        active_factor = (1 + ipca) * (1 + salary_growth)
        civil_payroll *= active_factor
        military_payroll *= active_factor
        if year == 2026:
            continue
        # A contribuição civil demonstrável já é a posição de 2026. Sua
        # projeção começa em 2027, sem reaplicar o IPCA de 2026.
        civil_employer *= active_factor
        rcl *= 1 + rcl_growth
        year_shortfalls = shortfalls.loc[year]
        finance_civil = float(year_shortfalls["Financeiro / Civil"])
        pension_civil = float(year_shortfalls["Previdenciário / Civil"])
        pension_military = float(year_shortfalls["Previdenciário / Militar"])
        total_shortfall = finance_civil + pension_civil + pension_military
        active_payroll = civil_payroll + military_payroll
        known_active_subtotal = active_payroll + civil_employer
        total_with_shortfall = known_active_subtotal + total_shortfall
        rows.append(
            {
                "Ano": year,
                "Cenário-base": scenario,
                "Crescimento anual da RCL": rcl_growth_percent,
                "Crescimento real anual da folha ativa": salary_growth_percent,
                "Custo anual da folha ativa": active_payroll,
                "Contribuição patronal civil demonstrável": civil_employer,
                "Contribuição patronal militar": None,
                "Subtotal ativo conhecido": known_active_subtotal,
                "Insuficiência Financeiro/Civil": finance_civil,
                "Insuficiência Previdenciário/Civil": pension_civil,
                "Insuficiência Previdenciário/Militar": pension_military,
                "Insuficiência total": total_shortfall,
                "Total com insuficiência": total_with_shortfall,
                "RCL ajustada projetada": rcl,
                "Comprometimento gerencial": total_with_shortfall / rcl * 100 if rcl else None,
                "Status / limitações": (
                    "CENÁRIO GERENCIAL CONDICIONADO — NÃO REPRESENTA DTP OFICIAL; "
                    "patronal militar N/A; fluxos DRAA originais sem crescimento salarial."
                ),
            }
        )
    return pd.DataFrame(rows)


def fiscal_dtp_fractionation(
    fiscal: pd.DataFrame,
    annual_costs: pd.DataFrame,
    insufficiency: dict[str, object],
) -> dict[str, object]:
    """Aplica o gate A + B = DTP sem tratar N/A como zero."""
    latest = fiscal.sort_values("Ano").iloc[-1]
    indexed = annual_costs.set_index("Componente")
    total_active = indexed.loc["TOTAL DOS ATIVOS", "Valor anual"]
    military_employer = indexed.loc["CONTRIBUIÇÃO ENTE MILITAR", "Valor anual"]
    active_complete = pd.notna(military_employer)
    insufficiency_validated = bool(insufficiency.get("validated", False))
    aggregate = (
        float(total_active) + float(insufficiency["value"])
        if active_complete and insufficiency_validated and insufficiency.get("value") is not None
        else None
    )
    dtp = float(latest["DTP"])
    rcl = float(latest["RCL ajustada (pessoal)"])
    residual = dtp - aggregate if aggregate is not None else None
    commitment_a = aggregate / rcl * 100 if aggregate is not None and rcl else None
    commitment_b = residual / rcl * 100 if residual is not None and rcl else None
    reconciled = bool(
        aggregate is not None
        and residual is not None
        and math.isclose(aggregate + residual, dtp, abs_tol=0.01)
    )
    return {
        "exercise": int(latest["Ano"]),
        "dtp": dtp,
        "rcl": rcl,
        "total_active_known": float(total_active),
        "insufficiency_scenario": insufficiency.get("value"),
        "aggregate": aggregate,
        "commitment_a": commitment_a,
        "residual": residual,
        "commitment_b": commitment_b,
        "reconciled": reconciled,
        "status": "COMPLETO" if reconciled else "CONDICIONADO — A + B ainda não reconciliado com a DTP oficial",
    }


def fiscal_long(frame: pd.DataFrame, indicators: Iterable[str]) -> pd.DataFrame:
    selected = [indicator for indicator in indicators if indicator in frame.columns]
    melted = frame.melt(
        id_vars=["Ano", "Competência RREO", "Competência RGF", "Nota de comparabilidade"],
        value_vars=selected,
        var_name="Indicador",
        value_name="Valor",
    )
    melted["Valor"] = pd.to_numeric(melted["Valor"], errors="coerce")
    return melted


def fiscal_personnel_composition(frame: pd.DataFrame) -> pd.DataFrame:
    """Composição publicada no RGF, sem inventar a segregação civil/militar."""
    columns = ["Folha ativa bruta", "Aposentadorias, reserva e reformas", "Pensões — RGF"]
    result = fiscal_long(frame, columns)
    result["Recorte"] = "Consolidado oficial; separação civil/militar não publicada"
    return result.rename(columns={"Indicador": "Componente"})


def fiscal_composition_catalog() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ("Efetivos civis", "DEPENDENTE DE EXTRAÇÃO", "RGF/detalhamento contábil"),
            ("Militares ativos", "DEPENDENTE DE EXTRAÇÃO", "RGF/detalhamento contábil"),
            ("Demais vínculos", "DEPENDENTE DE EXTRAÇÃO", "Taxonomia contábil pendente"),
            ("Aposentados / reserva / reformas", "DISPONÍVEL SEM SEGREGAÇÃO CIVIL-MILITAR", "RGF Anexo 01"),
            ("Pensionistas", "DISPONÍVEL SEM SEGREGAÇÃO CIVIL-MILITAR", "RGF Anexo 01"),
            ("Outros componentes", "DEPENDENTE DE EXTRAÇÃO", "Lista de rubricas pendente"),
        ],
        columns=["Componente", "Status", "Fonte / limitação"],
    )


def fiscal_rgf_reconciliation(frame: pd.DataFrame) -> pd.DataFrame:
    """Camada RGF. O total de deduções permanece N/A até extração homologada."""
    result = frame[
        [
            "Ano", "Competência RGF", "Data de referência RGF", "Folha ativa bruta",
            "Inativos e pensionistas — bruta", "DTP", "RCL", "RCL ajustada (pessoal)",
            "DTP / RCL ajustada", "Nota de comparabilidade",
        ]
    ].copy()
    result["Despesa bruta mapeada"] = (
        pd.to_numeric(result["Folha ativa bruta"], errors="coerce")
        + pd.to_numeric(result["Inativos e pensionistas — bruta"], errors="coerce")
    )
    result["Deduções legais"] = float("nan")
    result["Status da conciliação"] = "CONDICIONADA — detalhamento das deduções não homologado"
    return result


def fiscal_financing(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "Ano", "Competência RREO", "Data de referência RREO",
        "Cobertura de insuficiências financeiras",
        "Cobertura de déficit financeiro — fundo em capitalização",
        "Contribuições militares", "Benefícios mantidos pelo Tesouro",
        "Resultado associado aos militares", "Nota de comparabilidade",
    ]
    result = frame[columns].copy()
    result["Contribuições patronais"] = float("nan")
    result["Necessidade de financiamento"] = float("nan")
    result["Status"] = "Rubricas exibidas separadamente; total de financiamento não conciliado"
    return result


def fiscal_pressure_catalog(frame: pd.DataFrame, year: int) -> pd.DataFrame:
    row = frame.loc[frame["Ano"].eq(year)]
    value = None if row.empty else float(row.iloc[0]["DTP / RCL ajustada"])
    competence = "N/A" if row.empty else str(row.iloc[0]["Competência RGF"])
    return pd.DataFrame(
        [
            ("DTP / RCL ajustada", value, "DISPONÍVEL E VALIDADO", f"RGF · {competence}"),
            ("Inativos e pensionistas / DTP", None, "DEPENDENTE DE VALIDAÇÃO", "Fórmula pendente"),
            ("Despesa previdenciária / DTP", None, "DEPENDENTE DE VALIDAÇÃO", "Competências a compatibilizar"),
            ("Aportes / RCL ajustada", None, "DEPENDENTE DE VALIDAÇÃO", "Bases temporais distintas"),
            ("Necessidade de financiamento / RCL ajustada", None, "DEPENDENTE DE VALIDAÇÃO", "Conceito não aprovado"),
        ],
        columns=["Indicador", "Valor", "Status", "Base / ressalva"],
    )


def fiscal_metadata(series: pd.DataFrame, indicators: Iterable[str]) -> pd.DataFrame:
    selected = series.loc[series["Indicador"].isin(list(indicators))].copy()
    columns = [
        "Ano", "Competência", "Periodicidade", "Poder", "Órgão", "Anexo",
        "Demonstrativo", "Indicador", "Unidade", "Fonte", "Status",
        "Data de referência", "Base temporal", "Natureza do indicador",
        "Estado de disponibilidade",
    ]
    return selected[columns].sort_values(["Ano", "Fonte", "Indicador"]).reset_index(drop=True)


def contribution_rate_catalog(frame: pd.DataFrame) -> pd.DataFrame:
    """Normaliza a apresentação sem inferir taxa média nem converter ausência em zero."""
    result = frame.copy()
    result = result.rename(columns={"Vigência 2026": "Vigência", "Observação": "Ressalva"})
    result = result.fillna("N/A")
    patronal = result["Grupo"].eq("Patronal normal civil")
    result.loc[patronal, "Percentual/regra"] = "Dobro da contribuição do segurado; piso 15%; teto 44%"
    return result[["Grupo", "Percentual/regra", "Base", "Lei", "Artigo", "Vigência", "Status", "Ressalva"]]


def fiscal_projection_scenarios(frame: pd.DataFrame) -> pd.DataFrame:
    """Expõe somente os valores homologados de 2027–2035, sem recalcular a memória."""
    result = frame.loc[frame["Ano"].between(2027, 2035)].copy()
    columns = {
        "RCL nominal": "RCL ajustada projetada",
        "Custo direto parcial dos ativos": "Custo direto estimado",
        "Comprometimento direto parcial": "Comprometimento direto",
        "Status/limitação": "Limitação",
    }
    result = result.rename(columns=columns)
    result["Comprometimento direto"] = pd.to_numeric(result["Comprometimento direto"], errors="coerce") * 100
    ordered = [
        "Cenário", "Ano", "Classificação", "Crescimento real da folha",
        "RCL ajustada projetada", "Custo direto estimado", "Comprometimento direto",
        "Pressão adicional", "Comprometimento ampliado", "Limitação",
    ]
    return result[ordered].sort_values(["Cenário", "Ano"]).reset_index(drop=True)


def official_dtp_rcl_series(frame: pd.DataFrame) -> pd.DataFrame:
    """Série oficial observada; 2026 permanece parcial e nunca é anualizado."""
    result = frame[[
        "Ano", "DTP", "RCL ajustada (pessoal)", "DTP / RCL ajustada",
        "Competência RGF", "Data de referência RGF", "Nota de comparabilidade",
    ]].copy()
    result["Situação do exercício"] = result["Ano"].map(lambda year: "PARCIAL — não anualizado" if int(year) == 2026 else "FECHADO")
    result["Periodicidade"] = "RGF · quadrimestral · últimos 12 meses"
    result["Fonte"] = "Siconfi · RGF Anexo 01 · Série Fiscal Histórica MA v0.2"
    return result


def safe_delta(current: object, previous: object) -> str | None:
    if any(value is None or pd.isna(value) for value in (current, previous)):
        return None
    if math.isclose(float(previous), 0.0):
        return None
    return percent((float(current) / float(previous) - 1) * 100)
