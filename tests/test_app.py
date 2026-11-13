from streamlit.testing.v1 import AppTest


def rodar(generos=None):
    at = AppTest.from_file("../app.py", default_timeout=60).run()
    if generos is not None:
        at.multiselect[0].set_value(generos).run()
    assert not at.exception, at.exception
    return at


def test_app_abre_com_todos_os_generos():
    at = rodar()
    assert any("Maior salto do período" in m.value for m in at.markdown)


def test_um_genero_so_avisa_na_comparacao_e_mantem_o_sql():
    at = rodar(["MPB"])
    assert any("ao menos dois gêneros" in i.value for i in at.info)
    assert at.text_area  # a aba SQL continua de pé
