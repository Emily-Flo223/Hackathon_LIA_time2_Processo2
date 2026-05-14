import json
import os

from agent.llm import call_llm
from agent.logger import get_logger
from agent.state import PropostaState
from agent.utils.prompts import load_prompt


def emit(state: PropostaState) -> dict:
    """
    Nó de Emissão — Proposta Individual:
    Gera e salva, dentro da pasta da proposta:
      - {id}_parecer.json
      - {id}_parecer.md
      - {id}_email_individual.txt
    """
    log = get_logger()

    diretorio = state.get("diretorio_proposta")
    id_prop = state.get("id_proposta")
    status = state.get("status_enquadramento")
    resultados = state.get("resultados_validacao", [])

    nome_coord = (
        state.get("dados_formulario", {}).get("dados_coordenador", {}).get("nome", "N/A")
    )
    titulo_proj = (
        state.get("dados_formulario", {}).get("dados_projeto", {}).get("7_titulo_plano_trabalho", "N/A")
    )
    unidade = (
        state.get("dados_formulario", {}).get("dados_projeto", {}).get("13_unidade_executora", "N/A")
    )
    modalidade = (
        state.get("dados_formulario", {}).get("dados_projeto", {}).get("9_programa", "IC&T")
    )

    falhas = [res for res in resultados if not res.passou]

    # --- E-mail individual via LLM ---
    if status == "ENQUADRADA":
        contexto_falhas = "Nenhuma. A proposta atendeu a todos os requisitos formais do edital."
    else:
        textos = [
            f"Regra {i}: {f.regra}\nMotivo: {f.motivo}\nEvidência: {f.evidencia}"
            for i, f in enumerate(falhas, 1)
        ]
        contexto_falhas = "\n\n".join(textos)

    system_prompt = load_prompt("email_individual.md")
    user_prompt = f"""DADOS:
- Pesquisador: {nome_coord}
- ID da Proposta: {id_prop}
- Título: <u>"{titulo_proj}"</u>
- Modalidade: {modalidade}
- Status: {status}

INCONFORMIDADES:
{contexto_falhas}

Redija o e-mail individual agora."""

    log.info("emit.individual.start", proposal_id=id_prop, coordinator=nome_coord)
    try:
        email_individual = call_llm(
            system_prompt, user_prompt, temperature=0.1, log_event="emit.individual"
        )
    except Exception as e:
        log.error("emit.individual.error", proposal_id=id_prop, error=str(e))
        email_individual = f"Erro de comunicação com a API (E-mail Individual): {str(e)}"

    # 1. Parecer em JSON
    caminho_json = os.path.join(diretorio, f"{id_prop}_parecer.json")
    dados_saida = {
        "id_proposta": id_prop,
        "coordenador": nome_coord,
        "unidade_lotacao": unidade,
        "titulo_projeto": titulo_proj,
        "status_final": status,
        "data_processamento": "2026-05-14",
        "auditoria": [res.model_dump() for res in resultados],
    }
    with open(caminho_json, "w", encoding="utf-8") as f:
        json.dump(dados_saida, f, indent=4, ensure_ascii=False)

    # 2. Parecer em Markdown
    caminho_md = os.path.join(diretorio, f"{id_prop}_parecer.md")
    md = f"# Parecer de Enquadramento — {id_prop}\n\n"
    md += f"**Resultado:** {status}\n\n"
    md += "## Detalhes da Validação\n"
    for res in resultados:
        icon = "✅" if res.passou else "❌"
        md += f"### {icon} {res.regra}\n"
        md += f"- **Motivo:** {res.motivo}\n"
        md += f"- **Evidência:** {res.evidencia}\n\n"
    with open(caminho_md, "w", encoding="utf-8") as f:
        f.write(md)

    # 3. E-mail individual em TXT (mantendo tags HTML para o Streamlit)
    caminho_txt = os.path.join(diretorio, f"{id_prop}_email_individual.txt")
    with open(caminho_txt, "w", encoding="utf-8") as f:
        f.write(email_individual)

    log.info(
        "emit.individual.done",
        proposal_id=id_prop,
        artifacts=["parecer.json", "parecer.md", "email_individual.txt"],
    )
    return state


# ---------------------------------------------------------------------------
# Função auxiliar (usada pelo orquestrador, não é nó do grafo)
# ---------------------------------------------------------------------------

def gerar_email_unico_pesquisador(lista_propostas: list, diretorio_outputs: str) -> None:
    """
    Gera um e-mail consolidado (HTML) para um pesquisador com todos os seus projetos
    e salva em diretorio_outputs/EMAIL_{NOME}.txt.
    """
    log = get_logger()

    primeira = lista_propostas[0]
    nome_coord = (
        primeira.get("dados_formulario", {})
        .get("dados_coordenador", {})
        .get("nome", "Prezado(a) Coordenador(a)")
    )

    contexto_projetos = ""
    for i, prop in enumerate(lista_propostas, 1):
        dados_proj = prop.get("dados_formulario", {}).get("dados_projeto", {})
        titulo = dados_proj.get("7_titulo_plano_trabalho", "Projeto Não Identificado")
        id_proposta = dados_proj.get("id_proposta", prop.get("id_proposta", f"PROPOSTA_{i:03d}"))
        modalidade = dados_proj.get("9_programa", "IC&T")
        status = prop.get("status_enquadramento", "ERRO")
        falhas = [r for r in prop.get("resultados_validacao", []) if not r.passou]

        contexto_projetos += f"\nPROJETO {i}:\n"
        contexto_projetos += f"- ID: {id_proposta}\n"
        contexto_projetos += f'- Título: <u>"{titulo}"</u>\n'
        contexto_projetos += f"- Modalidade: {modalidade}\n"
        contexto_projetos += f"- Status Final: {status}\n"

        if status == "ENQUADRADA":
            contexto_projetos += "- Inconformidades: Nenhuma.\n"
        else:
            contexto_projetos += "- Inconformidades Encontradas:\n"
            for f in falhas:
                contexto_projetos += (
                    f"  Regra Violada: {f.regra}\n"
                    f"  Motivo: {f.motivo}\n"
                    f"  Evidência: {f.evidencia}\n"
                )

    system_prompt = load_prompt("email_consolidado.md")
    user_prompt = f"""DADOS DA SUBMISSÃO 🏷️
- Pesquisador: {nome_coord}

RESUMO DE TODOS OS PROJETOS ENVIADOS E RESULTADOS DA AUDITORIA:
{contexto_projetos}

Por favor, redija o e-mail consolidado agora."""

    log.info(
        "emit.consolidated.start",
        coordinator=nome_coord,
        num_proposals=len(lista_propostas),
    )
    try:
        rascunho = call_llm(
            system_prompt, user_prompt, temperature=0.1, log_event="emit.consolidated"
        )
    except Exception as e:
        log.error("emit.consolidated.error", coordinator=nome_coord, error=str(e))
        rascunho = f"Erro de comunicação com a API: {str(e)}"

    # Salva em TXT mantendo as tags HTML para o Streamlit
    nome_arquivo = nome_coord.replace(" ", "_").upper()
    caminho_txt = os.path.join(diretorio_outputs, f"EMAIL_{nome_arquivo}.txt")
    with open(caminho_txt, "w", encoding="utf-8") as f:
        f.write(rascunho)

    log.info("emit.consolidated.done", coordinator=nome_coord, output=caminho_txt)
