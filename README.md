# Acessos à Wikipédia e eventos da música brasileira

Projeto de portfólio feito para demonstrar, com dados públicos, o ciclo completo de uma análise: coleta por API, banco SQLite consultado em SQL, análise estatística em Python e painel publicado em Streamlit. O tema é como acontecimentos do mundo real (um aniversário, a data de uma morte) aparecem nos acessos aos verbetes de 24 artistas brasileiros na Wikipédia em português.

**App no ar:** https://wikipedia-musica-brasileira.streamlit.app

![Radar da semana](docs/radar.jpg)

## Problema

Os acessos diários a um verbete sobem e descem o tempo todo. Quando algo acontece com um artista, mais gente abre a página dele, e o evento fica registrado nos dados. Só que esse registro vem misturado à oscilação comum, e olhar o gráfico não basta para separar uma coisa da outra.

O projeto responde três perguntas com critério estatístico explícito:

1. **A semana de um artista fugiu do padrão dele?** Cada semana é comparada com as 26 anteriores do próprio artista.
2. **Em que dias os acessos saltaram?** O painel lista os dias atípicos, que são os candidatos a evento.
3. **Os artistas de um gênero têm mais acessos que os de outro, ou a diferença cabe no acaso?** Um teste de hipótese responde, com o tamanho da amostra à vista.

## Dados

- **Fonte:** [Wikimedia Pageviews API](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/), dados abertos sob licença CC0, sem chave de acesso.
- **Recorte:** acessos diários a 24 verbetes da Wikipédia em português, de 01/01/2024 até o último domingo antes da coleta. Só acessos humanos (`agent=user`); robôs ficam de fora.
- **Artistas e gêneros:** 6 artistas por gênero (Sertanejo, Funk e pop, MPB, Rap e trap), listados em [`artistas.csv`](artistas.csv). O agrupamento é editorial, feito para este projeto.
- **Limite:** o dado conta quantas vezes cada verbete foi aberto. Não mede audiência, streams nem atividade em redes sociais.

## Método

| Etapa | Arquivo | O que faz |
|---|---|---|
| Coleta | [`coleta.py`](coleta.py) | Chama a API para cada artista, respeita o limite de taxa (espera e tenta de novo) e grava no SQLite. Rodar de novo substitui as linhas, sem duplicar, e quem sai de `artistas.csv` sai do banco. Tudo numa transação só. |
| Banco | [`schema.sql`](schema.sql) | Duas tabelas: `artistas` e `pageviews` (chave artigo + data). |
| Consulta | [`analise.py`](analise.py) | A agregação semanal sai de SQL (semana de segunda a domingo). O app tem uma aba para rodar consultas próprias, com o banco aberto só para leitura. |
| Faixa de normalidade | `faixa_normal()` | Mediana e intervalo interquartil (IQR) das 26 semanas anteriores. Acima de Q3 + 1,5 × IQR é "acima do normal", o critério do boxplot. Com menos de 8 semanas de histórico, não julga. |
| Picos | `picos()` | z-score robusto em escala log: mediana e MAD dos 90 dias anteriores, corte em 3,5. Mediana e MAD não se deixam distorcer por um único dia viral, como aconteceria com média e desvio padrão. |
| Comparação de gêneros | `welch()` | Teste t de Welch sobre a média do log dos acessos semanais **por artista**. Cada artista é uma observação, para não contar 12 semanas do mesmo artista como 12 casos independentes. Welch porque não supõe variâncias iguais. Mostra p-valor, tamanho do efeito (d de Cohen) e n. |
| Atualização | [`coleta.yml`](.github/workflows/coleta.yml) | Toda segunda às 6h (Brasília), o GitHub Actions coleta a semana que fechou no domingo, roda os testes e só então grava o banco. O Streamlit Cloud republica o app a cada gravação. |
| Testes | [`tests/`](tests) | `pytest` com dados sintéticos: a faixa classifica certo, o pico plantado é achado, o teste respeita a amostra mínima, toda semana do SQL começa na segunda, e o app abre sem erro com um gênero ou com todos. |

## Resultado

Leituras da coleta de 13/11/2026. O painel recalcula tudo toda segunda, com a coleta automática, e os números abaixo ficam como registro dessa data.

- **Picos explicáveis:** o maior pico de Chico Buarque foi em 19/06/2024, dia em que ele fez 80 anos: 10.961 acessos contra 592 num dia típico, 18,5 vezes mais. Na semana de 02/11/2026, a de Marília Mendonça somou 11.159 acessos, 304% acima da mediana de 26 semanas, na semana em que se completaram cinco anos da morte dela (05/11/2021). O método aponta *quando* os acessos saltaram; o *porquê* sai da checagem em notícias.
- **Gêneros:** nas últimas 12 semanas, um artista de MPB teve, em média geométrica, 4,9 vezes os acessos semanais de um artista de Funk e pop (Welch, p = 0,020, d = 1,85, n = 6 por grupo). Funk e pop contra Rap e trap não teve diferença detectável (p = 0,51). Com 6 artistas por grupo, p alto quer dizer "não deu para ver", não "são iguais".

![Série semanal com faixa de normalidade](docs/serie.jpg)

![Comparação de gêneros](docs/generos.jpg)

## Como rodar

```bash
python -m venv .venv
.venv/Scripts/activate        # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python coleta.py              # opcional: o banco já vem no repositório e se atualiza toda segunda
streamlit run app.py
python -m pytest tests -q
```

## Próximos passos

- Cruzar os picos com datas de lançamento e notícias para classificar a causa.
- Somar uma segunda fonte de dados, como seguidores em plataformas de streaming, para ver se os eventos aparecem nas duas.

---

Projeto de portfólio de Lucas Tapajós. Os artistas aparecem só como objeto de dados públicos; o projeto não tem relação com eles nem com suas gravadoras.
