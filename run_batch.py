"""
run_batch.py — Ponto de entrada principal do pipeline de auditoria de propostas.

Uso:
    python run_batch.py [--propostas <caminho>] [--outputs <caminho>]

Padrão (sem argumentos):
    - Propostas: data/
    - Outputs:   outputs/

Logs estruturados (NDJSON) são salvos em outputs/logs/pipeline_<execution_id>.jsonl
"""

import argparse
import glob
import os
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from agent.graph import build_workflow
from agent.logger import get_logger, init_logger
from agent.nodes.emit import gerar_email_unico_pesquisador
from agent.nodes.report import generate_consolidated_report

# Raiz do projeto = pasta onde este script está (funciona em qualquer SO)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def executar_processamento_completo(
    diretorio_propostas: str,
    diretorio_outputs: str,
    arquivo_saida: str,
) -> None:
    """Orquestra o processamento de todas as propostas e consolida os resultados."""
    log = get_logger()
    app = build_workflow()
    pastas_propostas = glob.glob(os.path.join(diretorio_propostas, "PROPOSTA_*"))

    agrupamento_pesquisadores: dict = defaultdict(list)
    todos_estados_finais: list = []

    log.info(
        "pipeline.start",
        proposals_dir=diretorio_propostas,
        outputs_dir=diretorio_outputs,
        total_proposals=len(pastas_propostas),
    )

    for pasta in sorted(pastas_propostas):
        proposal_id = os.path.basename(pasta)
        log.info("proposal.start", proposal_id=proposal_id)

        estado_inicial = {
            "diretorio_proposta": pasta,
            "resultados_validacao": [],
        }

        try:
            estado_final = app.invoke(estado_inicial)
            todos_estados_finais.append(estado_final)

            status = estado_final.get("status_enquadramento", "DESCONHECIDO")
            log.info("proposal.done", proposal_id=proposal_id, status=status)

            cpf = (
                estado_final.get("dados_formulario", {})
                .get("dados_coordenador", {})
                .get("6_cpf")
            )
            if cpf:
                agrupamento_pesquisadores[cpf].append(estado_final)

        except Exception as e:
            log.error("proposal.error", proposal_id=proposal_id, error=str(e))

    # 1. E-mails consolidados por pesquisador
    log.info("emails.start", total_researchers=len(agrupamento_pesquisadores))
    for lista_estados in agrupamento_pesquisadores.values():
        gerar_email_unico_pesquisador(lista_estados, diretorio_outputs)

    # 2. Relatório gerencial em Excel
    log.info("report.start")
    generate_consolidated_report(todos_estados_finais, arquivo_saida)

    # 3. Resumo final com totais de tokens
    enquadradas = sum(
        1 for s in todos_estados_finais if s.get("status_enquadramento") == "ENQUADRADA"
    )
    log.summary(
        total_proposals=len(todos_estados_finais),
        enquadradas=enquadradas,
        nao_enquadradas=len(todos_estados_finais) - enquadradas,
        outputs_dir=diretorio_outputs,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline de auditoria de propostas UFMS")
    parser.add_argument(
        "--propostas",
        default=os.path.join(BASE_DIR, "data"),
        help="Diretório com as pastas PROPOSTA_* (padrão: data/)",
    )
    parser.add_argument(
        "--outputs",
        default=os.path.join(BASE_DIR, "outputs"),
        help="Diretório de saída para e-mails e relatórios (padrão: outputs/)",
    )
    args = parser.parse_args()

    diretorio_propostas = os.path.abspath(args.propostas)
    diretorio_outputs = os.path.abspath(args.outputs)
    os.makedirs(diretorio_outputs, exist_ok=True)

    # Inicializa o logger estruturado com ID único para esta execução
    execution_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:8]
    log_dir = os.path.join(diretorio_outputs, "logs")
    log_file = os.path.join(log_dir, f"pipeline_{execution_id}.jsonl")
    init_logger(execution_id, log_file=log_file)

    arquivo_saida = os.path.join(diretorio_outputs, "estatisticas_enquadramento.xlsx")

    if not os.path.exists(diretorio_propostas):
        get_logger().error(
            "pipeline.abort",
            reason="Diretório de propostas não encontrado",
            path=diretorio_propostas,
        )
        return

    executar_processamento_completo(diretorio_propostas, diretorio_outputs, arquivo_saida)


if __name__ == "__main__":
    main()
