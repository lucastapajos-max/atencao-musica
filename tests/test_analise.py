import numpy as np
import pandas as pd

import analise


def test_faixa_normal_classifica():
    hist = [100, 110, 90, 105, 95, 100, 108, 92]
    assert analise.faixa_normal(hist, 100)["status"] == "dentro do normal"
    assert analise.faixa_normal(hist, 500)["status"] == "acima do normal"
    assert analise.faixa_normal(hist, 10)["status"] == "abaixo do normal"
    assert analise.faixa_normal(hist[:5], 100) is None  # histórico curto não julga


def test_picos_acha_o_dia_atipico():
    rng = np.random.default_rng(0)
    views = rng.integers(90, 110, 120)
    views[100] = 5000
    d = pd.DataFrame({"artista": "X", "genero": "G", "views": views,
                      "data": pd.date_range("2025-01-01", periods=120).strftime("%Y-%m-%d")})
    p = analise.picos(d)
    assert list(p["data"]) == ["2025-04-11"]


def test_welch_detecta_diferenca_e_respeita_minimo():
    linhas = [{"artista": f"{g}{i}", "genero": g, "semana": f"2025-01-{s:02d}",
               "views": base * (1 + i / 10)}
              for g, base in [("A", 10000), ("B", 100)] for i in range(5) for s in range(1, 13)]
    sem = pd.DataFrame(linhas)
    r = analise.welch(sem, "A", "B")
    assert r["significante"] and r["razao"] > 50
    assert analise.welch(sem[sem["artista"] != "B0"].query("artista != 'B1'"), "A", "B") is None


def test_sql_semanal_roda_no_banco():
    sem = analise.consultar(analise.SQL_SEMANAL)
    assert {"artista", "genero", "semana", "views"} <= set(sem.columns)
    assert pd.to_datetime(sem["semana"]).dt.dayofweek.eq(0).all()  # toda semana começa na segunda
