"""Coleta diária de pageviews da Wikipédia em português e grava no SQLite.

Fonte: Wikimedia REST API (dados CC0, sem chave). Conta só acessos de pessoas
(agent=user), excluindo robôs. Rodar de novo é seguro: as linhas são substituídas,
e artistas que saíram de artistas.csv saem do banco.

Uso: python coleta.py [AAAA-MM-DD início]
"""
import csv
import json
import sqlite3
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

RAIZ = Path(__file__).parent
DB = RAIZ / "data" / "atencao.db"
API = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
       "pt.wikipedia/all-access/user/{artigo}/daily/{ini}/{fim}")
# A Wikimedia pede um User-Agent que identifique o cliente.
HEADERS = {"User-Agent": "portfolio-atencao-musica/1.0 (projeto de estudo)"}


def ultimo_domingo(hoje=None):
    hoje = hoje or date.today()
    return hoje - timedelta(days=hoje.weekday() + 1)


def linhas_da_api(artigo, resposta):
    """Resposta da API -> linhas (artigo, AAAA-MM-DD, views). O timestamp vem como AAAAMMDDHH."""
    return [(artigo, f"{i['timestamp'][:4]}-{i['timestamp'][4:6]}-{i['timestamp'][6:8]}", int(i["views"]))
            for i in resposta["items"]]


def baixar(url):
    for tentativa in range(5):
        try:
            with urlopen(Request(url, headers=HEADERS), timeout=30) as r:
                return json.load(r)
        except HTTPError as e:
            if e.code != 429 or tentativa == 4:
                raise
            time.sleep(5 * (tentativa + 1))  # limite de taxa da API: espera e tenta de novo


def coletar(inicio="2024-01-01"):
    fim = ultimo_domingo()
    DB.parent.mkdir(exist_ok=True)
    with open(RAIZ / "artistas.csv", encoding="utf-8") as f:
        artistas = list(csv.DictReader(f))
    con = sqlite3.connect(DB)
    con.executescript((RAIZ / "schema.sql").read_text(encoding="utf-8"))
    with con:  # uma transação só: ou a semana entra inteira, ou nada muda
        artigos = [a["artigo"] for a in artistas]
        marcas = ",".join("?" * len(artigos))
        con.execute(f"DELETE FROM pageviews WHERE artigo NOT IN ({marcas})", artigos)
        con.execute(f"DELETE FROM artistas WHERE artigo NOT IN ({marcas})", artigos)
        con.executemany("INSERT OR REPLACE INTO artistas VALUES (:artigo, :artista, :genero)", artistas)
        for a in artistas:
            url = API.format(artigo=quote(a["artigo"], safe=""),
                             ini=inicio.replace("-", ""), fim=fim.strftime("%Y%m%d"))
            linhas = linhas_da_api(a["artigo"], baixar(url))
            con.executemany("INSERT OR REPLACE INTO pageviews VALUES (?, ?, ?)", linhas)
            print(f"{a['artista']:<22} {len(linhas):>5} dias")
            time.sleep(1)
    con.close()


if __name__ == "__main__":
    coletar(*sys.argv[1:2])
