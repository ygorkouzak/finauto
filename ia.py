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
FONTES = {"Dinheiro", "Cartão Crédito", "PIX"}
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


def extrair_dados_com_ia(mensagem):
    """Recebe mensagem em português e devolve um dict validado com a transação."""
    if not mensagem or not mensagem.strip():
        raise ValueError("Mensagem vazia.")

    data_hoje = datetime.now().strftime("%Y-%m-%d")

    prompt = f"""
Você é um assistente financeiro que extrai transações de mensagens em português do Brasil.
Hoje é {data_hoje}.

Mensagem do usuário:
"{mensagem}"

Devolva APENAS um JSON válido com os campos abaixo:

- "movimentacao": "Entrada" (ganho) ou "Saída" (gasto).
- "responsavel": "Y" (eu), "M" (esposa) ou "MY" (compartilhado). Padrão: "Y".
- "tipo": para Saída use "P. Unico", "D. Fixa" ou "Parcelado".
          Para Entrada use "Receita Fixa" ou "Receita Variável".
- "categoria": ex. Alimentação, Transporte, Moradia, Salário, Freelancer.
- "descricao": local, item ou pagador (ex. "iFood", "Mercado").
- "valor": número decimal, sem símbolo (ex. 27.50). Vírgula vira ponto.
- "parcelas": "1" à vista; "N/T" se parcelado (ex. "1/4").
- "data": "AAAA-MM-DD". "hoje" → {data_hoje}.
- "fonte": "Dinheiro", "Cartão Crédito" ou "PIX". Padrão: "Dinheiro".
- "status": Para Saída use "Pago" (já pago), "A pagar" (futuro), ou "Atrasado" (vencido não pago). Para Entrada use "Recebido" (já caiu), "A receber" (futuro), ou "Atrasado" (devia ter caído e não caiu). Se a mensagem não indicar, use "Pago" ou "Recebido".

Exemplos:

Entrada: "gastei 27,50 no ifood hoje"
Saída: {{"movimentacao":"Saída","responsavel":"Y","tipo":"P. Unico","categoria":"Alimentação","descricao":"iFood","valor":27.50,"parcelas":"1","data":"{data_hoje}","fonte":"Dinheiro","status":"Pago"}}

Entrada: "comprei fone de 800 em 4x no cartão"
Saída: {{"movimentacao":"Saída","responsavel":"Y","tipo":"Parcelado","categoria":"Eletrônicos","descricao":"Fone","valor":200.00,"parcelas":"1/4","data":"{data_hoje}","fonte":"Cartão Crédito","status":"Pago"}}

Entrada: "recebi 1900 da Alvank via pix"
Saída: {{"movimentacao":"Entrada","responsavel":"Y","tipo":"Receita Variável","categoria":"Freelancer","descricao":"Alvank","valor":1900.00,"parcelas":"1","data":"{data_hoje}","fonte":"PIX","status":"Recebido"}}
"""

    try:
        resposta = cliente.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )
    except Exception as err:
        raise RuntimeError(f"Falha ao chamar o Gemini: {err}") from err

    texto_bruto = resposta.text

    try:
        dados = json.loads(texto_bruto)
    except json.JSONDecodeError as err:
        raise ValueError(f"Gemini devolveu JSON inválido:\n{texto_bruto}") from err

    problemas = _validar(dados)
    if problemas:
        raise ValueError("JSON fora do schema: " + "; ".join(problemas))

    return dados


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