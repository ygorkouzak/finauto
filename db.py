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


def buscar_historico(texto, limite=3):
    """
    Busca transações anteriores cuja descrição contenha palavras do texto.
    Usado para dar contexto à IA sobre padrões recorrentes (ex: 'energia' → D. Fixa).
    """
    palavras = [p for p in texto.lower().split() if len(p) > 2]
    vistos = {}
    for palavra in palavras[:4]:
        try:
            r = (
                supabase.table(TABELA)
                .select("descricao, movimentacao, tipo, categoria, fonte, status, responsavel")
                .ilike("descricao", f"%{palavra}%")
                .order("id", desc=True)
                .limit(limite)
                .execute()
            )
            for row in r.data:
                key = row.get("descricao", "").lower()
                if key not in vistos:
                    vistos[key] = row
        except Exception:
            pass
    return list(vistos.values())[:limite]


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

# ---------------------------------------------------------------------------
# Pendências — perguntas de volta do classificador aguardando resposta.
# Uma linha por telefone. TTL de 15 minutos aplicado aqui (não no banco).
# ---------------------------------------------------------------------------
TABELA_PENDENCIAS = "pendencias"
PENDENCIA_TTL_MINUTOS = 15


def ler_pendencia_ativa(telefone):
    """
    Devolve a pendência não expirada para o telefone, ou None.
    Também limpa a linha se estiver fora do TTL.
    """
    from datetime import datetime, timedelta, timezone

    if not telefone:
        return None

    try:
        resp = (
            supabase.table(TABELA_PENDENCIAS)
            .select("*")
            .eq("telefone", telefone)
            .limit(1)
            .execute()
        )
    except Exception as err:
        print(f"[DB] Aviso ler_pendencia: {err}")
        return None

    if not resp.data:
        return None

    linha = resp.data[0]
    criado_em_str = linha.get("created_at") or ""
    try:
        # Supabase devolve ISO 8601 com timezone (ex: 2026-04-21T22:15:00+00:00)
        criado_em = datetime.fromisoformat(criado_em_str.replace("Z", "+00:00"))
    except ValueError:
        print(f"[DB] Aviso: created_at fora do padrao: {criado_em_str!r}")
        return None

    agora = datetime.now(timezone.utc)
    if agora - criado_em > timedelta(minutes=PENDENCIA_TTL_MINUTOS):
        remover_pendencia(telefone)
        return None

    return linha


def salvar_pendencia(telefone, mensagem, pergunta, tentativas, responsavel=None):
    """
    Upsert da pendência. Reinicia created_at a cada gravação.
    `mensagem` é o texto acumulado (original + respostas anteriores concatenadas).
    """
    from datetime import datetime, timezone

    if not telefone:
        raise ValueError("telefone obrigatório para salvar pendência.")

    payload = {
        "telefone": telefone,
        "mensagem": mensagem,
        "pergunta": pergunta,
        "tentativas": int(tentativas),
        "responsavel": responsavel,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        supabase.table(TABELA_PENDENCIAS).upsert(payload, on_conflict="telefone").execute()
    except Exception as err:
        raise RuntimeError(f"Falha ao salvar pendência: {err}") from err

    print(f"[DB] Pendência salva tel={telefone} tentativa={tentativas}")


def remover_pendencia(telefone):
    """Apaga a pendência do telefone (se existir). Nunca levanta erro."""
    if not telefone:
        return
    try:
        supabase.table(TABELA_PENDENCIAS).delete().eq("telefone", telefone).execute()
        print(f"[DB] Pendência removida tel={telefone}")
    except Exception as err:
        print(f"[DB] Aviso remover_pendencia: {err}")


def marcar_como_quitado(id_transacao, movimentacao):
    """
    Muda status para 'Pago' (Saída) ou 'Recebido' (Entrada).
    """
    novo_status = "Pago" if movimentacao == "Saída" else "Recebido"
    try:
        supabase.table(TABELA).update({"status": novo_status}).eq("id", id_transacao).execute()
    except Exception as err:
        raise RuntimeError(f"Falha ao quitar: {err}") from err

    print(f"[DB] Quitado id={id_transacao} -> {novo_status}")


def _ja_existe_no_mes(descricao, responsavel, ano, mes):
    """Retorna True se já há transação com essa descrição+responsável nesse mês."""
    try:
        prox_mes = mes + 1 if mes < 12 else 1
        prox_ano = ano if mes < 12 else ano + 1
        resp = (
            supabase.table(TABELA)
            .select("id")
            .ilike("descricao", descricao)
            .eq("responsavel", responsavel)
            .gte("data", f"{ano}-{mes:02d}-01")
            .lt("data", f"{prox_ano}-{prox_mes:02d}-01")
            .limit(1)
            .execute()
        )
        return len(resp.data) > 0
    except Exception:
        return False


def gerar_recorrencias(id_transacao):
    """
    Gera recorrências futuras para uma transação D. Fixa ou Parcelado.
    D. Fixa: uma entrada por mês até 12 meses a frente do dia de hoje.
    Parcelado: parcelas N+1 até o total, cada uma no mês seguinte.
    Pula meses que já possuem entrada com mesma descrição+responsável.
    Retorna quantidade de registros inseridos.
    """
    from dateutil.relativedelta import relativedelta
    from datetime import date

    try:
        resp = supabase.table(TABELA).select("*").eq("id", id_transacao).execute()
    except Exception as err:
        raise RuntimeError(f"Transação {id_transacao} não encontrada: {err}") from err

    if not resp.data:
        raise RuntimeError(f"Transação {id_transacao} não encontrada")

    t = resp.data[0]
    tipo = t.get("tipo", "")
    if tipo not in ("D. Fixa", "Parcelado"):
        return 0

    data_base = date.fromisoformat(t["data"])
    hoje = date.today()
    base = {k: v for k, v in t.items() if k != "id"}
    inseridos = 0

    if tipo == "Parcelado":
        parcelas_str = t.get("parcelas", "1")
        if "/" not in parcelas_str:
            return 0
        try:
            n_atual, total = map(int, parcelas_str.split("/"))
        except ValueError:
            return 0

        for i in range(n_atual + 1, total + 1):
            nova_data = data_base + relativedelta(months=(i - n_atual))
            if _ja_existe_no_mes(t["descricao"], t["responsavel"], nova_data.year, nova_data.month):
                continue
            novo = {**base,
                    "data": nova_data.isoformat(),
                    "parcelas": f"{i}/{total}",
                    "status": "A pagar" if t["movimentacao"] == "Saída" else "A receber"}
            try:
                supabase.table(TABELA).insert(novo).execute()
                inseridos += 1
            except Exception as err:
                print(f"[DB] Aviso recorrência Parcelado: {err}")

    elif tipo == "D. Fixa":
        horizonte = hoje + relativedelta(months=12)
        proximo = data_base + relativedelta(months=1)
        while proximo <= horizonte:
            if not _ja_existe_no_mes(t["descricao"], t["responsavel"], proximo.year, proximo.month):
                novo = {**base,
                        "data": proximo.isoformat(),
                        "status": "A pagar" if t["movimentacao"] == "Saída" else "A receber"}
                try:
                    supabase.table(TABELA).insert(novo).execute()
                    inseridos += 1
                except Exception as err:
                    print(f"[DB] Aviso recorrência D.Fixa: {err}")
            proximo += relativedelta(months=1)

    print(f"[DB] Geradas {inseridos} recorrências para id={id_transacao} (tipo={tipo})")
    return inseridos


def gerar_recorrencias_retroativas():
    """
    Varre D. Fixa e Parcelado existentes e gera recorrências faltantes.
    Para D. Fixa processa a partir da entrada mais antiga de cada série.
    Para Parcelado processa a partir da menor parcela de cada série.
    Retorna total de registros inseridos.
    """
    try:
        resp = (
            supabase.table(TABELA)
            .select("*")
            .in_("tipo", ["D. Fixa", "Parcelado"])
            .order("data")
            .execute()
        )
    except Exception as err:
        raise RuntimeError(f"Falha ao listar recorrentes: {err}") from err

    vistos_fixas = {}       # chave → id mais antigo
    vistos_parcelados = {}  # chave → (n_menor, id)

    for t in resp.data:
        tipo = t["tipo"]
        chave = (t["descricao"].lower().strip(), t["responsavel"])

        if tipo == "D. Fixa":
            if chave not in vistos_fixas:
                vistos_fixas[chave] = t["id"]

        elif tipo == "Parcelado":
            parcelas_str = t.get("parcelas", "")
            if "/" not in parcelas_str:
                continue
            try:
                n, _ = map(int, parcelas_str.split("/"))
            except ValueError:
                continue
            if chave not in vistos_parcelados or n < vistos_parcelados[chave][0]:
                vistos_parcelados[chave] = (n, t["id"])

    total_inseridos = 0

    for chave, id_t in vistos_fixas.items():
        try:
            total_inseridos += gerar_recorrencias(id_t)
        except Exception as err:
            print(f"[DB] Aviso retroativo D.Fixa id={id_t}: {err}")

    for chave, (_, id_t) in vistos_parcelados.items():
        try:
            total_inseridos += gerar_recorrencias(id_t)
        except Exception as err:
            print(f"[DB] Aviso retroativo Parcelado id={id_t}: {err}")

    print(f"[DB] Retroativo concluído: {total_inseridos} transações geradas")
    return total_inseridos


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
