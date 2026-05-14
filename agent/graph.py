from langgraph.graph import END, StateGraph

from agent.nodes.decide import decide
from agent.nodes.emit import emit
from agent.nodes.ingest import load_proposal
from agent.nodes.validate_ficha import check_ficha_pontuacao
from agent.nodes.validate_limite import check_limit_proposals
from agent.nodes.validate_pendencias import check_pendencias_e_projetos
from agent.nodes.validate_titulacao import check_titulacao
from agent.state import PropostaState


def build_workflow():
    """
    Constrói e compila o grafo de auditoria de propostas.

    Fluxo sequencial:
      carregar → titulacao → ficha → limite → pendencias → decisao → emitir_docs → END
    """
    workflow = StateGraph(PropostaState)

    workflow.add_node("carregar", load_proposal)
    workflow.add_node("titulacao", check_titulacao)
    workflow.add_node("ficha", check_ficha_pontuacao)
    workflow.add_node("limite", check_limit_proposals)
    workflow.add_node("pendencias", check_pendencias_e_projetos)
    workflow.add_node("decisao", decide)
    workflow.add_node("emitir_docs", emit)

    workflow.set_entry_point("carregar")
    workflow.add_edge("carregar", "titulacao")
    workflow.add_edge("titulacao", "ficha")
    workflow.add_edge("ficha", "limite")
    workflow.add_edge("limite", "pendencias")
    workflow.add_edge("pendencias", "decisao")
    workflow.add_edge("decisao", "emitir_docs")
    workflow.add_edge("emitir_docs", END)

    return workflow.compile()
