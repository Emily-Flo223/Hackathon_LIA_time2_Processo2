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
# 2. AUTENTICAÇÃO
# =====================================================================
USUARIOS_VALIDOS = {
    "admin@propp.ufms.br":   "propp2025",
    "auditor@propp.ufms.br": "auditoria123",
}

def tela_login():
    st.markdown("""
        <style>.login-container{max-width:420px;margin:60px auto 0 auto;}</style>
    """, unsafe_allow_html=True)
    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        st.markdown("## 🎓 PROPP — Sistema de Auditoria")
        st.markdown("##### Acesso Restrito — Informe suas credenciais")
        st.divider()
        email = st.text_input("📧 E-mail", placeholder="seu@email.com")
        senha = st.text_input("🔒 Senha", type="password", placeholder="••••••••")
        if st.button("Entrar", type="primary", use_container_width=True):
            if email in USUARIOS_VALIDOS and USUARIOS_VALIDOS[email] == senha:
                st.session_state.autenticado   = True
                st.session_state.usuario_logado = email
                st.rerun()
            else:
                st.error("❌ E-mail ou senha incorretos.")
        st.caption("Sistema interno — acesso não autorizado é proibido.")

st.session_state.setdefault("autenticado",    False)
st.session_state.setdefault("usuario_logado", None)

if not st.session_state.autenticado:
    tela_login()
    st.stop()

# =====================================================================
# 3. CAMINHOS  — tudo relativo à raiz do projeto
# =====================================================================
BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
PASTA_PROPOSTAS  = os.path.join(BASE_DIR, "data")                       # data/PROPOSTA_*/
CAMINHO_DB       = os.path.join(BASE_DIR, "data", "internal_database.json")
PASTA_OUTPUTS    = os.path.join(BASE_DIR, "outputs")
CAMINHO_EXCEL    = os.path.join(PASTA_OUTPUTS, "estatisticas_enquadramento.xlsx")
ARQUIVO_REVISOES = os.path.join(PASTA_OUTPUTS, "historico_revisoes.json")
RUN_BATCH_PATH   = os.path.join(BASE_DIR, "run_batch.py")
URL_EDITAL       = "https://www.ufms.br/wp-content/uploads/2025/07/EDITAL-PROPP_RTR-n-215-de-18-07-2025..pdf"

# Garante que outputs/ sempre existe
os.makedirs(PASTA_OUTPUTS, exist_ok=True)

# =====================================================================
# 4. ESTADO DE NAVEGAÇÃO
# =====================================================================
st.session_state.setdefault("menu",                  "🏠 Tela Inicial (Kanban)")
st.session_state.setdefault("proposta_selecionada",  None)
st.session_state.setdefault("email_coordenador",     None)
st.session_state.setdefault("proposta_origem_email", None)
st.session_state.setdefault("menu_origem",           "🏠 Tela Inicial (Kanban)")
st.session_state.setdefault("aba_atual",             "📋 Formulário")

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
# _menu_redirect permite que código (botão Voltar, etc.) mude a aba
# sem conflitar com o widget já instanciado.
if "_menu_redirect" in st.session_state:
    destino = st.session_state.pop("_menu_redirect")
    if destino in menu_opcoes:
        st.session_state.menu = destino

menu = st.sidebar.radio(
    "Navegue pelas funcionalidades:",
    menu_opcoes,
    key="menu",
    index=menu_opcoes.index(st.session_state.get("menu", menu_opcoes[0]))
          if st.session_state.get("menu") in menu_opcoes else 0,
)
# Limpa a proposta selecionada quando o usuário navega pelo menu lateral.
# Usa um flag para distinguir navegação de menu vs rerun gerado pelo botão "Ver detalhes".
_menu_anterior = st.session_state.get("_menu_anterior", menu)
if menu != _menu_anterior:
    # O usuário clicou em outra aba do menu — limpa o contexto
    st.session_state.proposta_selecionada  = None
    st.session_state.aba_atual             = "📋 Formulário"
    st.session_state.email_coordenador     = None
    st.session_state.proposta_origem_email = None
st.session_state["_menu_anterior"] = menu

st.sidebar.divider()
st.sidebar.info("Desenvolvido para otimização, transparência e inovação na gestão pública de editais.")
st.sidebar.caption(f"👤 {st.session_state.get('usuario_logado', '')}")
if st.sidebar.button("🚪 Sair", use_container_width=True):
    st.session_state.autenticado    = False
    st.session_state.usuario_logado = None
    st.rerun()

# =====================================================================
# HELPERS
# =====================================================================

def listar_propostas() -> list[str]:
    """Retorna lista ordenada de IDs de proposta encontrados em data/."""
    if not os.path.exists(PASTA_PROPOSTAS):
        return []
    return sorted([
        p for p in os.listdir(PASTA_PROPOSTAS)
        if p.startswith("PROPOSTA_") and os.path.isdir(os.path.join(PASTA_PROPOSTAS, p))
    ])


def carregar_base_interna() -> list:
    if os.path.exists(CAMINHO_DB):
        try:
            with open(CAMINHO_DB, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def carregar_revisoes() -> list:
    if os.path.exists(ARQUIVO_REVISOES):
        try:
            with open(ARQUIVO_REVISOES, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
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
    with open(ARQUIVO_REVISOES, "w", encoding="utf-8") as f:
        json.dump(revisoes, f, indent=4, ensure_ascii=False)


def obter_nome_coordenador(proposta_id: str) -> str:
    """Retorna o nome do coordenador para exibição nos seletores."""
    # 1. Tenta no parecer gerado
    caminho_json = os.path.join(PASTA_PROPOSTAS, proposta_id, f"{proposta_id}_parecer.json")
    if os.path.exists(caminho_json):
        try:
            with open(caminho_json, "r", encoding="utf-8") as f:
                nome = json.load(f).get("coordenador", "")
            if nome:
                return nome.title()
        except Exception:
            pass
    # 2. Tenta no formulário
    caminho_form = os.path.join(PASTA_PROPOSTAS, proposta_id, "formulario.json")
    if os.path.exists(caminho_form):
        try:
            with open(caminho_form, "r", encoding="utf-8") as f:
                dados = json.load(f)
            nome = dados.get("dados_coordenador", {}).get("nome", "")
            if nome:
                return nome.title()
        except Exception:
            pass
    return "Coordenador Desconhecido"


def obter_cpf_coordenador(proposta_id: str) -> str | None:
    """Retorna o CPF do coordenador lendo o formulario.json."""
    caminho_form = os.path.join(PASTA_PROPOSTAS, proposta_id, "formulario.json")
    if not os.path.exists(caminho_form):
        return None
    try:
        with open(caminho_form, "r", encoding="utf-8") as f:
            dados = json.load(f)
        return dados.get("dados_coordenador", {}).get("6_cpf")
    except Exception:
        return None


def get_arquivo_email(proposta_id: str) -> str | None:
    """
    Retorna o caminho completo do arquivo EMAIL_*.txt correspondente
    ao coordenador desta proposta, ou None se não encontrado.
    """
    nome_coord = obter_nome_coordenador(proposta_id)
    if not nome_coord or nome_coord == "Coordenador Desconhecido":
        return None
    # Nome do arquivo: EMAIL_NOME_SOBRENOME.txt (uppercase, underscore)
    nome_chave = nome_coord.upper().replace(" ", "_")
    caminho = os.path.join(PASTA_OUTPUTS, f"EMAIL_{nome_chave}.txt")
    if os.path.exists(caminho):
        return caminho
    # Busca fuzzy: percorre outputs/ procurando sobreposição de nomes
    if os.path.exists(PASTA_OUTPUTS):
        for arq in os.listdir(PASTA_OUTPUTS):
            if arq.startswith("EMAIL_") and arq.endswith(".txt"):
                nome_arq = arq.replace("EMAIL_", "").replace(".txt", "")
                # verifica se os tokens do nome batem
                partes_coord = set(nome_chave.split("_"))
                partes_arq   = set(nome_arq.split("_"))
                if len(partes_coord & partes_arq) >= min(2, len(partes_coord)):
                    return os.path.join(PASTA_OUTPUTS, arq)
    return None


def renderizar_email_html(conteudo: str):
    """
    Renderiza o conteúdo do email no Streamlit.
    Detecta automaticamente se o conteúdo é HTML ou texto puro.
    """
    tem_html = bool(re.search(r'<(strong|br|div|p|u|h[1-6])\b', conteudo, re.IGNORECASE))
    if tem_html:
        # Já é HTML — renderiza direto
        html = conteudo
    else:
        # Texto puro — formata emojis de marcação e converte quebras
        conteudo = re.sub(r'(?<!\n)(📌)', r'\n\1', conteudo)
        conteudo = re.sub(r'(?<!\n)(🔎)', r'\n\1', conteudo)
        html = conteudo.replace('\n', '<br>')

    st.markdown(
        f'<div style="background:#f8f9fa;border:1px solid #dee2e6;border-radius:8px;'
        f'padding:20px;font-family:Arial,sans-serif;font-size:14px;'
        f'line-height:1.9;color:#212529">{html}</div>',
        unsafe_allow_html=True,
    )


def exportar_relatorio_html() -> str | None:
    if not os.path.exists(CAMINHO_EXCEL):
        return None
    try:
        df = pd.read_excel(CAMINHO_EXCEL, sheet_name="Resumo Propostas")
    except Exception:
        return None
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
    <title>Relatório PROPP</title>
    <style>body{{font-family:Arial;padding:30px}}h1{{color:#007BC0}}
    table{{width:100%;border-collapse:collapse;margin-top:20px}}
    th{{background:#007BC0;color:white;padding:8px;text-align:left}}
    td{{padding:8px;border-bottom:1px solid #ddd}}
    .card{{display:inline-block;padding:15px;border-radius:8px;text-align:center;min-width:120px;margin:5px}}</style>
    </head><body>
    <h1>PROPP — Relatório de Enquadramento IC&T 2026</h1>
    <p>Gerado em: {datetime.now().strftime("%d/%m/%Y às %H:%M")}</p>
    <div>
      <div class="card" style="background:#e8f4fd"><strong>{total}</strong><br>Total</div>
      <div class="card" style="background:#d4edda"><strong>{enquadradas}</strong><br>Enquadradas</div>
      <div class="card" style="background:#f8d7da"><strong>{nao_enquadradas}</strong><br>Não Enquadradas</div>
    </div>
    <table><tr><th>ID</th><th>Coordenador</th><th>Unidade</th><th>Status</th><th>Inconformidades</th></tr>
    {linhas}</table></body></html>"""


def exportar_estatisticas_html() -> str | None:
    if not os.path.exists(CAMINHO_EXCEL):
        return None
    try:
        df = pd.read_excel(CAMINHO_EXCEL, sheet_name="Estatísticas de Erros")
    except Exception:
        return None
    linhas     = "".join("<tr>" + "".join(f"<td>{v}</td>" for v in row.values) + "</tr>" for _, row in df.iterrows())
    cabecalhos = "".join(f"<th>{c}</th>" for c in df.columns)
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
    <title>Estatísticas - PROPP</title>
    <style>body{{font-family:Arial;padding:30px}}h1{{color:#007BC0}}
    table{{width:100%;border-collapse:collapse;margin-top:20px}}
    th{{background:#007BC0;color:white;padding:8px;text-align:left}}
    td{{padding:8px;border-bottom:1px solid #ddd}}</style>
    </head><body>
    <h1>PROPP — Estatísticas de Erros</h1>
    <p>Gerado em: {datetime.now().strftime("%d/%m/%Y às %H:%M")}</p>
    <table><tr>{cabecalhos}</tr>{linhas}</table></body></html>"""


# =====================================================================
# TELA DE DETALHES DE UMA PROPOSTA
# =====================================================================
def mostrar_detalhes(proposta_id: str, voltar_para: str = "🏠 Tela Inicial (Kanban)"):
    if st.button("← Voltar"):
        st.session_state.proposta_selecionada = None
        st.session_state.aba_atual = "📋 Formulário"
        st.session_state["_menu_redirect"] = voltar_para
        st.rerun()

    st.title(f"🔍 Detalhes Completos — {proposta_id}")
    st.divider()

    caminho_proposta = os.path.join(PASTA_PROPOSTAS, proposta_id)
    if not os.path.exists(caminho_proposta):
        st.error(f"Pasta da proposta não encontrada: {caminho_proposta}")
        return

    abas = ["📋 Formulário", "👤 Lattes", "📊 Ficha de Pontuação",
            "🗃️ Base de Dados Interna", "⚖️ Parecer Final", "✉️ E-mail", "✅ Revisão Humana"]
    cols = st.columns(len(abas))
    for idx, titulo in enumerate(abas):
        with cols[idx]:
            tipo = "primary" if st.session_state.aba_atual == titulo else "secondary"
            if st.button(titulo, key=f"tab_{idx}_{proposta_id}", type=tipo, use_container_width=True):
                st.session_state.aba_atual = titulo
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    aba = st.session_state.aba_atual

    # ── Formulário ────────────────────────────────────────────────────
    if aba == "📋 Formulário":
        st.subheader("Dados do Formulário de Submissão")
        caminho_form = os.path.join(caminho_proposta, "formulario.json")
        if not os.path.exists(caminho_form):
            st.warning("formulario.json não encontrado.")
            return
        with open(caminho_form, "r", encoding="utf-8") as f:
            dados = json.load(f)

        st.write("#### 👨‍🏫 Dados do Coordenador")
        for campo, valor in dados.get("dados_coordenador", {}).items():
            c1, c2 = st.columns([1, 3])
            with c1:
                st.markdown(f"**{campo.replace('_', ' ').title()}:**")
            with c2:
                if "lattes" in campo.lower() or "lattes" in str(valor).lower():
                    if st.button(f"🔗 Abrir aba Lattes", key=f"btn_lattes_{campo}_{proposta_id}", type="secondary"):
                        st.session_state.aba_atual = "👤 Lattes"
                        st.rerun()
                else:
                    st.write(valor)

        st.markdown("---")
        st.write("#### 📝 Dados do Projeto")
        proj = dados.get("dados_projeto", {})
        # Renderiza campos simples em tabela, campos complexos separados
        simples   = {k: v for k, v in proj.items() if not isinstance(v, (list, dict))}
        complexos = {k: v for k, v in proj.items() if isinstance(v, (list, dict))}
        if simples:
            st.dataframe(pd.DataFrame(list(simples.items()), columns=["Campo", "Valor"]),
                         use_container_width=True, hide_index=True)
        for k, v in complexos.items():
            st.markdown(f"**{k.replace('_', ' ').title()}:**")
            if isinstance(v, list) and v and isinstance(v[0], dict):
                st.dataframe(pd.DataFrame(v), use_container_width=True, hide_index=True)
            elif isinstance(v, list):
                st.write(", ".join(str(i) for i in v))
            else:
                st.json(v)

        if "dados_estudante" in dados:
            st.markdown("---")
            st.write("#### 🎓 Estudante")
            st.table(pd.DataFrame(list(dados["dados_estudante"].items()), columns=["Campo", "Valor"]))

    # ── Lattes ────────────────────────────────────────────────────────
    elif aba == "👤 Lattes":
        st.subheader("Extração do Currículo Lattes")
        caminho_lattes = os.path.join(caminho_proposta, "lattes.xml")
        if not os.path.exists(caminho_lattes):
            st.warning("lattes.xml não encontrado.")
            return
        try:
            tree = ET.parse(caminho_lattes)
            root = tree.getroot()

            gerais = root.find("DADOS-GERAIS")
            if gerais is not None:
                c1, c2, c3 = st.columns(3)
                c1.metric("Nome",        gerais.get("NOME-COMPLETO", "N/A"))
                c2.metric("CPF",         gerais.get("CPF", "N/A"))
                c3.metric("Naturalidade",gerais.get("CIDADE-NASCIMENTO", "N/A"))

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
                            "Status":           el.get("STATUS-DO-CURSO", el.get("STATUS", "N/A")),
                        })
                if titulos:
                    st.dataframe(pd.DataFrame(titulos), use_container_width=True, hide_index=True)

            atuacoes = root.findall(".//ATUACAO-PROFISSIONAL")
            if atuacoes:
                st.markdown("#### 🏛️ Atuação Profissional")
                st.dataframe(pd.DataFrame([
                    {"Instituição": a.get("NOME-INSTITUICAO", "N/A"),
                     "Vínculo":     a.get("TIPO-VINCULO", "N/A")}
                    for a in atuacoes
                ]), use_container_width=True, hide_index=True)

            artigos = root.findall(".//ARTIGO-PUBLICADO")
            if artigos:
                st.markdown(f"#### 📚 Artigos Publicados ({len(artigos)} encontrados)")
                lista_art = []
                for art in artigos[:10]:
                    d   = art.find("DADOS-BASICOS-DO-ARTIGO")
                    det = art.find("DETALHAMENTO-DO-ARTIGO")
                    if d is not None:
                        lista_art.append({
                            "Título":    d.get("TITULO-DO-ARTIGO", "N/A"),
                            "Ano":       d.get("ANO-DO-ARTIGO", "N/A"),
                            "Periódico": det.get("TITULO-DO-PERIODICO-OU-REVISTA", "N/A") if det is not None else "N/A",
                        })
                st.dataframe(pd.DataFrame(lista_art), use_container_width=True, hide_index=True)
                if len(artigos) > 10:
                    st.caption(f"Exibindo 10 de {len(artigos)} artigos.")

            with st.expander("🔧 Ver XML Bruto"):
                with open(caminho_lattes, "r", encoding="ISO-8859-1") as f:
                    st.code(f.read(), language="xml")
        except Exception as e:
            st.error(f"Erro ao processar Lattes: {e}")

    # ── Ficha de Pontuação ────────────────────────────────────────────
    elif aba == "📊 Ficha de Pontuação":
        st.subheader("Ficha de Pontuação Declarada")
        caminho_ficha = os.path.join(caminho_proposta, "ficha_pontuacao.xlsx")
        if not os.path.exists(caminho_ficha):
            st.warning("ficha_pontuacao.xlsx não encontrado.")
            return
        try:
            df_ficha = pd.read_excel(caminho_ficha).dropna(how="all", axis=1)
            st.dataframe(df_ficha, height=500, use_container_width=True)
        except Exception as e:
            st.error(f"Erro ao ler ficha: {e}")

    # ── Base de Dados Interna ─────────────────────────────────────────
    elif aba == "🗃️ Base de Dados Interna":
        st.subheader("Base de Dados Interna — Docente vinculado à proposta")
        dados_base = carregar_base_interna()
        if not dados_base:
            st.error(f"Base interna não encontrada: {CAMINHO_DB}")
            return

        cpf_coord = obter_cpf_coordenador(proposta_id)
        docente   = next((d for d in dados_base if d["cpf"] == cpf_coord), None) if cpf_coord else None

        if docente:
            st.success(f"✅ Docente localizado: CPF **{docente['cpf']}** — Unidade: **{docente['unidade_lotacao']}**")
            c1, c2, c3 = st.columns(3)
            c1.metric("SIAPE",     docente["siape"])
            c2.metric("Unidade",   docente["unidade_lotacao"])
            c3.metric("Pendências",len(docente["pendencias_propp"]))
            st.markdown("---")
            st.markdown("**📁 Projetos em Andamento**")
            if docente["projetos_em_andamento"]:
                st.dataframe(pd.DataFrame(docente["projetos_em_andamento"]),
                             use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum projeto em andamento.")
            if docente["pendencias_propp"]:
                st.markdown("**⚠️ Pendências PROPP**")
                st.dataframe(pd.DataFrame(docente["pendencias_propp"]),
                             use_container_width=True, hide_index=True)
            else:
                st.success("Sem pendências registradas.")
        else:
            msg = f"CPF `{cpf_coord}` não encontrado na base." if cpf_coord else "CPF não identificado nesta proposta."
            st.warning(f"{msg} Exibindo base completa para consulta.")
            rows = [{"CPF": d["cpf"], "SIAPE": d["siape"], "Unidade": d["unidade_lotacao"],
                     "Pendências": len(d["pendencias_propp"]),
                     "Projetos em Andamento": len(d["projetos_em_andamento"])}
                    for d in dados_base]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ── Parecer Final ─────────────────────────────────────────────────
    elif aba == "⚖️ Parecer Final":
        st.subheader("Laudo Técnico da Auditoria")
        caminho_md   = os.path.join(caminho_proposta, f"{proposta_id}_parecer.md")
        caminho_json = os.path.join(caminho_proposta, f"{proposta_id}_parecer.json")

        if not os.path.exists(caminho_md) and not os.path.exists(caminho_json):
            st.info("Parecer ainda não gerado. Execute o back-end primeiro.")
            return

        formato = st.radio("Formato:", ["📝 Markdown", "📄 JSON"], horizontal=True, key="fmt_parecer")

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
                simples   = {k: v for k, v in dados_json.items() if not isinstance(v, (list, dict))}
                complexos = {k: v for k, v in dados_json.items() if isinstance(v, (list, dict))}
                if simples:
                    st.dataframe(
                        pd.DataFrame([{"Campo": k.replace("_", " ").title(), "Valor": str(v)}
                                       for k, v in simples.items()]),
                        use_container_width=True, hide_index=True,
                    )
                for k, v in complexos.items():
                    st.markdown(f"**{k.replace('_', ' ').title()}:**")
                    if isinstance(v, list) and v and isinstance(v[0], dict):
                        colunas = list(v[0].keys())
                        header  = "".join(
                            f'<th style="background:#007BC0;color:#fff;padding:8px 12px;text-align:left">{c}</th>'
                            for c in colunas
                        )
                        rows = ""
                        for i, item in enumerate(v):
                            bg    = "#f0f4f8" if i % 2 == 0 else "#ffffff"
                            cells = "".join(
                                f'<td style="padding:8px 12px;vertical-align:top;border-bottom:1px solid #dee2e6;'
                                f'white-space:pre-wrap;word-break:break-word;color:#212529;background:{bg}">{str(item.get(c,""))}</td>'
                                for c in colunas
                            )
                            rows += f'<tr>{cells}</tr>'
                        st.markdown(
                            f'<div style="overflow-x:auto;border-radius:6px;border:1px solid #dee2e6">'
                            f'<table style="width:100%;border-collapse:collapse">'
                            f'<thead><tr>{header}</tr></thead><tbody>{rows}</tbody></table></div>',
                            unsafe_allow_html=True,
                        )
                    elif isinstance(v, list):
                        st.write(", ".join(str(i) for i in v))
                    else:
                        st.json(v)
            else:
                st.info("Parecer em JSON não disponível.")

    # ── E-mail ────────────────────────────────────────────────────────
    elif aba == "✉️ E-mail":
        st.subheader("E-mail de Devolutiva")

        # E-mail individual (dentro da pasta da proposta)
        caminho_email_individual = os.path.join(caminho_proposta, f"{proposta_id}_email_individual.txt")
        # E-mail consolidado (em outputs/)
        caminho_email_consolidado = get_arquivo_email(proposta_id)

        if not os.path.exists(caminho_email_individual) and caminho_email_consolidado is None:
            st.warning("Nenhum e-mail gerado para esta proposta. Execute o back-end.")
            return

        opcoes_email = []
        if os.path.exists(caminho_email_individual):
            opcoes_email.append("📧 E-mail Individual")
        if caminho_email_consolidado:
            opcoes_email.append("📨 E-mail Consolidado (todos os projetos do coordenador)")

        tipo_email = st.radio("Tipo de e-mail:", opcoes_email, horizontal=True) if len(opcoes_email) > 1 else opcoes_email[0]

        if tipo_email == "📧 E-mail Individual":
            with open(caminho_email_individual, "r", encoding="utf-8") as f:
                conteudo = f.read()
        else:
            with open(caminho_email_consolidado, "r", encoding="utf-8") as f:
                conteudo = f.read()
            st.info("Este e-mail consolida todos os projetos do coordenador. Para editar, acesse a Central de Comunicação.")

        renderizar_email_html(conteudo)

        if tipo_email == "📨 E-mail Consolidado (todos os projetos do coordenador)":
            if st.button("✉️ Abrir na Central de Comunicação", type="primary", use_container_width=True):
                nome_coord = obter_nome_coordenador(proposta_id)
                st.session_state.email_coordenador     = nome_coord.upper().replace(" ", "_")
                st.session_state.proposta_origem_email = proposta_id
                st.session_state.proposta_selecionada  = None
                st.session_state["_menu_redirect"]      = "✉️ Central de Comunicação"
                st.rerun()

    # ── Revisão Humana ────────────────────────────────────────────────
    elif aba == "✅ Revisão Humana":
        st.subheader("Registrar Decisão Humana")
        st.caption("A decisão final é sempre de responsabilidade da equipe humana.")

        caminho_json  = os.path.join(caminho_proposta, f"{proposta_id}_parecer.json")
        status_agente = "N/A"
        coordenador   = "N/A"

        if not os.path.exists(caminho_json):
            st.info("Parecer ainda não gerado. Execute o back-end primeiro.")
            return

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
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ Confirmar sugestão do agente", use_container_width=True, type="primary"):
                    salvar_revisao(proposta_id, coordenador, status_agente, "CONFIRMADO", observacao)
                    st.success("Decisão registrada!")
                    st.rerun()
            with c2:
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
# TELA 0: KANBAN
# =====================================================================
if menu == "🏠 Tela Inicial (Kanban)":
    st.markdown("""
        <p style="color:#007BC0;font-size:5.5rem;margin:0 0 4px 0;
           font-family:'Segoe UI',Arial,sans-serif;font-weight:800;line-height:1.1;">PROPP</p>
        <p style="font-size:2rem;margin:0 0 30px 0;font-weight:400;
           font-family:'Segoe UI',Arial,sans-serif;">Pró-Reitoria de Pesquisa e Pós-Graduação</p>
    """, unsafe_allow_html=True)

    usuario_logado = st.session_state.get("usuario_logado", "")
    nome_usuario   = usuario_logado.split("@")[0].replace(".", " ").title() if usuario_logado else "Usuário"
    st.markdown(f"### Olá, {nome_usuario}!")
    st.markdown("Bem-vindo ao **Sistema de Orquestração e Auditoria de Editais (SIGProj-AI)**.")

    revisoes_feitas = {r["id_proposta"] for r in carregar_revisoes()}
    todas_propostas = listar_propostas()

    # Propostas com parecer gerado
    com_parecer = [p for p in todas_propostas
                   if os.path.exists(os.path.join(PASTA_PROPOSTAS, p, f"{p}_parecer.json"))]
    sem_parecer = [p for p in todas_propostas if p not in com_parecer]

    pendentes = len([p for p in com_parecer if p not in revisoes_feitas])
    if pendentes > 0:
        st.warning(f"⏳ **{pendentes} proposta(s) aguardando revisão humana.**")
    elif com_parecer:
        st.success("✅ Todas as propostas processadas já foram revisadas.")
    else:
        st.info("Nenhuma proposta processada ainda. Execute o back-end para iniciar.")

    st.divider()
    st.subheader("🗂️ Fluxo de Trabalho (Edital IC&T 2026)")
    col_todo, col_done, col_rev = st.columns(3)

    # Coluna 1: Para analisar
    with col_todo:
        st.markdown("#### 📥 Para Analisar")
        st.caption(f"{len(sem_parecer)} proposta(s) sem parecer")
        st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
        with st.container(border=True, height=380):
            if sem_parecer:
                for p in sem_parecer[:15]:
                    with st.container(border=True):
                        st.markdown(f"📄 **{p}**")
                        st.caption(obter_nome_coordenador(p))
                        if st.button("🔍 Ver detalhes", key=f"todo_{p}"):
                            st.session_state.proposta_selecionada = p
                            st.session_state.aba_atual = "📋 Formulário"
                            st.session_state.menu_origem = "🏠 Tela Inicial (Kanban)"
                            st.rerun()
            else:
                st.info("Nenhuma proposta aguardando análise.")

        if st.button("▶️ Executar Pipeline no LangGraph", type="primary", use_container_width=True):
            if os.path.exists(RUN_BATCH_PATH):
                with st.spinner("Executando o agente... Aguarde."):
                    resultado = subprocess.run(
                        [sys.executable, RUN_BATCH_PATH],
                        capture_output=True, text=True,
                        cwd=BASE_DIR,
                        env={**os.environ, "PYTHONPATH": BASE_DIR},
                    )
                if resultado.returncode == 0:
                    st.success("✅ Processamento concluído!")
                    with st.expander("Ver log"):
                        st.code(resultado.stdout or "(sem saída)")
                else:
                    st.error("❌ Erro durante o processamento.")
                    with st.expander("Ver log de erro"):
                        st.code(resultado.stderr or "(sem saída)")
            else:
                st.error(f"run_batch.py não encontrado em: {RUN_BATCH_PATH}")

    # Coluna 2: Analisadas aguardando revisão
    with col_done:
        st.markdown("#### ✅ Analisadas")
        st.caption("Aguardando revisão humana")
        filtro = st.selectbox("Filtrar:", ["Todos", "ENQUADRADA", "NÃO ENQUADRADA"], key="filtro_kanban")

        if os.path.exists(CAMINHO_EXCEL):
            try:
                df = pd.read_excel(CAMINHO_EXCEL, sheet_name="Resumo Propostas")
                if filtro != "Todos":
                    df = df[df["Status Final"] == filtro]
                df_pend = df[~df["ID da Proposta"].isin(revisoes_feitas)]
                with st.container(border=True, height=380):
                    if df_pend.empty:
                        st.info("Nenhuma proposta pendente de revisão.")
                    else:
                        for _, row in df_pend.iterrows():
                            id_prop = row["ID da Proposta"]
                            cor     = "🟢" if row["Status Final"] == "ENQUADRADA" else "🔴"
                            with st.container(border=True):
                                st.markdown(f"📄 **{id_prop}**")
                                st.markdown(f"{cor} {row['Status Final']}")
                                st.caption(str(row["Coordenador"]))
                                if st.button("🔍 Ver detalhes", key=f"done_{id_prop}"):
                                    st.session_state.proposta_selecionada = id_prop
                                    st.session_state.aba_atual = "✉️ E-mail"
                                    st.session_state.menu_origem = "🏠 Tela Inicial (Kanban)"
                                    st.rerun()
            except Exception as e:
                st.error(f"Erro ao ler Excel: {e}")
        else:
            with st.container(border=True, height=380):
                st.info("Execute o back-end para gerar os resultados.")

    # Coluna 3: Revisadas
    with col_rev:
        st.markdown("#### 📋 Revisadas")
        st.caption("Decisão humana registrada")
        st.markdown('<div style="height:38px"></div>', unsafe_allow_html=True)

        revisoes_dict = {r["id_proposta"]: r for r in carregar_revisoes()}
        with st.container(border=True, height=380):
            if not revisoes_feitas:
                st.info("Nenhuma proposta revisada ainda.")
            else:
                for id_prop, rev in revisoes_dict.items():
                    decisao   = rev.get("decisao", "")
                    icone_dec = "✅" if decisao == "CONFIRMADO" else "🔄"
                    # Busca status no Excel se disponível
                    status_label = ""
                    if os.path.exists(CAMINHO_EXCEL):
                        try:
                            df_rev = pd.read_excel(CAMINHO_EXCEL, sheet_name="Resumo Propostas")
                            row_rev = df_rev[df_rev["ID da Proposta"] == id_prop]
                            if not row_rev.empty:
                                s = row_rev.iloc[0]["Status Final"]
                                status_label = f"{'🟢' if s == 'ENQUADRADA' else '🔴'} {s}"
                        except Exception:
                            pass
                    with st.container(border=True):
                        st.markdown(f"📄 **{id_prop}**")
                        if status_label:
                            st.markdown(status_label)
                        st.markdown(f"{icone_dec} {decisao}")
                        st.caption(rev.get("coordenador", ""))
                        if st.button("📋 Ver detalhes", key=f"rev_{id_prop}"):
                            st.session_state.proposta_selecionada = id_prop
                            st.session_state.aba_atual = "✅ Revisão Humana"
                            st.session_state.menu_origem = "🏠 Tela Inicial (Kanban)"
                            st.rerun()

    st.divider()
    st.subheader("⚡ Ações Rápidas")
    st.link_button("📄 Abrir Edital IC&T (PDF)", URL_EDITAL, use_container_width=True)

    html_rel = exportar_relatorio_html()
    if html_rel:
        st.download_button("📥 Exportar Relatório (HTML)", data=html_rel.encode("utf-8"),
                           file_name=f"relatorio_{datetime.now().strftime('%Y%m%d_%H%M')}.html",
                           mime="text/html", use_container_width=True)
    else:
        st.button("📥 Exportar Relatório (execute o back-end primeiro)", disabled=True, use_container_width=True)

    html_stats = exportar_estatisticas_html()
    if html_stats:
        st.download_button("📊 Exportar Estatísticas (HTML)", data=html_stats.encode("utf-8"),
                           file_name=f"estatisticas_{datetime.now().strftime('%Y%m%d_%H%M')}.html",
                           mime="text/html", use_container_width=True)
    else:
        st.button("📊 Exportar Estatísticas (execute o back-end primeiro)", disabled=True, use_container_width=True)

    st.divider()
    st.subheader("📋 Log de Rastreabilidade")
    st.caption("Ações dos agentes de IA e da equipe humana.")

    entradas_log = []
    for r in sorted(carregar_revisoes(), key=lambda x: x.get("data_hora", ""), reverse=True):
        icone = "✅" if r.get("decisao") == "CONFIRMADO" else "🔄"
        entradas_log.append({"Data/Hora": r.get("data_hora", "—"), "Módulo": "Revisão Humana",
                              "Ação": f"{icone} {r.get('decisao','')} — {r.get('id_proposta','')} ({r.get('coordenador','')})"})

    for p in sorted(listar_propostas(), reverse=True):
        caminho_p = os.path.join(PASTA_PROPOSTAS, p, f"{p}_parecer.json")
        if os.path.exists(caminho_p):
            try:
                with open(caminho_p, "r", encoding="utf-8") as f:
                    dp = json.load(f)
                status = dp.get("status_final", "—")
                coord  = dp.get("coordenador", "—")
                data   = dp.get("data_processamento", "—")
                icone  = "🟢" if "ENQUADRADA" in status and "NÃO" not in status else "🔴"
                entradas_log.append({"Data/Hora": data, "Módulo": "Motor de Inferência",
                                     "Ação": f"{icone} Parecer gerado — {p} | {coord} | {status}"})
            except Exception:
                pass

    log_dir = os.path.join(PASTA_OUTPUTS, "logs")
    if os.path.exists(log_dir):
        for arq_log in sorted(os.listdir(log_dir), reverse=True)[:3]:
            try:
                with open(os.path.join(log_dir, arq_log), "r", encoding="utf-8") as f:
                    for linha in f:
                        try:
                            e = json.loads(linha.strip())
                            if e.get("event") in ("pipeline.start", "pipeline.summary", "proposal.done", "proposal.error"):
                                extra = {k: v for k, v in e.items() if k not in ("timestamp","execution_id","level","event")}
                                entradas_log.append({
                                    "Data/Hora": e.get("timestamp", "")[:19].replace("T", " "),
                                    "Módulo":    f"Pipeline [{e.get('execution_id','')[:16]}]",
                                    "Ação":      f"{e.get('event')} — {json.dumps(extra, ensure_ascii=False)}",
                                })
                        except Exception:
                            pass
            except Exception:
                pass

    if entradas_log:
        st.dataframe(pd.DataFrame(entradas_log), use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma atividade registrada ainda.")

# =====================================================================
# TELA 1: DASHBOARD
# =====================================================================
elif menu == "📊 Dashboard Executivo":
    st.title("📊 Painel Gerencial de Impacto Institucional - PROPP")
    st.markdown("Monitoramento de submissões (IC&T), enquadramentos e alinhamento com ODS da ONU.")
    st.divider()

    if not os.path.exists(CAMINHO_EXCEL):
        st.warning("Nenhum dado disponível. Execute o back-end para gerar os resultados.")
        st.stop()

    try:
        df = pd.read_excel(CAMINHO_EXCEL, sheet_name="Resumo Propostas")
    except Exception as e:
        st.error(f"Erro ao ler Excel: {e}")
        st.stop()

    total       = len(df)
    aprovadas   = len(df[df["Status Final"] == "ENQUADRADA"])
    reprovadas  = total - aprovadas
    inovadores  = len(df[df["Inovação Tecnológica"] == "Sim"])  if "Inovação Tecnológica" in df.columns else 0
    patentes    = len(df[df["Gera Patente"] == "Sim"])          if "Gera Patente"          in df.columns else 0

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Total",          total)
    c2.metric("✅ Enquadradas",  aprovadas)
    c3.metric("❌ Não Enquadradas", reprovadas)
    c4.metric("💡 Inovação",    inovadores)
    c5.metric("📜 Patentes",    patentes)

    st.markdown("<br>", unsafe_allow_html=True)
    cg1, cg2 = st.columns(2)
    with cg1:
        st.subheader("🌍 Impacto por ODS")
        if "ODS Vinculado" in df.columns:
            df_ods = df["ODS Vinculado"].value_counts().reset_index()
            df_ods.columns = ["ODS", "Quantidade"]
            st.plotly_chart(px.pie(df_ods, values="Quantidade", names="ODS", hole=0.4,
                                   color_discrete_sequence=px.colors.qualitative.Pastel),
                            use_container_width=True)
        else:
            st.warning("Coluna 'ODS Vinculado' não encontrada.")
    with cg2:
        st.subheader("📚 Status por Área de Conhecimento")
        if "Área de Conhecimento" in df.columns:
            df_area = df.groupby(["Área de Conhecimento", "Status Final"]).size().reset_index(name="Quantidade")
            st.plotly_chart(px.bar(df_area, x="Área de Conhecimento", y="Quantidade", color="Status Final",
                                   barmode="group",
                                   color_discrete_map={"ENQUADRADA": "#2ecc71", "NÃO ENQUADRADA": "#e74c3c"}),
                            use_container_width=True)
        else:
            st.warning("Coluna 'Área de Conhecimento' não encontrada.")

    st.divider()
    st.subheader("🔬 Principais Temas de Pesquisa")
    keywords_list = []
    for p in listar_propostas():
        caminho_form = os.path.join(PASTA_PROPOSTAS, p, "formulario.json")
        if os.path.exists(caminho_form):
            try:
                with open(caminho_form, "r", encoding="utf-8") as f:
                    kws = json.load(f).get("dados_projeto", {}).get("8_palavras_chave", [])
                keywords_list.extend(kws)
            except Exception:
                pass
    if keywords_list:
        df_kw = pd.DataFrame(keywords_list, columns=["Tema"]).value_counts().reset_index(name="Quantidade")
        df_kw = df_kw.sort_values("Quantidade", ascending=True).tail(10)
        st.plotly_chart(px.bar(df_kw, x="Quantidade", y="Tema", orientation="h",
                               color="Quantidade", color_continuous_scale="Blues"),
                        use_container_width=True)
    else:
        st.info("Nenhuma palavra-chave encontrada nas propostas.")

    st.divider()
    st.subheader("💡 Conclusões e Insights")
    i1, i2, i3 = st.columns(3)
    with i1:
        with st.expander("📈 Tendência de Impacto", expanded=True):
            ods_p = df["ODS Vinculado"].mode()[0] if "ODS Vinculado" in df.columns and not df["ODS Vinculado"].empty else "N/A"
            st.info(f"**ODS Predominante:** {ods_p}.\n\nForte alinhamento estratégico com metas sustentáveis.")
    with i2:
        with st.expander("🔍 Alerta de Qualidade", expanded=True):
            taxa = (reprovadas / total * 100) if total else 0
            st.warning(f"**Taxa de Recusa:** {taxa:.1f}%.\n\nIndica necessidade de orientação sobre a Ficha de Pontuação.")
    with i3:
        with st.expander("🛡️ Propriedade Intelectual", expanded=True):
            st.success(f"**Potencial de Patentes:** {patentes} projeto(s).\n\nFortalece os indicadores de inovação.")

# =====================================================================
# TELA 2: AUDITORIA
# =====================================================================
elif menu == "🔍 Auditoria de Propostas":
    st.title("🔍 Central de Auditoria Transparente")
    st.divider()

    pastas = listar_propostas()
    if not pastas:
        st.warning(f"Nenhuma proposta encontrada em: {PASTA_PROPOSTAS}")
    else:
        mapa = {f"{obter_nome_coordenador(p)} ({p})": p for p in pastas}
        sel  = st.selectbox("Selecione o coordenador para auditoria:", list(mapa.keys()))
        if st.button("🔍 Abrir Auditoria Detalhada", type="primary", use_container_width=True):
            st.session_state.proposta_selecionada = mapa[sel]
            st.session_state.aba_atual = "📋 Formulário"
            st.session_state.menu_origem = "🔍 Auditoria de Propostas"
            st.rerun()

# =====================================================================
# TELA 3: CENTRAL DE COMUNICAÇÃO
# =====================================================================
elif menu == "✉️ Central de Comunicação":
    st.title("✉️ Orquestração de Comunicados")
    st.divider()

    arquivos_email = []
    if os.path.exists(PASTA_OUTPUTS):
        arquivos_email = [f for f in os.listdir(PASTA_OUTPUTS)
                          if f.startswith("EMAIL_") and f.endswith(".txt")]

    if not arquivos_email:
        st.info("Nenhum rascunho de e-mail encontrado em outputs/. Execute o back-end primeiro.")
        st.stop()

    nomes = [f.replace("EMAIL_", "").replace(".txt", "").replace("_", " ").title()
             for f in arquivos_email]

    idx_default = 0
    if st.session_state.email_coordenador:
        busca = st.session_state.email_coordenador.replace("_", " ").title()
        for i, n in enumerate(nomes):
            if busca.upper() in n.upper() or n.upper() in busca.upper():
                idx_default = i
                break

    coordenador_sel = st.selectbox("Selecione o coordenador:", nomes, index=idx_default)

    if st.session_state.get("proposta_origem_email"):
        id_orig = st.session_state.proposta_origem_email
        if st.button(f"🔙 Voltar para {id_orig}", type="secondary"):
            st.session_state.proposta_selecionada = id_orig
            st.session_state["_menu_redirect"] = st.session_state.get("menu_origem", "🏠 Tela Inicial (Kanban)")
            st.rerun()

    arquivo_alvo   = f"EMAIL_{coordenador_sel.upper().replace(' ', '_')}.txt"
    caminho_email  = os.path.join(PASTA_OUTPUTS, arquivo_alvo)

    if not os.path.exists(caminho_email):
        st.warning(f"Arquivo não encontrado: {arquivo_alvo}")
        st.stop()

    with open(caminho_email, "r", encoding="utf-8") as f:
        conteudo_email = f.read()

    st.markdown("### 📝 Editar Conteúdo do Comunicado")
    st.caption("Edite o texto abaixo antes do envio oficial.")
    email_editado = st.text_area("Corpo do E-mail:", value=conteudo_email,
                                  height=350, key=f"editor_{arquivo_alvo}")

    if st.button("💾 Salvar Alterações", type="primary", use_container_width=True):
        try:
            with open(caminho_email, "w", encoding="utf-8") as f:
                f.write(email_editado)
            st.success("✅ Comunicado salvo com sucesso!")
        except Exception as e:
            st.error(f"❌ Erro ao salvar: {e}")

    st.divider()
    st.markdown("### 👁️ Pré-visualização (Como o docente receberá)")
    renderizar_email_html(email_editado)

# =====================================================================
# TELA 4: HISTÓRICO
# =====================================================================
elif menu == "📂 Histórico de Decisões":
    st.title("📂 Histórico de Decisões Auditadas")
    st.divider()
    revisoes = carregar_revisoes()
    if revisoes:
        st.dataframe(pd.DataFrame(revisoes), use_container_width=True, hide_index=True)
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
        st.error(f"Base interna não encontrada: {CAMINHO_DB}")
        st.stop()

    # Cruza CPF → nome usando formularios das propostas
    cpf_para_nome: dict = {}
    for p in listar_propostas():
        caminho_form = os.path.join(PASTA_PROPOSTAS, p, "formulario.json")
        if os.path.exists(caminho_form):
            try:
                with open(caminho_form, "r", encoding="utf-8") as f:
                    fj = json.load(f)
                coord = fj.get("dados_coordenador", {})
                cpf   = coord.get("6_cpf")
                nome  = coord.get("nome")
                if cpf and nome and cpf not in cpf_para_nome:
                    cpf_para_nome[cpf.strip()] = nome.strip().title()
            except Exception:
                pass

    opcoes = ["Todos"] + [
        f"{d['cpf']} — {cpf_para_nome.get(d['cpf'], 'Nome não encontrado')}"
        for d in dados_base
    ]
    filtro = st.selectbox("Selecione o docente:", opcoes, key="filtro_base_interna")

    dados_filtrados = dados_base if filtro == "Todos" else [
        d for d in dados_base if d["cpf"] == filtro.split(" — ")[0]
    ]

    st.markdown(f"**{len(dados_filtrados)} docente(s) exibido(s)**")
    rows = [{"CPF": d["cpf"], "SIAPE": d["siape"], "Unidade": d["unidade_lotacao"],
             "Pendências": len(d["pendencias_propp"]),
             "Projetos em Andamento": len(d["projetos_em_andamento"])}
            for d in dados_filtrados]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                 height=min((len(rows) + 1) * 35 + 10, 500))

    if filtro != "Todos" and len(dados_filtrados) == 1:
        d = dados_filtrados[0]
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**📁 Projetos em Andamento**")
            if d["projetos_em_andamento"]:
                st.dataframe(pd.DataFrame(d["projetos_em_andamento"]),
                             use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum projeto em andamento.")
        with c2:
            st.markdown("**⚠️ Pendências PROPP**")
            if d["pendencias_propp"]:
                st.dataframe(pd.DataFrame(d["pendencias_propp"]),
                             use_container_width=True, hide_index=True)
            else:
                st.success("Sem pendências registradas.")