import os
import glob
import json
from collections import defaultdict
from langgraph.graph import StateGraph, END

# Importação dos componentes do ficheiro de lógica (ingest.py ou nodes.py)
from nodes import (
    PropostaState,
    load_proposal,
    check_titulacao,
    check_ficha_pontuacao,
    check_limit_proposals,
    check_pendencias_e_projetos,
    decide,
    emit,
    generate_consolidated_report,
    gerar_email_unico_pesquisador # Nova função para o e-mail consolidado
)

def build_workflow():
    """
    Define a estrutura do Grafo apenas para a auditoria.
    O nó de rascunho de e-mail individual foi removido do fluxo sequencial.
    """
    workflow = StateGraph(PropostaState)

    # Definição dos Nós
    workflow.add_node("carregar", load_proposal)
    workflow.add_node("titulacao", check_titulacao)
    workflow.add_node("ficha", check_ficha_pontuacao)
    workflow.add_node("limite", check_limit_proposals)
    workflow.add_node("pendencias", check_pendencias_e_projetos)
    workflow.add_node("decisao", decide)
    workflow.add_node("emitir_docs", emit)

    # Definição das Arestas (Fluxo Sequencial)
    workflow.set_entry_point("carregar")
    workflow.add_edge("carregar", "titulacao")
    workflow.add_edge("titulacao", "ficha")
    workflow.add_edge("ficha", "limite")
    workflow.add_edge("limite", "pendencias")
    workflow.add_edge("pendencias", "decisao")
    workflow.add_edge("decisao", "emitir_docs")
    workflow.add_edge("emitir_docs", END)

    return workflow.compile()

def executar_processamento_completo(diretorio_base, diretorio_outputs, arquivo_saida):
    """
    Orquestra o processamento de todas as propostas e consolida os e-mails por CPF.
    Agora recebe o diretorio_outputs para salvar os resultados gerais no lugar certo.
    """
    app = build_workflow()
    pastas_propostas = glob.glob(f"{diretorio_base}/PROPOSTA_*")
    
    # Estrutura para agrupar propostas: { "CPF": [Estado_Final_1, Estado_Final_2] }
    agrupamento_pesquisadores = defaultdict(list)
    todos_estados_finais = []

    print(f"🔍 Iniciando auditoria de {len(pastas_propostas)} propostas...")

    for pasta in pastas_propostas:
        print(f"\n{'-'*60}\n🔄 PROCESSANDO: {os.path.basename(pasta)}\n{'-'*60}")
        
        # Inicializa o estado para cada proposta individual
        estado_inicial = {
            "diretorio_proposta": pasta,
            "resultados_validacao": []
        }
        
        try:
            # Executa o LangGraph
            estado_final = app.invoke(estado_inicial)
            todos_estados_finais.append(estado_final)
            
            # Agrupa os resultados pelo CPF do coordenador
            cpf = estado_final.get("dados_formulario", {}).get("dados_coordenador", {}).get("6_cpf")
            if cpf:
                agrupamento_pesquisadores[cpf].append(estado_final)
                
        except Exception as e:
            print(f"⚠️ Erro ao processar a pasta {pasta}: {e}")

    # 1. Geração dos E-mails Consolidados (Um por investigador)
    print("\n📧 Gerando rascunhos de e-mails consolidados...")
    for cpf, lista_estados in agrupamento_pesquisadores.items():
        # Passa o novo diretorio_outputs para salvar os emails consolidados lá!
        gerar_email_unico_pesquisador(lista_estados, diretorio_outputs)

    # 2. Geração do Relatório Gerencial (Excel)
    print("\n📊 Gerando relatório consolidado das estatísticas...")
    generate_consolidated_report(todos_estados_finais, arquivo_saida)

if __name__ == "__main__":
    # Descobre a pasta atual do arquivo (que é a processo_2)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    # Caminhos de execução
    CAMINHO_PROPOSTAS = os.path.join(BASE_DIR, "propostas_sinteticas_teste")  # Pasta onde estão as propostas sintéticas para teste
    
    # =====================================================================
    # Cria a pasta 'outputs' magicamente se ela não existir
    # =====================================================================
    DIRETORIO_OUTPUTS = os.path.join(BASE_DIR, "outputs")
    os.makedirs(DIRETORIO_OUTPUTS, exist_ok=True)
    
    # Define o caminho do Excel para dentro da pasta outputs
    PLANILHA_GERENCIAL = os.path.join(DIRETORIO_OUTPUTS, "estatisticas_enquadramento.xlsx")

    if os.path.exists(CAMINHO_PROPOSTAS):
        # Passamos os 3 caminhos agora
        executar_processamento_completo(CAMINHO_PROPOSTAS, DIRETORIO_OUTPUTS, PLANILHA_GERENCIAL)
        print(f"\n-> Pipeline finalizada com sucesso. Resultados salvos em: {DIRETORIO_OUTPUTS}")
    else:
        print(f"❌ Diretório de propostas não encontrado: {CAMINHO_PROPOSTAS}")