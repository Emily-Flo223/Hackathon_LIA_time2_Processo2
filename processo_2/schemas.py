from typing import TypedDict, List, Dict, Any
from pydantic import BaseModel, Field

# O contrato de saída de cada nó validador, conforme o briefing
class ValidationResult(BaseModel):
    regra: str = Field(description="Nome da regra verificada (ex: Titulação, Limite de Propostas)")
    passou: bool = Field(description="True se a proposta atende ao critério, False caso contrário")
    motivo: str = Field(description="Justificativa textual para o resultado")
    evidencia: str = Field(description="Trecho do documento ou valor que embasa a decisão")

# O estado global do nosso Grafo LangGraph
class PropostaState(TypedDict):
    id_proposta: str
    
    # Dados brutos extraídos no nó de ingestão
    dados_formulario: Dict[str, Any]
    dados_lattes: str # O XML puro em string ou um dict parseado
    caminho_ficha: str # Caminho para o Excel, para o nó específico ler usando pandas/openpyxl
    
    # Acumulador dos resultados dos nós paralelos
    resultados_validacao: List[ValidationResult]
    
    # Saídas finais
    status_enquadramento: str # "ENQUADRADA" ou "NÃO ENQUADRADA"
    rascunho_email: str