"""Camada analítica: SQL no SQLite, pandas e os testes estatísticos.

Três perguntas, uma função cada:
  - faixa_normal(): a semana está dentro do padrão do próprio artista? (mediana + IQR)
  - picos():        que dias fugiram muito do normal? (z-score robusto com MAD)
  - welch():        a atenção a um gênero é maior que a outro? (teste t de Welch)

Princípio: amostra pequena não vira conclusão. Abaixo do mínimo, a função
devolve None e o app avisa que não dá para dizer.
"""
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

DB = Path(__file__).parent / "data" / "atencao.db"
MIN_SEMANAS_FAIXA = 8   # semanas de histórico para definir o "normal"
MIN_DIAS_PICO = 60      # dias de histórico para julgar um pico
MIN_ARTISTAS = 4        # artistas por gênero para comparar gêneros

# Semana de segunda a domingo. 'weekday 0' leva ao domingo; -6 dias volta à segunda.
SQL_SEMANAL = """
SELECT a.artista, a.genero,
       date(p.data, 'weekday 0', '-6 days') AS semana,
       SUM(p.views) AS views
FROM pageviews p JOIN artistas a USING (artigo)
GROUP BY a.artista, a.genero, semana
ORDER BY semana
"""

SQL_DIARIO = """
SELECT a.artista, a.genero, p.data, p.views
FROM pageviews p JOIN artistas a USING (artigo)
ORDER BY p.data
"""


def consultar(sql, db=DB, params=()):
    with sqlite3.connect(db) as con:
        return pd.read_sql_query(sql, con, params=params)


def faixa_normal(historico, valor):
    """Mediana e IQR das semanas anteriores; limites em Q1-1,5·IQR e Q3+1,5·IQR."""
    s = pd.Series(historico, dtype=float).dropna()
    if len(s) < MIN_SEMANAS_FAIXA or valor is None or pd.isna(valor):
        return None
    q1, med, q3 = s.quantile(.25), s.median(), s.quantile(.75)
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    if valor > hi:
        status = "acima do normal"
    elif valor < lo:
        status = "abaixo do normal"
    else:
        status = "dentro do normal"
    return {"status": status, "valor": float(valor), "mediana": float(med),
            "q1": float(q1), "q3": float(q3), "lim_inf": float(max(lo, 0)),
            "lim_sup": float(hi), "n_semanas": len(s),
            "vs_mediana_pct": (valor - med) / med * 100 if med else None}


def radar_semana(semanal, semana, janela=26):
    """Aplica a faixa_normal a cada artista na `semana`, contra as `janela` anteriores."""
    linhas = []
    for (artista, genero), g in semanal.groupby(["artista", "genero"]):
        atual = g.loc[g["semana"] == semana, "views"]
        hist = g.loc[g["semana"] < semana, "views"].tail(janela)
        r = faixa_normal(hist, atual.iloc[0] if len(atual) else None)
        if r:
            linhas.append({"artista": artista, "genero": genero, **r})
    return pd.DataFrame(linhas)


def picos(diario, z_corte=3.5, janela=90):
    """Dias com views muito acima do padrão dos `janela` dias anteriores do artista.

    Mediana e MAD em vez de média e desvio padrão: um único dia de pico infla a
    média e esconde os outros. Trabalha em log, porque a atenção cresce aos saltos.
    """
    saida = []
    for artista, g in diario.groupby("artista"):
        g = g.sort_values("data").reset_index(drop=True)
        lv = np.log1p(g["views"].astype(float))
        med = lv.rolling(janela, min_periods=MIN_DIAS_PICO).median().shift(1)
        mad = lv.rolling(janela, min_periods=MIN_DIAS_PICO).apply(
            lambda x: np.median(np.abs(x - np.median(x))), raw=True).shift(1)
        z = (lv - med) / (1.4826 * mad.replace(0, np.nan))
        g = g.assign(z=z, base=np.expm1(med))
        saida.append(g[g["z"] >= z_corte])
    if not saida:
        return pd.DataFrame(columns=["artista", "genero", "data", "views", "z", "base"])
    out = pd.concat(saida)
    out["vezes_base"] = out["views"] / out["base"]
    return out.sort_values("z", ascending=False)


def welch(semanal, genero_a, genero_b, semanas=12):
    """Compara a atenção média de dois gêneros nas últimas `semanas`.

    Unidade de análise = artista (média do log das views semanais), para não
    tratar semanas do mesmo artista como observações independentes. Welch porque
    não supõe variâncias iguais entre os grupos.
    """
    ultimas = sorted(semanal["semana"].unique())[-semanas:]
    df = semanal[semanal["semana"].isin(ultimas)].copy()
    df["log_views"] = np.log10(df["views"].clip(lower=1))
    por_artista = df.groupby(["genero", "artista"])["log_views"].mean()
    if genero_a not in por_artista.index or genero_b not in por_artista.index:
        return None
    a, b = por_artista[genero_a], por_artista[genero_b]
    if len(a) < MIN_ARTISTAS or len(b) < MIN_ARTISTAS:
        return None
    t, p = stats.ttest_ind(a, b, equal_var=False)
    dp = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
    return {"a": genero_a, "b": genero_b, "n_a": len(a), "n_b": len(b),
            "media_a": 10 ** a.mean(), "media_b": 10 ** b.mean(),  # médias geométricas
            "razao": 10 ** (a.mean() - b.mean()), "t": float(t), "p": float(p),
            "d": float((a.mean() - b.mean()) / dp) if dp else None,
            "semanas": len(ultimas), "significante": bool(p < 0.05)}
