"""Dashboard: atenção digital à música brasileira (pageviews da Wikipédia)."""
import sqlite3

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import analise as an

st.set_page_config(page_title="Atenção à música brasileira", page_icon="🎧", layout="wide")


@st.cache_data
def carregar():
    return an.consultar(an.SQL_SEMANAL), an.consultar(an.SQL_DIARIO)


semanal, diario = carregar()
semanas = sorted(semanal["semana"].unique())
fmt = lambda v: f"{v:,.0f}".replace(",", ".")  # noqa: E731

st.title("Atenção digital à música brasileira")
st.caption(
    "Visualizações diárias dos verbetes de 24 artistas na Wikipédia em português, "
    f"de {pd.to_datetime(diario['data'].min()):%d/%m/%Y} a {pd.to_datetime(diario['data'].max()):%d/%m/%Y}. "
    "Fonte: Wikimedia Pageviews API (dados abertos, CC0), só acessos humanos. "
    "Visualização de verbete mede interesse (gente procurando saber do artista), não audiência."
)

with st.sidebar:
    semana = st.selectbox("Semana (segunda a domingo)", semanas[::-1],
                          format_func=lambda s: f"{pd.to_datetime(s):%d/%m/%Y}")
    generos = st.multiselect("Gêneros", sorted(semanal["genero"].unique()),
                             default=sorted(semanal["genero"].unique()))
    st.caption("Gêneros são um agrupamento editorial deste projeto, não uma classificação oficial.")

sem = semanal[semanal["genero"].isin(generos)]
radar = an.radar_semana(sem, semana)

aba1, aba2, aba3, aba4 = st.tabs(["Radar da semana", "Picos de atenção", "Gêneros (teste t)", "SQL"])

# --- Radar --------------------------------------------------------------------
with aba1:
    total = sem.loc[sem["semana"] == semana, "views"].sum()
    hist_total = sem[sem["semana"] < semana].groupby("semana")["views"].sum().tail(26)
    banda_total = an.faixa_normal(hist_total, total)
    c1, c2, c3 = st.columns(3)
    c1.metric("Visualizações na semana", fmt(total),
              f"{banda_total['vs_mediana_pct']:+.0f}% vs mediana de 26 semanas" if banda_total else None)
    if not radar.empty:
        c2.metric("Artistas acima do normal", int((radar["status"] == "acima do normal").sum()))
        c3.metric("Artistas abaixo do normal", int((radar["status"] == "abaixo do normal").sum()))
        st.markdown(
            "**Como ler:** para cada artista, o normal é a faixa das 26 semanas anteriores "
            "(mediana e intervalo interquartil). Fica *acima do normal* quem passa de Q3 + 1,5 × IQR, "
            "o mesmo critério do boxplot.")
        tab = radar.sort_values("vs_mediana_pct", ascending=False)
        st.dataframe(
            tab[["artista", "genero", "status", "valor", "mediana", "vs_mediana_pct"]],
            hide_index=True, use_container_width=True,
            column_config={
                "artista": "Artista", "genero": "Gênero", "status": "Leitura",
                "valor": st.column_config.NumberColumn("Views na semana", format="%d"),
                "mediana": st.column_config.NumberColumn("Mediana (26 sem.)", format="%d"),
                "vs_mediana_pct": st.column_config.NumberColumn("vs mediana", format="%+.0f%%"),
            })

        artista = st.selectbox("Série de um artista", tab["artista"])
        g = sem[sem["artista"] == artista].sort_values("semana").copy()
        roll = g["views"].rolling(26, min_periods=an.MIN_SEMANAS_FAIXA)
        g["q1"], g["q3"] = roll.quantile(.25).shift(1), roll.quantile(.75).shift(1)
        g["lim_sup"] = g["q3"] + 1.5 * (g["q3"] - g["q1"])
        fig = go.Figure([
            go.Scatter(x=g["semana"], y=g["q3"], line=dict(width=0), showlegend=False, hoverinfo="skip"),
            go.Scatter(x=g["semana"], y=g["q1"], fill="tonexty", line=dict(width=0),
                       fillcolor="rgba(120,120,120,.25)", name="Faixa usual (Q1-Q3)"),
            go.Scatter(x=g["semana"], y=g["lim_sup"], line=dict(dash="dot", color="gray"),
                       name="Limite de normalidade"),
            go.Scatter(x=g["semana"], y=g["views"], line=dict(color="#1f77b4"), name="Views na semana"),
        ])
        fig.add_vline(x=semana, line_color="red", line_width=1)
        fig.update_layout(height=380, margin=dict(t=20, b=10), legend=dict(orientation="h"))
        st.plotly_chart(fig, use_container_width=True)

# --- Picos --------------------------------------------------------------------
with aba2:
    st.markdown(
        "Dias em que o artista teve muito mais visualizações que o seu próprio padrão dos "
        "90 dias anteriores. O critério é um z-score robusto (mediana e MAD, em escala log) ≥ 3,5: "
        "um único dia viral não distorce a régua, como aconteceria com média e desvio padrão.")
    pk = an.picos(diario[diario["genero"].isin(generos)])
    top = st.slider("Quantos picos mostrar", 5, 50, 15)
    pk_top = pk.head(top)
    st.dataframe(
        pk_top[["data", "artista", "genero", "views", "base", "vezes_base"]],
        hide_index=True, use_container_width=True,
        column_config={
            "data": "Dia", "artista": "Artista", "genero": "Gênero",
            "views": st.column_config.NumberColumn("Views no dia", format="%d"),
            "base": st.column_config.NumberColumn("Dia típico (mediana 90 d)", format="%d"),
            "vezes_base": st.column_config.NumberColumn("× o dia típico", format="%.1f"),
        })
    st.caption(f"{len(pk)} dias atípicos no período, somando todos os artistas filtrados. "
               "O dado mostra *quando* a atenção saltou; o *porquê* (lançamento, show, notícia) "
               "pede checagem em fontes de notícia.")
    fig = px.scatter(pk, x="data", y="vezes_base", color="genero", hover_name="artista",
                     log_y=True, labels={"data": "", "vezes_base": "× o dia típico", "genero": "Gênero"})
    fig.update_layout(height=360, margin=dict(t=20, b=10))
    st.plotly_chart(fig, use_container_width=True)

# --- Welch --------------------------------------------------------------------
with aba3:
    st.markdown(
        "Um gênero atrai mais atenção que outro, ou a diferença cabe no acaso? "
        "Cada artista vira **um** ponto (média do log das views semanais na janela escolhida), "
        "para não contar semanas do mesmo artista como se fossem pessoas diferentes. "
        "O teste t de Welch não supõe que os dois grupos tenham a mesma variância.")
    todos = sorted(semanal["genero"].unique())
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
            f"Na média geométrica, um artista de **{mais}** teve **{str(round(razao, 1)).replace('.', ',')}×** as visualizações "
            f"semanais de um artista de **{menos}** nas últimas {r['semanas']} semanas. {veredito}")
        c1, c2, c3 = st.columns(3)
        c1.metric("p-valor", f"{r['p']:.3f}".replace(".", ","))
        c2.metric("t de Welch", f"{r['t']:.2f}".replace(".", ","))
        c3.metric("Tamanho do efeito (d)", f"{r['d']:.2f}".replace(".", ","))
        st.caption(f"n = {r['n_a']} artistas em {ga} e {r['n_b']} em {gb}. Com grupos tão pequenos, "
                   "o teste só detecta diferenças grandes: p alto aqui quer dizer 'não deu para ver', "
                   "não 'são iguais'.")
        ult = sorted(semanal["semana"].unique())[-janela:]
        pts = (semanal[semanal["semana"].isin(ult) & semanal["genero"].isin([ga, gb])]
               .assign(log=lambda d: np.log10(d["views"].clip(lower=1)))
               .groupby(["genero", "artista"])["log"].mean().reset_index()
               .assign(views=lambda d: 10 ** d["log"]))
        fig = px.strip(pts, x="genero", y="views", hover_name="artista", log_y=True,
                       labels={"genero": "", "views": "Views semanais (média geométrica)"})
        fig.update_layout(height=360, margin=dict(t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)

# --- SQL ----------------------------------------------------------------------
with aba4:
    st.markdown("Os dados ficam num banco SQLite com duas tabelas, `artistas` e `pageviews`. "
                "A agregação semanal do painel sai desta consulta:")
    st.code(an.SQL_SEMANAL.strip(), language="sql")
    st.markdown("Teste outra consulta (o banco abre só para leitura):")
    q = st.text_area("SQL", "SELECT a.genero, COUNT(DISTINCT a.artigo) AS artistas, SUM(p.views) AS views\n"
                            "FROM pageviews p JOIN artistas a USING (artigo)\n"
                            "WHERE p.data >= date('now', '-30 days')\nGROUP BY a.genero\nORDER BY views DESC",
                     height=140)
    if st.button("Rodar"):
        try:
            with sqlite3.connect(f"file:{an.DB.as_posix()}?mode=ro", uri=True) as con:
                st.dataframe(pd.read_sql_query(q, con), hide_index=True, use_container_width=True)
        except Exception as e:  # erro de SQL do visitante: mostra em vez de quebrar o app
            st.error(f"Erro na consulta: {e}")

st.divider()
st.caption("Projeto de portfólio de Lucas Tapajós · código em GitHub · "
           "metodologia de faixa de normalidade, picos e teste t descrita no README.")
