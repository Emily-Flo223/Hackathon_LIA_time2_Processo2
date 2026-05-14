"""
agent/logger.py — Logger estruturado em JSON para o pipeline de auditoria.

Cada linha do arquivo de log é um objeto JSON independente (formato NDJSON),
contendo obrigatoriamente:
  - timestamp   : ISO-8601 UTC
  - execution_id: identificador único da execução (gerado em run_batch.py)
  - level       : DEBUG | INFO | WARNING | ERROR
  - event       : chave de evento padronizada (snake_case)
  - (campos extras dependem do evento)

Uso:
    from agent.logger import get_logger
    log = get_logger()
    log.info("proposal.start", proposal_id="PROPOSTA_001")
    log.llm_call("emit.individual", tokens_in=210, tokens_out=480, model="gemma-4-31b")
    log.error("proposal.error", proposal_id="PROPOSTA_007", error="FileNotFoundError")
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any


class StructuredLogger:
    """
    Wrapper sobre logging.Logger que emite cada mensagem como uma linha JSON
    e mantém métricas de tokens acumuladas por execução.
    """

    def __init__(self, execution_id: str, log_file: str | None = None):
        self.execution_id = execution_id
        self._token_metrics: dict[str, int] = {
            "total_tokens_in": 0,
            "total_tokens_out": 0,
            "total_llm_calls": 0,
        }

        # Logger Python subjacente (apenas para gerenciar handlers)
        self._logger = logging.getLogger(f"pipeline.{execution_id}")
        self._logger.setLevel(logging.DEBUG)
        self._logger.handlers.clear()
        self._logger.propagate = False

        formatter = _NDJSONFormatter(execution_id)

        # Handler para stdout (sempre ativo)
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(formatter)
        self._logger.addHandler(sh)

        # Handler para arquivo (opcional)
        if log_file:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(formatter)
            self._logger.addHandler(fh)

    # ------------------------------------------------------------------
    # Métodos públicos de log por nível
    # ------------------------------------------------------------------

    def debug(self, event: str, **kwargs: Any) -> None:
        self._emit(logging.DEBUG, event, **kwargs)

    def info(self, event: str, **kwargs: Any) -> None:
        self._emit(logging.INFO, event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        self._emit(logging.WARNING, event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        self._emit(logging.ERROR, event, **kwargs)

    # ------------------------------------------------------------------
    # Método especializado para chamadas LLM (registra métricas de tokens)
    # ------------------------------------------------------------------

    def llm_call(
        self,
        event: str,
        *,
        tokens_in: int = 0,
        tokens_out: int = 0,
        model: str = "",
        duration_ms: float = 0.0,
        **kwargs: Any,
    ) -> None:
        """
        Registra uma chamada ao LLM com métricas de tokens.
        Acumula os totais internamente para o resumo final.
        """
        self._token_metrics["total_tokens_in"] += tokens_in
        self._token_metrics["total_tokens_out"] += tokens_out
        self._token_metrics["total_llm_calls"] += 1

        self._emit(
            logging.INFO,
            event,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            tokens_total=tokens_in + tokens_out,
            model=model,
            duration_ms=round(duration_ms, 2),
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Resumo final da execução
    # ------------------------------------------------------------------

    def summary(self, **kwargs: Any) -> None:
        """Emite um evento de encerramento com o total de tokens consumidos."""
        self._emit(
            logging.INFO,
            "pipeline.summary",
            **self._token_metrics,
            **kwargs,
        )

    @property
    def token_metrics(self) -> dict[str, int]:
        return dict(self._token_metrics)

    # ------------------------------------------------------------------
    # Interno
    # ------------------------------------------------------------------

    def _emit(self, level: int, event: str, **kwargs: Any) -> None:
        extra = {"event": event, "extra_fields": kwargs}
        self._logger.log(level, event, extra=extra)


class _NDJSONFormatter(logging.Formatter):
    """Formata cada registro de log como uma linha JSON (NDJSON)."""

    def __init__(self, execution_id: str):
        super().__init__()
        self.execution_id = execution_id

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_id": self.execution_id,
            "level": record.levelname,
            "event": getattr(record, "event", record.getMessage()),
        }
        payload.update(getattr(record, "extra_fields", {}))
        return json.dumps(payload, ensure_ascii=False)


# ------------------------------------------------------------------
# Singleton por execução — inicializado em run_batch.py via init_logger()
# ------------------------------------------------------------------

_current_logger: StructuredLogger | None = None


def init_logger(execution_id: str, log_file: str | None = None) -> StructuredLogger:
    """
    Cria e registra o logger global da execução.
    Deve ser chamado UMA vez, no início de run_batch.py.
    """
    global _current_logger
    _current_logger = StructuredLogger(execution_id, log_file=log_file)
    return _current_logger


def get_logger() -> StructuredLogger:
    """
    Retorna o logger da execução atual.
    Levanta RuntimeError se init_logger() ainda não foi chamado.
    """
    if _current_logger is None:
        raise RuntimeError(
            "Logger não inicializado. Chame agent.logger.init_logger() antes de usar get_logger()."
        )
    return _current_logger
