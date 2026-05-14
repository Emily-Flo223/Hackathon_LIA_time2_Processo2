import os
import json

from agent.state import PropostaState


def load_proposal(state: PropostaState) -> dict:
    """
    Nó de Ingestão: lê os arquivos do diretório da proposta e extrai
    os dados brutos para popular o estado inicial do LangGraph.
    """
    diretorio = state.get("diretorio_proposta")

    if not diretorio or not os.path.exists(diretorio):
        raise ValueError(f"Diretório da proposta não encontrado: {diretorio}")

    # A. Formulário (JSON)
    caminho_form = os.path.join(diretorio, "formulario.json")
    try:
        with open(caminho_form, "r", encoding="utf-8") as f:
            dados_formulario = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"formulario.json não encontrado em: {diretorio}")

    # B. Currículo Lattes (XML como string — encoding nativo ISO-8859-1)
    caminho_lattes = os.path.join(diretorio, "lattes.xml")
    try:
        with open(caminho_lattes, "r", encoding="ISO-8859-1") as f:
            dados_lattes = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"lattes.xml não encontrado em: {diretorio}")

    # C. Ficha de Pontuação (Excel — apenas registra o caminho; leitura feita no nó específico)
    caminho_ficha = os.path.join(diretorio, "ficha_pontuacao.xlsx")
    if not os.path.exists(caminho_ficha):
        raise FileNotFoundError(f"ficha_pontuacao.xlsx não encontrado em: {diretorio}")

    return {
        "id_proposta": dados_formulario.get("id_proposta", "DESCONHECIDO"),
        "dados_formulario": dados_formulario,
        "dados_lattes": dados_lattes,
        "caminho_ficha": caminho_ficha,
        "resultados_validacao": state.get("resultados_validacao", []),
    }
