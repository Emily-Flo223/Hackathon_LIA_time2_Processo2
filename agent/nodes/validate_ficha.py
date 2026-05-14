import os

import numpy as np
import pandas as pd

from agent.state import PropostaState, ValidationResult


def check_ficha_pontuacao(state: PropostaState) -> dict:
    """
    Nó de Validação — Ficha de Pontuação:
    Audita a estrutura, os cálculos, os limites e o detalhamento
    de periódicos na planilha Excel da proposta.
    """
    caminho_ficha = state.get("caminho_ficha")
    lista_motivos: list[str] = []
    lista_evidencias: list[str] = []

    try:
        _, extensao = os.path.splitext(caminho_ficha)
        if extensao.lower() not in (".xlsx", ".xls"):
            lista_motivos.append("Formato de arquivo inválido.")
            lista_evidencias.append(
                f"Extensão recebida: {extensao}. O sistema aceita apenas planilhas Excel."
            )
        else:
            try:
                df = pd.read_excel(caminho_ficha)
                arquivo_legivel = True
            except Exception as e:
                arquivo_legivel = False
                lista_motivos.append("O arquivo Excel está corrompido ou é ilegível.")
                lista_evidencias.append(f"Erro de leitura: {str(e)}")

            if arquivo_legivel:
                colunas_obrigatorias = ["Nº", "Critério", "Máx.(Qtde)", "Qtde", "Peso (valor)", "Total"]
                colunas_faltantes = [c for c in colunas_obrigatorias if c not in df.columns]

                if colunas_faltantes:
                    lista_motivos.append("A ficha de pontuação não segue o modelo padrão da UFMS.")
                    lista_evidencias.append(f"Faltam as colunas: {', '.join(colunas_faltantes)}")
                else:
                    df["Peso Num"] = pd.to_numeric(df["Peso (valor)"], errors="coerce")
                    linhas_val = df[df["Peso Num"] > 0].copy()

                    # 1. Células obrigatórias em branco
                    is_qtde_vazia = (
                        linhas_val["Qtde"].isna()
                        | (linhas_val["Qtde"].astype(str).str.strip() == "")
                        | (linhas_val["Qtde"].astype(str).str.lower() == "nan")
                    )
                    is_total_vazio = (
                        linhas_val["Total"].isna()
                        | (linhas_val["Total"].astype(str).str.strip() == "")
                        | (linhas_val["Total"].astype(str).str.lower() == "nan")
                    )
                    linhas_vazias = linhas_val[is_qtde_vazia | is_total_vazio]
                    if not linhas_vazias.empty:
                        criterios = linhas_vazias["Critério"].tolist()
                        lista_motivos.append("Células obrigatórias em branco.")
                        lista_evidencias.append(
                            f"'Qtde' ou 'Total' em branco nos itens:\n- " + "\n- ".join(str(c) for c in criterios)
                        )

                    # 2. Validação cruzada: artigos (1.1–1.8) vs periódicos listados
                    prefixos_artigos = ("1.1.", "1.2.", "1.3.", "1.4.", "1.5.", "1.6.", "1.7.", "1.8.")
                    df_artigos = linhas_val[
                        linhas_val["Critério"].astype(str).str.startswith(prefixos_artigos, na=False)
                    ]
                    total_artigos = int(pd.to_numeric(df_artigos["Qtde"], errors="coerce").fillna(0).sum())

                    idx_inicio = df[df["Critério"].astype(str).str.contains("Digite as informações dos periódicos", na=False)].index
                    idx_fim = df[df["Nº"].astype(str) == "2"].index
                    qtd_periodicos = 0

                    if not idx_inicio.empty and not idx_fim.empty:
                        sub = df.iloc[idx_inicio[0] + 1 : idx_fim[0]]
                        sub = sub[~sub["Critério"].astype(str).str.contains("Título do Periódico", na=False)]

                        for _, row in sub.iterrows():
                            titulo = str(row["Critério"]).strip() if pd.notna(row["Critério"]) else ""
                            issn = str(row["Máx.(Qtde)"]).strip() if pd.notna(row["Máx.(Qtde)"]) else ""
                            percentil = str(row["Qtde"]).strip() if pd.notna(row["Qtde"]) else ""
                            for val in (titulo, issn, percentil):
                                if val.lower() == "nan":
                                    val = ""
                            titulo = "" if titulo.lower() == "nan" else titulo
                            issn = "" if issn.lower() == "nan" else issn
                            percentil = "" if percentil.lower() == "nan" else percentil

                            if titulo or issn or percentil:
                                qtd_periodicos += 1
                                if not titulo:
                                    lista_motivos.append("Periódico listado sem título.")
                                    lista_evidencias.append(
                                        f"Linha com ISSN '{issn}' ou Percentil '{percentil}' sem Título."
                                    )
                                if not issn and not percentil:
                                    lista_motivos.append("Periódico sem ISSN e sem Percentil.")
                                    lista_evidencias.append(
                                        f"Periódico '{titulo or 'sem nome'}' incompleto."
                                    )

                    if total_artigos != qtd_periodicos:
                        lista_motivos.append("Quantidade de artigos incompatível com periódicos detalhados.")
                        lista_evidencias.append(
                            f"Artigos declarados (1.1–1.8): {total_artigos} | "
                            f"Periódicos na sub-tabela: {qtd_periodicos}."
                        )

                    # 3. Teto máximo
                    max_num = pd.to_numeric(linhas_val["Máx.(Qtde)"], errors="coerce")
                    qtd_num = pd.to_numeric(linhas_val["Qtde"], errors="coerce").fillna(0)
                    violacoes = linhas_val[(max_num.notna()) & (qtd_num > max_num)]
                    for _, row in violacoes.iterrows():
                        lista_motivos.append("Quantidade declarada excede o teto máximo do critério.")
                        lista_evidencias.append(
                            f"Critério: '{row['Critério']}' | Limite: {row['Máx.(Qtde)']} | Declarado: {row['Qtde']}"
                        )

                    # 4. Erro de cálculo linha a linha
                    subtotal_declarado = pd.to_numeric(linhas_val["Total"], errors="coerce").fillna(0)
                    subtotal_calculado = qtd_num * linhas_val["Peso Num"].fillna(0)
                    erros_calculo = linhas_val[~np.isclose(subtotal_calculado, subtotal_declarado, atol=0.01)]
                    if not erros_calculo.empty:
                        lista_motivos.append("Erro de cálculo (Qtde × Peso ≠ Total).")
                        lista_evidencias.append(
                            f"Itens com inconsistência: {', '.join(str(c) for c in erros_calculo['Critério'].tolist())}"
                        )

                    # 5. Somatório final
                    soma_real = subtotal_calculado.sum()
                    linha_total = df[
                        df["Nº"].astype(str).str.contains("TOTAL DA PONTUAÇÃO", case=False, na=False)
                        | df["Critério"].astype(str).str.contains("TOTAL DA PONTUAÇÃO", case=False, na=False)
                    ]
                    if not linha_total.empty:
                        total_raw = str(linha_total["Total"].values[0]).strip()
                        if not total_raw or total_raw.lower() == "nan":
                            lista_motivos.append("Campo TOTAL final está vazio.")
                            lista_evidencias.append("Célula do somatório total em branco.")
                        else:
                            total_declarado = pd.to_numeric(total_raw, errors="coerce")
                            if pd.isna(total_declarado) or not np.isclose(soma_real, total_declarado, atol=0.01):
                                lista_motivos.append("Inconsistência no somatório final da ficha.")
                                lista_evidencias.append(
                                    f"Soma calculada: {soma_real} | Declarado: {total_declarado}"
                                )

    except Exception as e:
        lista_motivos.append("Falha inesperada no processamento da ficha.")
        lista_evidencias.append(f"Erro técnico: {str(e)}")

    # Consolidação
    if not lista_motivos:
        passou = True
        motivo_final = "Ficha aprovada: estrutura, cálculos, limites e periódicos corretos."
        evidencia_final = "• Auditoria completa realizada com sucesso."
    else:
        passou = False
        motivo_final = f"Inconformidades encontradas na Ficha ({len(lista_motivos)} erro(s))."
        detalhes = [f"\n• Motivo: {m}\n  Evidência: {e}" for m, e in zip(lista_motivos, lista_evidencias)]
        evidencia_final = "\n".join(detalhes)

    resultado = ValidationResult(
        regra="Auditoria Completa da Ficha de Pontuação",
        passou=passou,
        motivo=motivo_final,
        evidencia=evidencia_final,
    )
    return {"resultados_validacao": state.get("resultados_validacao", []) + [resultado]}
