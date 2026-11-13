"""Coleta diária de pageviews da Wikipédia em português e grava no SQLite.

Fonte: Wikimedia REST API (dados CC0, sem chave). Conta só acessos de pessoas
(agent=user), excluindo robôs. Rodar de novo é seguro: as linhas são substituídas.

Uso: python coleta.py [AAAA-MM-DD início]
"""
import csv
import sqlite3
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

import requests

RAIZ = Path(__file__).parent
DB = RAIZ / "data" / "atencao.db"
API = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
       "pt.wikipedia/all-access/user/{artigo}/daily/{ini}/{fim}")
# A Wikimedia pede um User-Agent que identifique o cliente.
HEADERS = {"User-Agent": "portfolio-atencao-musica/1.0 (projeto de estudo)"}


def ultimo_domingo(hoje=None):
    hoje = hoje or date.today()
    return hoje - timedelta(days=hoje.weekday() + 1)


def criar_tabelas(con):
    con.executescript(Path(RAIZ / "schema.sql").read_text(encoding="utf-8"))


def coletar(inicio="2024-01-01"):
    fim = ultimo_domingo()
    DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB)
    criar_tabelas(con)
    with open(RAIZ / "artistas.csv", encoding="utf-8") as f:
        artistas = list(csv.DictReader(f))
    con.executemany("INSERT OR REPLACE INTO artistas VALUES (:artigo, :artista, :genero)", artistas)
    s = requests.Session()
    for a in artistas:
        url = API.format(artigo=quote(a["artigo"], safe=""),
                         ini=inicio.replace("-", ""), fim=fim.strftime("%Y%m%d"))
        for tentativa in range(5):
            r = s.get(url, headers=HEADERS, timeout=30)
            if r.status_code != 429:
                break
            time.sleep(5 * (tentativa + 1))  # limite de taxa da API: espera e tenta de novo
        r.raise_for_status()
        time.sleep(1)
        linhas = [(a["artigo"], f"{i['timestamp'][:4]}-{i['timestamp'][4:6]}-{i['timestamp'][6:8]}",
                   i["views"]) for i in r.json()["items"]]
        con.executemany("INSERT OR REPLACE INTO pageviews VALUES (?, ?, ?)", linhas)
        print(f"{a['artista']:<22} {len(linhas):>5} dias")
    con.commit()
    con.close()


if __name__ == "__main__":
    coletar(*sys.argv[1:2])
