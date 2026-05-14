import os
import time

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


def call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.0,
    model: str = "google/gemma-4-31b-it",
    log_event: str = "llm.call",
) -> str:
    """
    Chama o LLM via OpenRouter, registra métricas de tokens e retorna o conteúdo.

    Parâmetros:
        log_event: chave de evento usada no log (ex: "emit.individual", "emit.consolidado")
    """
    from agent.logger import get_logger  # import tardio para evitar ciclo

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError(
            "ERRO: OPENROUTER_API_KEY não encontrada. "
            "Verifique se o arquivo .env está na raiz do projeto."
        )

    llm = ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        model=model,
        temperature=temperature,
        timeout=30,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    t0 = time.perf_counter()
    response = llm.invoke(messages)
    duration_ms = (time.perf_counter() - t0) * 1000

    # Extrai métricas de uso (disponíveis via response_metadata do LangChain)
    usage = getattr(response, "response_metadata", {}).get("token_usage", {})
    tokens_in  = usage.get("prompt_tokens", 0)
    tokens_out = usage.get("completion_tokens", 0)

    # Estimativa por caracteres caso a API não retorne token_usage
    if tokens_in == 0:
        tokens_in  = max(1, len(system_prompt + user_prompt) // 4)
    if tokens_out == 0:
        tokens_out = max(1, len(response.content) // 4)

    try:
        log = get_logger()
        log.llm_call(
            log_event,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            model=model,
            duration_ms=duration_ms,
        )
    except RuntimeError:
        pass  # Logger não inicializado (ex: execução isolada/testes)

    return response.content
