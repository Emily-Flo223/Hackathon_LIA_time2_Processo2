import json
import os

from agent.state import PropostaState, ValidationResult


def check_pendencias_e_projetos(state: PropostaState) -> dict:
    """
    Nó de Validação — Histórico/Pendências:
    Verifica, contra a base interna da PROPP, se o proponente:
    1. Não possui pendências institucionais impeditivas.
    2. Possui projeto de pesquisa ativo.

    O internal_database.json deve estar em data/, que é o diretório
    pai das pastas PROPOSTA_* (ex: data/PROPOSTA_001).
    """
    cpf_atual = state.get("dados_formulario", {}).get("dados_coordenador", {}).get("6_cpf")
    diretorio_proposta = state.get("diretorio_proposta", "")

    if not cpf_atual or not diretorio_proposta:
        return {
            "resultados_validacao": state.get("resultados_validacao", []) + [
                ValidationResult(
                    regra="Histórico/Pendências do Proponente",
                    passou=False,
                    motivo="Falha ao identificar CPF.",
                    evidencia="Falha de ingestão de dados.",
                )
            ]
        }

    lista_motivos: list[str] = []
    lista_evidencias: list[str] = []
    projetos_ativos_str = ""

    try:
        # O internal_database.json fica em data/, diretório pai das pastas PROPOSTA_*
        dir_lote = os.path.dirname(diretorio_proposta)
        caminho_base = os.path.join(dir_lote, "internal_database.json")

        if not os.path.exists(caminho_base):
            raise FileNotFoundError(
                f"internal_database.json não encontrado em: {dir_lote}"
            )

        with open(caminho_base, "r", encoding="utf-8") as f:
            base_interna = json.load(f)

        registro = next((item for item in base_interna if item["cpf"] == cpf_atual), None)

        if not registro:
            lista_motivos.append("Proponente não localizado na base de dados da PROPP.")
            lista_evidencias.append(
                f"O CPF {cpf_atual} não retornou nenhum histórico no sistema interno."
            )
        else:
            # Regra A: Pendências impeditivas
            pendencias_impeditivas = [
                p for p in registro.get("pendencias_propp", []) if p.get("impeditiva") is True
            ]
            if pendencias_impeditivas:
                lista_motivos.append("Proponente possui pendências institucionais impeditivas ativas com a PROPP.")
                pend_str = [
                    f"[{p.get('id_pendencia', 'N/A')}] "
                    f"{p.get('descricao', 'Pendência não detalhada')} "
                    f"(Vencimento: {p.get('data_vencimento', 'N/A')})"
                    for p in pendencias_impeditivas
                ]
                lista_evidencias.append(
                    f"Pendências localizadas ({len(pendencias_impeditivas)}):\n    - " + "\n    - ".join(pend_str)
                )

            # Regra B: Projeto em andamento
            projetos = registro.get("projetos_em_andamento", [])
            if not projetos:
                lista_motivos.append("Proponente não está vinculado a nenhum projeto de pesquisa em andamento.")
                lista_evidencias.append(
                    "A lista de projetos em andamento retornou vazia na base interna do SIGProj/PROPP."
                )
            else:
                proj_str = [
                    f"[{p.get('id_sigproj', 'ID N/A')}] "
                    f"{p.get('titulo', 'Projeto')} ({p.get('papel', 'Pesquisador')}) "
                    f"— Vigência: {p.get('vigencia_fim', 'N/A')}"
                    for p in projetos
                ]
                projetos_ativos_str = (
                    f"Projetos ativos vinculados ao pesquisador ({len(projetos)}):\n  - "
                    + "\n  - ".join(proj_str)
                )

    except Exception as e:
        lista_motivos.append("Falha técnica ao consultar a base interna da PROPP.")
        lista_evidencias.append(str(e))

    if not lista_motivos:
        passou = True
        motivo_final = "Proponente regularizado: sem pendências e com projeto em andamento."
        evidencia_final = f"Consulta à base interna finalizada com status regular.\n{projetos_ativos_str}"
    else:
        passou = False
        motivo_final = f"Inconsistência no histórico do proponente: {len(lista_motivos)} bloqueio(s)."
        erros = [f"\n• Motivo: {m}\n  Evidência: {e}" for m, e in zip(lista_motivos, lista_evidencias)]
        evidencia_final = "\n\n".join(erros)

    resultado = ValidationResult(
        regra="Histórico/Pendências do Proponente",
        passou=passou,
        motivo=motivo_final,
        evidencia=evidencia_final,
    )
    return {"resultados_validacao": state.get("resultados_validacao", []) + [resultado]}
