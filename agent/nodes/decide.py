from agent.logger import get_logger
from agent.state import PropostaState


def decide(state: PropostaState) -> dict:
    """
    Nó Decisor (fan-in):
    Avalia todos os resultados das validações e determina o status final.
    • Todos passaram → ENQUADRADA
    • Algum falhou  → NÃO ENQUADRADA (com relatório completo)
    """
    log = get_logger()
    resultados = state.get("resultados_validacao", [])
    id_prop = state.get("id_proposta", "Desconhecido")
    nome_coord = (
        state.get("dados_formulario", {}).get("dados_coordenador", {}).get("nome", "N/A")
    )

    if not resultados:
        log.warning("decide.no_validations", proposal_id=id_prop)
        return {"status_enquadramento": "ERRO_FLUXO: Nenhuma validação executada."}

    falhas = [res for res in resultados if not res.passou]

    if not falhas:
        status_final = "ENQUADRADA"
        log.info(
            "decide.result",
            proposal_id=id_prop,
            coordinator=nome_coord,
            status=status_final,
            failures=0,
        )
    else:
        status_final = "NÃO ENQUADRADA"
        log.info(
            "decide.result",
            proposal_id=id_prop,
            coordinator=nome_coord,
            status=status_final,
            failures=len(falhas),
            failed_rules=[f.regra for f in falhas],
        )

    return {"status_enquadramento": status_final}
