import pandas as pd

from agent.logger import get_logger


def generate_consolidated_report(states: list, output_path: str) -> None:
    """
    Gera a planilha Excel gerencial com duas abas:
      - Resumo Propostas: uma linha por proposta com colunas enriquecidas.
      - Estatísticas de Erros: frequência e percentual de cada regra violada.
    """
    log = get_logger()

    if not states:
        log.warning("report.empty", message="Nenhum estado recebido para consolidação.")
        return

    rows = []
    motivos_falha = []

    for s in states:
        id_prop = s.get("id_proposta")
        status = s.get("status_enquadramento")
        resultados = s.get("resultados_validacao", [])

        dados_proj = s.get("dados_formulario", {}).get("dados_projeto", {})
        dados_coord = s.get("dados_formulario", {}).get("dados_coordenador", {})

        nome_coord = dados_coord.get("nome", "N/A")
        titulo_proj = dados_proj.get("7_titulo_plano_trabalho", "N/A")
        unidade = dados_proj.get("13_unidade_executora", "N/A")

        ods_lista = dados_proj.get("19_objetivos_desenvolvimento_sustentavel", ["Não Informado"])
        ods_sigla = ods_lista[0].split(":")[0] if ods_lista else "Não Informado"

        area_lista = dados_proj.get("10_areas_conhecimento", ["Não Informada"])
        area = area_lista[0] if area_lista else "Não Informada"

        inovacao = dados_proj.get("18_possui_inovacao_tecnologica", "Não")
        patente = dados_proj.get("17_gera_patente", "Não")

        erros = [r for r in resultados if not r.passou]

        rows.append(
            {
                "ID da Proposta": id_prop,
                "Unidade": unidade,
                "Área de Conhecimento": area,
                "Coordenador": nome_coord,
                "Título do Projeto": titulo_proj,
                "Status Final": status,
                "ODS Vinculado": ods_sigla,
                "Inovação Tecnológica": inovacao,
                "Gera Patente": patente,
                "Qtd Inconformidades": len(erros),
            }
        )

        for r in erros:
            motivos_falha.append(r.regra)

    df_geral = pd.DataFrame(rows)

    if motivos_falha:
        df_stats = pd.DataFrame(motivos_falha, columns=["Regra Violada"])
        df_stats = df_stats.value_counts().reset_index(name="Frequência")
        df_stats["% do Lote"] = (df_stats["Frequência"] / len(states) * 100).round(2)
    else:
        df_stats = pd.DataFrame(
            {"Aviso": ["100% das propostas foram aprovadas. Nenhum erro encontrado."]}
        )

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_geral.to_excel(writer, sheet_name="Resumo Propostas", index=False)
        df_stats.to_excel(writer, sheet_name="Estatísticas de Erros", index=False)

        ws = writer.sheets["Resumo Propostas"]
        for i, col in enumerate(df_geral.columns):
            col_letter = chr(65 + i)
            max_len = max(df_geral[col].astype(str).map(len).max(), len(col)) + 2
            ws.column_dimensions[col_letter].width = min(max_len, 50)

    log.info("report.generated", output=output_path, total_proposals=len(states))
