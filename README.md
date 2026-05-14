# Hackathon LIA — Time 2 | Processo 2

Agente inteligente desenvolvido durante o Hackathon do projeto **MDA** (Ministério do Desenvolvimento Agrário e Agricultura Familiar). Utiliza **LangGraph** e **LLM via OpenRouter** para automatizar a auditoria de enquadramento de propostas de bolsas IC&T da UFMS.

---

## Arquitetura do Projeto

```
Hackathon_LIA_time2_Processo2/
│
├── agent/                          # Núcleo do agente LangGraph
│   ├── graph.py                    # Construção e compilação do grafo de fluxo
│   ├── llm.py                      # Wrapper de chamada ao LLM (OpenRouter)
│   ├── state.py                    # PropostaState e ValidationResult (schemas)
│   ├── nodes/                      # Um arquivo por nó do grafo
│   │   ├── ingest.py               # Nó de ingestão: lê formulário, Lattes e ficha
│   │   ├── validate_titulacao.py   # Nó: verifica titulação de Doutor no Lattes XML
│   │   ├── validate_ficha.py       # Nó: audita a Ficha de Pontuação Excel
│   │   ├── validate_limite.py      # Nó: verifica limite de propostas por CPF
│   │   ├── validate_pendencias.py  # Nó: consulta base interna PROPP
│   │   ├── decide.py               # Nó decisor: agrega resultados e emite status final
│   │   ├── emit.py                 # Nó de emissão: gera parecer JSON/MD e e-mail individual
│   │   │                           # + função auxiliar gerar_email_unico_pesquisador()
│   │   └── report.py               # Função: gera relatório gerencial Excel consolidado
│   └── utils/                      # Utilitários futuros (few-shot, helpers, etc.)
│
├── data/                           # Dados de entrada (ignorados pelo git)
│   ├── PROPOSTA_001/               # Cada proposta tem sua própria pasta

│   ├── PROPOSTA_00N/               # ...
│   └── internal_database.json      # Base interna da PROPP (CPF, pendências, projetos)
│
├── outputs/                        # Saídas geradas em execução (ignoradas pelo git)
│   ├── EMAIL_*.txt                 # E-mails consolidados por pesquisador (HTML)
│   └── estatisticas_enquadramento.xlsx
│
├── tests/                          # Testes automatizados
│
├── run_batch.py                    # Ponto de entrada — processa todas as propostas
├── requirements.txt
├── .env.example
└── README.md
```

---

## Fluxo do Grafo (LangGraph)

```
carregar → titulacao → ficha → limite → pendencias → decisao → emitir_docs → END
```

Cada nó valida um critério e acumula seu resultado em `resultados_validacao`. O nó `decisao` define `status_enquadramento` como `ENQUADRADA` ou `NÃO ENQUADRADA`. O nó `emitir_docs` gera os artefatos dentro da pasta da proposta.

Após o loop, o orquestrador chama:
- `gerar_email_unico_pesquisador()` — e-mail HTML consolidado por pesquisador
- `generate_consolidated_report()` — planilha Excel gerencial

---

## Instalação

```bash
git clone https://github.com/Emily-Flo223/Hackathon_LIA_time2_Processo2.git
cd Hackathon_LIA_time2_Processo2

python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

pip install -r requirements.txt

cp .env.example .env
# Edite .env e insira sua OPENROUTER_API_KEY
```

---

## Execução

```bash
# Padrão: processa data/test_proposals/ → outputs/
python run_batch.py

# Personalizando caminhos
python run_batch.py --propostas data --outputs outputs
```

**Artefatos gerados em `outputs/`:**
- `EMAIL_<NOME>.txt` — e-mail HTML consolidado por pesquisador
- `estatisticas_enquadramento.xlsx` — relatório gerencial

**Artefatos gerados dentro de cada `PROPOSTA_*/`:**
- `PROPOSTA_XXX_parecer.json`
- `PROPOSTA_XXX_parecer.md`
- `PROPOSTA_XXX_email_individual.txt`

---

## Variáveis de Ambiente

| Variável | Descrição |
|---|---|
| `OPENROUTER_API_KEY` | Chave de acesso à API do OpenRouter |
