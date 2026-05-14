from typing import TypedDict, List, Dict, Any
from pydantic import BaseModel, Field


class ValidationResult(BaseModel):
    """Contrato de saída de cada nó validador."""

    regra: str = Field(description="Nome da regra verificada (ex: Titulação, Limite de Propostas)")
    passou: bool = Field(description="True se a proposta atende ao critério, False caso contrário")
    motivo: str = Field(description="Justificativa textual para o resultado")
    evidencia: str = Field(description="Trecho do documento ou valor que embasa a decisão")


class PropostaState(TypedDict):
    """Estado global do Grafo LangGraph."""

    diretorio_proposta: str  # Caminho da pasta recebida como entrada
    id_proposta: str

    # Dados brutos extraídos no nó de ingestão
    dados_formulario: Dict[str, Any]
    dados_lattes: str        # XML puro em string
    caminho_ficha: str       # Caminho para o Excel (lido pelo nó específico)

    # Acumulador dos resultados dos nós validadores
    resultados_validacao: List[ValidationResult]

    # Saídas finais
    status_enquadramento: str  # "ENQUADRADA" ou "NÃO ENQUADRADA"
    rascunho_email: str
