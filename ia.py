import json
import os
import re
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY não encontrada no .env")

cliente = genai.Client(api_key=API_KEY)

# ---------------------------------------------------------------------------
# Schema: valores aceitos pela tabela `transacoes` no Supabase.
# Se mudar algo no banco, atualize aqui também.
# ---------------------------------------------------------------------------
CAMPOS_OBRIGATORIOS = {
    "movimentacao", "responsavel", "tipo", "categoria", "descricao",
    "valor", "parcelas", "data", "fonte", "status",
}
MOVIMENTACOES = {"Entrada", "Saída"}
RESPONSAVEIS = {"Y", "M", "MY"}
FONTES = {"Dinheiro", "Cartão Crédito"}
TIPOS_SAIDA = {"P. Unico", "D. Fixa", "Parcelado"}
TIPOS_ENTRADA = {"Receita Fixa", "Receita Variável"}


def _validar(dados):
    """Confere o dict contra o schema. Devolve lista de problemas (vazia = OK)."""
    # Primeiro checa campos faltando. Se algum faltar, retornamos só isso —
    # não faz sentido validar tipos se o campo nem existe.
    faltando = CAMPOS_OBRIGATORIOS - dados.keys()
    if faltando:
        return [f"campo ausente: {campo}" for campo in faltando]

    problemas = []

    mov = dados["movimentacao"]
    if mov not in MOVIMENTACOES:
        problemas.append(f"movimentacao inválida: {mov!r}")

    if dados["responsavel"] not in RESPONSAVEIS:
        problemas.append(f"responsavel inválido: {dados['responsavel']!r}")

    if dados["fonte"] not in FONTES:
        problemas.append(f"fonte inválida: {dados['fonte']!r}")

    # Validação cruzada: o tipo depende da movimentação.
    tipo = dados["tipo"]
    status_saida_validos = {"Pago", "A pagar", "Atrasado"}
    status_entrada_validos = {"Recebido", "A receber", "Atrasado"}

    if mov == "Saída":
        if tipo not in TIPOS_SAIDA:
            problemas.append(f"tipo de Saída inválido: {tipo!r}")
        if dados["status"] not in status_saida_validos:
            problemas.append(f"status de Saída inválido: {dados['status']!r}")
    elif mov == "Entrada":
        if tipo not in TIPOS_ENTRADA:
            problemas.append(f"tipo de Entrada inválido: {tipo!r}")
        if dados["status"] not in status_entrada_validos:
            problemas.append(f"status de Entrada inválido: {dados['status']!r}")
            
    # Data precisa bater no formato AAAA-MM-DD.
    try:
        datetime.strptime(str(dados["data"]), "%Y-%m-%d")
    except ValueError:
        problemas.append(f"data fora do formato AAAA-MM-DD: {dados['data']!r}")

    # Valor precisa ser número (int ou float).
    if not isinstance(dados["valor"], (int, float)):
        problemas.append(f"valor precisa ser número: {dados['valor']!r}")

    # Parcelas: "1" ou "N/T".
    parcelas = str(dados["parcelas"])
    if parcelas != "1" and not re.fullmatch(r"\d+/\d+", parcelas):
        problemas.append(f"parcelas fora do padrão '1' ou 'N/T': {parcelas!r}")

    return problemas


def _instrucoes_enum(data_hoje, cats_saida, cats_entrada, responsavel, historico):
    """Monta o bloco de regras comuns para todos os prompts."""
    if responsavel:
        resp_regra = (
            f'EXATAMENTE "{responsavel}" — mensagem enviada por este responsável. '
            f'Só mude se a mensagem indicar explicitamente outro responsável.'
        )
    else:
        resp_regra = 'EXATAMENTE "Y", "M" ou "MY". Padrão: "Y".'

    cats_bloco = ""
    if cats_saida:
        cats_bloco += "\n    CATEGORIAS DE SAÍDA: " + ", ".join(f'"{c}"' for c in cats_saida)
    if cats_entrada:
        cats_bloco += "\n    CATEGORIAS DE ENTRADA: " + ", ".join(f'"{c}"' for c in cats_entrada)

    historico_bloco = ""
    if historico:
        linhas = []
        for h in historico:
            linhas.append(
                f'  • "{h.get("descricao","")}" → {h.get("movimentacao","")}, '
                f'{h.get("tipo","")}, {h.get("categoria","")}, '
                f'fonte: {h.get("fonte","")}, status padrão: {h.get("status","")}'
            )
        historico_bloco = (
            "\nHISTÓRICO (use como referência para classificar itens recorrentes):\n"
            + "\n".join(linhas)
            + "\nSe a mensagem mencionar algo do histórico, replique a classificação exata."
        )

    return f"""
REGRA CRÍTICA: campos com valores fixos aceitam EXATAMENTE os valores listados — nenhum outro.

- "movimentacao": EXATAMENTE "Entrada" ou "Saída".
- "responsavel": {resp_regra}
- "tipo":
    Saída → EXATAMENTE "P. Unico", "D. Fixa" ou "Parcelado".
    Entrada → EXATAMENTE "Receita Fixa" ou "Receita Variável".
- "categoria": EXATAMENTE uma da lista. Proibido criar ou adaptar.{cats_bloco}
- "descricao": nome do local, item ou pagador.
- "valor": decimal sem símbolo (ex. 27.50). Vírgula → ponto.
- "parcelas": EXATAMENTE "1" à vista ou "N/T" parcelado (ex. "2/10").
- "data": EXATO "AAAA-MM-DD". Hoje = {data_hoje}.
- "fonte": EXATAMENTE "Dinheiro" ou "Cartão Crédito". Padrão: "Dinheiro".
    PIX, transferência, débito → use "Dinheiro". "Cartão Crédito" só se explicitamente dito.
- "status":
    Saída → EXATAMENTE "Pago", "A pagar" ou "Atrasado".
    Entrada → EXATAMENTE "Recebido", "A receber" ou "Atrasado".
    Se não informado → "Pago" (Saída) ou "Recebido" (Entrada).
{historico_bloco}"""


def extrair_dados_com_ia(mensagem, categorias_saida=None, categorias_entrada=None,
                         responsavel=None, historico=None):
    """Recebe mensagem em português e devolve um dict validado com a transação."""
    if not mensagem or not mensagem.strip():
        raise ValueError("Mensagem vazia.")

    data_hoje = datetime.now().strftime("%Y-%m-%d")
    instrucoes = _instrucoes_enum(data_hoje, categorias_saida, categorias_entrada,
                                  responsavel, historico)

    prompt = f"""Você é um assistente financeiro. Extraia a transação da mensagem abaixo e devolva APENAS um JSON válido.
Hoje é {data_hoje}.

Mensagem: "{mensagem}"
{instrucoes}
Exemplos:
Entrada "gastei 27,50 no ifood hoje" → {{"movimentacao":"Saída","responsavel":"Y","tipo":"P. Unico","categoria":"Alimentação","descricao":"iFood","valor":27.50,"parcelas":"1","data":"{data_hoje}","fonte":"Dinheiro","status":"Pago"}}
Entrada "comprei fone 800 em 4x no cartão" → {{"movimentacao":"Saída","responsavel":"Y","tipo":"Parcelado","categoria":"Compras On","descricao":"Fone","valor":200.00,"parcelas":"1/4","data":"{data_hoje}","fonte":"Cartão Crédito","status":"Pago"}}
Entrada "recebi 1900 da Alvank" → {{"movimentacao":"Entrada","responsavel":"Y","tipo":"Receita Variável","categoria":"Freelancer","descricao":"Alvank","valor":1900.00,"parcelas":"1","data":"{data_hoje}","fonte":"Dinheiro","status":"Recebido"}}
"""

    return _chamar_gemini_e_validar(prompt, categorias_saida, categorias_entrada, "texto")


def _chamar_gemini_e_validar(contents, categorias_saida, categorias_entrada, tipo_midia="mídia"):
    """Chama o Gemini com contents multimodal, parseia e valida o JSON retornado."""
    try:
        resposta = cliente.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )
    except Exception as err:
        raise RuntimeError(f"Falha ao chamar Gemini com {tipo_midia}: {err}") from err

    try:
        dados = json.loads(resposta.text)
    except json.JSONDecodeError as err:
        raise ValueError(f"Gemini devolveu JSON inválido:\n{resposta.text}") from err

    if isinstance(dados, list):
        if not dados:
            raise ValueError("Gemini devolveu lista vazia.")
        dados = dados[0]

    problemas = _validar(dados)
    if problemas:
        raise ValueError("JSON fora do schema: " + "; ".join(problemas))

    mov = dados.get("movimentacao")
    cats_validas = categorias_saida if mov == "Saída" else categorias_entrada
    if cats_validas and dados.get("categoria") not in cats_validas:
        raise ValueError(
            f"Categoria '{dados['categoria']}' não existe para {mov}. "
            "Reformule a mensagem indicando a categoria correta."
        )
    return dados


def extrair_dados_com_ia_imagem(mensagem, bytes_imagem, tipo_mime="image/jpeg",
                                categorias_saida=None, categorias_entrada=None,
                                responsavel=None, historico=None):
    """Extrai dados de transação a partir de bytes de imagem (nota fiscal, comprovante)."""
    data_hoje = datetime.now().strftime("%Y-%m-%d")
    instrucoes = _instrucoes_enum(data_hoje, categorias_saida, categorias_entrada,
                                  responsavel, historico)
    prompt_texto = (
        f"Você é um assistente financeiro. Analise a imagem (nota fiscal, comprovante ou foto de despesa).\n"
        f"Hoje é {data_hoje}. Mensagem adicional: \"{mensagem}\"\n"
        f"Devolva APENAS um JSON válido.\n{instrucoes}"
    )
    return _chamar_gemini_e_validar(
        [types.Part.from_bytes(data=bytes_imagem, mime_type=tipo_mime), prompt_texto],
        categorias_saida, categorias_entrada, "imagem",
    )


def extrair_dados_com_ia_audio(mensagem, bytes_audio, tipo_mime="audio/ogg",
                               categorias_saida=None, categorias_entrada=None,
                               responsavel=None, historico=None):
    """Extrai dados de transação a partir de áudio (mensagem de voz do WhatsApp)."""
    data_hoje = datetime.now().strftime("%Y-%m-%d")
    instrucoes = _instrucoes_enum(data_hoje, categorias_saida, categorias_entrada,
                                  responsavel, historico)
    prompt_texto = (
        f"Você é um assistente financeiro. Transcreva o áudio e extraia a transação financeira mencionada.\n"
        f"Hoje é {data_hoje}. Texto adicional do usuário: \"{mensagem}\"\n"
        f"Devolva APENAS um JSON válido.\n{instrucoes}"
    )
    return _chamar_gemini_e_validar(
        [types.Part.from_bytes(data=bytes_audio, mime_type=tipo_mime), prompt_texto],
        categorias_saida, categorias_entrada, "áudio",
    )


if __name__ == "__main__":
    mensagens_teste = [
        "gastei 50 reais no mercado hoje",
        "paguei 1200 de aluguel ontem",
        "recebi 3000 de salário",
        "comprei um celular de 3600 em 12x",
        "paguei 80 de uber pra balada",     # "balada" força categoria nova
    ]
    for msg in mensagens_teste:
        print(f"\n>>> {msg}")
        try:
            resultado = extrair_dados_com_ia(msg)
            print(f"✅ {resultado}")
        except (ValueError, RuntimeError) as err:
            print(f"❌ {err}")