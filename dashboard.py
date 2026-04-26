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

# Estilização CSS para os Cards de KPI
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'Inter', sans-serif !important;
}

div[data-testid="metric-container"] {
    background: #1a1b26 !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 10px !important;
    padding: 16px 18px !important;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
}
</style>
""", unsafe_allow_html=True)

st.title("💰 FinAuto - Dashboard Financeiro")

# --- Filtros na Barra Lateral ---
st.sidebar.header("Filtros")
mes_atual = datetime.now().month
ano_atual = datetime.now().year

mes = st.sidebar.selectbox("Mês", list(range(1, 13)), index=mes_atual-1, format_func=lambda x: calendar.month_name[x])
ano = st.sidebar.selectbox("Ano", [ano_atual, ano_atual-1], index=0)

# --- Carregamento de Dados ---
df = listar_transacoes(ano=ano, mes=mes)

if df.empty:
    st.warning(f"Nenhuma transação encontrada para {calendar.month_name[mes]}/{ano}.")
else:
    # --- KPIs Principais ---
    receita = df[df['movimentacao'] == 'Entrada']['valor'].sum()
    despesa = df[df['movimentacao'] == 'Saída']['valor'].sum()
    saldo = receita - despesa

    c1, c2, c3 = st.columns(3)
    c1.metric("Faturamento", formatar_moeda(receita))
    c2.metric("Despesas", formatar_moeda(despesa), delta_color="inverse")
    c3.metric("Saldo Líquido", formatar_moeda(saldo))

    st.divider()

    # --- Gráficos ---
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.subheader("Despesas por Categoria")
        df_gastos = df[df['movimentacao'] == 'Saída'].groupby('categoria')['valor'].sum().reset_index()
        chart_cat = alt.Chart(df_gastos).mark_arc(innerRadius=50).encode(
            theta=alt.Theta(field="valor", type="quantitative"),
            color=alt.Color(field="categoria", type="nominal"),
            tooltip=['categoria', 'valor']
        )
        st.altair_chart(chart_cat, use_container_width=True)

    with col_g2:
        st.subheader("Evolução Mensal")
        df_evolucao = listar_evolucao_mensal()
        chart_evol = alt.Chart(df_evolucao).mark_line(point=True).encode(
            x='mes_ano:T',
            y='total:Q',
            color='movimentacao:N',
            tooltip=['mes_ano', 'total', 'movimentacao']
        )
        st.altair_chart(chart_evol, use_container_width=True)

# --- Seção: Adicionar Transação Manual ---
st.divider()
with st.expander("➕ Adicionar Nova Transação Manual"):
    with st.form("form_nova_transacao"):
        c_mov, c_resp, c_tipo = st.columns(3)
        with c_mov:
            # Ao mudar aqui, a lista de categorias abaixo será filtrada
            mov_manual = st.selectbox("Movimentação", ["Saída", "Entrada"])
        with c_resp:
            resp_manual = st.selectbox("Responsável", ["Y", "M", "MY"])
        with c_tipo:
            tipo_manual = st.selectbox("Tipo", ["P. Unico", "D. Fixa", "Parcelado", "Receita Fixa"])

        c_cat, c_desc, c_val = st.columns(3)
        with c_cat:
            # Lógica Dinâmica: Usa a função do db.py com o filtro de movimentação
            opcoes_cat = listar_categorias(mov_manual)
            cat_manual = st.selectbox("Categoria", opcoes_cat)
        with c_desc:
            desc_manual = st.text_input("Descrição")
        with c_val:
            val_manual = st.number_input("Valor", min_value=0.0, step=0.01)

        c_data, c_fonte, c_status = st.columns(3)
        with c_data:
            data_manual = st.date_input("Data", datetime.now())
        with c_fonte:
            fonte_manual = st.text_input("Fonte/Cartão", value="Nubank")
        with c_status:
            status_manual = st.selectbox("Status", ["Pago", "Pendente"])

        btn_salvar = st.form_submit_button("Salvar Transação")

        if btn_salvar:
            nova_t = {
                "movimentacao": mov_manual,
                "responsavel": resp_manual,
                "tipo": tipo_manual,
                "categoria": cat_manual,
                "descricao": desc_manual,
                "valor": val_manual,
                "data": data_manual.strftime("%Y-%m-%d"),
                "fonte": fonte_manual,
                "status": status_manual,
                "parcelas": "1/1"
            }
            try:
                id_gerado = inserir_transacao(nova_t)
                gerar_recorrencias(id_gerado)
                st.success(f"Transação #{id_gerado} inserida com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao inserir: {e}")

# --- Tabela de Edição e Exclusão ---
st.divider()
st.subheader("📝 Gerenciar Transações")
if not df.empty:
    # Preparar DF para o data_editor
    df_edit = df.copy()
    df_edit.insert(0, "excluir", False)
    
    # Lista de todas as categorias para o seletor da tabela (opcionalmente pode ser a lista completa)
    todas_cats = listar_categorias()

    editado = st.data_editor(
        df_edit,
        column_config={
            "excluir": st.column_config.CheckboxColumn("🗑️"),
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "valor": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
            "categoria": st.column_config.SelectboxColumn("Categoria", options=todas_cats),
            "movimentacao": st.column_config.SelectboxColumn("Mov", options=["Saída", "Entrada"]),
            "responsavel": st.column_config.SelectboxColumn("Resp", options=["Y", "M", "MY"]),
            "tipo": st.column_config.SelectboxColumn("Tipo", options=["P. Unico", "D. Fixa", "Parcelado", "Receita Fixa"]),
            "data": st.column_config.DateColumn("Data", disabled=True)
        },
        disabled=["id", "data"],
        hide_index=True,
        use_container_width=True
    )

    col_u, col_d = st.columns([1, 4])
    with col_u:
        if st.button("💾 Salvar Alterações", use_container_width=True):
            # Lógica para detectar mudanças e chamar atualizar_transacao...
            # (Simplificado: compara df original com o editado)
            alteracoes = 0
            for i in range(len(editado)):
                id_trans = editado.iloc[i]['id']
                # Aqui você faria a comparação campo a campo e chamaria atualizar_transacao(id_trans, novos_dados)
                pass
            st.info("Funcionalidade de salvamento em lote pronta para ser implementada.")

    with col_d:
        if st.button("🗑️ Excluir marcadas", use_container_width=True):
            para_excluir = editado[editado["excluir"]]["id"].tolist()
            if para_excluir:
                for id_excluir in para_excluir:
                    deletar_transacao(id_excluir)
                st.success(f"{len(para_excluir)} transações excluídas.")
                st.rerun()