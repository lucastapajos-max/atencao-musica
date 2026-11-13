"""Dashboard: atenção digital à música brasileira (pageviews da Wikipédia)."""
import sqlite3

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import analise as an

st.set_page_config(page_title="Atenção à música brasileira", page_icon=":material/graphic_eq:", layout="wide")

# Legendas e links com contraste de leitura (o cinza padrão fica abaixo de 4,5:1) e texto
# corrido com no máximo ~75 caracteres por linha. Tabelas e gráficos não são afetados.
st.markdown("""<style>
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * { color: #4a4f57 !important; opacity: 1 !important; }
[data-testid="stCaptionContainer"] a, [data-testid="stMarkdownContainer"] a { color: #0b5e53 !important; opacity: 1 !important; }
[data-testid="stMarkdownContainer"] p, [data-testid="stCaptionContainer"] p { max-width: 62ch; text-wrap: pretty; }
</style>""", unsafe_allow_html=True)

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

def rotulo_semana(s):
    ini = pd.to_datetime(s)
    return f"{ini:%d/%m} a {ini + pd.Timedelta(days=6):%d/%m/%Y}"


st.title("Atenção digital à música brasileira")
st.caption(
    "Quanto as pessoas procuram saber de 24 artistas brasileiros, medido pelas visualizações dos "
    f"verbetes na Wikipédia em português, de {diario['data'].min():%d/%m/%Y} a "
    f"{diario['data'].max():%d/%m/%Y}. Atualizado toda segunda. Fonte: Wikimedia Pageviews API "
    "(dados abertos, CC0), só acessos humanos.")

with st.sidebar:
    semana = st.selectbox("Semana", semanas[::-1], format_func=rotulo_semana)
    generos = st.multiselect("Gêneros", list(CORES), default=list(CORES))
    st.caption("Agrupamento editorial deste projeto, não uma classificação oficial.")

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
                "mediana": st.column_config.NumberColumn("Mediana 26 sem.", format=NUM),
                "vs_mediana_pct": st.column_config.NumberColumn("vs mediana", format="%+.0f%%"),
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
    pk = an.picos(diario[diario["genero"].isin(generos)])
    if pk.empty:
        st.info("Nenhum dia atípico nos gêneros escolhidos.")
    else:
        maior = pk.iloc[0]
        na_semana = pk[(pk["data"] >= pd.to_datetime(semana)) & (pk["data"] <= fim_semana)]
        resumo = (f"Maior salto do período: **{maior['artista']}** em {maior['data']:%d/%m/%Y}, "
                  f"com {br(maior['vezes_base'], 1)} vezes as visualizações de um dia típico. ")
        if len(na_semana):
            dias = na_semana.sort_values("data")
            resumo += (f"Na semana de {rotulo_semana(semana)}: "
                       + lista(f"{r.artista} ({r.data:%d/%m}, {br(r.vezes_base, 1)} vezes)" for r in dias.itertuples())
                       + ".")
        else:
            resumo += f"Na semana de {rotulo_semana(semana)}, nenhum artista teve um dia fora do padrão."
        st.markdown(resumo)
        with st.expander("Como calculei"):
            st.markdown(
                "Um pico é um dia em que o artista teve muito mais visualizações que o próprio padrão "
                "dos 90 dias anteriores. A régua é a mediana desses dias, e a distância é medida pelo "
                "desvio absoluto mediano (MAD), em escala logarítmica, com corte em 3,5. Mediana e MAD "
                "não se deixam distorcer por um único dia viral, como média e desvio padrão se deixariam.")
        top = st.slider("Quantos picos mostrar", 5, 50, 15)
        st.dataframe(
            pk.head(top).round({"base": 0, "vezes_base": 1})[["data", "artista", "genero", "views", "base", "vezes_base"]],
            hide_index=True, width="stretch",
            column_config={
                "data": st.column_config.DateColumn("Dia", format="DD/MM/YYYY"),
                "artista": "Artista", "genero": "Gênero",
                "views": st.column_config.NumberColumn("Views no dia", format=NUM),
                "base": st.column_config.NumberColumn("Dia típico", format=NUM, help="Mediana dos 90 dias anteriores"),
                "vezes_base": st.column_config.NumberColumn("Vezes o dia típico", format=NUM),
            })
        st.caption(f"{br(len(pk))} dias atípicos no período, somando os artistas filtrados. O dado mostra "
                   "quando a atenção saltou; o porquê (lançamento, show, notícia) pede checagem em notícias.")
        fig = px.scatter(pk, x="data", y="vezes_base", color="genero", hover_name="artista", log_y=True,
                         color_discrete_map=CORES, category_orders={"genero": list(CORES)},
                         labels={"data": "", "vezes_base": "Vezes o dia típico (log)", "genero": "Gênero"},
                         hover_data={"data": "|%d/%m/%Y", "vezes_base": ":.1f", "genero": False})
        fig.add_vrect(x0=pd.to_datetime(semana), x1=fim_semana + pd.Timedelta(days=1),
                      fillcolor="gray", opacity=.25, line_width=0,
                      annotation_text="semana escolhida", annotation_position="top left")
        fig.update_layout(separators=",.")
        grafico(fig)

# --- Welch --------------------------------------------------------------------
with aba3:
    st.markdown("Um gênero atrai mais atenção que outro, ou a diferença cabe no acaso?")
    r = None
    if len(generos) < 2:
        st.info("Para comparar, deixe ao menos dois gêneros marcados na barra lateral.")
    else:
        c1, c2, c3 = st.columns(3)
        ga = c1.selectbox("Gênero A", generos, index=generos.index("MPB") if "MPB" in generos else 0)
        gb = c2.selectbox("Gênero B", [g for g in generos if g != ga])
        janela = c3.slider("Janela (semanas)", 4, 52, 12)
        r = an.welch(semanal, ga, gb, janela)
        if r is None:
            st.info(f"Amostra insuficiente: são precisos ao menos {an.MIN_ARTISTAS} artistas por gênero.")
    if r:
        mais, menos = (ga, gb) if r["razao"] >= 1 else (gb, ga)
        razao = max(r["razao"], 1 / r["razao"])
        veredito = ("A diferença é estatisticamente significante (p < 0,05)." if r["significante"]
                    else "Com essa amostra, não dá para afirmar que a diferença não é acaso (p ≥ 0,05).")
        st.markdown(
            f"Na média geométrica, um artista de **{mais}** teve **{br(razao, 1)} vezes** as visualizações "
            f"semanais de um artista de **{menos}** nas últimas {r['semanas']} semanas. {veredito}")
        st.caption(f"Base: {r['n_a']} artistas de {ga} e {r['n_b']} de {gb}. Com grupos tão pequenos, o "
                   "teste só enxerga diferenças grandes: quando ele não acha diferença, quer dizer \"não "
                   "deu para ver\", não \"são iguais\".")
        with st.expander("Como calculei"):
            st.markdown(
                "Cada artista vira um ponto: a média do log das visualizações semanais na janela "
                "escolhida. Assim, 12 semanas do mesmo artista não contam como 12 casos independentes. "
                "O teste t de Welch compara os dois grupos sem supor que eles variem do mesmo jeito.\n\n"
                f"p-valor **{br(r['p'], 3)}** (abaixo de 0,05, a diferença dificilmente é acaso) · "
                f"t de Welch **{br(r['t'], 2)}** · tamanho do efeito, d de Cohen, **{br(r['d'], 2)}** "
                "(a partir de 0,8 em módulo, a diferença é considerada grande)")
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
    st.caption("A consulta enxerga o banco inteiro: os filtros da barra lateral não se aplicam aqui.")
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
