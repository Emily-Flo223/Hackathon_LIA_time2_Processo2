import json
import os
import re
import xml.etree.ElementTree as ET

from agent.state import PropostaState, ValidationResult


def check_limit_proposals(state: PropostaState) -> dict:
    """
    Nó de Validação — Limite de Propostas:
    Verifica se o proponente respeita o limite de submissões cruzando
    o CPF com todas as propostas no diretório.
    Pesquisadores com Bolsa PQ (CNPq) têm limite de 3; demais, 2.
    """
    cpf_atual = state.get("dados_formulario", {}).get("dados_coordenador", {}).get("6_cpf")
    xml_string = state.get("dados_lattes", "")
    diretorio_proposta = state.get("diretorio_proposta", "")

    if not cpf_atual or not diretorio_proposta:
        return {
            "resultados_validacao": state.get("resultados_validacao", []) + [
                ValidationResult(
                    regra="Limite de Propostas",
                    passou=False,
                    motivo="CPF ou diretório base não encontrados no estado.",
                    evidencia="Falha de ingestão de dados.",
                )
            ]
        }

    passou = False
    motivo = "Erro ao verificar limites."
    evidencia = "N/A"

    try:
        # 1. Detecta Bolsa PQ no Lattes
        is_pq = False
        try:
            xml_clean = re.sub(r"<\?xml.*?\?>", "", xml_string).strip()
            root = ET.fromstring(xml_clean)
            for v in root.findall(".//VINCULOS"):
                if v.get("TIPO-DE-VINCULO") == "Bolsista de Produtividade" and v.get("ORGAO") == "CNPq":
                    is_pq = True
                    break
        except ET.ParseError:
            pass

        limite_permitido = 3 if is_pq else 2

        # 2. Conta propostas do mesmo CPF no lote
        dir_base = os.path.dirname(diretorio_proposta)
        total_submissoes = 0
        titulos_encontrados: list[str] = []

        for pasta in os.listdir(dir_base):
            caminho_form = os.path.join(dir_base, pasta, "formulario.json")
            if os.path.isfile(caminho_form):
                try:
                    with open(caminho_form, "r", encoding="utf-8") as f:
                        form = json.load(f)
                    if form.get("dados_coordenador", {}).get("6_cpf") == cpf_atual:
                        total_submissoes += 1
                        titulo = form.get("dados_projeto", {}).get(
                            "7_titulo_plano_trabalho", "Título não informado"
                        )
                        titulos_encontrados.append(f"  - {titulo} (ID: {form.get('id_proposta', 'N/A')})")
                except Exception:
                    continue

        lista_titulos = "\n".join(titulos_encontrados)

        if total_submissoes <= limite_permitido:
            passou = True
            motivo = f"Proponente respeitou o limite de propostas (máximo: {limite_permitido})."
            evidencia = (
                f"Status PQ: {'Sim' if is_pq else 'Não'}.\n"
                f"Projetos encontrados no sistema ({total_submissoes}):\n{lista_titulos}"
            )
        else:
            passou = False
            motivo = "Proponente excedeu o limite de propostas submetidas."
            evidencia = (
                f"Status PQ: {'Sim' if is_pq else 'Não'} (Limite: {limite_permitido}).\n"
                f"Projetos encontrados no sistema ({total_submissoes}):\n{lista_titulos}"
            )

    except Exception as e:
        motivo = "Falha técnica ao varrer propostas e contar limites."
        evidencia = str(e)

    resultado = ValidationResult(
        regra="Limite de Propostas",
        passou=passou,
        motivo=motivo,
        evidencia=evidencia,
    )
    return {"resultados_validacao": state.get("resultados_validacao", []) + [resultado]}
