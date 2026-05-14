import re
import xml.etree.ElementTree as ET

from agent.state import PropostaState, ValidationResult


def check_titulacao(state: PropostaState) -> dict:
    """
    Nó de Validação — Titulação:
    Verifica se o proponente possui o título de Doutor concluído
    navegando na árvore real do Currículo Lattes.
    """
    xml_string = state.get("dados_lattes", "")

    passou = False
    motivo = "Não foi possível encontrar a titulação de Doutorado."
    evidencia = "Ausência da tag <DOUTORADO> na árvore de formação."

    try:
        # Remove a declaração <?xml ...?> para evitar conflito de encoding
        xml_clean = re.sub(r"<\?xml.*?\?>", "", xml_string).strip()
        root = ET.fromstring(xml_clean)

        formacao = root.find(".//FORMACAO-ACADEMICA-TITULACAO")

        if formacao is not None:
            doutorado = formacao.find("DOUTORADO")

            if doutorado is not None:
                status = doutorado.get("STATUS-DO-CURSO", doutorado.get("STATUS", "")).upper()

                if status == "CONCLUIDO":
                    passou = True
                    motivo = "Proponente possui titulação de Doutor concluída."
                    tese = doutorado.get("NOME-CURSO", "Título da tese não informado")
                    instituicao = doutorado.get("NOME-INSTITUICAO", "Instituição não informada")
                    ano = doutorado.get("ANO-DE-CONCLUSAO", "Ano não informado")
                    evidencia = (
                        f"Título da tese: {tese}. | "
                        f"Instituição: {instituicao}. | "
                        f"Conclusão: {ano}."
                    )
                else:
                    motivo = f"Proponente possui registro de Doutorado, mas o status é: {status}."
                    evidencia = f"Tag <DOUTORADO> encontrada com status '{status}' (esperado: 'CONCLUIDO')."
            else:
                mestrado = formacao.find("MESTRADO")
                if mestrado is not None:
                    tese = mestrado.get("NOME-CURSO", "Título da tese não informado")
                    instituicao = mestrado.get("NOME-INSTITUICAO", "Instituição não informada")
                    ano = mestrado.get("ANO-DE-CONCLUSAO", "Ano não informado")
                    motivo = "Proponente possui apenas nível de Mestrado ou inferior."
                    evidencia = (
                        f"Apenas tag <MESTRADO> localizada na Formação Acadêmica. "
                        f"Tese: {tese} | Instituição: {instituicao} | Conclusão: {ano}."
                    )
        else:
            motivo = "O bloco de Formação Acadêmica não foi encontrado no currículo."
            evidencia = "Tag <FORMACAO-ACADEMICA-TITULACAO> ausente."

    except ET.ParseError as e:
        motivo = "Erro crítico ao processar o arquivo XML do Lattes."
        evidencia = f"Arquivo corrompido ou mal formatado. Erro: {str(e)}"

    resultado = ValidationResult(
        regra="Verificação de Titulação",
        passou=passou,
        motivo=motivo,
        evidencia=evidencia,
    )

    return {"resultados_validacao": state.get("resultados_validacao", []) + [resultado]}
