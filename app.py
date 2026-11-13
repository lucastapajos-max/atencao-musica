"""Dashboard: atenção digital à música brasileira (pageviews da Wikipédia)."""
import sqlite3

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import analise as an

st.set_page_config(page_title="Atenção à música brasileira", page_icon="🎧", layout="wide")

# Uma cor por gênero no app inteiro. Vermelho fica de fora: aqui ele leria como alerta.
CORES = {"Sertanejo": "#C27C0E", "Funk e pop": "#C2416B", "MPB": "#0F7B6C", "Rap e trap": "#2F5BB7"}
STATUS_FUNDO = {"acima do normal": "rgba(15,123,108,.22)", "abaixo do normal": "rgba(194,124,14,.25)"}
NUM = "localized"  # separador de milhar conforme o idioma do navegador


@st.cache_data
def carregar():
    sem, dia = an.consultar(an.SQL_SEMANAL), an.consultar(an.SQL_DIARIO)
    dia["data"] = pd.to_datetime(dia["data"])
    return sem, dia


def br(v, casas=0):
    return f"{v:,.{casas}f}".replace(",", "x").replace(".", ",").replace("x", ".")


def lista(nomes):
    nomes = list(nomes)
    return nomes[0] if len(nomes) == 1 else ", ".join(nomes[:-1]) + " e " + nomes[-1]


def grafico(fig, altura=360):
    fig.update_layout(height=altura, margin=dict(t=10, b=10, l=10, r=10),
                      legend=dict(orientation="h", y=-0.15, title=None))
    st.plotly_chart(fig, width="stretch")


semanal, diario = carregar()
semanas = sorted(semanal["semana"].unique())

st.title("Atenção digital à música brasileira")
st.caption(
    "Visualizações diárias dos verbetes de 24 artistas na Wikipédia em português, "
    f"de {diario['data'].min():%d/%m/%Y} a {diario['data'].max():%d/%m/%Y}. "
    "Fonte: Wikimedia Pageviews API (dados abertos, CC0), só acessos humanos. "
    "Visualização de verbete mede interesse (gente procurando saber do artista), não audiência.")

with st.sidebar:
    semana = st.selectbox("Semana (segunda a domingo)", semanas[::-1],
                          format_func=lambda s: f"{pd.to_datetime(s):%d/%m/%Y}")
    generos = st.multiselect("Gêneros", list(CORES), default=list(CORES))
    st.caption("Gêneros são um agrupamento editorial deste projeto, não uma classificação oficial.")

if not generos:
    st.info("Escolha ao menos um gênero na barra lateral para ver o painel.")
    st.stop()

sem = semanal[semanal["genero"].isin(generos)]
radar = an.radar_semana(sem, semana)
fim_semana = pd.to_datetime(semana) + pd.Timedelta(days=6)

aba1, aba2, aba3, aba4 = st.tabs(["Radar da semana", "Picos de atenção", "Gêneros (teste t)", "SQL"])

# --- Radar --------------------------------------------------------------------
with aba1:
    if radar.empty:
        st.info("Esta semana ainda não tem 8 semanas de histórico antes dela para definir o normal. "
                "Escolha uma semana mais recente.")
    else:
        total = sem.loc[sem["semana"] == semana, "views"].sum()
        hist_total = sem[sem["semana"] < semana].groupby("semana")["views"].sum().tail(26)
        bt = an.faixa_normal(hist_total, total)
        acima = radar[radar["status"] == "acima do normal"].sort_values("vs_mediana_pct", ascending=False)
        abaixo = radar[radar["status"] == "abaixo do normal"].sort_values("vs_mediana_pct")
        frases = [f"Semana de {pd.to_datetime(semana):%d/%m} a {fim_semana:%d/%m/%Y}: "
                  f"**{br(total)} visualizações** nos gêneros escolhidos"]
        if bt:
            frases[0] += (f", {br(abs(bt['vs_mediana_pct']))}% {'acima' if bt['vs_mediana_pct'] >= 0 else 'abaixo'} "
                          f"da mediana das 26 semanas anteriores ({bt['status']}).")
        else:
            frases[0] += "."
        frases.append(f"Acima do normal: {lista(acima['artista'])}." if len(acima)
                      else "Nenhum artista ficou acima do normal.")
        frases.append(f"Abaixo do normal: {lista(abaixo['artista'])}." if len(abaixo)
                      else "Nenhum ficou abaixo.")
        st.markdown(" ".join(frases))

        tab = radar.assign(mediana=radar["mediana"].round()).sort_values("vs_mediana_pct", ascending=False)[
            ["artista", "genero", "status", "valor", "mediana", "vs_mediana_pct"]]
        st.dataframe(
            tab.style.map(lambda s: f"background-color: {STATUS_FUNDO.get(s, 'transparent')}", subset=["status"]),
            hide_index=True, width="stretch",
            column_config={
                "artista": "Artista", "genero": "Gênero", "status": "Leitura",
                "valor": st.column_config.NumberColumn("Views na semana", format=NUM),
                "mediana": st.column_config.NumberColumn("Mediana de 26 semanas", format=NUM),
                "vs_mediana_pct": st.column_config.NumberColumn("Diferença da mediana", format="%+.0f%%"),
            })
        st.caption("O normal de cada artista é a faixa das 26 semanas anteriores (mediana e intervalo "
                   "interquartil). Fica acima do normal quem passa de Q3 + 1,5 × IQR, o critério do boxplot.")

        artista = st.selectbox("Série semanal de um artista", tab["artista"])
        g = sem[sem["artista"] == artista].sort_values("semana").copy()
        roll = g["views"].rolling(26, min_periods=an.MIN_SEMANAS_FAIXA)
        g["q1"], g["q3"] = roll.quantile(.25).shift(1), roll.quantile(.75).shift(1)
        g["lim_sup"] = g["q3"] + 1.5 * (g["q3"] - g["q1"])
        cor = CORES[g["genero"].iloc[0]]
        fig = go.Figure([
            go.Scatter(x=g["semana"], y=g["q3"], line=dict(width=0), showlegend=False, hoverinfo="skip"),
            go.Scatter(x=g["semana"], y=g["q1"], fill="tonexty", line=dict(width=0),
                       fillcolor="rgba(128,128,128,.22)", name="Faixa usual (Q1 a Q3)", hoverinfo="skip"),
            go.Scatter(x=g["semana"], y=g["lim_sup"], line=dict(dash="dot", color="gray", width=1),
                       name="Limite do normal", hovertemplate="%{y:,.0f}<extra>Limite</extra>"),
            go.Scatter(x=g["semana"], y=g["views"], line=dict(color=cor, width=2), name="Views na semana",
                       hovertemplate="%{x|%d/%m/%Y}: %{y:,.0f}<extra></extra>"),
        ])
        fig.add_vline(x=semana, line_color="gray", line_width=1, line_dash="dash")
        fig.update_layout(separators=",.", hovermode="x unified")
        grafico(fig, 380)

# --- Picos --------------------------------------------------------------------
with aba2:
    st.markdown(
        "Dias em que o artista teve muito mais visualizações que o próprio padrão dos 90 dias anteriores. "
        "O critério é um z-score robusto (mediana e MAD, em escala log) de 3,5 ou mais: um único dia "
        "viral não distorce a régua, como aconteceria com média e desvio padrão.")
    pk = an.picos(diario[diario["genero"].isin(generos)])
    if pk.empty:
        st.info("Nenhum dia atípico nos gêneros escolhidos.")
    else:
        top = st.slider("Quantos picos mostrar", 5, 50, 15)
        st.dataframe(
            pk.head(top).round({"base": 0, "vezes_base": 1})[["data", "artista", "genero", "views", "base", "vezes_base"]],
            hide_index=True, width="stretch",
            column_config={
                "data": st.column_config.DateColumn("Dia", format="DD/MM/YYYY"),
                "artista": "Artista", "genero": "Gênero",
                "views": st.column_config.NumberColumn("Views no dia", format=NUM),
                "base": st.column_config.NumberColumn("Dia típico (mediana de 90 dias)", format=NUM),
                "vezes_base": st.column_config.NumberColumn("Vezes o dia típico", format=NUM),
            })
        st.caption(f"{br(len(pk))} dias atípicos no período, somando os artistas filtrados. O dado mostra "
                   "quando a atenção saltou; o porquê (lançamento, show, notícia) pede checagem em notícias.")
        fig = px.scatter(pk, x="data", y="vezes_base", color="genero", hover_name="artista", log_y=True,
                         color_discrete_map=CORES, category_orders={"genero": list(CORES)},
                         labels={"data": "", "vezes_base": "Vezes o dia típico (log)", "genero": "Gênero"},
                         hover_data={"data": "|%d/%m/%Y", "vezes_base": ":.1f", "genero": False})
        fig.update_layout(separators=",.")
        grafico(fig)

# --- Welch --------------------------------------------------------------------
with aba3:
    st.markdown(
        "Um gênero atrai mais atenção que outro, ou a diferença cabe no acaso? Cada artista vira **um** "
        "ponto (média do log das views semanais na janela escolhida), para não contar semanas do mesmo "
        "artista como se fossem pessoas diferentes. O teste t de Welch não supõe que os dois grupos "
        "tenham a mesma variância.")
    todos = list(CORES)
    c1, c2, c3 = st.columns(3)
    ga = c1.selectbox("Gênero A", todos, index=todos.index("MPB"))
    gb = c2.selectbox("Gênero B", [g for g in todos if g != ga])
    janela = c3.slider("Janela (semanas)", 4, 52, 12)
    r = an.welch(semanal, ga, gb, janela)
    if r is None:
        st.info(f"Amostra insuficiente: são precisos ao menos {an.MIN_ARTISTAS} artistas por gênero.")
    else:
        mais, menos = (ga, gb) if r["razao"] >= 1 else (gb, ga)
        razao = max(r["razao"], 1 / r["razao"])
        veredito = ("A diferença é estatisticamente significante (p < 0,05)." if r["significante"]
                    else "Com essa amostra, não dá para afirmar que a diferença não é acaso (p ≥ 0,05).")
        st.markdown(
            f"Na média geométrica, um artista de **{mais}** teve **{br(razao, 1)} vezes** as visualizações "
            f"semanais de um artista de **{menos}** nas últimas {r['semanas']} semanas. {veredito}")
        st.markdown(f"p-valor **{br(r['p'], 3)}** · t de Welch **{br(r['t'], 2)}** · "
                    f"tamanho do efeito (d de Cohen) **{br(r['d'], 2)}** · "
                    f"n = {r['n_a']} artistas em {ga} e {r['n_b']} em {gb}")
        st.caption("Com grupos tão pequenos, o teste só detecta diferenças grandes: p alto aqui quer "
                   "dizer \"não deu para ver\", não \"são iguais\".")
        ult = sorted(semanal["semana"].unique())[-janela:]
        pts = (semanal[semanal["semana"].isin(ult) & semanal["genero"].isin([ga, gb])]
               .assign(log=lambda d: np.log10(d["views"].clip(lower=1)))
               .groupby(["genero", "artista"])["log"].mean().reset_index()
               .assign(views=lambda d: 10 ** d["log"]))
        fig = px.box(pts, x="genero", y="views", color="genero", points="all", hover_name="artista",
                     log_y=True, color_discrete_map=CORES, category_orders={"genero": [ga, gb]},
                     labels={"genero": "", "views": "Views semanais (média geométrica, log)"},
                     hover_data={"genero": False, "views": ":,.0f"})
        fig.update_layout(showlegend=False, separators=",.")
        grafico(fig)

# --- SQL ----------------------------------------------------------------------
with aba4:
    st.markdown("Os dados ficam num banco SQLite com duas tabelas, `artistas` e `pageviews`. "
                "A agregação semanal do painel sai desta consulta:")
    st.code(an.SQL_SEMANAL.strip(), language="sql")
    q = st.text_area("Escreva outra consulta (o banco abre só para leitura)",
                     "SELECT a.genero, COUNT(DISTINCT a.artigo) AS artistas, SUM(p.views) AS views\n"
                     "FROM pageviews p JOIN artistas a USING (artigo)\n"
                     "WHERE p.data >= date((SELECT MAX(data) FROM pageviews), '-29 days')\n"
                     "GROUP BY a.genero\nORDER BY views DESC",
                     height=140)
    if st.button("Rodar consulta", type="primary"):
        try:
            with sqlite3.connect(f"file:{an.DB.as_posix()}?mode=ro", uri=True) as con:
                st.dataframe(pd.read_sql_query(q, con), hide_index=True, width="stretch")
        except Exception as e:  # erro de SQL do visitante: mostra em vez de quebrar o app
            st.error(f"A consulta não rodou: {e}. Confira os nomes das tabelas e colunas acima.")

st.divider()
st.caption("Projeto de portfólio de Lucas Tapajós · [código no GitHub](https://github.com/lucastapajos-max/atencao-musica) · "
           "metodologia descrita no README.")
