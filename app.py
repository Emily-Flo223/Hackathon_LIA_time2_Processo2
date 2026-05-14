import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

# =====================================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# =====================================================================
st.set_page_config(page_title="PROPP - Sistema de Auditoria", layout="wide", page_icon="🎓")

# =====================================================================
# 2. AUTENTICAÇÃO (LOGIN SINTÉTICO)
# =====================================================================
USUARIOS_VALIDOS = {
    "admin@propp.ufms.br": "propp2025",
    "auditor@propp.ufms.br": "auditoria123",
}


def tela_login():
    st.markdown("""
        <style>
        .login-container { max-width: 420px; margin: 60px auto 0 auto; }
        </style>
    """, unsafe_allow_html=True)

    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        st.markdown("<div class='login-container'>", unsafe_allow_html=True)
        st.markdown("## 🎓 PROPP — Sistema de Auditoria")
        st.markdown("##### Acesso Restrito — Informe suas credenciais")
        st.divider()

        email = st.text_input("📧 E-mail", placeholder="seu@email.com")
        senha = st.text_input("🔒 Senha", type="password", placeholder="••••••••")

        if st.button("Entrar", type="primary", use_container_width=True):
            if email in USUARIOS_VALIDOS and USUARIOS_VALIDOS[email] == senha:
                st.session_state.autenticado = True
                st.session_state.usuario_logado = email
                st.rerun()
            else:
                st.error("❌ E-mail ou senha incorretos. Tente novamente.")

        st.markdown("</div>", unsafe_allow_html=True)
        st.caption("Sistema interno — acesso não autorizado é proibido.")


st.session_state.setdefault("autenticado", False)
st.session_state.setdefault("usuario_logado", None)

if not st.session_state.autenticado:
    tela_login()
    st.stop()

# =====================================================================
# 3. CONFIGURAÇÃO DE CAMINHOS  (nova estrutura do projeto)
# =====================================================================
BASE_DIR          = os.path.dirname(os.path.abspath(__file__))
PASTA_OUTPUTS     = os.path.join(BASE_DIR, "outputs")
CAMINHO_EXCEL     = os.path.join(PASTA_OUTPUTS, "estatisticas_enquadramento.xlsx")
PASTA_PROPOSTAS   = os.path.join(BASE_DIR, "data")           # propostas ficam em data/PROPOSTA_*/
ARQUIVO_REVISOES  = os.path.join(PASTA_OUTPUTS, "historico_revisoes.json")
RUN_BATCH_PATH    = os.path.join(BASE_DIR, "run_batch.py")   # ponto de entrada do backend
CAMINHO_DB        = os.path.join(BASE_DIR, "data", "internal_database.json")
URL_EDITAL        = "https://www.ufms.br/wp-content/uploads/2025/07/EDITAL-PROPP_RTR-n-215-de-18-07-2025..pdf"

# =====================================================================
# 4. ESTADO DE NAVEGAÇÃO
# =====================================================================
st.session_state.setdefault("menu", "🏠 Tela Inicial (Kanban)")
st.session_state.setdefault("proposta_selecionada", None)
st.session_state.setdefault("email_coordenador", None)
st.session_state.setdefault("proposta_origem_email", None)
st.session_state.setdefault("menu_origem", "🏠 Tela Inicial (Kanban)")

# =====================================================================
# 5. MENU LATERAL
# =====================================================================
st.sidebar.title("🔵 Menu PROPP")
menu_opcoes = [
    "🏠 Tela Inicial (Kanban)",
    "📊 Dashboard Executivo",
    "🔍 Auditoria de Propostas",
    "✉️ Central de Comunicação",
    "📂 Histórico de Decisões",
    "🗃️ Base de Dados Interna",
]
menu = st.sidebar.radio(
    "Navegue pelas funcionalidades:",
    menu_opcoes,
    key="menu",
    index=menu_opcoes.index(st.session_state.menu) if st.session_state.menu in menu_opcoes else 0,
)

if menu != "🔍 Auditoria de Propostas":
    st.session_state.proposta_selecionada = None
if menu != "✉️ Central de Comunicação":
    st.session_state.email_coordenador = None
    st.session_state.proposta_origem_email = None

st.sidebar.divider()
st.sidebar.info("Desenvolvido para otimização, transparência e inovação na gestão pública de editais.")
st.sidebar.caption(f"👤 {st.session_state.get('usuario_logado', '')}")
if st.sidebar.button("🚪 Sair", use_container_width=True):
    st.session_state.autenticado = False
    st.session_state.usuario_logado = None
    st.rerun()

# =====================================================================
# HELPERS GERAIS
# =====================================================================

def carregar_base_interna() -> list:
    """Carrega o internal_database.json de data/. Retorna lista vazia se não encontrado."""
    if os.path.exists(CAMINHO_DB):
        try:
            with open(CAMINHO_DB, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def formatar_email(conteudo: str) -> str:
    conteudo = re.sub(r'(?<!\n)(📌)', r'\n\1', conteudo)
    conteudo = re.sub(r'(?<!\n)(🔎)', r'\n\1', conteudo)
    return conteudo


def renderizar_email_html(conteudo: str):
    html = formatar_email(conteudo).replace('\n', '<br>')
    st.markdown(
        f'<div style="background:#f8f9fa;border:1px solid #dee2e6;border-radius:8px;padding:20px;'
        f'font-family:Arial,sans-serif;font-size:14px;line-height:1.9;color:#212529">{html}</div>',
        unsafe_allow_html=True,
    )


def carregar_revisoes() -> list:
    if os.path.exists(ARQUIVO_REVISOES):
        with open(ARQUIVO_REVISOES, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return []
    return []


def salvar_revisao(proposta_id, coordenador, status_agente, decisao, observacao=""):
    revisoes = carregar_revisoes()
    idx = next((i for i, r in enumerate(revisoes) if r["id_proposta"] == proposta_id), None)
    entrada = {
        "id_proposta":   proposta_id,
        "coordenador":   coordenador,
        "status_agente": status_agente,
        "decisao":       decisao,
        "observacao":    observacao,
        "data_hora":     datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    }
    if idx is not None:
        revisoes[idx] = entrada
    else:
        revisoes.append(entrada)
    os.makedirs(PASTA_OUTPUTS, exist_ok=True)
    with open(ARQUIVO_REVISOES, "w", encoding="utf-8") as f:
        json.dump(revisoes, f, indent=4, ensure_ascii=False)


def obter_nome_coordenador(proposta_id: str) -> str:
    """Busca o nome do coordenador para usar nos seletores da interface."""
    caminho_json = os.path.join(PASTA_PROPOSTAS, proposta_id, f"{proposta_id}_parecer.json")
    if os.path.exists(caminho_json):
        try:
            with open(caminho_json, "r", encoding="utf-8") as f:
                nome = json.load(f).get("coordenador", "")
                if nome:
                    return nome.title()
        except Exception:
            pass
    caminho_form = os.path.join(PASTA_PROPOSTAS, proposta_id, "formulario.json")
    if os.path.exists(caminho_form):
        try:
            with open(caminho_form, "r", encoding="utf-8") as f:
                dados = json.load(f)
            coord = dados.get("dados_coordenador", {})
            for k, v in coord.items():
                if "nome" in k.lower():
                    return str(v).title()
            if coord:
                return str(list(coord.values())[0]).title()
        except Exception:
            pass
    return "Coordenador Desconhecido"


def get_coordenador_email(proposta_id: str) -> str | None:
    caminho_json = os.path.join(PASTA_PROPOSTAS, proposta_id, f"{proposta_id}_parecer.json")
    if not os.path.exists(caminho_json):
        return None
    with open(caminho_json, "r", encoding="utf-8") as f:
        dados = json.load(f)
    nome = dados.get("coordenador", "")
    return nome.replace(" ", "_").upper() if nome else None


def exportar_relatorio_html():
    if not os.path.exists(CAMINHO_EXCEL):
        return None
    df = pd.read_excel(CAMINHO_EXCEL, sheet_name="Resumo Propostas")
    total           = len(df)
    enquadradas     = len(df[df["Status Final"] == "ENQUADRADA"])
    nao_enquadradas = total - enquadradas
    linhas = ""
    for _, row in df.iterrows():
        cor = "#d4edda" if row["Status Final"] == "ENQUADRADA" else "#f8d7da"
        linhas += (
            f'<tr style="background:{cor}"><td>{row["ID da Proposta"]}</td>'
            f'<td>{row["Coordenador"]}</td><td>{row["Unidade"]}</td>'
            f'<td>{row["Status Final"]}</td><td>{row["Qtd Inconformidades"]}</td></tr>'
        )
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
    <title>Relatório PROPP - Enquadramento IC&T</title>
    <style>body{{font-family:Arial;padding:30px}}h1{{color:#007BC0}}
    table{{width:100%;border-collapse:collapse;margin-top:20px}}
    th{{background:#007BC0;color:white;padding:8px;text-align:left}}
    td{{padding:8px;border-bottom:1px solid #ddd}}
    .resumo{{display:flex;gap:30px;margin:20px 0}}
    .card{{padding:15px;border-radius:8px;text-align:center;min-width:120px}}
    .total{{background:#e8f4fd}}.ok{{background:#d4edda}}.nok{{background:#f8d7da}}</style>
    </head><body>
    <h1>PROPP — Relatório de Enquadramento IC&T 2026</h1>
    <p>Gerado em: {datetime.now().strftime("%d/%m/%Y às %H:%M")}</p>
    <div class="resumo">
      <div class="card total"><strong>{total}</strong><br>Total</div>
      <div class="card ok"><strong>{enquadradas}</strong><br>Enquadradas</div>
      <div class="card nok"><strong>{nao_enquadradas}</strong><br>Não Enquadradas</div>
    </div>
    <table><tr><th>ID</th><th>Coordenador</th><th>Unidade</th><th>Status</th><th>Inconformidades</th></tr>
    {linhas}</table></body></html>"""


def exportar_estatisticas_html():
    if not os.path.exists(CAMINHO_EXCEL):
        return None
    try:
        df = pd.read_excel(CAMINHO_EXCEL, sheet_name="Estatísticas de Erros")
    except Exception:
        return None
    linhas     = ""
    for _, row in df.iterrows():
        linhas += "<tr>" + "".join(f"<td>{v}</td>" for v in row.values) + "</tr>"
    cabecalhos = "".join(f"<th>{c}</th>" for c in df.columns)
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
    <title>Estatísticas de Erros - PROPP</title>
    <style>body{{font-family:Arial;padding:30px}}h1{{color:#007BC0}}
    table{{width:100%;border-collapse:collapse;margin-top:20px}}
    th{{background:#007BC0;color:white;padding:8px;text-align:left}}
    td{{padding:8px;border-bottom:1px solid #ddd}}</style>
    </head><body>
    <h1>PROPP — Estatísticas de Erros de Enquadramento</h1>
    <p>Gerado em: {datetime.now().strftime("%d/%m/%Y às %H:%M")}</p>
    <table><tr>{cabecalhos}</tr>{linhas}</table>
    </body></html>"""


# =====================================================================
# HELPER: Tela de detalhes de uma proposta
# =====================================================================
def mostrar_detalhes(proposta_id: str, voltar_para: str = "🏠 Tela Inicial (Kanban)"):
    if st.button("← Voltar"):
        st.session_state.proposta_selecionada = None
        st.session_state.aba_atual = "📋 Formulário"
        st.session_state.menu = voltar_para
        st.rerun()

    st.title(f"🔍 Detalhes Completos — {proposta_id}")
    st.divider()

    caminho_proposta = os.path.join(PASTA_PROPOSTAS, proposta_id)
    if not os.path.exists(caminho_proposta):
        st.error(f"Pasta da proposta não encontrada: {caminho_proposta}")
        return

    st.session_state.setdefault("aba_atual", "📋 Formulário")

    abas_titulos = [
        "📋 Formulário", "👤 Lattes", "📊 Ficha de Pontuação",
        "🗃️ Base de Dados Interna", "⚖️ Parecer Final", "✉️ E-mail", "✅ Revisão Humana",
    ]
    cols_abas = st.columns(len(abas_titulos))
    for idx, titulo in enumerate(abas_titulos):
        with cols_abas[idx]:
            tipo_btn = "primary" if st.session_state.aba_atual == titulo else "secondary"
            if st.button(titulo, key=f"tab_btn_{titulo}", type=tipo_btn, use_container_width=True):
                st.session_state.aba_atual = titulo
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── ABA: Formulário ───────────────────────────────────────────────
    if st.session_state.aba_atual == "📋 Formulário":
        st.subheader("Dados do Formulário de Submissão")
        caminho_form = os.path.join(caminho_proposta, "formulario.json")
        if os.path.exists(caminho_form):
            with open(caminho_form, "r", encoding="utf-8") as f:
                dados = json.load(f)

            st.write("#### 👨‍🏫 Dados do Coordenador")
            for campo, valor in dados.get("dados_coordenador", {}).items():
                col_c, col_v = st.columns([1, 3])
                with col_c:
                    st.markdown(f"**{campo.replace('_', ' ').title()}:**")
                with col_v:
                    if "lattes" in campo.lower() or "lattes" in str(valor).lower():
                        if st.button(f"🔗 {valor} (Clique para abrir a aba Lattes)", key=f"btn_lattes_{campo}", type="secondary"):
                            st.session_state.aba_atual = "👤 Lattes"
                            st.rerun()
                    else:
                        st.write(valor)

            st.markdown("---")
            st.write("#### 📝 Dados do Projeto")
            st.dataframe(
                pd.DataFrame(list(dados["dados_projeto"].items()), columns=["Campo", "Valor"]),
                use_container_width=True, hide_index=True,
            )
            if "dados_estudante" in dados:
                st.markdown("---")
                st.write("#### 🎓 Estudante")
                st.table(pd.DataFrame(list(dados["dados_estudante"].items()), columns=["Campo", "Valor"]))
        else:
            st.warning("Formulário não encontrado.")

    # ── ABA: Lattes ───────────────────────────────────────────────────
    elif st.session_state.aba_atual == "👤 Lattes":
        st.subheader("Extração do Currículo Lattes")
        caminho_lattes = os.path.join(caminho_proposta, "lattes.xml")
        if os.path.exists(caminho_lattes):
            try:
                tree = ET.parse(caminho_lattes)
                root = tree.getroot()

                gerais = root.find("DADOS-GERAIS")
                if gerais is not None:
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("Nome", gerais.get("NOME-COMPLETO", "N/A"))
                    col_b.metric("CPF", gerais.get("CPF", "N/A"))
                    col_c.metric("Naturalidade", gerais.get("CIDADE-NASCIMENTO", "N/A"))

                formacao = root.find(".//FORMACAO-ACADEMICA-TITULACAO")
                if formacao is not None:
                    st.markdown("#### 🎓 Formação Acadêmica")
                    titulos = []
                    for nivel in ["DOUTORADO", "MESTRADO", "ESPECIALIZACAO", "GRADUACAO"]:
                        for el in formacao.findall(nivel):
                            titulos.append({
                                "Nível":            nivel.capitalize(),
                                "Instituição":      el.get("NOME-INSTITUICAO", "N/A"),
                                "Curso":            el.get("NOME-CURSO", "N/A"),
                                "Ano de conclusão": el.get("ANO-DE-CONCLUSAO", "N/A"),
                            })
                    if titulos:
                        st.dataframe(pd.DataFrame(titulos), use_container_width=True, hide_index=True)

                atuacoes = root.findall(".//ATUACAO-PROFISSIONAL")
                if atuacoes:
                    st.markdown("#### 🏛️ Atuação Profissional")
                    st.dataframe(
                        pd.DataFrame([{"Instituição": a.get("NOME-INSTITUICAO", "N/A"), "Vínculo": a.get("TIPO-VINCULO", "N/A")} for a in atuacoes]),
                        use_container_width=True, hide_index=True,
                    )

                artigos = root.findall(".//ARTIGO-PUBLICADO")
                if artigos:
                    st.markdown(f"#### 📚 Artigos Publicados ({len(artigos)} encontrados)")
                    lista_art = []
                    for art in artigos[:10]:
                        d = art.find("DADOS-BASICOS-DO-ARTIGO")
                        det = art.find("DETALHAMENTO-DO-ARTIGO")
                        if d is not None:
                            lista_art.append({
                                "Título":    d.get("TITULO-DO-ARTIGO", "N/A"),
                                "Ano":       d.get("ANO-DO-ARTIGO", "N/A"),
                                "Periódico": det.get("TITULO-DO-PERIODICO-OU-REVISTA", "N/A") if det is not None else "N/A",
                            })
                    st.dataframe(pd.DataFrame(lista_art), use_container_width=True, hide_index=True)
                    if len(artigos) > 10:
                        st.caption(f"Exibindo os 10 primeiros de {len(artigos)} artigos.")

                with st.expander("🔧 Ver XML Bruto (avançado)"):
                    with open(caminho_lattes, "r", encoding="ISO-8859-1") as f:
                        st.code(f.read(), language="xml")

            except Exception as e:
                st.error(f"Erro ao ler o XML do Lattes: {e}")
        else:
            st.warning("Arquivo Lattes XML não encontrado.")

    # ── ABA: Ficha de Pontuação ───────────────────────────────────────
    elif st.session_state.aba_atual == "📊 Ficha de Pontuação":
        st.subheader("Ficha de Pontuação Declarada")
        caminho_ficha = os.path.join(caminho_proposta, "ficha_pontuacao.xlsx")
        if os.path.exists(caminho_ficha):
            df_ficha = pd.read_excel(caminho_ficha).dropna(how="all", axis=1)
            st.dataframe(df_ficha, height=500, use_container_width=True)
        else:
            st.warning("Ficha de pontuação não encontrada.")

    # ── ABA: Base de Dados Interna ────────────────────────────────────
    elif st.session_state.aba_atual == "🗃️ Base de Dados Interna":
        st.subheader("Base de Dados Interna — Docente vinculado à proposta")
        dados_base = carregar_base_interna()

        if not dados_base:
            st.error(f"Base interna não encontrada em: {CAMINHO_DB}")
            return

        # Tenta encontrar CPF do coordenador
        cpf_coord = None
        caminho_json_parecer = os.path.join(caminho_proposta, f"{proposta_id}_parecer.json")
        if os.path.exists(caminho_json_parecer):
            try:
                with open(caminho_json_parecer, "r", encoding="utf-8") as f:
                    dados_parecer = json.load(f)
                cpf_coord = dados_parecer.get("cpf_coordenador") or dados_parecer.get("cpf")
            except Exception:
                pass
        if not cpf_coord:
            caminho_form = os.path.join(caminho_proposta, "formulario.json")
            if os.path.exists(caminho_form):
                try:
                    with open(caminho_form, "r", encoding="utf-8") as f:
                        dados_form = json.load(f)
                    for k, v in dados_form.get("dados_coordenador", {}).items():
                        if "cpf" in k.lower():
                            cpf_coord = str(v)
                            break
                except Exception:
                    pass

        docente = next((d for d in dados_base if d["cpf"] == cpf_coord), None)

        if docente:
            st.success(f"✅ Docente encontrado: CPF **{docente['cpf']}** — Unidade: **{docente['unidade_lotacao']}**")
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("SIAPE", docente["siape"])
            col_b.metric("Unidade", docente["unidade_lotacao"])
            col_c.metric("Pendências", len(docente["pendencias_propp"]))
            st.markdown("---")
            st.markdown("**📁 Projetos em Andamento**")
            if docente["projetos_em_andamento"]:
                st.dataframe(pd.DataFrame(docente["projetos_em_andamento"]), use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum projeto em andamento.")
            if docente["pendencias_propp"]:
                st.markdown("**⚠️ Pendências PROPP**")
                st.dataframe(pd.DataFrame(docente["pendencias_propp"]), use_container_width=True, hide_index=True)
            else:
                st.success("Sem pendências registradas.")
        else:
            st.warning("CPF do coordenador não encontrado na base interna. Exibindo base completa.")
            rows = [{"CPF": d["cpf"], "SIAPE": d["siape"], "Unidade": d["unidade_lotacao"],
                     "Pendências": len(d["pendencias_propp"]), "Projetos": len(d["projetos_em_andamento"])}
                    for d in dados_base]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ── ABA: Parecer Final ────────────────────────────────────────────
    elif st.session_state.aba_atual == "⚖️ Parecer Final":
        st.subheader("Laudo Técnico da Auditoria")
        caminho_md   = os.path.join(caminho_proposta, f"{proposta_id}_parecer.md")
        caminho_json = os.path.join(caminho_proposta, f"{proposta_id}_parecer.json")

        formato = st.radio("Formato de visualização:", ["📝 Markdown", "📄 JSON"], horizontal=True, key="fmt_parecer")

        if formato == "📝 Markdown":
            if os.path.exists(caminho_md):
                with open(caminho_md, "r", encoding="utf-8") as f:
                    st.markdown(f.read())
            else:
                st.info("Parecer em Markdown não disponível.")
        else:
            if os.path.exists(caminho_json):
                with open(caminho_json, "r", encoding="utf-8") as f:
                    dados_json = json.load(f)
                campos_simples   = {k: v for k, v in dados_json.items() if not isinstance(v, (list, dict))}
                campos_complexos = {k: v for k, v in dados_json.items() if isinstance(v, (list, dict))}
                if campos_simples:
                    st.dataframe(
                        pd.DataFrame([{"Campo": k.replace("_", " ").title(), "Valor": str(v)} for k, v in campos_simples.items()]),
                        use_container_width=True, hide_index=True,
                    )
                for k, v in campos_complexos.items():
                    st.markdown(f"**{k.replace('_', ' ').title()}:**")
                    if isinstance(v, list) and v and isinstance(v[0], dict):
                        colunas = list(v[0].keys())
                        header  = "".join(f'<th style="background:#007BC0;color:#fff;padding:8px 12px;text-align:left;font-size:13px">{c}</th>' for c in colunas)
                        rows    = ""
                        for i, item in enumerate(v):
                            bg    = "#f0f4f8" if i % 2 == 0 else "#ffffff"
                            cells = "".join(
                                f'<td style="padding:8px 12px;font-size:13px;vertical-align:top;border-bottom:1px solid #dee2e6;white-space:pre-wrap;word-break:break-word">{str(item.get(c,""))}</td>'
                                for c in colunas
                            )
                            rows += f'<tr style="background:{bg}">{cells}</tr>'
                        st.markdown(
                            f'<div style="overflow-x:auto;border-radius:6px;border:1px solid #dee2e6">'
                            f'<table style="width:100%;border-collapse:collapse">'
                            f'<thead><tr>{header}</tr></thead><tbody>{rows}</tbody></table></div>',
                            unsafe_allow_html=True,
                        )
                    elif isinstance(v, list):
                        st.dataframe(pd.DataFrame({"Valor": v}), use_container_width=True, hide_index=True)
                    else:
                        st.dataframe(pd.DataFrame([v]), use_container_width=True, hide_index=True)
            else:
                st.info("Parecer em JSON não disponível.")

    # ── ABA: E-mail ───────────────────────────────────────────────────
    elif st.session_state.aba_atual == "✉️ E-mail":
        st.subheader("E-mail de Devolutiva")
        nome_coord_email = get_coordenador_email(proposta_id)

        arquivo_encontrado = None
        if nome_coord_email and os.path.exists(PASTA_OUTPUTS):
            for arq in os.listdir(PASTA_OUTPUTS):
                if arq.startswith("EMAIL_") and arq.endswith(".txt"):
                    nome_arq = arq.replace("EMAIL_", "").replace(".txt", "")
                    if nome_coord_email in nome_arq or nome_arq in nome_coord_email:
                        arquivo_encontrado = arq.replace("EMAIL_", "").replace(".txt", "").replace("_", " ")
                        break

        if arquivo_encontrado:
            st.info(f"E-mail consolidado disponível para o coordenador **{arquivo_encontrado.title()}**.")
            if st.button("✉️ Abrir na Central de Comunicação", type="primary", use_container_width=True):
                st.session_state.email_coordenador     = arquivo_encontrado
                st.session_state.proposta_origem_email = proposta_id
                st.session_state.proposta_selecionada  = None
                st.session_state.menu                  = "✉️ Central de Comunicação"
                st.rerun()
        else:
            st.warning("E-mail não encontrado. Execute o back-end para gerar os e-mails.")

    # ── ABA: Revisão Humana ───────────────────────────────────────────
    elif st.session_state.aba_atual == "✅ Revisão Humana":
        st.subheader("Registrar Decisão Humana")
        st.caption("A decisão final é sempre de responsabilidade da equipe humana.")

        caminho_json  = os.path.join(caminho_proposta, f"{proposta_id}_parecer.json")
        status_agente = "N/A"
        coordenador   = "N/A"
        if os.path.exists(caminho_json):
            with open(caminho_json, "r", encoding="utf-8") as f:
                dados_parecer = json.load(f)
            status_agente = dados_parecer.get("status_final", "N/A")
            coordenador   = dados_parecer.get("coordenador", "N/A")
            cor = "🟢" if "ENQUADRADA" in status_agente and "NÃO" not in status_agente else "🔴"
            st.info(f"**Sugestão do agente:** {cor} {status_agente}")

        revisoes          = carregar_revisoes()
        revisao_existente = next((r for r in revisoes if r["id_proposta"] == proposta_id), None)

        if revisao_existente:
            st.success(f"✅ Revisada em {revisao_existente['data_hora']} — Decisão: **{revisao_existente['decisao']}**")
            if revisao_existente.get("observacao"):
                st.markdown(f"**Observação:** {revisao_existente['observacao']}")
            if st.button("🔄 Alterar decisão"):
                revisoes = [r for r in revisoes if r["id_proposta"] != proposta_id]
                with open(ARQUIVO_REVISOES, "w", encoding="utf-8") as f:
                    json.dump(revisoes, f, indent=4, ensure_ascii=False)
                st.rerun()
        else:
            observacao = st.text_area("Observação (opcional):", placeholder="Adicione um comentário...")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Confirmar sugestão do agente", use_container_width=True, type="primary"):
                    salvar_revisao(proposta_id, coordenador, status_agente, "CONFIRMADO", observacao)
                    st.success("Decisão registrada!")
                    st.rerun()
            with col2:
                if st.button("❌ Encaminhar para revisão manual", use_container_width=True):
                    salvar_revisao(proposta_id, coordenador, status_agente, "REVISÃO MANUAL", observacao)
                    st.success("Encaminhada para revisão manual!")
                    st.rerun()


# =====================================================================
# ROTEAMENTO PRINCIPAL
# =====================================================================
if st.session_state.proposta_selecionada:
    mostrar_detalhes(
        st.session_state.proposta_selecionada,
        voltar_para=st.session_state.get("menu_origem", "🏠 Tela Inicial (Kanban)"),
    )
    st.stop()

# =====================================================================
# TELA 0: HOME / KANBAN
# =====================================================================
if menu == "🏠 Tela Inicial (Kanban)":

    st.markdown("""
        <p style="color:#007BC0;font-size:5.5rem;margin:0 0 4px 0;font-family:'Segoe UI',Arial,sans-serif;font-weight:800;line-height:1.1;">PROPP</p>
        <p style="font-size:2rem;margin:0 0 30px 0;font-weight:400;font-family:'Segoe UI',Arial,sans-serif;">Pró-Reitoria de Pesquisa e Pós-Graduação</p>
    """, unsafe_allow_html=True)

    usuario_logado = st.session_state.get("usuario_logado", "")
    nome_usuario   = usuario_logado.split("@")[0].replace(".", " ").title() if usuario_logado else "Usuário"
    st.markdown(f"### Olá, {nome_usuario}!")
    st.markdown("Bem-vindo ao **Sistema de Orquestração e Auditoria de Editais (SIGProj-AI)**.")

    revisoes_feitas = {r["id_proposta"] for r in carregar_revisoes()}
    pendentes = 0
    if os.path.exists(CAMINHO_EXCEL):
        try:
            df_pend = pd.read_excel(CAMINHO_EXCEL, sheet_name="Resumo Propostas")
            pendentes = len([r for _, r in df_pend.iterrows() if r["ID da Proposta"] not in revisoes_feitas])
        except Exception:
            pass

    if pendentes > 0:
        st.warning(f"⏳ **{pendentes} proposta(s) aguardando revisão humana.**")
    else:
        st.success("✅ Todas as propostas processadas já foram revisadas.")

    st.divider()
    st.subheader("🗂️ Fluxo de Trabalho (Edital IC&T 2026)")

    col_todo, col_done, col_rev = st.columns(3)

    with col_todo:
        st.markdown("#### 📥 Para Analisar")
        st.caption("Clique para ver os detalhes")
        st.markdown('<div style="height:38px"></div>', unsafe_allow_html=True)
        # Propostas ainda sem parecer gerado
        propostas_sem_parecer = []
        if os.path.exists(PASTA_PROPOSTAS):
            for p in sorted(os.listdir(PASTA_PROPOSTAS)):
                if not p.startswith("PROPOSTA_"):
                    continue
                caminho_p = os.path.join(PASTA_PROPOSTAS, p)
                if not os.path.isdir(caminho_p):
                    continue
                if not os.path.exists(os.path.join(caminho_p, f"{p}_parecer.json")):
                    propostas_sem_parecer.append(p)

        with st.container(border=True, height=420):
            if propostas_sem_parecer:
                for p in propostas_sem_parecer[:10]:
                    with st.container(border=True):
                        st.markdown(f"📄 **{p}**")
                        st.caption(obter_nome_coordenador(p))
                        if st.button("🔍 Ver detalhes", key=f"todo_{p}"):
                            st.session_state.proposta_selecionada = p
                            st.session_state.menu_origem = "🏠 Tela Inicial (Kanban)"
                            st.rerun()
            else:
                st.info("Nenhuma proposta aguardando análise.")

        # Botão para executar o backend (run_batch.py)
        if st.button("▶️ Executar Fila no LangGraph", type="primary", use_container_width=True):
            if os.path.exists(RUN_BATCH_PATH):
                with st.spinner("Executando o agente... Aguarde."):
                    resultado = subprocess.run(
                        [sys.executable, RUN_BATCH_PATH],
                        capture_output=True,
                        text=True,
                        cwd=BASE_DIR,
                        env={**os.environ, "PYTHONPATH": BASE_DIR},
                    )
                if resultado.returncode == 0:
                    st.success("✅ Processamento concluído com sucesso!")
                    with st.expander("Ver log de execução"):
                        st.code(resultado.stdout)
                else:
                    st.error("❌ Erro durante o processamento.")
                    with st.expander("Ver log de erro"):
                        st.code(resultado.stderr)
            else:
                st.error(f"run_batch.py não encontrado em: {RUN_BATCH_PATH}")

    with col_done:
        st.markdown("#### ✅ Analisadas")
        st.caption("Aguardando revisão humana")
        filtro = st.selectbox("Filtrar:", ["Todos", "ENQUADRADA", "NÃO ENQUADRADA"], key="filtro_kanban")
        if os.path.exists(CAMINHO_EXCEL):
            try:
                df = pd.read_excel(CAMINHO_EXCEL, sheet_name="Resumo Propostas")
                if filtro != "Todos":
                    df = df[df["Status Final"] == filtro]
                df_pendentes = df[~df["ID da Proposta"].isin(revisoes_feitas)]
                if df_pendentes.empty:
                    st.info("Nenhuma proposta pendente de revisão.")
                else:
                    with st.container(border=True, height=420):
                        for _, row in df_pendentes.iterrows():
                            id_prop = row["ID da Proposta"]
                            cor     = "🟢" if row["Status Final"] == "ENQUADRADA" else "🔴"
                            with st.container(border=True):
                                st.markdown(f"📄 **{id_prop}**")
                                st.markdown(f"{cor} {row['Status Final']}")
                                st.caption(row["Coordenador"])
                                if st.button("✉️ Ver detalhes - E-mail", key=f"done_{id_prop}"):
                                    st.session_state.proposta_selecionada = id_prop
                                    st.session_state.aba_atual = "✉️ E-mail"
                                    st.session_state.menu_origem = "🏠 Tela Inicial (Kanban)"
                                    st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")
        else:
            st.info("Nenhum processo finalizado ainda.")

    with col_rev:
        st.markdown("#### 📋 Revisadas")
        st.caption("Decisão humana registrada")
        st.markdown('<div style="height:38px"></div>', unsafe_allow_html=True)
        if os.path.exists(CAMINHO_EXCEL) and revisoes_feitas:
            try:
                df = pd.read_excel(CAMINHO_EXCEL, sheet_name="Resumo Propostas")
                df_revisadas  = df[df["ID da Proposta"].isin(revisoes_feitas)]
                revisoes_dict = {r["id_proposta"]: r for r in carregar_revisoes()}
                if df_revisadas.empty:
                    st.info("Nenhuma proposta revisada ainda.")
                else:
                    with st.container(border=True, height=420):
                        for _, row in df_revisadas.iterrows():
                            id_prop   = row["ID da Proposta"]
                            revisao   = revisoes_dict.get(id_prop, {})
                            decisao   = revisao.get("decisao", "")
                            cor       = "🟢" if row["Status Final"] == "ENQUADRADA" else "🔴"
                            icone_dec = "✅" if decisao == "CONFIRMADO" else "🔄"
                            with st.container(border=True):
                                st.markdown(f"📄 **{id_prop}**")
                                st.markdown(f"{cor} {row['Status Final']}")
                                st.markdown(f"{icone_dec} {decisao}")
                                st.caption(row["Coordenador"])
                                if st.button("✅ Ver detalhes e Revisão", key=f"rev_{id_prop}"):
                                    st.session_state.proposta_selecionada = id_prop
                                    st.session_state.aba_atual = "✅ Revisão Humana"
                                    st.session_state.menu_origem = "🏠 Tela Inicial (Kanban)"
                                    st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")
        else:
            st.info("Nenhuma proposta revisada ainda.")

    st.divider()
    st.subheader("⚡ Ações Rápidas")
    st.link_button("📄 Abrir Edital IC&T (PDF)", URL_EDITAL, use_container_width=True)

    html_rel = exportar_relatorio_html()
    if html_rel:
        st.download_button(
            label="📥 Exportar Relatório (HTML/PDF)",
            data=html_rel.encode("utf-8"),
            file_name=f"relatorio_enquadramento_{datetime.now().strftime('%Y%m%d_%H%M')}.html",
            mime="text/html",
            use_container_width=True,
        )
    else:
        st.button("📥 Exportar Relatório (execute o back-end primeiro)", disabled=True, use_container_width=True)

    html_stats = exportar_estatisticas_html()
    if html_stats:
        st.download_button(
            label="📊 Exportar Estatísticas de Erros (HTML)",
            data=html_stats.encode("utf-8"),
            file_name=f"estatisticas_erros_{datetime.now().strftime('%Y%m%d_%H%M')}.html",
            mime="text/html",
            use_container_width=True,
        )
    else:
        st.button("📊 Exportar Estatísticas (execute o back-end primeiro)", disabled=True, use_container_width=True)

    st.divider()
    st.subheader("📋 Log de Rastreabilidade")
    st.caption("Registro das ações realizadas pelos agentes de IA e pela equipe humana.")

    entradas_log = []

    # Revisões humanas
    for r in sorted(carregar_revisoes(), key=lambda x: x.get("data_hora", ""), reverse=True):
        icone = "✅" if r.get("decisao") == "CONFIRMADO" else "🔄"
        entradas_log.append({
            "Data/Hora": r.get("data_hora", "—"),
            "Módulo":    "Revisão Humana",
            "Ação":      f"{icone} {r.get('decisao','')} — {r.get('id_proposta','')} ({r.get('coordenador','')})",
        })

    # Pareceres gerados pelo agente (lê *_parecer.json de cada proposta em data/)
    if os.path.exists(PASTA_PROPOSTAS):
        for pasta in sorted(os.listdir(PASTA_PROPOSTAS), reverse=True):
            if not pasta.startswith("PROPOSTA_"):
                continue
            caminho_p = os.path.join(PASTA_PROPOSTAS, pasta)
            if not os.path.isdir(caminho_p):
                continue
            for arq in os.listdir(caminho_p):
                if arq.endswith("_parecer.json"):
                    try:
                        with open(os.path.join(caminho_p, arq), "r", encoding="utf-8") as f:
                            dados_p = json.load(f)
                        status = dados_p.get("status_final", "—")
                        coord  = dados_p.get("coordenador", "—")
                        data   = dados_p.get("data_processamento", "—")
                        icone  = "🟢" if "ENQUADRADA" in status and "NÃO" not in status else "🔴"
                        entradas_log.append({
                            "Data/Hora": data,
                            "Módulo":    "Motor de Inferência",
                            "Ação":      f"{icone} Parecer gerado — {pasta} | {coord} | {status}",
                        })
                    except Exception:
                        pass

    # Logs estruturados do pipeline (outputs/logs/*.jsonl)
    log_dir = os.path.join(PASTA_OUTPUTS, "logs")
    if os.path.exists(log_dir):
        for arq_log in sorted(os.listdir(log_dir), reverse=True)[:3]:  # últimos 3 arquivos
            caminho_log = os.path.join(log_dir, arq_log)
            try:
                with open(caminho_log, "r", encoding="utf-8") as f:
                    for linha in f:
                        try:
                            entrada = json.loads(linha.strip())
                            event   = entrada.get("event", "")
                            # Exibe apenas eventos relevantes para o log de rastreabilidade
                            if event in ("pipeline.start", "pipeline.summary", "proposal.done", "proposal.error"):
                                entradas_log.append({
                                    "Data/Hora": entrada.get("timestamp", "—")[:19].replace("T", " "),
                                    "Módulo":    f"Pipeline [{entrada.get('execution_id','')[:16]}]",
                                    "Ação":      f"{event} — {json.dumps({k: v for k, v in entrada.items() if k not in ('timestamp','execution_id','level','event')}, ensure_ascii=False)}",
                                })
                        except Exception:
                            pass
            except Exception:
                pass

    if entradas_log:
        st.dataframe(pd.DataFrame(entradas_log), use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma atividade registrada ainda. Execute o agente para gerar os primeiros registros.")

# =====================================================================
# TELA 1: DASHBOARD EXECUTIVO
# =====================================================================
elif menu == "📊 Dashboard Executivo":
    st.title("📊 Painel Gerencial de Impacto Institucional - PROPP")
    st.markdown("Monitoramento de submissões (IC&T), enquadramentos e alinhamento com as metas ESG / ODS da ONU.")
    st.divider()

    if not os.path.exists(CAMINHO_EXCEL):
        st.error(f"❌ Arquivo Excel não encontrado em: {CAMINHO_EXCEL}")
    else:
        try:
            df = pd.read_excel(CAMINHO_EXCEL, sheet_name="Resumo Propostas")
            total_propostas = len(df)
            aprovadas       = len(df[df["Status Final"] == "ENQUADRADA"])
            reprovadas      = total_propostas - aprovadas
            inovadores      = len(df[df["Inovação Tecnológica"] == "Sim"]) if "Inovação Tecnológica" in df.columns else 0
            patentes        = len(df[df["Gera Patente"] == "Sim"]) if "Gera Patente" in df.columns else 0

            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Total de Submissões", total_propostas)
            col2.metric("✅ Enquadradas", aprovadas)
            col3.metric("❌ Não Enquadradas", reprovadas)
            col4.metric("💡 Inovação", inovadores)
            col5.metric("📜 Patentes", patentes)

            st.markdown("<br>", unsafe_allow_html=True)
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                st.subheader("🌍 Impacto por ODS")
                if "ODS Vinculado" in df.columns:
                    df_ods = df["ODS Vinculado"].value_counts().reset_index()
                    df_ods.columns = ["ODS", "Quantidade"]
                    fig_ods = px.pie(df_ods, values="Quantidade", names="ODS", hole=0.4,
                                     color_discrete_sequence=px.colors.qualitative.Pastel)
                    st.plotly_chart(fig_ods, use_container_width=True)
                else:
                    st.warning("Coluna 'ODS Vinculado' não encontrada.")
            with col_g2:
                st.subheader("📚 Status por Área de Conhecimento")
                if "Área de Conhecimento" in df.columns:
                    df_area = df.groupby(["Área de Conhecimento", "Status Final"]).size().reset_index(name="Quantidade")
                    fig_area = px.bar(df_area, x="Área de Conhecimento", y="Quantidade", color="Status Final",
                                      barmode="group",
                                      color_discrete_map={"ENQUADRADA": "#2ecc71", "NÃO ENQUADRADA": "#e74c3c"})
                    st.plotly_chart(fig_area, use_container_width=True)
                else:
                    st.warning("Coluna 'Área de Conhecimento' não encontrada.")

            st.divider()
            st.subheader("🔬 Principais Temas de Pesquisa (Palavras-chave)")
            keywords_list = []
            if os.path.exists(PASTA_PROPOSTAS):
                for p in os.listdir(PASTA_PROPOSTAS):
                    if not p.startswith("PROPOSTA_"):
                        continue
                    caminho_form = os.path.join(PASTA_PROPOSTAS, p, "formulario.json")
                    if os.path.exists(caminho_form):
                        try:
                            with open(caminho_form, "r", encoding="utf-8") as f:
                                dados_json = json.load(f)
                            kws = dados_json.get("dados_projeto", {}).get("8_palavras_chave", [])
                            keywords_list.extend(kws)
                        except Exception:
                            pass
            if keywords_list:
                df_kw = pd.DataFrame(keywords_list, columns=["Tema"])
                df_kw_count = df_kw.value_counts().reset_index(name="Quantidade")
                df_kw_count = df_kw_count.sort_values(by="Quantidade", ascending=True).tail(10)
                fig_kw = px.bar(df_kw_count, x="Quantidade", y="Tema", orientation="h",
                                color="Quantidade", color_continuous_scale="Blues")
                fig_kw.update_layout(margin=dict(t=0, b=0, l=0, r=0), showlegend=False, yaxis_title="")
                st.plotly_chart(fig_kw, use_container_width=True)
            else:
                st.info("Nenhuma palavra-chave encontrada nas propostas.")

            st.divider()
            st.subheader("💡 Conclusões e Insights")
            c1, c2, c3 = st.columns(3)
            with c1:
                with st.expander("📈 Tendência de Impacto", expanded=True):
                    ods_p = df["ODS Vinculado"].mode()[0] if "ODS Vinculado" in df.columns else "N/A"
                    st.info(f"**ODS Predominante:** {ods_p}.\n\nForte alinhamento estratégico com metas sustentáveis e impacto regional.")
            with c2:
                with st.expander("🔍 Alerta de Qualidade", expanded=True):
                    taxa_erro = (reprovadas / total_propostas * 100) if total_propostas else 0
                    st.warning(f"**Taxa de Recusa:** {taxa_erro:.1f}%.\n\nIndica necessidade de workshops sobre preenchimento da Ficha de Pontuação.")
            with c3:
                with st.expander("🛡️ Propriedade Intelectual", expanded=True):
                    st.success(f"**Potencial de Patentes:** {patentes} projetos sinalizados.\n\nFortalece os indicadores de inovação e transferência de tecnologia.")
        except Exception as e:
            st.error(f"Erro no Dashboard: {e}")

# =====================================================================
# TELA 2: AUDITORIA DE PROPOSTAS
# =====================================================================
elif menu == "🔍 Auditoria de Propostas":
    st.title("🔍 Central de Auditoria Transparente")
    st.divider()

    if os.path.exists(PASTA_PROPOSTAS):
        pastas = sorted([
            p for p in os.listdir(PASTA_PROPOSTAS)
            if p.startswith("PROPOSTA_") and os.path.isdir(os.path.join(PASTA_PROPOSTAS, p))
        ])
        if pastas:
            mapa_opcoes = {f"{obter_nome_coordenador(p)} ({p})": p for p in pastas}
            coordenador_selecionado = st.selectbox("Selecione o coordenador para auditoria:", list(mapa_opcoes.keys()))
            proposta_escolhida = mapa_opcoes[coordenador_selecionado]
            if st.button("🔍 Abrir Auditoria Detalhada", type="primary", use_container_width=True):
                st.session_state.proposta_selecionada = proposta_escolhida
                st.session_state.menu_origem = "🔍 Auditoria de Propostas"
                st.rerun()
        else:
            st.warning("Nenhuma proposta encontrada em data/.")
    else:
        st.error(f"Diretório não encontrado: {PASTA_PROPOSTAS}")

# =====================================================================
# TELA 3: CENTRAL DE COMUNICAÇÃO
# =====================================================================
elif menu == "✉️ Central de Comunicação":
    st.title("✉️ Orquestração de Comunicados")
    st.divider()

    if os.path.exists(PASTA_OUTPUTS):
        arquivos_email = [f for f in os.listdir(PASTA_OUTPUTS) if f.startswith("EMAIL_") and f.endswith(".txt")]
        if arquivos_email:
            nomes = [f.replace("EMAIL_", "").replace(".txt", "").replace("_", " ") for f in arquivos_email]

            idx_default = 0
            if st.session_state.email_coordenador:
                nome_busca = st.session_state.email_coordenador
                for i, n in enumerate(nomes):
                    if nome_busca.upper() in n.upper() or n.upper() in nome_busca.upper():
                        idx_default = i
                        break

            coordenador_selecionado = st.selectbox("Selecione o coordenador:", nomes, index=idx_default)

            if st.session_state.get("proposta_origem_email"):
                id_prop_origem = st.session_state.proposta_origem_email
                if st.button(f"🔙 Voltar para Detalhes da {id_prop_origem}", type="secondary", use_container_width=True):
                    st.session_state.proposta_selecionada = id_prop_origem
                    st.session_state.menu = st.session_state.get("menu_origem", "🏠 Tela Inicial (Kanban)")
                    st.rerun()

            arquivo_alvo = f"EMAIL_{coordenador_selecionado.replace(' ', '_').upper()}.txt"
            caminho_email_completo = os.path.join(PASTA_OUTPUTS, arquivo_alvo)

            if os.path.exists(caminho_email_completo):
                with open(caminho_email_completo, "r", encoding="utf-8") as f:
                    conteudo_email = f.read()

                st.markdown("### 📝 Editar Conteúdo do Comunicado")
                st.caption("Você pode alterar qualquer trecho do e-mail gerado abaixo antes do envio oficial.")

                email_editado = st.text_area(
                    label="Corpo do E-mail:",
                    value=conteudo_email,
                    height=350,
                    key=f"editor_{arquivo_alvo}",
                )

                if st.button("💾 Salvar Alterações no Comunicado", type="primary", use_container_width=True):
                    try:
                        with open(caminho_email_completo, "w", encoding="utf-8") as f:
                            f.write(email_editado)
                        st.success("✅ Arquivo de comunicado atualizado e salvo com sucesso!")
                    except Exception as e:
                        st.error(f"❌ Erro ao salvar: {e}")

                st.divider()
                st.markdown("### 👁️ Pré-visualização Real (Como o docente receberá)")
                renderizar_email_html(email_editado)
            else:
                st.warning(f"Arquivo de e-mail não localizado: {arquivo_alvo}")
        else:
            st.info("Nenhum rascunho de e-mail localizado em outputs/.")
    else:
        st.error(f"Pasta de outputs não encontrada: {PASTA_OUTPUTS}")

# =====================================================================
# TELA 4: HISTÓRICO DE DECISÕES
# =====================================================================
elif menu == "📂 Histórico de Decisões":
    st.title("📂 Histórico de Decisões Auditadas")
    st.divider()
    revisoes_salvas = carregar_revisoes()
    if revisoes_salvas:
        st.dataframe(pd.DataFrame(revisoes_salvas), use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma revisão registrada até o momento.")

# =====================================================================
# TELA 5: BASE DE DADOS INTERNA
# =====================================================================
elif menu == "🗃️ Base de Dados Interna":
    st.title("🗃️ Base de Dados Interna")
    st.divider()

    dados_base = carregar_base_interna()
    if not dados_base:
        st.error(f"Base interna não encontrada em: {CAMINHO_DB}")
        st.stop()

    # Cruza CPF com nomes dos pareceres/formulários
    cpf_para_nome: dict = {}
    if os.path.exists(PASTA_PROPOSTAS):
        for pasta in os.listdir(PASTA_PROPOSTAS):
            if not pasta.startswith("PROPOSTA_"):
                continue
            caminho_p = os.path.join(PASTA_PROPOSTAS, pasta)
            if not os.path.isdir(caminho_p):
                continue
            for arq in os.listdir(caminho_p):
                if arq.endswith("_parecer.json"):
                    try:
                        with open(os.path.join(caminho_p, arq), "r", encoding="utf-8") as f:
                            pj = json.load(f)
                        cpf  = pj.get("cpf_coordenador") or pj.get("cpf")
                        nome = pj.get("coordenador") or pj.get("nome_coordenador")
                        if cpf and nome:
                            cpf_para_nome[cpf.strip()] = nome.strip().title()
                    except Exception:
                        pass
            caminho_form = os.path.join(caminho_p, "formulario.json")
            if os.path.exists(caminho_form):
                try:
                    with open(caminho_form, "r", encoding="utf-8") as f:
                        fj = json.load(f)
                    coord = fj.get("dados_coordenador", {})
                    cpf   = next((str(v) for k, v in coord.items() if "cpf" in k.lower()), None)
                    nome  = next((str(v) for k, v in coord.items() if "nome" in k.lower()), None)
                    if cpf and nome and cpf not in cpf_para_nome:
                        cpf_para_nome[cpf.strip()] = nome.strip().title()
                except Exception:
                    pass

    opcoes = ["Todos"] + [
        f"{d['cpf']} — {cpf_para_nome.get(d['cpf'], 'Nome não encontrado')}"
        for d in dados_base
    ]
    filtro_docente = st.selectbox("Selecione o docente — CPF:", opcoes, key="filtro_base_interna")

    dados_filtrados = dados_base if filtro_docente == "Todos" else [
        d for d in dados_base if d["cpf"] == filtro_docente.split(" — ")[0]
    ]

    st.markdown(f"**{len(dados_filtrados)} docente(s) exibido(s)**")
    rows_main = [{"CPF": d["cpf"], "SIAPE": d["siape"], "Unidade": d["unidade_lotacao"],
                  "Pendências": len(d["pendencias_propp"]), "Projetos em Andamento": len(d["projetos_em_andamento"])}
                 for d in dados_filtrados]
    st.dataframe(pd.DataFrame(rows_main), use_container_width=True, hide_index=True,
                 height=(len(rows_main) + 1) * 35 + 10)

    if filtro_docente != "Todos" and len(dados_filtrados) == 1:
        d = dados_filtrados[0]
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**📁 Projetos em Andamento**")
            if d["projetos_em_andamento"]:
                st.dataframe(pd.DataFrame(d["projetos_em_andamento"]), use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum projeto em andamento.")
        with col2:
            st.markdown("**⚠️ Pendências PROPP**")
            if d["pendencias_propp"]:
                st.dataframe(pd.DataFrame(d["pendencias_propp"]), use_container_width=True, hide_index=True)
            else:
                st.success("Sem pendências registradas.")
