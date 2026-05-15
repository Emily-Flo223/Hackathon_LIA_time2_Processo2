# Hackathon LIA
# Processo 2: PROPP — Auditoria Inteligente de Enquadramento de Propostas IC&T

Time 2 — Emily Flores · Arthur Schneider · Thiago Poganski · Willian Cintra

---

## Sobre o projeto

A PROPP (Pró-Reitoria de Pesquisa e Pós-Graduação) da UFMS publica anualmente o Edital de Bolsas de Iniciação Científica e Tecnológica (PIBIC/PIBIC-AF/PIBITI). Após o prazo de submissão, a equipe da SEICT/DIPEQ analisa manualmente cada proposta verificando titulação do proponente, limite de submissões, qualidade da ficha de pontuação e pendências institucionais. Com centenas de propostas em janelas de tempo curtas, erros nessa etapa atrasam todo o ciclo do edital.

Este projeto automatiza a **Análise de Enquadramento** com um agente LangGraph que verifica cada critério de forma determinística, gera um parecer estruturado e rascunha o e-mail de devolutiva para o pesquisador. A interface Streamlit permite à equipe da PROPP acompanhar, revisar e confirmar as decisões com total rastreabilidade.

---

## O que o agente faz

O agente recebe a pasta de uma proposta (formulário JSON, Lattes XML, Ficha Excel) e executa cinco etapas em sequência:

**Titulação** — navega no XML do Currículo Lattes e confirma se o proponente possui título de Doutor com status `CONCLUIDO`. Decisão determinística, sem LLM.

**Ficha de Pontuação** — audita a planilha Excel verificando estrutura de colunas, cálculos linha a linha (Qtde × Peso = Total), limites máximos por critério, somatório final e consistência entre artigos declarados e periódicos detalhados. Decisão determinística, sem LLM.

**Limite de Propostas** — varre todas as pastas do lote, conta submissões por CPF e aplica o limite correto: 2 para Doutor padrão, 3 para Doutor com Bolsa PQ do CNPq (detectado via XML do Lattes). Decisão determinística, sem LLM.

**Pendências Institucionais** — consulta a base interna da PROPP (`internal_database.json`) verificando pendências impeditivas e existência de projeto de pesquisa em andamento na UFMS. Decisão determinística, sem LLM.

**Emissão** — consolida os resultados, determina `ENQUADRADA` ou `NÃO ENQUADRADA` e usa o LLM exclusivamente para redigir o e-mail de devolutiva em HTML, personalizado por proposta e por pesquisador.

---

## Arquitetura

```
START
  │
  ▼
[carregar]       lê formulario.json, lattes.xml e caminho da ficha Excel
  │
  ▼
[titulacao]      verifica Doutorado concluído no XML do Lattes
  │
  ▼
[ficha]          audita estrutura, cálculos, limites e periódicos do Excel
  │
  ▼
[limite]         conta submissões por CPF; detecta Bolsa PQ para limite 3
  │
  ▼
[pendencias]     consulta base interna: pendências impeditivas e projeto ativo
  │
  ▼
[decisao]        agrega resultados → ENQUADRADA / NÃO ENQUADRADA
  │
  ▼
[emitir_docs]    LLM redige e-mail; salva parecer JSON, MD e e-mail TXT
  │
  ▼
 END
```

Após o loop de propostas, o orquestrador (`run_batch.py`) agrupa os estados por CPF e chama:
- `gerar_email_unico_pesquisador()` — e-mail HTML consolidado por pesquisador
- `generate_consolidated_report()` — planilha Excel gerencial com duas abas

---

## Tecnologias

| Camada | Tecnologia |
|---|---|
| Linguagem | Python 3.11+ |
| Orquestração de agentes | LangGraph |
| Integração com LLM | LangChain OpenAI via OpenRouter |
| Modelo | google/gemma-4-31b-it |
| Interface | Streamlit + Plotly |
| Leitura de Excel | pandas + openpyxl |
| Leitura de XML | xml.etree.ElementTree (stdlib) |
| Logs estruturados | NDJSON com execution_id e métricas de tokens |

---

## Estrutura do projeto

```
│
├── agent/
│   ├── graph.py                        # Construção e compilação do StateGraph
│   ├── llm.py                          # Wrapper OpenRouter com captura de tokens
│   ├── logger.py                       # Logger NDJSON com execution_id
│   ├── state.py                        # PropostaState (TypedDict) + ValidationResult (Pydantic)
│   ├── nodes/
│   │   ├── ingest.py                   # Lê formulario.json, lattes.xml e ficha Excel
│   │   ├── validate_titulacao.py       # Verifica Doutorado concluído no Lattes
│   │   ├── validate_ficha.py           # Audita estrutura, cálculos e periódicos do Excel
│   │   ├── validate_limite.py          # Conta submissões por CPF; detecta Bolsa PQ
│   │   ├── validate_pendencias.py      # Consulta base interna PROPP
│   │   ├── decide.py                   # Agrega resultados e define status final
│   │   ├── emit.py                     # Gera parecer JSON/MD e e-mails via LLM
│   │   └── report.py                   # Gera planilha Excel gerencial
│   └── utils/
│       └── prompts.py                  # load_prompt() — carrega .md de prompts/
│
├── prompts/
│   ├── email_individual.md             # Prompt do e-mail de proposta única
│   └── email_consolidado.md           # Prompt do e-mail consolidado por pesquisador
│
├── data/                               # Dados de entrada — não versionados
│   ├── PROPOSTA_001/
│   │   ├── formulario.json
│   │   ├── lattes.xml
│   │   └── ficha_pontuacao.xlsx
│   ├── PROPOSTA_00N/
│   └── internal_database.json
│
├── outputs/                            # Gerado em runtime — não versionado
│   ├── logs/pipeline_<execution_id>.jsonl
│   ├── EMAIL_<NOME>.txt
│   ├── estatisticas_enquadramento.xlsx
│   └── historico_revisoes.json
│
├── tests/
├── app.py                              # Interface Streamlit
├── run_batch.py                        # Orquestrador CLI
├── requirements.txt
└── .env.example
```

---

## Como rodar

### Pré-requisitos

- Python 3.11 ou superior
- Conta no [OpenRouter](https://openrouter.ai) com créditos disponíveis

### Instalação

```bash
git clone https://github.com/Emily-Flo223/Hackathon_LIA_time2_Processo2.git
cd Hackathon_LIA_time2_Processo2

python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / Mac
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Edite o .env e preencha sua OPENROUTER_API_KEY
```

### Executando o pipeline

```bash
# Processa todas as propostas em data/
python run_batch.py

# Apontando para outro diretório
python run_batch.py --propostas data/ --outputs outputs/
```

### Executando a interface

```bash
streamlit run app.py
```

Credenciais de acesso (desenvolvimento):

| Usuário | Senha |
|---|---|
| `admin@propp.ufms.br` | `propp2025` |
| `auditor@propp.ufms.br` | `auditoria123` |

### Saídas geradas

Após rodar o `run_batch.py`, a pasta `outputs/` conterá:

- `PROPOSTA_XXX_parecer.json` — laudo estruturado com todas as validações (dentro de cada pasta em `data/`)
- `PROPOSTA_XXX_parecer.md` — parecer em Markdown legível
- `PROPOSTA_XXX_email_individual.txt` — rascunho do e-mail individual em HTML
- `EMAIL_<NOME>.txt` — e-mail consolidado por pesquisador
- `estatisticas_enquadramento.xlsx` — planilha gerencial com abas "Resumo Propostas" e "Estatísticas de Erros"
- `logs/pipeline_<execution_id>.jsonl` — log NDJSON com métricas de tokens por execução

---

## Variáveis de ambiente

| Variável | Descrição |
|---|---|
| `OPENROUTER_API_KEY` | Chave de acesso à API do OpenRouter |

---

## Decisões de design

**Validações 100% determinísticas.** O LLM não participa de nenhuma decisão de enquadramento. Titulação, ficha, limite e pendências são verificados por código puro sobre dados estruturados. A mesma proposta produz sempre o mesmo resultado, independente do modelo ou da temperatura.

**LLM apenas para geração de texto.** O único ponto de uso do LLM é a redação do e-mail de devolutiva. O prompt é carregado de arquivo `.md` versionado — ajustes de tom e formato não exigem alteração de código Python.

**E-mail consolidado por pesquisador.** Pesquisadores podem submeter até 3 propostas. O orquestrador agrupa os estados finais por CPF e gera um único e-mail com o resultado de todas as propostas.

**Log NDJSON com execution_id.** Cada execução recebe um identificador único no formato `YYYYMMDDTHHMMSS_<8hex>`. Todos os eventos carregam esse ID, permitindo rastrear exatamente o que aconteceu em cada rodada — essencial para auditoria de processos públicos.

**Human-in-the-loop na interface.** A equipe da PROPP visualiza o parecer do agente, confirma ou encaminha para revisão manual, e cada ação é registrada em `historico_revisoes.json` com data/hora.