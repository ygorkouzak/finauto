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
)

from utils import formatar_moeda, enviar_lembrete_twilio

st.set_page_config(page_title="FinAuto", page_icon="💰", layout="wide")

st.markdown(
    """
    <style>
    /* Neutraliza fundo vermelho dos pills do multiselect */
    span[data-baseweb="tag"] {
        background-color: #334155 !important;
    }
    span[data-baseweb="tag"] span {
        color: #f1f5f9 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

@st.cache_data(ttl=300)
def _get_categorias(movimentacao=None):
    try:
        return listar_categorias(movimentacao)
    except Exception:
        return []


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
        parcelas = st.text_input("Parcelas", value="1", help="'1' à vista, ou 'N/T' (ex: '2/10')")
        _cats = _get_categorias(mov)
        categoria = st.selectbox("Categoria", _cats if _cats else ["—"])

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
                "parcelas": parcelas.strip() or "1",
                "data": data.isoformat(),
                "fonte": fonte,
                "status": status,
            }
            try:
                inserir_transacao(dados_novos)
                st.success("Transação adicionada!")
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
col1.metric("Entradas", formatar_moeda(entradas))
col2.metric("Saídas", formatar_moeda(saidas))
col3.metric("Saldo", formatar_moeda(saldo))

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
col_a.metric("Saldo realizado", formatar_moeda(saldo_real),
             help="Só conta o que já foi Pago/Recebido.")
col_b.metric("Taxa de poupança", f"{taxa_poupanca:.1f}%",
             help="Saldo realizado / Entradas recebidas. Saudável: >20%.")
col_c.metric("Comprometimento com D. Fixa", f"{compromet_fixa:.1f}%",
             help="Despesas fixas / Entradas recebidas. Crítico: >50%.")

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

        cols_row = st.columns([4, 1, 1, 1]) if chave_prefix == "prox" else st.columns([4, 1, 1])
        with cols_row[0]:
            st.markdown(
                f"{cor} **{linha['data']}** — {linha['descricao']} "
                f"({linha['categoria']}) — "
                f"{formatar_moeda(linha['valor']).replace('$', chr(92) + '$')} "
                f"· {linha['responsavel']}"
            )
        with cols_row[1]:
            if st.button("✏️", key=f"edit_{chave_prefix}_{linha['id']}", width="stretch"):
                modal_editar_transacao(dict(linha))
        if chave_prefix == "prox":
            with cols_row[2]:
                if st.button("📱", key=f"lembrete_{linha['id']}", width="stretch",
                             help="Enviar lembrete WhatsApp"):
                    try:
                        sid = enviar_lembrete_twilio(
                            linha["responsavel"],
                            linha["data"],
                            linha["descricao"],
                        )
                        st.success(f"Lembrete enviado! ({sid[:8]}…)")
                    except RuntimeError as err:
                        st.error(str(err))
            with cols_row[3]:
                if st.button(label_btn, key=f"{chave_prefix}_{linha['id']}", width="stretch"):
                    try:
                        marcar_como_quitado(int(linha["id"]), linha["movimentacao"])
                        st.rerun()
                    except RuntimeError as err:
                        st.error(f"Erro: {err}")
        else:
            with cols_row[2]:
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
        c1.metric("📥 A receber", formatar_moeda(prev_entrada))
        c2.metric("📤 A pagar", formatar_moeda(prev_saida))
        _render_lista_com_quitar("Próximos 30 dias", proximas, "prox")
    else:
        st.subheader("📅 Próximos 30 dias")
        st.info("Sem compromissos agendados.")

st.divider()

# ---------------------------------------------------------------------------
# Gráficos de barras — categorias
# ---------------------------------------------------------------------------
def _grafico_barras(df_valor, cor):
    df_valor = df_valor.copy()
    df_valor["valor_label"] = df_valor["valor"].apply(lambda v: f"R$ {v:,.0f}")

    base = alt.Chart(df_valor).encode(
        y=alt.Y("categoria:N", sort="-x", title=""),
    )

    barras = base.mark_bar(color=cor).encode(
        x=alt.X("valor:Q", title="R$", axis=alt.Axis(format=",.0f")),
        tooltip=[
            alt.Tooltip("categoria:N", title="Categoria"),
            alt.Tooltip("valor:Q", title="Valor", format=",.2f"),
        ],
    )

    rotulos = base.mark_text(
        align="left",
        baseline="middle",
        dx=4,
        color="#e5e7eb",
    ).encode(
        x=alt.X("valor:Q"),
        text=alt.Text("valor_label:N"),
    )

    return (barras + rotulos).properties(height=alt.Step(28))

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

    grafico = (linhas + rotulos_linha).properties(height=350)
    st.altair_chart(grafico, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Calendário (só quando um mês está selecionado)
# ---------------------------------------------------------------------------
if mes_sel != "Todos":
    st.subheader(f"Calendário de {titulo_periodo}")

    por_dia = (
        df.groupby([df["data"].apply(lambda d: d.day), "movimentacao"])["valor"]
        .sum()
        .unstack(fill_value=0)
    )
    entradas_dia = por_dia.get("Entrada", {}).to_dict() if "Entrada" in por_dia.columns else {}
    saidas_dia = por_dia.get("Saída", {}).to_dict() if "Saída" in por_dia.columns else {}

    cal = calendar.Calendar(firstweekday=0)
    semanas = cal.monthdayscalendar(ano, mes_sel)
    DIAS_SEMANA = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

    cols_header = st.columns(7)
    for i, nome in enumerate(DIAS_SEMANA):
        cols_header[i].markdown(f"**{nome}**")

    for semana in semanas:
        cols = st.columns(7)
        for i, dia in enumerate(semana):
            with cols[i]:
                if dia == 0:
                    st.markdown("&nbsp;", unsafe_allow_html=True)
                    continue

                entrada = entradas_dia.get(dia, 0)
                saida = saidas_dia.get(dia, 0)

                linhas = [f"**{dia}**"]
                if entrada:
                    texto_e = formatar_moeda(entrada).replace("$", "\\$")
                    linhas.append(f"<span style='color:#22c55e'>+{texto_e}</span>")
                if saida:
                    texto_s = formatar_moeda(saida).replace("$", "\\$")
                    linhas.append(f"<span style='color:#ef4444'>-{texto_s}</span>")

                st.markdown("<br>".join(linhas), unsafe_allow_html=True)

    st.divider()

# ---------------------------------------------------------------------------
# Tabela com edição e exclusão
# ---------------------------------------------------------------------------
st.subheader(f"Transações de {titulo_periodo}")

colunas_visiveis = ["id", "data", "movimentacao", "categoria", "descricao",
                    "valor", "responsavel", "fonte", "parcelas", "status"]

df_editavel = df[colunas_visiveis].copy()
df_editavel["data"] = df_editavel["data"].apply(lambda d: d.strftime("%d/%m/%Y"))
df_editavel["excluir"] = False

_cats_tabela = sorted(set(_get_categorias("Saída") + _get_categorias("Entrada")))

editado = st.data_editor(
    df_editavel,
    width="stretch",
    hide_index=True,
    disabled=["id", "data"],
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
        "excluir": st.column_config.CheckboxColumn("🗑️"),
    },
    key="tabela_edicao",
)

col_s, col_d = st.columns(2)

with col_s:
    if st.button("💾 Salvar alterações", type="primary", width="stretch"):
        alteracoes = 0
        original = df[colunas_visiveis].set_index("id")
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
    if st.button("🗑️ Excluir marcadas", width="stretch"):
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