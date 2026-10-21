from __future__ import annotations


BLOCKED_INDICATORS = frozenset(
    {
        "Tesouro Militar 2022 — desagregado",
        "Vigência e causalidade normativa definitivas",
        "MIL FIN 2026",
        "Projeção fiscal de fechamento 2026",
    }
)

SOURCE_LABELS = {
    "actuarial": "Avaliações Atuariais 2023 e 2026 · datas-base 31/12/2022 e 31/12/2025",
    "fiscal": "Siconfi RREO/RGF · 2022–2025 fechados; 2026 parcial",
    "flows": "DRAA 2023 ajustado e DRAA 2026",
    "release": "Critérios públicos de disponibilidade · 13/10/2026",
    "rates": "Quadro público de alíquotas previdenciárias MA 2026 v0.2",
    "projection": "Premissas públicas da projeção fiscal MA 2027–2035 v0.2",
}
