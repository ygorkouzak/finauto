"""
db.py — Módulo de acesso ao banco de dados Supabase.
Responsabilidade única: inserir e ler da tabela `transacoes`.
"""
import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_URL ou SUPABASE_KEY não encontrados no .env"
    )

TABELA = "transacoes"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def inserir_transacao(dados):
    """
    Insere um dict de transação na tabela `transacoes`.
    Retorna o id gerado pelo banco.
    """
    print(f"[DB] Inserindo: {dados}")

    try:
        resposta = supabase.table(TABELA).insert(dados).execute()
    except Exception as err:
        raise RuntimeError(f"Falha ao inserir no Supabase: {err}") from err

    if not resposta.data:
        raise RuntimeError(f"Supabase não retornou dados após insert: {resposta}")

    id_gerado = resposta.data[0]["id"]
    print(f"[DB] OK, id={id_gerado}")
    return id_gerado


def listar_ultimas(limite=5):
    """
    Devolve as últimas N transações (ordenadas da mais nova para a mais antiga).
    """
    try:
        resposta = (
            supabase.table(TABELA)
            .select("*")
            .order("id", desc=True)
            .limit(limite)
            .execute()
        )
    except Exception as err:
        raise RuntimeError(f"Falha ao ler do Supabase: {err}") from err

    return resposta.data


def listar_transacoes(ano=None, mes=None, responsavel=None):
    """
    Lê transações do banco com filtros opcionais.
    - ano/mes: filtra por período (ex: ano=2026, mes=4)
    - responsavel: "Y", "M" ou "MY"
    """
    query = supabase.table(TABELA).select("*").order("id", desc=True)

    if ano and mes:
        data_inicio = f"{ano}-{mes:02d}-01"
        prox_mes = mes + 1 if mes < 12 else 1
        prox_ano = ano if mes < 12 else ano + 1
        data_fim = f"{prox_ano}-{prox_mes:02d}-01"
        query = query.gte("data", data_inicio).lt("data", data_fim)

    if responsavel:
        query = query.eq("responsavel", responsavel)

    try:
        resposta = query.execute()
    except Exception as err:
        raise RuntimeError(f"Falha ao ler do Supabase: {err}") from err

    return resposta.data

def listar_categorias(movimentacao=None):
    """Retorna categorias únicas. Se movimentacao='Entrada'/'Saída', filtra por tipo."""
    try:
        query = supabase.table(TABELA).select("categoria, movimentacao")
        if movimentacao:
            query = query.eq("movimentacao", movimentacao)
        resposta = query.execute()
    except Exception as err:
        raise RuntimeError(f"Falha ao ler categorias: {err}") from err

    cats = {row["categoria"] for row in resposta.data if row.get("categoria")}
    return sorted(cats)


def listar_evolucao_mensal(ano, responsavel=None):
    """Retorna todas as transações do ano, para o gráfico de evolução mensal."""
    query = (
        supabase.table(TABELA)
        .select("data, movimentacao, valor")
        .gte("data", f"{ano}-01-01")
        .lt("data", f"{ano + 1}-01-01")
    )
    if responsavel:
        query = query.eq("responsavel", responsavel)

    try:
        resposta = query.execute()
    except Exception as err:
        raise RuntimeError(f"Falha ao ler do Supabase: {err}") from err

    return resposta.data


def atualizar_transacao(id_transacao, novos_dados):
    """Atualiza campos de uma transação existente."""
    try:
        resposta = (
            supabase.table(TABELA)
            .update(novos_dados)
            .eq("id", id_transacao)
            .execute()
        )
    except Exception as err:
        raise RuntimeError(f"Falha ao atualizar: {err}") from err

    if not resposta.data:
        raise RuntimeError(f"Nenhuma transação encontrada com id {id_transacao}")

    print(f"[DB] Atualizada id={id_transacao}")
    return resposta.data[0]


def deletar_transacao(id_transacao):
    """Remove uma transação pelo id."""
    try:
        supabase.table(TABELA).delete().eq("id", id_transacao).execute()
    except Exception as err:
        raise RuntimeError(f"Falha ao deletar: {err}") from err

    print(f"[DB] Deletada id={id_transacao}")

def listar_proximos(dias=30, responsavel=None):
    """
    Transações futuras (A pagar / A receber) nos próximos N dias.
    Útil para planejamento.
    """
    from datetime import date, timedelta
    hoje = date.today().isoformat()
    limite = (date.today() + timedelta(days=dias)).isoformat()

    query = (
        supabase.table(TABELA)
        .select("*")
        .in_("status", ["A pagar", "A receber"])
        .gte("data", hoje)
        .lte("data", limite)
        .order("data")
    )
    if responsavel:
        query = query.eq("responsavel", responsavel)

    try:
        return query.execute().data
    except Exception as err:
        raise RuntimeError(f"Falha ao ler futuras: {err}") from err


def listar_atrasadas(responsavel=None):
    """Transações com status 'Atrasado'."""
    query = (
        supabase.table(TABELA)
        .select("*")
        .eq("status", "Atrasado")
        .order("data")
    )
    if responsavel:
        query = query.eq("responsavel", responsavel)

    try:
        return query.execute().data
    except Exception as err:
        raise RuntimeError(f"Falha ao ler atrasadas: {err}") from err

def marcar_como_quitado(id_transacao, movimentacao):
    """
    Muda status para 'Pago' (Saída) ou 'Recebido' (Entrada).
    """
    novo_status = "Pago" if movimentacao == "Saída" else "Recebido"
    try:
        supabase.table(TABELA).update({"status": novo_status}).eq("id", id_transacao).execute()
    except Exception as err:
        raise RuntimeError(f"Falha ao quitar: {err}") from err

    print(f"[DB] Quitado id={id_transacao} → {novo_status}")

if __name__ == "__main__":
    transacao_teste = {
        "movimentacao": "Saída",
        "responsavel": "Y",
        "tipo": "P. Unico",
        "categoria": "Alimentação",
        "descricao": "Teste inicial",
        "valor": 10.00,
        "parcelas": "1",
        "data": "2026-04-19",
        "fonte": "Dinheiro",
        "status": "Pago",
    }

    id_novo = inserir_transacao(transacao_teste)
    print(f"\nTransação inserida com id {id_novo}")

    print("\nÚltimas transações no banco:")
    for linha in listar_ultimas(3):
        print(f"  #{linha['id']}: {linha['descricao']} - R$ {linha['valor']}")