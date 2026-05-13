import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# Carrega as variáveis do arquivo .env para o ambiente do sistema
load_dotenv()

def call_llm(system_prompt: str, user_prompt: str, temperature: float = 0.0, model: str = "google/gemma-4-31b-it") -> str:
    
    # Busca a chave carregada do .env de forma segura
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("ERRO: OPENROUTER_API_KEY não encontrada. Verifique se o arquivo .env está na mesma pasta e com o nome correto.")

    llm = ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        model=model,
        temperature=temperature,
        timeout=30,
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_prompt},
    ]
    
    return llm.invoke(messages).content