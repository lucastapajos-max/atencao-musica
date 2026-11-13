CREATE TABLE IF NOT EXISTS artistas (
    artigo  TEXT PRIMARY KEY,   -- título do verbete na Wikipédia pt
    artista TEXT NOT NULL,
    genero  TEXT NOT NULL       -- agrupamento editorial do projeto
);
CREATE TABLE IF NOT EXISTS pageviews (
    artigo TEXT NOT NULL REFERENCES artistas(artigo),
    data   TEXT NOT NULL,       -- AAAA-MM-DD
    views  INTEGER NOT NULL,
    PRIMARY KEY (artigo, data)
);
