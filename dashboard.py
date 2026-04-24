import calendar
from datetime import datetime
import altair as alt
import pandas as pd
import streamlit as st
from db import (
    listar_transacoes,
    listar_evolucao_mensal,
    atualizar_transacao,
    deletar_transacao,
    listar_proximos,
    listar_atrasadas,
    marcar_como_quitado,
    inserir_transacao,
    listar_categorias,
    gerar_recorrencias,
)

from utils import formatar_moeda, enviar_lembrete_twilio

st.set_page_config(page_title="FinAuto", page_icon="💰", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'Inter', sans-serif !important;
}

/* ── KPI CARDS ──────────────────────────────────────────────── */
div[data-testid="metric-container"] {
    background: #1a1b26 !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 10px !important;
    padding: 16px 18px !important;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3) !important;
}
div[data-testid="stMetricLabel"] > div {
    font-size: 11px !important;
    font-weight: 500 !important;
    color: rgba(232,234,240,0.45) !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase !important;
}
div[data-testid="stMetricValue"] > div {
    font-size: 22px !important;
    font-weight: 700 !important;
    letter-spacing: -0.03em !important;
    color: #e8eaf0 !important;
}

/* ── SIDEBAR ─────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: #151621 !important;
    border-right: 1px solid rgba(255,255,255,0.07) !important;
}
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stMultiSelect label,
section[data-testid="stSidebar"] .stTextInput label {
    font-size: 10px !important;
    font-weight: 600 !important;
    letter-spacing: 0.07em !important;
    text-transform: uppercase !important;
    color: rgba(232,234,240,0.4) !important;
}

/* ── INPUTS ──────────────────────────────────────────────────── */
.stSelectbox > div > div,
.stMultiSelect > div > div,
.stTextInput > div > div > input {
    background: #1e2030 !important;
    border: 1px solid rgba(255,255,255,0.11) !important;
    border-radius: 7px !important;
    color: #e8eaf0 !important;
    font-size: 12px !important;
}

/* Multiselect tags */
span[data-baseweb="tag"] {
    background-color: rgba(99,102,241,0.18) !important;
    border: 1px solid rgba(99,102,241,0.3) !important;
    border-radius: 100px !important;
}
span[data-baseweb="tag"] span {
    color: #a5b4fc !important;
    font-size: 11px !important;
}

/* ── BOTÕES ──────────────────────────────────────────────────── */
.stButton > button[kind="primary"] {
    background: #6366f1 !important;
    border: none !important;
    border-radius: 7px !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    letter-spacing: 0.01em !important;
    transition: background 0.15s !important;
}
.stButton > button[kind="primary"]:hover {
    background: #4f46e5 !important;
}
.stButton > button[kind="secondary"],
.stButton > button:not([kind="primary"]) {
    background: #1e2030 !important;
    border: 1px solid rgba(255,255,255,0.11) !important;
    border-radius: 7px !important;
    color: rgba(232,234,240,0.6) !important;
    font-size: 13px !important;
    font-weight: 500 !important;
}
.stButton > button:not([kind="primary"]):hover {
    background: rgba(255,255,255,0.06) !important;
    color: #e8eaf0 !important;
}

/* ── TABELA ──────────────────────────────────────────────────── */
div[data-testid="stDataEditor"],
div[data-testid="stDataFrame"] {
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 10px !important;
    overflow: hidden !important;
}

/* ── DIVIDER ─────────────────────────────────────────────────── */
hr {
    border-color: rgba(255,255,255,0.07) !important;
    margin: 20px 0 !important;
}

/* ── SUBHEADERS ──────────────────────────────────────────────── */
h2, h3 {
    letter-spacing: -0.02em !important;
    font-weight: 700 !important;
    color: #e8eaf0 !important;
}

/* ── ALERTAS ─────────────────────────────────────────────────── */
div[data-testid="stAlert"] {
    border-radius: 9px !important;
    border: 1px solid !important;
}

/* ── CALENDÁRIO ──────────────────────────────────────────────── */
[data-testid="stColumns"]:has(> [data-testid="stColumn"]:nth-child(7)) .stButton > button {
    min-height: 68px !important;
    white-space: pre-line !important;
    text-align: left !important;
    align-items: flex-start !important;
    justify-content: flex-start !important;
    padding: 8px 10px !important;
    font-size: 11px !important;
    line-height: 1.55 !important;
    border-radius: 9px !important;
    transition: background 0.15s, border-color 0.15s !important;
}
/* Dia selecionado */
[data-testid="stColumns"]:has(> [data-testid="stColumn"]:nth-child(7)) .stButton > button[kind="primary"] {
    background: rgba(99,102,241,0.22) !important;
    border: 1px solid #6366f1 !important;
    color: #e8eaf0 !important;
    box-shadow: 0 0 0 2px rgba(99,102,241,0.18) !important;
}
/* Hover dias normais */
[data-testid="stColumns"]:has(> [data-testid="stColumn"]:nth-child(7)) .stButton > button:not([kind="primary"]):hover {
    background: rgba(255,255,255,0.05) !important;
    border-color: rgba(255,255,255,0.18) !important;
}
/* Responsivo: telas menores */
@media (max-width: 768px) {
    [data-testid="stColumns"]:has(> [data-testid="stColumn"]:nth-child(7)) .stButton > button {
        min-height: 52px !important;
        font-size: 9.5px !important;
        padding: 5px 6px !important;
    }
}

/* ── ESCONDER MENU / FOOTER ──────────────────────────────────── */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header[data-testid="stHeader"] { background: rgba(15,17,23,0.95) !important; backdrop-filter: blur(16px); }

/* ── RESPONSIVO: ocultar seções no mobile ────────────────────── */
@media (max-width: 768px) {
    [data-testid="stElementContainer"]:has(#compromisos-start) ~ *:not(
        [data-testid="stElementContainer"]:has(#compromisos-end) ~ *
    ):not([data-testid="stElementContainer"]:has(#compromisos-end)) {
        display: none !important;
    }
    [data-testid="stElementContainer"]:has(#calendario-start) ~ *:not(
        [data-testid="stElementContainer"]:has(#calendario-end) ~ *
    ):not([data-testid="stElementContainer"]:has(#calendario-end)) {
        display: none !important;
    }
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Estado do calendário: dia selecionado
# ---------------------------------------------------------------------------
if "cal_dia_sel" not in st.session_state:
    st.session_state.cal_dia_sel = None
if "cal_mes_prev" not in st.session_state:
    st.session_state.cal_mes_prev = None


@st.cache_data(ttl=300)
def _get_categorias(movimentacao=None):
    try:
        return listar_categorias(movimentacao)
    except Exception:
        return []


def kpi_card(label, valor, cor="#e8eaf0"):
    return f"""
    <div style="background:#1a1b26;border:1px solid rgba(255,255,255,0.07);
                border-radius:10px;padding:16px 18px;box-shadow:0 4px 20px rgba(0,0,0,0.3)">
        <div style="font-size:11px;font-weight:600;color:rgba(232,234,240,0.4);
                    letter-spacing:0.07em;text-transform:uppercase;margin-bottom:8px">{label}</div>
        <div style="font-size:22px;font-weight:700;letter-spacing:-0.03em;color:{cor}">{valor}</div>
    </div>"""


st.title("💰 FinAuto — Dashboard")
st.caption("Seu controle financeiro automatizado via WhatsApp.")

# ---------------------------------------------------------------------------
# Modal de nova transação
# ---------------------------------------------------------------------------
@st.dialog("➕ Nova transação", width="large")
def modal_nova_transacao():
    mov = st.radio(
        "Tipo de movimentação",
        ["Saída", "Entrada"],
        horizontal=True,
        format_func=lambda m: f"🔴 {m}" if m == "Saída" else f"🟢 {m}",
    )

    col1, col2 = st.columns(2)
    with col1:
        data = st.date_input("Data", value=datetime.now().date())
        valor = st.number_input("Valor (R$)", min_value=0.01, step=10.0, format="%.2f")
        responsavel_nova = st.selectbox("Responsável", ["Y", "M", "MY"])
        fonte = st.selectbox("Fonte", ["Dinheiro", "Cartão Crédito"])

    with col2:
        if mov == "Saída":
            tipo = st.selectbox("Tipo", ["P. Unico", "D. Fixa", "Parcelado"])
            status_opts = ["Pago", "A pagar", "Atrasado"]
        else:
            tipo = st.selectbox("Tipo", ["Receita Fixa", "Receita Variável"])
            status_opts = ["Recebido", "A receber", "Atrasado"]

        status = st.selectbox("Status", status_opts)

        if tipo == "Parcelado":
            cp, ct = st.columns(2)
            with cp:
                parc_atual = st.number_input("Parcela atual", min_value=1, max_value=999, value=1, step=1)
            with ct:
                parc_total = st.number_input("Total de parcelas", min_value=2, max_value=999, value=12, step=1)
            parcelas = f"{int(parc_atual)}/{int(parc_total)}"
            restantes = int(parc_total) - int(parc_atual)
            if restantes > 0:
                st.caption(f"{restantes} parcela(s) seguinte(s) serão geradas automaticamente.")
        else:
            parcelas = "1"

        _cats = _get_categorias(mov)
        categoria = st.selectbox("Categoria", _cats if _cats else ["—"])

    if tipo in ("D. Fixa", "Receita Fixa"):
        st.info("Recorrências mensais serão geradas automaticamente por 12 meses.")

    descricao = st.text_input("Descrição", placeholder="Ex: Mercado Extra, Freelancer...")

    col_s, col_c = st.columns(2)
    with col_s:
        if st.button("💾 Salvar", type="primary", width="stretch"):
            if not categoria or categoria == "—" or not descricao.strip():
                st.error("Categoria e descrição são obrigatórias.")
                return

            dados_novos = {
                "movimentacao": mov,
                "responsavel": responsavel_nova,
                "tipo": tipo,
                "categoria": categoria,
                "descricao": descricao.strip(),
                "valor": float(valor),
                "parcelas": parcelas,
                "data": data.isoformat(),
                "fonte": fonte,
                "status": status,
            }
            try:
                id_novo = inserir_transacao(dados_novos)
                msg = "Transação adicionada!"
                if dados_novos["tipo"] in ("D. Fixa", "Receita Fixa", "Parcelado"):
                    try:
                        qtd = gerar_recorrencias(id_novo)
                        if qtd:
                            msg += f" +{qtd} recorrências geradas."
                    except Exception as err_rec:
                        msg += f" (aviso recorrências: {err_rec})"
                st.success(msg)
                st.rerun()
            except Exception as err:
                st.error(f"Erro: {err}")

    with col_c:
        if st.button("❌ Cancelar", width="stretch"):
            st.rerun()


@st.dialog("✏️ Editar transação", width="large")
def modal_editar_transacao(transacao):
    mov = st.radio(
        "Tipo de movimentação",
        ["Saída", "Entrada"],
        index=0 if transacao["movimentacao"] == "Saída" else 1,
        horizontal=True,
        format_func=lambda m: f"🔴 {m}" if m == "Saída" else f"🟢 {m}",
    )

    col1, col2 = st.columns(2)
    with col1:
        try:
            data_atual = datetime.strptime(str(transacao["data"]), "%Y-%m-%d").date()
        except ValueError:
            data_atual = datetime.now().date()
        data = st.date_input("Data", value=data_atual)
        valor = st.number_input("Valor (R$)", min_value=0.01, step=10.0, format="%.2f",
                                value=float(transacao["valor"]))
        resp_opts = ["Y", "M", "MY"]
        responsavel_ed = st.selectbox("Responsável", resp_opts,
                                      index=resp_opts.index(transacao["responsavel"])
                                      if transacao["responsavel"] in resp_opts else 0)
        fonte_opts = ["Dinheiro", "Cartão Crédito"]
        fonte = st.selectbox("Fonte", fonte_opts,
                             index=fonte_opts.index(transacao["fonte"])
                             if transacao["fonte"] in fonte_opts else 0)

    with col2:
        if mov == "Saída":
            tipo_opts = ["P. Unico", "D. Fixa", "Parcelado"]
            status_opts = ["Pago", "A pagar", "Atrasado"]
        else:
            tipo_opts = ["Receita Fixa", "Receita Variável"]
            status_opts = ["Recebido", "A receber", "Atrasado"]

        tipo = st.selectbox("Tipo", tipo_opts,
                            index=tipo_opts.index(transacao["tipo"])
                            if transacao["tipo"] in tipo_opts else 0)
        status = st.selectbox("Status", status_opts,
                              index=status_opts.index(transacao["status"])
                              if transacao["status"] in status_opts else 0)
        parcelas = st.text_input("Parcelas", value=str(transacao.get("parcelas", "1")))
        _cats = _get_categorias(mov)
        cat_atual = transacao.get("categoria", "")
        cat_idx = _cats.index(cat_atual) if cat_atual in _cats else 0
        categoria = st.selectbox("Categoria", _cats if _cats else ["—"], index=cat_idx)

    descricao = st.text_input("Descrição", value=transacao.get("descricao", ""))

    col_s, col_c = st.columns(2)
    with col_s:
        if st.button("💾 Salvar", type="primary", width="stretch"):
            novos_dados = {
                "movimentacao": mov,
                "responsavel": responsavel_ed,
                "tipo": tipo,
                "categoria": categoria,
                "descricao": descricao.strip(),
                "valor": float(valor),
                "parcelas": parcelas.strip() or "1",
                "data": data.isoformat(),
                "fonte": fonte,
                "status": status,
            }
            try:
                atualizar_transacao(int(transacao["id"]), novos_dados)
                st.success("Transação atualizada!")
                st.rerun()
            except Exception as err:
                st.error(f"Erro: {err}")
    with col_c:
        if st.button("❌ Cancelar", width="stretch"):
            st.rerun()


# Botão de abrir o modal
if st.button("➕ Nova transação", type="primary"):
    modal_nova_transacao()

st.divider()

hoje = datetime.now()
MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
         "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

# ---------------------------------------------------------------------------
# Filtros (sidebar)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Filtros")
    ano = st.selectbox("Ano", range(hoje.year - 2, hoje.year + 2), index=2)

    mes_opcoes = ["Todos"] + list(range(1, 13))
    mes_sel = st.selectbox(
        "Mês",
        mes_opcoes,
        index=hoje.month,
        format_func=lambda m: "Todos" if m == "Todos" else MESES[m - 1],
    )

    responsavel = st.selectbox("Responsável", ["Todos", "Y", "M", "MY"])

    STATUS_OPCOES = ["Pago", "Recebido", "A pagar", "A receber", "Atrasado"]
    STATUS_CORES = {
        "Pago": "🔴", "A pagar": "🔴", "Atrasado": "🔴",
        "Recebido": "🟢", "A receber": "🟢",
    }
    status_sel = st.multiselect(
        "Status",
        STATUS_OPCOES,
        default=STATUS_OPCOES,
        format_func=lambda s: f"{STATUS_CORES[s]} {s}",
    )

    movimentacao_sel = st.multiselect(
        "Movimentação",
        ["Entrada", "Saída"],
        default=["Entrada", "Saída"],
        format_func=lambda m: f"🟢 {m}" if m == "Entrada" else f"🔴 {m}",
    )

    _cats_saida_todas = _get_categorias("Saída")
    _cats_entrada_todas = _get_categorias("Entrada")
    cats_saida_sel = st.multiselect(
        "Categorias Saída",
        _cats_saida_todas,
        placeholder="Todas",
    )
    cats_entrada_sel = st.multiselect(
        "Categorias Entrada",
        _cats_entrada_todas,
        placeholder="Todas",
    )

    busca = st.text_input("Buscar descrição", placeholder="Ex: Felipe, Cartão...")

resp_filtro = None if responsavel == "Todos" else responsavel
mes_filtro = None if mes_sel == "Todos" else mes_sel

titulo_periodo = f"{ano}" if mes_sel == "Todos" else f"{MESES[mes_sel-1]}/{ano}"

# ---------------------------------------------------------------------------
# Busca e filtra dados
# ---------------------------------------------------------------------------
dados = listar_transacoes(ano=ano, mes=mes_filtro, responsavel=resp_filtro)

if not dados:
    st.info(f"Nenhuma transação em {titulo_periodo}.")
    st.stop()

df = pd.DataFrame(dados)
df["valor"] = pd.to_numeric(df["valor"])
df["data"] = pd.to_datetime(df["data"]).dt.date

if status_sel:
    df = df[df["status"].isin(status_sel)]
if movimentacao_sel:
    df = df[df["movimentacao"].isin(movimentacao_sel)]
if cats_saida_sel:
    df = df[~((df["movimentacao"] == "Saída") & (~df["categoria"].isin(cats_saida_sel)))]
if cats_entrada_sel:
    df = df[~((df["movimentacao"] == "Entrada") & (~df["categoria"].isin(cats_entrada_sel)))]
if busca:
    df = df[df["descricao"].str.contains(busca, case=False, na=False)]

if df.empty:
    st.warning("Nenhuma transação após os filtros.")
    st.stop()

entradas = df.loc[df["movimentacao"] == "Entrada", "valor"].sum()
saidas = df.loc[df["movimentacao"] == "Saída", "valor"].sum()
saldo = entradas - saidas

# ---------------------------------------------------------------------------
# KPIs principais
# ---------------------------------------------------------------------------
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(kpi_card("Entradas", formatar_moeda(entradas), "#22c55e"), unsafe_allow_html=True)
with col2:
    st.markdown(kpi_card("Saídas", formatar_moeda(saidas), "#ef4444"), unsafe_allow_html=True)
with col3:
    cor_saldo = "#22c55e" if saldo >= 0 else "#ef4444"
    st.markdown(kpi_card("Saldo", formatar_moeda(saldo), cor_saldo), unsafe_allow_html=True)

st.divider()

# ---------------------------------------------------------------------------
# KPIs de planejamento
# ---------------------------------------------------------------------------
entradas_pagas = df[(df["movimentacao"] == "Entrada") & (df["status"] == "Recebido")]["valor"].sum()
saidas_pagas = df[(df["movimentacao"] == "Saída") & (df["status"] == "Pago")]["valor"].sum()
saldo_real = entradas_pagas - saidas_pagas

saidas_fixas = df[
    (df["movimentacao"] == "Saída") & (df["tipo"] == "D. Fixa")
]["valor"].sum()

taxa_poupanca = (saldo_real / entradas_pagas * 100) if entradas_pagas > 0 else 0
compromet_fixa = (saidas_fixas / entradas_pagas * 100) if entradas_pagas > 0 else 0

col_a, col_b, col_c = st.columns(3)
with col_a:
    cor_sr = "#22c55e" if saldo_real >= 0 else "#ef4444"
    st.markdown(kpi_card("Saldo realizado", formatar_moeda(saldo_real), cor_sr), unsafe_allow_html=True)
with col_b:
    cor_tp = "#22c55e" if taxa_poupanca >= 20 else ("#f59e0b" if taxa_poupanca >= 10 else "#ef4444")
    st.markdown(kpi_card("Taxa de poupança", f"{taxa_poupanca:.1f}%", cor_tp), unsafe_allow_html=True)
with col_c:
    cor_cf = "#ef4444" if compromet_fixa >= 50 else ("#f59e0b" if compromet_fixa >= 35 else "#22c55e")
    st.markdown(kpi_card("Comprometimento D. Fixa", f"{compromet_fixa:.1f}%", cor_cf), unsafe_allow_html=True)

st.divider()

# ---------------------------------------------------------------------------
# Alertas e próximos compromissos
# ---------------------------------------------------------------------------
def _render_lista_com_quitar(titulo, transacoes, chave_prefix):
    st.subheader(titulo)
    if not transacoes:
        return

    df_lista = pd.DataFrame(transacoes)
    df_lista["valor"] = pd.to_numeric(df_lista["valor"])
    df_lista["data"] = pd.to_datetime(df_lista["data"]).dt.strftime("%d/%m/%Y")

    for _, linha in df_lista.iterrows():
        cor = "🔴" if linha["movimentacao"] == "Saída" else "🟢"
        label_btn = "✅ Pago" if linha["movimentacao"] == "Saída" else "✅ Recebido"

        col_info, col_btn = st.columns([4, 1])
        with col_info:
            st.markdown(
                f"{cor} **{linha['data']}** — {linha['descricao']} "
                f"({linha['categoria']}) — "
                f"{formatar_moeda(linha['valor']).replace('$', chr(92) + '$')} "
                f"· {linha['responsavel']}"
            )
        with col_btn:
            if st.button(label_btn, key=f"{chave_prefix}_{linha['id']}", width="stretch"):
                try:
                    marcar_como_quitado(int(linha["id"]), linha["movimentacao"])
                    st.rerun()
                except RuntimeError as err:
                    st.error(f"Erro: {err}")


atrasadas = listar_atrasadas(responsavel=resp_filtro)
proximas = listar_proximos(dias=30, responsavel=resp_filtro)

if movimentacao_sel:
    atrasadas = [t for t in atrasadas if t["movimentacao"] in movimentacao_sel]
    proximas  = [t for t in proximas  if t["movimentacao"] in movimentacao_sel]
if status_sel:
    proximas = [t for t in proximas if t["status"] in status_sel]
if busca:
    _busca = busca.lower()
    atrasadas = [t for t in atrasadas if _busca in t.get("descricao", "").lower()]
    proximas  = [t for t in proximas  if _busca in t.get("descricao", "").lower()]

total_atrasado = sum(float(t["valor"]) for t in atrasadas) if atrasadas else 0

st.markdown('<span id="compromisos-start" style="display:none"></span>', unsafe_allow_html=True)

if atrasadas:
    cor_barra = "#ef4444"
    texto_barra = f"⚠️ {formatar_moeda(total_atrasado).replace('$', chr(92) + '$')} em atraso"
else:
    cor_barra = "#22c55e"
    texto_barra = "✓ Nada atrasado."

st.markdown(f"""
<div style="background:#1a1b26;border:1px solid rgba(255,255,255,0.07);
            border-radius:10px;overflow:hidden;height:44px;
            display:flex;align-items:center;margin-bottom:16px">
    <div style="height:100%;width:100%;background:{cor_barra};
                display:flex;align-items:center;padding-left:18px;
                font-size:13px;font-weight:600;color:#fff">
        {texto_barra}
    </div>
</div>
""", unsafe_allow_html=True)

col_atr, col_prox = st.columns(2)

with col_atr:
    if atrasadas:
        df_atr = pd.DataFrame(atrasadas)
        df_atr["valor"] = pd.to_numeric(df_atr["valor"])
        total_atr = df_atr["valor"].sum()
        st.metric("🔴 Total atrasado", formatar_moeda(total_atr))
        _render_lista_com_quitar("Atrasadas", atrasadas, "atr")
    else:
        st.subheader("🔴 Atrasadas")
        st.success("Nada atrasado.")

with col_prox:
    if proximas:
        df_prox = pd.DataFrame(proximas)
        df_prox["valor"] = pd.to_numeric(df_prox["valor"])
        prev_entrada = df_prox[df_prox["movimentacao"] == "Entrada"]["valor"].sum()
        prev_saida = df_prox[df_prox["movimentacao"] == "Saída"]["valor"].sum()
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(kpi_card("📥 A receber", formatar_moeda(prev_entrada), "#3b82f6"), unsafe_allow_html=True)
        with c2:
            st.markdown(kpi_card("📤 A pagar", formatar_moeda(prev_saida), "#f59e0b"), unsafe_allow_html=True)
        st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)
        _render_lista_com_quitar("Próximos 30 dias", proximas, "prox")
    else:
        st.subheader("📅 Próximos 30 dias")
        st.info("Sem compromissos agendados.")

st.divider()
st.markdown('<span id="compromisos-end" style="display:none"></span>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Gráficos de barras — categorias
# ---------------------------------------------------------------------------
def _grafico_barras(df_valor, cor):
    df_valor = df_valor.copy()
    df_valor["valor_label"] = df_valor["valor"].apply(lambda v: f"R$ {v:,.0f}")

    base = alt.Chart(df_valor).encode(
        y=alt.Y("categoria:N", sort="-x", title=""),
    )

    barras = base.mark_bar(color=cor, cornerRadiusTopRight=4, cornerRadiusBottomRight=4).encode(
        x=alt.X("valor:Q", title="R$",
                axis=alt.Axis(format=",.0f", gridColor="rgba(255,255,255,0.04)",
                              labelColor="rgba(232,234,240,0.5)", tickColor="transparent")),
        tooltip=[
            alt.Tooltip("categoria:N", title="Categoria"),
            alt.Tooltip("valor:Q", title="Valor", format=",.2f"),
        ],
    )

    rotulos = base.mark_text(
        align="left", baseline="middle", dx=6,
        color="rgba(232,234,240,0.75)", fontSize=11, fontWeight=500,
    ).encode(
        x=alt.X("valor:Q"),
        text=alt.Text("valor_label:N"),
    )

    return (
        (barras + rotulos)
        .properties(height=alt.Step(30))
        .configure_view(strokeOpacity=0, fill="#1a1b26")
        .configure_axis(labelColor="rgba(232,234,240,0.5)", titleColor="rgba(232,234,240,0.4)",
                        gridColor="rgba(255,255,255,0.04)", domainColor="rgba(255,255,255,0.07)")
    )

col_esq, col_dir = st.columns(2)

with col_esq:
    st.subheader("Saídas por categoria")
    df_saidas = df[df["movimentacao"] == "Saída"]
    if df_saidas.empty:
        st.caption("Sem saídas neste período.")
    else:
        agrupado = df_saidas.groupby("categoria", as_index=False)["valor"].sum()
        st.altair_chart(_grafico_barras(agrupado, "#ef4444"), use_container_width=True)

with col_dir:
    st.subheader("Entradas por categoria")
    df_entradas = df[df["movimentacao"] == "Entrada"]
    if df_entradas.empty:
        st.caption("Sem entradas neste período.")
    else:
        agrupado = df_entradas.groupby("categoria", as_index=False)["valor"].sum()
        st.altair_chart(_grafico_barras(agrupado, "#22c55e"), use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Evolução mensal
# ---------------------------------------------------------------------------
st.subheader(f"Evolução mensal de {ano}")
dados_ano = listar_evolucao_mensal(ano=ano, responsavel=resp_filtro)

if not dados_ano:
    st.caption("Sem dados no ano.")
else:
    df_ano = pd.DataFrame(dados_ano)
    df_ano["valor"] = pd.to_numeric(df_ano["valor"])
    df_ano["mes_num"] = pd.to_datetime(df_ano["data"]).dt.month

    if movimentacao_sel:
        df_ano = df_ano[df_ano["movimentacao"].isin(movimentacao_sel)]
    if status_sel and "status" in df_ano.columns:
        df_ano = df_ano[df_ano["status"].isin(status_sel)]

    pivot = (
        df_ano.groupby(["mes_num", "movimentacao"])["valor"]
        .sum()
        .unstack(fill_value=0)
        .reindex(range(1, 13), fill_value=0)
    )

    entradas_mes = pivot.get("Entrada", pd.Series(0, index=pivot.index))
    saidas_mes = pivot.get("Saída", pd.Series(0, index=pivot.index))

    longo = pd.DataFrame({
        "mes_num": list(range(1, 13)) * 3,
        "Serie": ["Entradas"] * 12 + ["Saídas"] * 12 + ["Saldo"] * 12,
        "valor": list(entradas_mes) + list(saidas_mes) + list(entradas_mes - saidas_mes),
    })
    longo["mes"] = longo["mes_num"].apply(lambda m: MESES[m - 1])
    longo["valor_label"] = longo["valor"].apply(lambda v: f"R$ {v:,.0f}")

    base_linha = alt.Chart(longo)
    cor_scale = alt.Scale(
        domain=["Entradas", "Saídas", "Saldo"],
        range=["#22c55e", "#ef4444", "#3b82f6"],
    )
    encode_base = dict(
        x=alt.X("mes:N", sort=MESES, title=""),
        color=alt.Color("Serie:N", scale=cor_scale, title=""),
    )

    linhas = base_linha.mark_line(point=True).encode(
        **encode_base,
        y=alt.Y("valor:Q", title="R$", axis=alt.Axis(format=",.0f")),
        tooltip=[
            alt.Tooltip("mes:N", title="Mês"),
            alt.Tooltip("Serie:N", title="Série"),
            alt.Tooltip("valor:Q", title="Valor", format=",.2f"),
        ],
    )

    rotulos_linha = base_linha.mark_text(dy=-10, fontSize=11).encode(
        **encode_base,
        y=alt.Y("valor:Q"),
        text=alt.Text("valor_label:N"),
    )

    grafico = (
        (linhas + rotulos_linha)
        .properties(height=350)
        .configure_view(strokeOpacity=0, fill="#1a1b26")
        .configure_axis(
            labelColor="rgba(232,234,240,0.5)",
            titleColor="rgba(232,234,240,0.4)",
            gridColor="rgba(255,255,255,0.04)",
            domainColor="rgba(255,255,255,0.07)",
        )
        .configure_legend(
            labelColor="rgba(232,234,240,0.7)",
            titleColor="rgba(232,234,240,0.4)",
        )
    )
    st.altair_chart(grafico, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Calendário interativo (só quando um mês está selecionado)
# ---------------------------------------------------------------------------
if mes_sel != "Todos":
    # Reseta seleção ao trocar de mês/ano
    chave_periodo = (ano, mes_sel)
    if st.session_state.cal_mes_prev != chave_periodo:
        st.session_state.cal_dia_sel = None
        st.session_state.cal_mes_prev = chave_periodo

    dia_sel = st.session_state.cal_dia_sel

    st.markdown('<span id="calendario-start" style="display:none"></span>', unsafe_allow_html=True)

    # Cabeçalho
    col_titulo_cal, col_clear = st.columns([5, 2])
    with col_titulo_cal:
        st.subheader(f"Calendário de {titulo_periodo}")
    with col_clear:
        if dia_sel:
            st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)
            if st.button(
                f"✕ {dia_sel:02d}/{MESES[mes_sel-1]} — limpar filtro",
                key="cal_clear",
                use_container_width=True,
            ):
                st.session_state.cal_dia_sel = None
                st.rerun()

    # Agrupamentos por dia
    por_dia = (
        df.groupby([df["data"].apply(lambda d: d.day), "movimentacao"])["valor"]
        .sum()
        .unstack(fill_value=0)
    )
    entradas_dia = por_dia.get("Entrada", {}).to_dict() if "Entrada" in por_dia.columns else {}
    saidas_dia   = por_dia.get("Saída",   {}).to_dict() if "Saída"   in por_dia.columns else {}

    cal_obj   = calendar.Calendar(firstweekday=0)
    semanas   = cal_obj.monthdayscalendar(ano, mes_sel)
    DIAS_SEMANA = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    hoje_dia  = hoje.day if (mes_sel == hoje.month and ano == hoje.year) else -1

    # Linha de cabeçalho dos dias da semana
    cols_header = st.columns(7)
    for i, nome in enumerate(DIAS_SEMANA):
        cor_header = "#a5b4fc" if i >= 5 else "rgba(232,234,240,0.4)"
        cols_header[i].markdown(
            f"<div style='text-align:center;font-size:11px;font-weight:600;"
            f"letter-spacing:0.06em;color:{cor_header};padding:4px 0'>{nome}</div>",
            unsafe_allow_html=True,
        )

    # Células dos dias
    for semana in semanas:
        cols = st.columns(7)
        for i, dia in enumerate(semana):
            with cols[i]:
                if dia == 0:
                    # Célula vazia estilizada
                    st.markdown(
                        "<div style='min-height:68px;border-radius:9px;"
                        "background:rgba(255,255,255,0.02);margin:2px 0'></div>",
                        unsafe_allow_html=True,
                    )
                    continue

                entrada = entradas_dia.get(dia, 0)
                saida   = saidas_dia.get(dia, 0)
                e_hoje  = (dia == hoje_dia)

                # Linha 1: número do dia + marcador de hoje
                marcador_hoje = " 🔵" if e_hoje else ""
                label_partes  = [f"{dia}{marcador_hoje}"]

                if entrada:
                    v = formatar_moeda(entrada).replace("R$\u00a0", "").replace("R$ ", "")
                    label_partes.append(f"+R${v}")
                if saida:
                    v = formatar_moeda(saida).replace("R$\u00a0", "").replace("R$ ", "")
                    label_partes.append(f"-R${v}")

                label      = "\n".join(label_partes)
                selecionado = (dia_sel == dia)

                if st.button(
                    label,
                    key=f"cal_{ano}_{mes_sel}_{dia}",
                    type="primary" if selecionado else "secondary",
                    use_container_width=True,
                ):
                    # Toggle: clicar no mesmo dia desfaz a seleção
                    st.session_state.cal_dia_sel = None if selecionado else dia
                    st.rerun()

    st.divider()
    st.markdown('<span id="calendario-end" style="display:none"></span>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Tabela com edição e exclusão
# ---------------------------------------------------------------------------

# Aplica filtro de dia do calendário (se houver)
_dia_ativo = st.session_state.get("cal_dia_sel") if mes_sel != "Todos" else None
df_tabela = df[df["data"].apply(lambda d: d.day) == _dia_ativo].copy() if _dia_ativo else df.copy()

# Subtítulo da tabela: mostra dia selecionado, se houver
if _dia_ativo:
    subtitulo_tab = f"{_dia_ativo:02d}/{MESES[mes_sel-1]}/{ano} — clique no dia novamente para limpar"
    badge = (f"<span style='background:rgba(99,102,241,0.18);border:1px solid rgba(99,102,241,0.35);"
             f"border-radius:100px;padding:2px 10px;font-size:10px;color:#a5b4fc;"
             f"margin-left:8px'>{_dia_ativo:02d}/{MESES[mes_sel-1]}</span>")
else:
    subtitulo_tab = titulo_periodo
    badge = ""

st.markdown(f"""
<div style="background:#1a1b26;border:1px solid rgba(255,255,255,0.07);
            border-radius:10px 10px 0 0;padding:14px 18px 12px;
            border-bottom:1px solid rgba(255,255,255,0.07)">
    <div style="font-size:13px;font-weight:600;color:#e8eaf0">Transações{badge}</div>
    <div style="font-size:11px;color:rgba(232,234,240,0.35);margin-top:2px">{subtitulo_tab}</div>
</div>
""", unsafe_allow_html=True)

colunas_visiveis = ["id", "data", "movimentacao", "categoria", "descricao",
                    "valor", "responsavel", "telefone", "fonte", "parcelas", "status"]

# `telefone` pode não existir em linhas antigas — garante a coluna no df
if "telefone" not in df_tabela.columns:
    df_tabela = df_tabela.copy()
    df_tabela["telefone"] = None

df_editavel = df_tabela[colunas_visiveis].copy()
df_editavel["data"] = df_editavel["data"].apply(lambda d: d.strftime("%d/%m/%Y"))
df_editavel["excluir"] = False

_cats_tabela = sorted(set(_get_categorias("Saída") + _get_categorias("Entrada")))

editado = st.data_editor(
    df_editavel,
    width="stretch",
    hide_index=True,
    disabled=["id", "data", "telefone"],
    column_config={
        "movimentacao": st.column_config.SelectboxColumn(
            options=["Entrada", "Saída"], required=True),
        "responsavel": st.column_config.SelectboxColumn(
            options=["Y", "M", "MY"], required=True),
        "fonte": st.column_config.SelectboxColumn(
            options=["Dinheiro", "Cartão Crédito"], required=True),
        "status": st.column_config.SelectboxColumn(
            options=["Pago", "Recebido", "A pagar", "A receber", "Atrasado"],
            required=True),
        "categoria": st.column_config.SelectboxColumn(
            options=_cats_tabela, required=True) if _cats_tabela else None,
        "valor": st.column_config.NumberColumn(format="R$ %.2f", min_value=0.01),
        "telefone": st.column_config.TextColumn("Telefone", disabled=True),
        "excluir": st.column_config.CheckboxColumn("🗑️"),
    },
    key="tabela_edicao",
)

col_s, col_d = st.columns(2)

with col_s:
    if st.button("💾 Salvar alterações", type="primary", use_container_width=True):
        alteracoes = 0
        original = df_tabela[colunas_visiveis].set_index("id")
        novo = editado.set_index("id")

        for id_trans in novo.index:
            linha_original = original.loc[id_trans].to_dict()
            linha_nova = novo.loc[id_trans].drop("excluir").to_dict()

            # "data" é desabilitado na tabela — exclui para evitar falso diff por tipo
            diff = {k: v for k, v in linha_nova.items()
                    if k != "data" and str(linha_original.get(k, "")) != str(v)}

            if diff:
                if "valor" in diff:
                    diff["valor"] = float(diff["valor"])
                try:
                    atualizar_transacao(int(id_trans), diff)
                    alteracoes += 1
                except RuntimeError as err:
                    st.error(f"Erro ao atualizar #{id_trans}: {err}")

        if alteracoes:
            st.success(f"{alteracoes} transação(ões) atualizada(s).")
            st.rerun()
        else:
            st.info("Nenhuma alteração detectada.")

with col_d:
    if st.button("🗑️ Excluir marcadas", use_container_width=True):
        para_excluir = editado[editado["excluir"]]["id"].tolist()
        if not para_excluir:
            st.info("Nenhuma transação marcada para exclusão.")
        else:
            for id_trans in para_excluir:
                try:
                    deletar_transacao(int(id_trans))
                except RuntimeError as err:
                    st.error(f"Erro ao excluir #{id_trans}: {err}")
            st.success(f"{len(para_excluir)} transação(ões) excluída(s).")
            st.rerun()