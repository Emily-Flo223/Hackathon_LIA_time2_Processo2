import os

# Pasta prompts/ fica na raiz do projeto (dois níveis acima de agent/utils/)
_UTILS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(_UTILS_DIR)), "prompts")


def load_prompt(filename: str) -> str:
    """
    Carrega o conteúdo de um arquivo .md da pasta prompts/.

    Exemplo:
        system_prompt = load_prompt("email_individual.md")
    """
    caminho = os.path.join(_PROMPTS_DIR, filename)
    if not os.path.exists(caminho):
        raise FileNotFoundError(
            f"Prompt não encontrado: '{filename}'\n"
            f"Verifique se o arquivo existe em: {_PROMPTS_DIR}"
        )
    with open(caminho, "r", encoding="utf-8") as f:
        return f.read().strip()
