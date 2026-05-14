import os
import json
from typing import TypedDict, List, Dict, Any
from pydantic import BaseModel, Field
import xml.etree.ElementTree as ET
import pandas as pd
import json
import numpy as np
import xml.etree.ElementTree as ET
import re
import glob
import os
from collections import defaultdict
from llm import call_llm

# ---------------------------------------------------------
# 1. DEFINIÇÃO DOS SCHEMAS E DO ESTADO
# ---------------------------------------------------------

class ValidationResult(BaseModel):
    regra: str = Field(description="Nome da regra verificada")
    passou: bool = Field(description="True se a proposta atende ao critério, False caso contrário")
    motivo: str = Field(description="Justificativa textual para o resultado")
    evidencia: str = Field(description="Trecho do documento ou valor que embasa a decisão")

class PropostaState(TypedDict):
    diretorio_proposta: str # Caminho da pasta recebida como entrada
    id_proposta: str
    dados_formulario: Dict[str, Any]
    dados_lattes: str 
    caminho_ficha: str 
    resultados_validacao: List[ValidationResult]
    status_enquadramento: str 
    rascunho_email: str

# ---------------------------------------------------------
# 2. IMPLEMENTAÇÃO DO NÓ DE INGESTÃO
# ---------------------------------------------------------

'''
artigos 1.1 a 1.8 se preenchidos precisam ter o título do periodico preenchido e ISSN ou Percentil preenchidos
caso o mas(qtde) tenha teto, precisa validar se a coluna qtde respeita o teto, ou seja, se a qtde é menor ou igual ao teto.
'''

def load_proposal(state: PropostaState) -> dict:
    """
    Lê os arquivos do diretório da proposta e extrai os dados brutos 
    para popular o estado inicial do LangGraph.
    """
    diretorio = state.get("diretorio_proposta")
    
    if not diretorio or not os.path.exists(diretorio):
        raise ValueError(f"Diretório da proposta não encontrado: {diretorio}")

    # A. Carregar Formulário (JSON)
    caminho_form = os.path.join(diretorio, "formulario.json")
    try:
        with open(caminho_form, "r", encoding="utf-8") as f:
            dados_formulario = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Arquivo formulario.json não encontrado em {diretorio}")

   # B. Carregar XML do Lattes (como string) - ATUALIZADO
    caminho_lattes = os.path.join(diretorio, "lattes.xml")
    try:
        # A plataforma Lattes utiliza o padrão ISO-8859-1 nativamente
        with open(caminho_lattes, "r", encoding="ISO-8859-1") as f:
            dados_lattes = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Arquivo lattes.xml não encontrado em {diretorio}")

    # C. Registrar o caminho da Ficha de Pontuação (Excel)
    # Não vamos abrir o Excel neste nó para não sobrecarregar a memória do estado; 
    # o nó validador específico fará a leitura usando este caminho.
    caminho_ficha = os.path.join(diretorio, "ficha_pontuacao.xlsx")
    if not os.path.exists(caminho_ficha):
        raise FileNotFoundError(f"Arquivo ficha_pontuacao.xlsx não encontrado em {diretorio}")

    # No LangGraph, um nó retorna apenas um dicionário com as chaves que deseja atualizar no estado global.
    return {
        "id_proposta": dados_formulario.get("id_proposta", "DESCONHECIDO"),
        "dados_formulario": dados_formulario,
        "dados_lattes": dados_lattes,
        "caminho_ficha": caminho_ficha,
        # Inicializa a lista de validações vazia se não existir
        "resultados_validacao": state.get("resultados_validacao", [])
    }

# ---------------------------------------------------------
# 3. IMPLEMENTAÇÃO DO NÓ DE VALIDAÇÃO (TITULAÇÃO) - ATUALIZADO
# ---------------------------------------------------------

def check_titulacao(state: PropostaState) -> dict:
    """
    Verifica se o proponente possui o título de Doutor concluído navegando na
    árvore real do Currículo Lattes.
    """
    xml_string = state.get("dados_lattes", "")
    
    passou = False
    motivo = "Não foi possível encontrar a titulação de Doutorado."
    evidencia = "Ausência da tag <DOUTORADO> na árvore de formação."
    
    try:
        # Limpeza de segurança: Remove a declaração <?xml ...?> do topo da string. 
        # O ET.fromstring do Python costuma falhar se a string estiver declarada 
        # como ISO-8859-1 mas for passada como string Unicode nativa.
        xml_string_clean = re.sub(r'<\?xml.*?\?>', '', xml_string).strip()
        
        root = ET.fromstring(xml_string_clean)
        
        # Busca o caminho exato dentro da nova estrutura do Lattes
        # O .*? significa que pode estar em qualquer lugar, mas respeitando a hierarquia
        formacao = root.find(".//FORMACAO-ACADEMICA-TITULACAO")
        
        if formacao is not None:
            doutorado = formacao.find("DOUTORADO")
            
            if doutorado is not None:
                status = doutorado.get("STATUS-DO-CURSO", doutorado.get("STATUS", "")).upper()
                if status == "CONCLUIDO":
                    passou = True
                    motivo = "Proponente possui titulação de Doutor concluída."
                    
                    # Tenta pegar a instituição para dar uma evidência mais rica (se existir)
                    tese_doutorado = doutorado.get("NOME-CURSO", "'Título da tese não informado'")
                    instituicao = doutorado.get("NOME-INSTITUICAO", "Instituição não informada")
                    ano = doutorado.get("ANO-DE-CONCLUSAO", "Ano não informado")
                    evidencia = f"Título da tese: {tese_doutorado}. | Instituição: {instituicao}. | Conclusão: {ano}."
                else:
                    motivo = f"Proponente possui registro de Doutorado, mas o status é: {status}."
                    evidencia = f"Tag Doutorado encontrada com status '{status}' (esperado: 'CONCLUIDO')."
            else:
                # Se não tem doutorado, checa se tem mestrado para a justificativa
                mestrado = formacao.find("MESTRADO")
                if mestrado is not None:
                    tese_mestrado = mestrado.get("NOME-CURSO", "Título da tese não informado")
                    instituicao = mestrado.get("NOME-INSTITUICAO", "Instituição não informada")
                    ano = mestrado.get("ANO-DE-CONCLUSAO", "Ano não informado")
                    motivo = "Proponente possui apenas nível de Mestrado ou inferior."
                    evidencia = f"Apenas tag <MESTRADO> localizada na Formação Acadêmica. \nTítulo da tese de mestrado: {tese_mestrado} | Instituição: {instituicao} | Conclusão: {ano}."
        else:
            motivo = "O bloco de Formação Acadêmica não foi encontrado no currículo."
            evidencia = "Tag <FORMACAO-ACADEMICA-TITULACAO> ausente."
                
    except ET.ParseError as e:
        motivo = "Erro crítico ao processar o arquivo XML do Lattes."
        evidencia = f"O arquivo está corrompido ou mal formatado. Erro: {str(e)}"

    resultado = ValidationResult(
        regra="Verificação de Titulação",
        passou=passou,
        motivo=motivo,
        evidencia=evidencia
    )
    
    resultados_atuais = state.get("resultados_validacao", [])
    return {"resultados_validacao": resultados_atuais + [resultado]}

# ---------------------------------------------------------
# 4. IMPLEMENTAÇÃO DO NÓ DE VALIDAÇÃO (FICHA DE PONTUAÇÃO)
# ---------------------------------------------------------

def check_ficha_pontuacao(state: PropostaState) -> dict:
    caminho_ficha = state.get("caminho_ficha")
    lista_motivos = []
    lista_evidencias = []
    
    try:
        _, extensao = os.path.splitext(caminho_ficha)
        if extensao.lower() not in ['.xlsx', '.xls']:
            lista_motivos.append("Formato de arquivo inválido.")
            lista_evidencias.append(f"Extensão recebida: {extensao}. O sistema aceita apenas planilhas Excel.")
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
                colunas_faltantes = [col for col in colunas_obrigatorias if col not in df.columns]
                
                if colunas_faltantes:
                    lista_motivos.append("A ficha de pontuação não segue o modelo padrão da UFMS.")
                    lista_evidencias.append(f"Faltam as colunas exatas: {', '.join(colunas_faltantes)}")
                else:
                    # Filtra apenas linhas com pesos numéricos para a validação matemática
                    df['Peso Num'] = pd.to_numeric(df['Peso (valor)'], errors='coerce')
                    linhas_com_pontuacao = df[df['Peso Num'] > 0].copy()
                    
                    # --- 1. VALIDAÇÃO DE CAMPOS VAZIOS (BRANCOS / NULOS) ---
                    # Essa verificação agora pega strings vazias "", "   ", None e NaN
                    is_qtde_empty = linhas_com_pontuacao['Qtde'].isna() | (linhas_com_pontuacao['Qtde'].astype(str).str.strip() == "") | (linhas_com_pontuacao['Qtde'].astype(str).str.lower() == "nan")
                    is_total_empty = linhas_com_pontuacao['Total'].isna() | (linhas_com_pontuacao['Total'].astype(str).str.strip() == "") | (linhas_com_pontuacao['Total'].astype(str).str.lower() == "nan")
                    
                    linhas_vazias = linhas_com_pontuacao[is_qtde_empty | is_total_empty]
                    
                    if not linhas_vazias.empty:
                        criterios_vazios = linhas_vazias['Critério'].tolist()
                        lista_motivos.append("Existem células obrigatórias apagadas ou deixadas em branco.")
                        lista_evidencias.append(f"As colunas 'Qtde' ou 'Total' estão em branco nos seguintes itens: \n- {'\n- '.join(str(c) for c in criterios_vazios)}")


                    # --- 2. VALIDAÇÃO CRUZADA: ARTIGOS (1.1 a 1.8) vs PERIÓDICOS ---
                    prefixos_artigos = ("1.1.", "1.2.", "1.3.", "1.4.", "1.5.", "1.6.", "1.7.", "1.8.")
                    df_artigos = linhas_com_pontuacao[linhas_com_pontuacao['Critério'].astype(str).str.startswith(prefixos_artigos, na=False)]
                    total_artigos_declarados = int(pd.to_numeric(df_artigos['Qtde'], errors='coerce').fillna(0).sum())

                    idx_inicio = df[df['Critério'].astype(str).str.contains("Digite as informações dos periódicos", na=False)].index
                    idx_fim = df[df['Nº'].astype(str) == "2"].index
                    
                    qtd_periodicos_listados = 0

                    if not idx_inicio.empty and not idx_fim.empty:
                        sub_tabela_raw = df.iloc[idx_inicio[0]+1 : idx_fim[0]]
                        sub_tabela = sub_tabela_raw[~sub_tabela_raw['Critério'].astype(str).str.contains("Título do Periódico", na=False)]

                        for idx, row in sub_tabela.iterrows():
                            titulo = str(row['Critério']).strip() if pd.notna(row['Critério']) else ""
                            issn = str(row['Máx.(Qtde)']).strip() if pd.notna(row['Máx.(Qtde)']) else ""
                            percentil = str(row['Qtde']).strip() if pd.notna(row['Qtde']) else ""
                            
                            # Limpeza de "nan" que o Pandas cria ao converter float nulo para string
                            if titulo.lower() == "nan": titulo = ""
                            if issn.lower() == "nan": issn = ""
                            if percentil.lower() == "nan": percentil = ""

                            if titulo or issn or percentil:
                                qtd_periodicos_listados += 1

                                if not titulo:
                                    lista_motivos.append("Na tabela de periódicos, uma linha foi preenchida sem o Título do Periódico.")
                                    lista_evidencias.append(f"Linha identificada com ISSN '{issn}' ou Percentil '{percentil}', mas sem Título.")

                                if not issn and not percentil:
                                    nome_exibicao = titulo if titulo else "Periódico sem nome"
                                    lista_motivos.append("Na tabela de periódicos, um periódico foi listado sem ISSN e sem Percentil.")
                                    lista_evidencias.append(f"O periódico '{nome_exibicao}' está incompleto (obrigatório ISSN para Sucupira ou Percentil para Scopus).")

                    if total_artigos_declarados != qtd_periodicos_listados:
                        lista_motivos.append("A quantidade de artigos pontuada não é compatível com o preenchimento da tabela de periódicos.")
                        lista_evidencias.append(f"Soma declarada nos itens 1.1 a 1.8: {total_artigos_declarados} artigo(s). | Quantidade de periódicos detalhados na sub-tabela: {qtd_periodicos_listados}.")

                    # --- 3. VALIDAÇÃO DE TETO MÁXIMO ---
                    max_qtd_num = pd.to_numeric(linhas_com_pontuacao['Máx.(Qtde)'], errors='coerce')
                    qtd_num = pd.to_numeric(linhas_com_pontuacao['Qtde'], errors='coerce').fillna(0)
                    violacoes_teto = linhas_com_pontuacao[(max_qtd_num.notna()) & (qtd_num > max_qtd_num)]
                    
                    for idx, row in violacoes_teto.iterrows():
                        lista_motivos.append("Quantidade declarada excede o limite máximo (Teto) do critério.")
                        lista_evidencias.append(f"Critério: '{row['Critério']}' | Limite: {row['Máx.(Qtde)']} | Declarado: {row['Qtde']}")

                    # --- 4. VALIDAÇÃO MATEMÁTICA LINHA A LINHA ---
                    subtotal_declarado = pd.to_numeric(linhas_com_pontuacao['Total'], errors='coerce').fillna(0)
                    subtotal_calculado = qtd_num * linhas_com_pontuacao['Peso Num'].fillna(0)
                    linhas_com_erro = linhas_com_pontuacao[~np.isclose(subtotal_calculado, subtotal_declarado, atol=0.01)]
                    
                    if not linhas_com_erro.empty:
                        criterios_errados = linhas_com_erro['Critério'].tolist()
                        lista_motivos.append("Erro de cálculo na multiplicação (Qtde x Peso != Total).")
                        lista_evidencias.append(f"Inconsistência nos itens: {', '.join(str(c) for c in criterios_errados)}")
                    
                    # --- 5. VALIDAÇÃO DO SOMATÓRIO FINAL ---
                    soma_real_total = subtotal_calculado.sum()
                    linha_total = df[df['Nº'].astype(str).str.contains("TOTAL DA PONTUAÇÃO", case=False, na=False) | 
                                     df['Critério'].astype(str).str.contains("TOTAL DA PONTUAÇÃO", case=False, na=False)]
                    
                    if not linha_total.empty:
                        total_declarado_raw = str(linha_total['Total'].values[0]).strip()
                        
                        if not total_declarado_raw or total_declarado_raw.lower() == "nan":
                            lista_motivos.append("O campo de TOTAL final está vazio ou foi apagado.")
                            lista_evidencias.append("A célula do somatório total geral está em branco na planilha.")
                        else:
                            total_declarado = pd.to_numeric(total_declarado_raw, errors='coerce')
                            if pd.isna(total_declarado) or not np.isclose(soma_real_total, total_declarado, atol=0.01):
                                lista_motivos.append("Inconsistência no somatório final da ficha.")
                                lista_evidencias.append(f"Soma calculada: {soma_real_total} | Declarado: {total_declarado}")

    except Exception as e:
        lista_motivos.append("Falha inesperada no processamento da ficha.")
        lista_evidencias.append(f"Erro técnico: {str(e)}")

    # CONSOLIDAÇÃO
    if not lista_motivos:
        passou = True
        motivo_final = "Ficha aprovada: estrutura, cálculos, limites e detalhamento de periódicos corretos."
        evidencia_final = "• Auditoria completa realizada com sucesso."
    else:
        passou = False
        motivo_final = f"Inconformidades encontradas na Ficha ({len(lista_motivos)} erro(s))."
        detalhes = [f"\n• Motivo: {m}\n  Evidência: {e}" for m, e in zip(lista_motivos, lista_evidencias)]
        evidencia_final = "\n".join(detalhes)

    return {"resultados_validacao": state.get("resultados_validacao", []) + [ValidationResult(regra="Auditoria Completa da Ficha de Pontuação", passou=passou, motivo=motivo_final, evidencia=evidencia_final)]}

# ---------------------------------------------------------
# 5. IMPLEMENTAÇÃO DO NÓ DE VALIDAÇÃO (LIMITE DE PROPOSTAS) - COM TÍTULOS
# ---------------------------------------------------------

def check_limit_proposals(state: PropostaState) -> dict:
    """
    Verifica se o proponente respeita o limite de submissões cruzando o CPF atual 
    com todas as propostas no diretório. Agora também lista os títulos encontrados.
    """

    # Lendo o CPF da nova estrutura (49 perguntas):
    cpf_atual = state.get("dados_formulario", {}).get("dados_coordenador", {}).get("6_cpf")

    xml_string = state.get("dados_lattes", "")
    diretorio_proposta = state.get("diretorio_proposta", "")
    
    passou = False
    motivo = "Erro ao verificar limites."
    evidencia = "N/A"
    
    if not cpf_atual or not diretorio_proposta:
        return {
            "resultados_validacao": state.get("resultados_validacao", []) + [
                ValidationResult(
                    regra="Limite de Propostas", 
                    passou=False, 
                    motivo="CPF ou diretório base não encontrados no estado.", 
                    evidencia="Falha de ingestão de dados."
                )
            ]
        }

    try:
        # 1. Verifica no Lattes se o proponente tem Bolsa Produtividade (PQ)
        is_pq = False
        try:
            # Limpeza de segurança para evitar erro de encoding do XML
            xml_string_clean = re.sub(r'<\?xml.*?\?>', '', xml_string).strip()
            root = ET.fromstring(xml_string_clean)
            
            vinculos = root.findall(".//VINCULOS")
            for v in vinculos:
                if v.get("TIPO-DE-VINCULO") == "Bolsista de Produtividade" and v.get("ORGAO") == "CNPq":
                    is_pq = True
                    break
        except ET.ParseError:
            pass 

        # 2. Define o limite com base no status PQ
        limite_permitido = 3 if is_pq else 2
        
        # 3. Conta e coleta as propostas desse CPF no lote atual
        dir_base = os.path.dirname(diretorio_proposta)
        total_submissoes = 0
        titulos_encontrados = [] # Nova lista para guardar os títulos
        
        for pasta in os.listdir(dir_base):
            caminho_form = os.path.join(dir_base, pasta, "formulario.json")
            if os.path.isfile(caminho_form):
                try:
                    with open(caminho_form, "r", encoding="utf-8") as f:
                        form_dados = json.load(f)
                        
                        # ATUALIZADO: Busca o CPF dentro de dados_coordenador -> 6_cpf
                        if form_dados.get("dados_coordenador", {}).get("6_cpf") == cpf_atual:
                            total_submissoes += 1
                            
                            # ATUALIZADO: Extrai o título de dados_projeto -> 7_titulo_plano_trabalho
                            titulo = form_dados.get("dados_projeto", {}).get("7_titulo_plano_trabalho", "Título não informado")
                            titulos_encontrados.append(f"  - {titulo} (ID: {form_dados.get('id_proposta', 'N/A')})")
                except Exception:
                    continue 

        # 4. Formata a lista de títulos para exibição
        lista_titulos_str = "\n".join(titulos_encontrados)

        # 5. Avalia a regra e monta a evidência rica
        if total_submissoes <= limite_permitido:
            passou = True
            motivo = f"O proponente respeitou o limite de propostas (Máximo permitido: {limite_permitido})."
            evidencia = (f"Status PQ: {'Sim' if is_pq else 'Não'}.\n"
                         f"Projetos encontrados no sistema ({total_submissoes}):\n{lista_titulos_str}")
        else:
            passou = False
            motivo = f"O proponente excedeu o limite de propostas submetidas."
            evidencia = (f"Status PQ: {'Sim' if is_pq else 'Não'} (Limite: {limite_permitido}).\n"
                         f"Projetos encontrados no sistema ({total_submissoes}):\n{lista_titulos_str}")

    except Exception as e:
        motivo = "Falha técnica ao varrer propostas e contar limites."
        evidencia = str(e)

    resultado = ValidationResult(
        regra="Limite de Propostas",
        passou=passou,
        motivo=motivo,
        evidencia=evidencia
    )
    
    resultados_atuais = state.get("resultados_validacao", [])
    return {"resultados_validacao": resultados_atuais + [resultado]}

# ---------------------------------------------------------
# 6. IMPLEMENTAÇÃO DO NÓ DE VALIDAÇÃO (BASE INTERNA PROPP)
# ---------------------------------------------------------

def check_pendencias_e_projetos(state: PropostaState) -> dict:
    """
    Verifica contra a base interna sintética da PROPP se o proponente:
    1. Não possui pendências impeditivas.
    2. Possui projeto de pesquisa ativo.
    """
    cpf_atual = state.get("dados_formulario", {}).get("dados_coordenador", {}).get("6_cpf")
    diretorio_proposta = state.get("diretorio_proposta", "")
    
    lista_motivos = []
    lista_evidencias = []
    projetos_ativos_str = "" 
    
    if not cpf_atual or not diretorio_proposta:
        return {"resultados_validacao": state.get("resultados_validacao", []) + [ValidationResult(regra="Histórico/Pendências do Proponente", passou=False, motivo="Falha ao identificar CPF.", evidencia="Falha")]}

    try:
        dir_base = os.path.dirname(diretorio_proposta)
        caminho_base = os.path.join(dir_base, "internal_database.json")
        
        if not os.path.exists(caminho_base):
            raise FileNotFoundError(f"Arquivo {caminho_base} não encontrado.")
            
        with open(caminho_base, "r", encoding="utf-8") as f:
            base_interna = json.load(f)
            
        registro_proponente = next((item for item in base_interna if item["cpf"] == cpf_atual), None)
        
        if not registro_proponente:
            lista_motivos.append("Proponente não localizado na base de dados da PROPP.")
            lista_evidencias.append(f"O CPF {cpf_atual} não retornou nenhum histórico no sistema interno.")
        else:
            # Regra A: Verifica Pendências filtrando apenas as Impeditivas
            pendencias = registro_proponente.get("pendencias_propp", [])
            pendencias_impeditivas = [p for p in pendencias if p.get("impeditiva") is True]
            
            if pendencias_impeditivas: 
                lista_motivos.append("O proponente possui pendências institucionais impeditivas ativas com a PROPP.")
                
                pend_str = []
                for p in pendencias_impeditivas:
                    pend_str.append(f"[{p.get('id_pendencia', 'N/A')}] {p.get('descricao', 'Pendência não detalhada')} (Vencimento: {p.get('data_vencimento', 'N/A')})")
                    
                pendencias_formatadas = "\n    - ".join(pend_str)
                lista_evidencias.append(f"Pendências localizadas ({len(pendencias_impeditivas)}):\n    - {pendencias_formatadas}")
                
            # Regra B: Verifica Projetos em Andamento
            projetos = registro_proponente.get("projetos_em_andamento", [])
            if not projetos: 
                lista_motivos.append("O proponente não está vinculado a nenhum projeto de pesquisa em andamento.")
                lista_evidencias.append("A lista de projetos em andamento retornou vazia na base interna do SIGProj/PROPP.")
            else:
                proj_str = []
                for p in projetos:
                    proj_str.append(f"[{p.get('id_sigproj', 'ID N/A')}] {p.get('titulo', 'Projeto')} ({p.get('papel', 'Pesquisador')}) - Vigência: {p.get('vigencia_fim', 'N/A')}")
                
                projetos_formatados = "\n  - ".join(proj_str)
                projetos_ativos_str = f"Projetos ativos vinculados ao pesquisador ({len(projetos)}):\n  - {projetos_formatados}"

    except Exception as e:
        lista_motivos.append("Falha técnica ao consultar a base interna da PROPP.")
        lista_evidencias.append(str(e))

    if len(lista_motivos) == 0:
        passou = True
        motivo_final = "Proponente regularizado: sem pendências e com projeto em andamento."
        evidencia_final = f"Consulta à base interna finalizada com status regular.\n{projetos_ativos_str}"
    else:
        passou = False
        motivo_final = f"Inconsistência no histórico do proponente: {len(lista_motivos)} bloqueio(s) encontrado(s)."
        erros_detalhados = []
        for m, e in zip(lista_motivos, lista_evidencias):
            erros_detalhados.append(f"\n• Motivo: {m}\n  Evidência: {e}")
        evidencia_final = "\n\n".join(erros_detalhados)

    resultado = ValidationResult(regra="Histórico/Pendências do Proponente", passou=passou, motivo=motivo_final, evidencia=evidencia_final)
    return {"resultados_validacao": state.get("resultados_validacao", []) + [resultado]}

# ---------------------------------------------------------
# 7. IMPLEMENTAÇÃO DO NÓ DECISOR (FAN-IN)
# ---------------------------------------------------------
def decide(state: PropostaState) -> dict:
    """
    Nó agregador que avalia todos os resultados das validações.
    Se todos passaram -> ENQUADRADA.
    Se algum falhou -> NÃO ENQUADRADA (com relatório completo de motivos e evidências).
    """
    resultados = state.get("resultados_validacao", [])
    id_prop = state.get("id_proposta", "Desconhecido")
    #nome_coord = state.get("dados_formulario", {}).get("coordenador", {}).get("nome", "Não informado")
    nome_coord = state.get("dados_formulario", {}).get("dados_coordenador", {}).get("nome", "N/A")
    
    # Prevenção contra falhas no fluxo
    if not resultados:
        return {"status_enquadramento": "ERRO_FLUXO: Nenhuma validação executada."}
        
    # Filtra apenas as validações que falharam (passou == False)
    falhas = [res for res in resultados if not res.passou]
    
    # Lógica de Decisão e Formatação da Saída
    if len(falhas) == 0:
        status_final = "ENQUADRADA"
        
        print(f"\n{'='*70}")
        print(f"✅ DECISÃO FINAL: {id_prop} -> {status_final}")
        print(f"Coordenador(a): {nome_coord}")
        print(f"{'-'*70}")
        print("Todas as regras de enquadramento foram cumpridas com sucesso.")
        print(f"{'='*70}\n")
        
    else:
        status_final = "NÃO ENQUADRADA"
        
        print(f"\n{'='*70}")
        print(f"🛑 DECISÃO FINAL: {id_prop} -> {status_final}")
        print(f"Coordenador(a): {nome_coord}")
        print(f"{'-'*70}")
        print(f"A proposta foi rejeitada devido a {len(falhas)} inconformidade(s) encontrada(s):\n")
        
        for i, falha in enumerate(falhas, 1):
            print(f"{i}. REGRA VIOLADA: {falha.regra}")
            # Substitui as quebras de linha para manter a indentação bonita no terminal
            motivo_formatado = str(falha.motivo).replace("\n", "\n   ")
            evidencia_formatada = str(falha.evidencia).replace("\n", "\n   ")
            
            print(f"   Motivo: {motivo_formatado}")
            print(f"   Evidência: {evidencia_formatada}")
            print("-" * 40)
            
        print(f"{'='*70}\n")

    # Atualiza o estado com o status. O nó draft_email usará esse status e a 
    # própria lista de resultados_validacao para instruir o LLM.
    return {
        "status_enquadramento": status_final
    }

# ---------------------------------------------------------
# 8. IMPLEMENTAÇÃO DO NÓ DE E-MAIL CONSOLIDADO (LLM via OpenRouter)
# ---------------------------------------------------------

def gerar_email_unico_pesquisador(lista_propostas, diretorio_base):
    # Pega os dados do coordenador da primeira proposta (é o mesmo para todas)
    primeira = lista_propostas[0]
    nome_coord = primeira.get("dados_formulario", {}).get("dados_coordenador", {}).get("nome", "Prezado(a) Coordenador(a)")
    
    # Monta o contexto com TODOS os projetos submetidos por essa pessoa
    contexto_projetos = ""
    for i, prop in enumerate(lista_propostas, 1):
        #titulo = prop.get("dados_formulario", {}).get("dados_projeto", {}).get("7_titulo_plano_trabalho", "Projeto Não Identificado")
        dados_proj = prop.get("dados_formulario", {}).get("dados_projeto", {})

        titulo = dados_proj.get(
            "7_titulo_plano_trabalho",
            "Projeto Não Identificado"
        )

        id_proposta = dados_proj.get(
            "id_proposta",
            prop.get("id_proposta", f"PROPOSTA_{i:03d}")
        )
        modalidade = prop.get("dados_formulario", {}).get("dados_projeto", {}).get("9_programa", "IC&T")
        status = prop.get("status_enquadramento", "ERRO")
        resultados = prop.get("resultados_validacao", [])
        
        falhas = [res for res in resultados if not res.passou]
        
        contexto_projetos += f"\nPROJETO {i}:\n"
        contexto_projetos += f"- ID: {id_proposta}\n"
        contexto_projetos += f"- Título: <u>\"{titulo}\"</u>\n"
        contexto_projetos += f"- Modalidade: {modalidade}\n"
        contexto_projetos += f"- Status Final: {status}\n"
        
        if status == "ENQUADRADA":
            contexto_projetos += "- Inconformidades: Nenhuma. A proposta atendeu a todos os requisitos formais do edital.\n"
        else:
            contexto_projetos += "- Inconformidades Encontradas:\n"
            for f in falhas:
                contexto_projetos += f"  Regra Violada: {f.regra}\n  Motivo: {f.motivo}\n  Evidência: {f.evidencia}\n"

    system_prompt = """Você é um assistente administrativo da Pró-Reitoria de Pesquisa e Pós-Graduação (PROPP) da UFMS.
Sua tarefa é redigir um ÚNICO e-mail formal e institucional para um pesquisador, comunicando o resultado da Análise de Enquadramento de TODOS os projetos submetidos por ele. O e-mail deve suportar formatação em HTML.

DIRETRIZES DE ESTILO E ESTRUTURA:
1. Tom: Institucional, cortês, respeitoso e estritamente profissional.
2. Assunto: Faça uma linha de assunto clara e direta, por exemplo: "Resultado da Análise de Enquadramento - Bolsas IC&T UFMS".
3. Saudação: Cumprimente o pesquisador nominalmente.
4. Introdução: Agradeça pela submissão e informe que o e-mail contém o resultado da análise de enquadramento de todos os projetos submetidos por ele (informe quantos foram <u>enquadrados</u> e quantos foram <u>não enquadrados</u>, mas sem aparecer no texto caracteres tipo <strong>).
5. Estrutura de Projetos: Como o pesquisador pode ter múltiplos projetos, liste e separe claramente quais projetos foram ID_projeto <strong style="color: green;">ENQUADRADOS</strong> e quais foram ID_projeto <strong style="color: red;">NÃO ENQUADRADOS</strong>. Faça o mesmo caso tenha apenas 1 projeto
    - TODOS os projetos DEVEM ser identificados obrigatoriamente no formato: "ID_DA_PROPOSTA - TÍTULO DO PROJETO"
    - Isso é obrigatório mesmo quando existir apenas 1 projeto.
    - Nunca omita o ID da proposta.
    - Exemplo correto: "PROPOSTA_003 - Mineração de Dados em Ambientes Educacionais - Estudo de Caso 003"
6. Para os projetos "ENQUADRADADOS": Parabenize e informe que o projeto seguirá para a próxima etapa (Avaliação de Mérito). Destaque a decisão usando a tag HTML: <strong style="color: green;">ENQUADRADA</strong>.
7. Para os projetos "NÃO ENQUADRADOS": Lamente a recusa e faça uma lista com marcadores citando cada regra violada do respectivo projeto. Destaque a decisão usando a tag HTML: <strong style="color: red;">NÃO ENQUADRADA</strong>.
   - OBRIGATÓRIO: Use sempre o caractere '📌' para motivos e '🔎' para Evidências para as listas e tópicos (NUNCA use asteriscos '*').
   - OBRIGATÓRIO: NUNCA use formatação Markdown com duplo asterisco (**). Para destacar o título do projeto ou outras informações, use a tag HTML de sublinhado <u>.
   - Explique o motivo de forma clara e apresente a evidência embaixo extraída da auditoria (📌Motivo e 🔎Evidência). Dê um espaço entre cada conjunto de motivo com evidência.
   - Se a recusa for por limites de projetos ou pendências, cite claramente os "IDs" e as "Datas de Vencimento".
   - quando tiver justificativa/motivo que tenha 'itens' ou algo similar, separá-los com '-' com quebra de linha entre eles com espaçamento de 1,5 à direita (exemplo: "📌Motivo: O proponente excedeu o limite de propostas submetidas. \n   - Projeto 1: Título (ID) \n   - Projeto 2: Título (ID)"), mas sem parecer "<br>" no texto.
8. Despedida: Assine institucionalmente como "Equipe SEICT/DIPEQ/PROPP - UFMS".
9. Retorne APENAS o corpo do e-mail, sem comentários adicionais."""

    user_prompt = f"""DADOS DA SUBMISSÃO:🏷️
- Pesquisador: {nome_coord}

RESUMO DE TODOS OS PROJETOS ENVIADOS E RESULTADOS DA AUDITORIA:
{contexto_projetos}

Por favor, redija o e-mail consolidado agora."""

    try:
        print(f"Enviando dados para o OpenRouter (LLM) - Coordenador: {nome_coord}...")
        rascunho_final = call_llm(system_prompt, user_prompt, temperature=0.1)
    except Exception as e:
        rascunho_final = f"Erro de comunicação com a API: {str(e)}"

    # TRUQUE VISUAL PARA O TERMINAL: Converte tags HTML para ANSI
    email_terminal = rascunho_final.replace('<strong style="color: red;">', '\033[91m\033[1m')
    email_terminal = email_terminal.replace('<strong style="color: green;">', '\033[92m\033[1m')
    email_terminal = email_terminal.replace('</strong>', '\033[0m')
    email_terminal = email_terminal.replace('<u>', '\033[4m')
    email_terminal = email_terminal.replace('</u>', '\033[0m')

    print(f"\n{'='*70}")
    print(f"✉️  E-MAIL CONSOLIDADO - {nome_coord.upper()}:")
    print(f"{'-'*70}")
    print(email_terminal)  
    print(f"{'='*70}\n")

    # ---------------------------------------------------------
    # SALVANDO OS E-MAILS CONSOLIDADOS
    # ---------------------------------------------------------
    nome_arquivo = nome_coord.replace(" ", "_").upper()
    
    # Salva em TXT mantendo as tags HTML intactas para o Streamlit ler as cores
    caminho_txt = os.path.join(diretorio_base, f"EMAIL_{nome_arquivo}.txt")
    with open(caminho_txt, "w", encoding="utf-8") as f:
        f.write(rascunho_final)

# ---------------------------------------------------------
# 9. IMPLEMENTAÇÃO DO NÓ EMIT E CONSOLIDAÇÃO (GRAFO)
# ---------------------------------------------------------

def emit(state: PropostaState) -> dict:
    diretorio = state.get("diretorio_proposta")
    id_prop = state.get("id_proposta")
    status = state.get("status_enquadramento")
    resultados = state.get("resultados_validacao", [])
    
    nome_coord = state.get("dados_formulario", {}).get("dados_coordenador", {}).get("nome", "N/A")
    titulo_proj = state.get("dados_formulario", {}).get("dados_projeto", {}).get("7_titulo_plano_trabalho", "N/A")
    unidade = state.get("dados_formulario", {}).get("dados_projeto", {}).get("13_unidade_executora", "N/A")
    modalidade = state.get("dados_formulario", {}).get("dados_projeto", {}).get("9_programa", "IC&T")
    
    # =======================================================================
    # NOVO: GERAÇÃO DO E-MAIL INDIVIDUAL DA PROPOSTA VIA LLM
    # =======================================================================
    falhas = [res for res in resultados if not res.passou]
    
    if status == "ENQUADRADA":
        contexto_falhas = "Nenhuma. A proposta atendeu a todos os requisitos formais do edital."
    else:
        textos_falhas = []
        for i, f in enumerate(falhas, 1):
            textos_falhas.append(f"Regra {i}: {f.regra}\nMotivo: {f.motivo}\nEvidência: {f.evidencia}")
        contexto_falhas = "\n\n".join(textos_falhas)

    sys_prompt_ind = """Você é um assistente administrativo da PROPP/UFMS.
Sua tarefa é redigir um e-mail comunicando o resultado do enquadramento de UMA proposta específica.
DIRETRIZES DE ESTILO E ESTRUTURA:
1. Tom: Institucional, cortês, respeitoso e estritamente profissional.
2. Assunto: Faça uma linha de assunto clara e direta, por exemplo: "Resultado da Análise de Enquadramento - Bolsas IC&T UFMS".
3. Saudação: Cumprimente o pesquisador nominalmente.
4. Introdução: Agradeça pela submissão e informe que o e-mail contém o resultado da análise de enquadramento da proposta submetida.
5. Estrutura da Proposta:
    - A proposta DEVE ser identificada obrigatoriamente no formato:
    "ID_DA_PROPOSTA - TÍTULO DO PROJETO"
    - Nunca omita o ID da proposta.
    - O título deve aparecer sublinhado usando <u>.
    - Exemplo correto:
    PROPOSTA_040 - <u>"Mineração de Dados em Ambientes Educacionais"</u>
6. Para os projetos "ENQUADRADADOS": Parabenize e informe que o projeto seguirá para a próxima etapa (Avaliação de Mérito). Destaque a decisão usando a tag HTML: <strong style="color: green;">ENQUADRADA</strong>.
7. Para os projetos "NÃO ENQUADRADOS": Lamente a recusa e faça uma lista com marcadores citando cada regra violada do respectivo projeto. Destaque a decisão usando a tag HTML: <strong style="color: red;">NÃO ENQUADRADA</strong>.
   - OBRIGATÓRIO: Use sempre o caractere '📌' para motivos e '🔎' para Evidências para as listas e tópicos (NUNCA use asteriscos '*').
   - OBRIGATÓRIO: NUNCA use formatação Markdown com duplo asterisco (**). Para destacar o título do projeto ou outras informações, use a tag HTML de sublinhado <u>.
   - Explique o motivo de forma clara e apresente a evidência embaixo extraída da auditoria (📌Motivo e 🔎Evidência). Dê um espaço entre cada conjunto de motivo com evidência.
   - Se a recusa for por limites de projetos ou pendências, cite claramente os "IDs" e as "Datas de Vencimento".
   - quando tiver justificativa/motivo que tenha 'itens' ou algo similar, separá-los com '-' com quebra de linha entre eles com espaçamento de 1,5 à direita (exemplo: "📌Motivo: O proponente excedeu o limite de propostas submetidas. \n   - Projeto 1: Título (ID) \n   - Projeto 2: Título (ID)"), mas sem parecer "<br>" no texto.
8. Despedida: Assine institucionalmente como "Equipe SEICT/DIPEQ/PROPP - UFMS".
9. Retorne APENAS o corpo do e-mail, sem comentários adicionais."""

    user_prompt_ind = f"""DADOS:
- Pesquisador: {nome_coord}
- ID da Proposta: {id_prop}
- Título: <u>"{titulo_proj}"</u>
- Modalidade: {modalidade}
- Status: {status}

INCONFORMIDADES:
{contexto_falhas}

Redija o e-mail individual agora."""

    try:
        email_individual = call_llm(sys_prompt_ind, user_prompt_ind, temperature=0.1)
    except Exception as e:
        email_individual = f"Erro de comunicação com a API (E-mail Individual): {str(e)}"
    # =======================================================================

    # 1. PARECER TÉCNICO EM JSON
    caminho_json = os.path.join(diretorio, f"{id_prop}_parecer.json")
    dados_saida = {
        "id_proposta": id_prop,
        "coordenador": nome_coord,
        "unidade_lotacao": unidade,
        "titulo_projeto": titulo_proj,
        "status_final": status,
        "data_processamento": "2026-05-13",
        "auditoria": [res.model_dump() for res in resultados]
    }
    with open(caminho_json, "w", encoding="utf-8") as f:
        json.dump(dados_saida, f, indent=4, ensure_ascii=False)

    # 2. PARECER TÉCNICO EM MD
    caminho_md_parecer = os.path.join(diretorio, f"{id_prop}_parecer.md")
    md_content = f"# Parecer de Enquadramento - {id_prop}\n\n"
    md_content += f"**Resultado:** {status}\n\n"
    md_content += "## Detalhes da Validação\n"
    for res in resultados:
        icon = "✅" if res.passou else "❌"
        md_content += f"### {icon} {res.regra}\n"
        md_content += f"- **Motivo:** {res.motivo}\n"
        md_content += f"- **Evidência:** {res.evidencia}\n\n"
    with open(caminho_md_parecer, "w", encoding="utf-8") as f:
        f.write(md_content)

    # 3. SALVAR E-MAIL INDIVIDUAL EM TXT (Mantendo as tags HTML para o Streamlit)
    caminho_txt_email = os.path.join(diretorio, f"{id_prop}_email_individual.txt")
    with open(caminho_txt_email, "w", encoding="utf-8") as f:
        f.write(email_individual)

    print(f"📦 Artefatos de laudo e e-mail individual da {id_prop} gerados em: {diretorio}")
    return state

# ---------------------------------------------------------
# 10. NÓ DE RELATÓRIO CONSOLIDADO PARA A PROPP (GRAFO)
# ---------------------------------------------------------

def generate_consolidated_report(states: list, output_path: str):
    if not states:
        print("⚠️ Nenhum estado recebido para consolidação.")
        return

    rows = []
    motivos_falha = []

    for s in states:
        id_prop = s.get("id_proposta")
        status = s.get("status_enquadramento")
        resultados = s.get("resultados_validacao", [])
        
        # Facilita o acesso aos dicionários do formulário
        dados_proj = s.get("dados_formulario", {}).get("dados_projeto", {})
        dados_coord = s.get("dados_formulario", {}).get("dados_coordenador", {})
        
        nome_coord = dados_coord.get("nome", "N/A")
        titulo_proj = dados_proj.get("7_titulo_plano_trabalho", "N/A")
        unidade = dados_proj.get("13_unidade_executora", "N/A")
        
        # ==========================================================
        # EXTRAÇÃO DOS NOVOS DADOS PARA O DASHBOARD STREAMLIT
        # ==========================================================
        
        # 1. ODS (Pega só a sigla antes dos dois pontos, ex: "ODS 9")
        ods_lista = dados_proj.get("19_objetivos_desenvolvimento_sustentavel", ["Não Informado"])
        ods_sigla = ods_lista[0].split(":")[0] if ods_lista else "Não Informado"
        
        # 2. Área de Conhecimento
        area_lista = dados_proj.get("10_areas_conhecimento", ["Não Informada"])
        area_conhecimento = area_lista[0] if area_lista else "Não Informada"
        
        # 3. Potencial de Inovação e Patente
        inovacao = dados_proj.get("18_possui_inovacao_tecnologica", "Não")
        patente = dados_proj.get("17_gera_patente", "Não")
        
        erros = [r for r in resultados if not r.passou]
        
        # Adiciona as novas colunas na planilha
        rows.append({
            "ID da Proposta": id_prop,
            "Unidade": unidade,
            "Área de Conhecimento": area_conhecimento, # NOVA COLUNA
            "Coordenador": nome_coord,
            "Título do Projeto": titulo_proj,
            "Status Final": status,
            "ODS Vinculado": ods_sigla,                # NOVA COLUNA
            "Inovação Tecnológica": inovacao,          # NOVA COLUNA
            "Gera Patente": patente,                   # NOVA COLUNA
            "Qtd Inconformidades": len(erros)
        })
        
        for r in erros:
            motivos_falha.append(r.regra)

    df_geral = pd.DataFrame(rows)
    
    if motivos_falha:
        df_stats = pd.DataFrame(motivos_falha, columns=["Regra Violada"])
        df_stats = df_stats.value_counts().reset_index(name="Frequência")
        df_stats["% do Lote"] = (df_stats["Frequência"] / len(states) * 100).round(2)
    else:
        df_stats = pd.DataFrame({"Aviso": ["100% das propostas foram aprovadas. Nenhum erro encontrado."]})

    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df_geral.to_excel(writer, sheet_name="Resumo Propostas", index=False)
        df_stats.to_excel(writer, sheet_name="Estatísticas de Erros", index=False)
        
        worksheet = writer.sheets['Resumo Propostas']
        for i, col in enumerate(df_geral.columns):
            col_letter = chr(65 + i) 
            max_len = max(df_geral[col].astype(str).map(len).max(), len(col)) + 2
            worksheet.column_dimensions[col_letter].width = min(max_len, 50)
    
    print(f"📊 Relatório consolidado gerado com sucesso: {output_path}")

'''
# ---------------------------------------------------------
# 11. TESTE INTEGRADO (Ingestão + Titulação + Ficha de Pontuação + Limite de Propostas + Pendências e Projetos + Decisão + E-mail Consolidado + Relatório Excel)
# ---------------------------------------------------------
if __name__ == "__main__":

    # Descobre a pasta atual do arquivo (que é processo_2)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # Define a pasta onde estão os dados gerados
    DIRETORIO_PROPOSTAS = os.path.join(BASE_DIR, "propostas_sinteticas_teste")
    
    # =====================================================================
    # NOVO: Cria a pasta 'outputs' dentro de processo_2
    # =====================================================================
    DIRETORIO_OUTPUTS = os.path.join(BASE_DIR, "outputs")
    os.makedirs(DIRETORIO_OUTPUTS, exist_ok=True)
    
    # O glob pega o '*' e transforma numa lista com todas as pastas PROPOSTA_001, 002, etc.
    pastas = glob.glob(os.path.join(DIRETORIO_PROPOSTAS, "PROPOSTA_*"))
    
    if not pastas:
        print(f"❌ Nenhuma proposta encontrada no diretório: {DIRETORIO_PROPOSTAS}")
    else:
        print(f"Iniciando processamento em lote ({len(pastas)} propostas encontradas)...")
        
        todos_estados = []
        agrupamento_pesquisadores = defaultdict(list)
        
        # 1. LOOP DE AUDITORIA INDIVIDUAL
        for pasta in pastas:
            print(f"\n{'-'*60}\n🔄 PROCESSANDO: {os.path.basename(pasta)}\n{'-'*60}")
            
            # Inicia o estado limpo para a proposta da vez
            estado_global = {"diretorio_proposta": pasta, "resultados_validacao": []}
            
            # Passa a proposta por todos os nós de validação
            estado_global.update(load_proposal(estado_global))
            estado_global.update(check_titulacao(estado_global))
            estado_global.update(check_ficha_pontuacao(estado_global))
            estado_global.update(check_limit_proposals(estado_global))
            estado_global.update(check_pendencias_e_projetos(estado_global))
            estado_global.update(decide(estado_global))
            estado_global = emit(estado_global)
            
            # Guarda o resultado final
            todos_estados.append(estado_global)
            
            # Agrupa os projetos pelo CPF do coordenador para o e-mail consolidado
            cpf = estado_global.get("dados_formulario", {}).get("dados_coordenador", {}).get("6_cpf")
            if cpf:
                agrupamento_pesquisadores[cpf].append(estado_global)

        # 2. GERAÇÃO DOS E-MAILS CONSOLIDADOS POR PESQUISADOR
        print(f"\n{'='*70}\n📧 GERANDO E-MAILS CONSOLIDADOS\n{'='*70}")
        for cpf, propostas_do_pesquisador in agrupamento_pesquisadores.items():
            # Passamos o DIRETORIO_OUTPUTS para salvar os e-mails na nova pasta
            gerar_email_unico_pesquisador(propostas_do_pesquisador, DIRETORIO_OUTPUTS)
            
        # 3. GERAÇÃO DO RELATÓRIO EXCEL DA PROPP
        print(f"\n{'='*70}\n📊 GERANDO PLANILHA DE RELATÓRIO\n{'='*70}")
        # Apontamos o Excel para ser salvo dentro do DIRETORIO_OUTPUTS
        caminho_planilha = os.path.join(DIRETORIO_OUTPUTS, "estatisticas_enquadramento.xlsx")
        generate_consolidated_report(todos_estados, caminho_planilha)
        
        print("\n✅ Processamento em lote finalizado com sucesso!")
        print(f"📁 Relatórios consolidados e E-mails foram salvos na pasta: {DIRETORIO_OUTPUTS}")
'''