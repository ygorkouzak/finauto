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


def extrair_dados_com_ia(mensagem, categorias_saida=None, categorias_entrada=None):
    """Recebe mensagem em português e devolve um dict validado com a transação."""
    if not mensagem or not mensagem.strip():
        raise ValueError("Mensagem vazia.")

    data_hoje = datetime.now().strftime("%Y-%m-%d")
    _cats_instrucao = ""
    if categorias_saida:
        _cats_instrucao += (
            "\n    CATEGORIAS DE SAÍDA permitidas (use EXATAMENTE uma): "
            + ", ".join(f'"{c}"' for c in categorias_saida)
        )
    if categorias_entrada:
        _cats_instrucao += (
            "\n    CATEGORIAS DE ENTRADA permitidas (use EXATAMENTE uma): "
            + ", ".join(f'"{c}"' for c in categorias_entrada)
        )

    prompt = f"""
Você é um assistente financeiro que extrai transações de mensagens em português do Brasil.
Hoje é {data_hoje}.

Mensagem do usuário:
"{mensagem}"

Devolva APENAS um JSON válido com os campos abaixo.
REGRA CRÍTICA: os campos com valores fixos só aceitam EXATAMENTE os valores listados — qualquer outro valor é inválido.

- "movimentacao": EXATAMENTE "Entrada" ou "Saída". Nenhum outro valor.
- "responsavel": EXATAMENTE "Y", "M" ou "MY". Padrão: "Y". Nenhum outro valor.
- "tipo":
    Se Saída → EXATAMENTE "P. Unico", "D. Fixa" ou "Parcelado". Nenhum outro valor.
    Se Entrada → EXATAMENTE "Receita Fixa" ou "Receita Variável". Nenhum outro valor.
- "categoria": escolha EXATAMENTE uma da lista abaixo. Proibido criar ou adaptar categorias.{_cats_instrucao}
- "descricao": nome do local, item ou pagador (ex. "iFood", "Mercado").
- "valor": número decimal sem símbolo (ex. 27.50). Vírgula → ponto.
- "parcelas": EXATAMENTE "1" se à vista, ou formato "N/T" se parcelado (ex. "2/10"). Nenhum outro formato.
- "data": formato EXATO "AAAA-MM-DD". Hoje = {data_hoje}.
- "fonte": EXATAMENTE "Dinheiro" ou "Cartão Crédito". Padrão: "Dinheiro".
    IMPORTANTE: PIX, transferência, débito ou qualquer outro meio → use "Dinheiro".
    Só use "Cartão Crédito" se explicitamente mencionado cartão de crédito ou crédito parcelado.
- "status":
    Se Saída → EXATAMENTE "Pago", "A pagar" ou "Atrasado". Nenhum outro valor.
    Se Entrada → EXATAMENTE "Recebido", "A receber" ou "Atrasado". Nenhum outro valor.
    Se não informado → use "Pago" (Saída) ou "Recebido" (Entrada).

Exemplos:

Entrada: "gastei 27,50 no ifood hoje"
Saída: {{"movimentacao":"Saída","responsavel":"Y","tipo":"P. Unico","categoria":"Alimentação","descricao":"iFood","valor":27.50,"parcelas":"1","data":"{data_hoje}","fonte":"Dinheiro","status":"Pago"}}

Entrada: "comprei fone de 800 em 4x no cartão"
Saída: {{"movimentacao":"Saída","responsavel":"Y","tipo":"Parcelado","categoria":"Eletrônicos","descricao":"Fone","valor":200.00,"parcelas":"1/4","data":"{data_hoje}","fonte":"Cartão Crédito","status":"Pago"}}

Entrada: "recebi 1900 da Alvank via pix"
Saída: {{"movimentacao":"Entrada","responsavel":"Y","tipo":"Receita Variável","categoria":"Freelancer","descricao":"Alvank","valor":1900.00,"parcelas":"1","data":"{data_hoje}","fonte":"Dinheiro","status":"Recebido"}}
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

    mov = dados.get("movimentacao")
    cats_validas = categorias_saida if mov == "Saída" else categorias_entrada
    if cats_validas and dados.get("categoria") not in cats_validas:
        raise ValueError(
            f"Categoria '{dados['categoria']}' não existe para {mov}. "
            "Reformule a mensagem indicando a categoria correta."
        )

    return dados


def extrair_dados_com_ia_imagem(mensagem, bytes_imagem, tipo_mime="image/jpeg",
                               categorias_saida=None, categorias_entrada=None):
    """Extrai dados de transação a partir de bytes de imagem (nota fiscal, comprovante)."""
    data_hoje = datetime.now().strftime("%Y-%m-%d")
    _cats_instrucao = ""
    if categorias_saida:
        _cats_instrucao += (
            "\n    CATEGORIAS DE SAÍDA permitidas: "
            + ", ".join(f'"{c}"' for c in categorias_saida)
        )
    if categorias_entrada:
        _cats_instrucao += (
            "\n    CATEGORIAS DE ENTRADA permitidas: "
            + ", ".join(f'"{c}"' for c in categorias_entrada)
        )

    prompt_texto = f"""
Você é um assistente financeiro. Analise esta imagem (nota fiscal, comprovante ou foto de despesa).
Hoje é {data_hoje}.
Mensagem adicional do usuário: "{mensagem}"

Devolva APENAS um JSON válido. Os campos com valores fixos só aceitam EXATAMENTE os valores listados.

- "movimentacao": EXATAMENTE "Entrada" ou "Saída".
- "responsavel": EXATAMENTE "Y", "M" ou "MY". Padrão: "Y".
- "tipo":
    Se Saída → EXATAMENTE "P. Unico", "D. Fixa" ou "Parcelado".
    Se Entrada → EXATAMENTE "Receita Fixa" ou "Receita Variável".
- "categoria": EXATAMENTE uma da lista abaixo. Proibido criar ou adaptar.{_cats_instrucao}
- "descricao": nome do estabelecimento ou pagador (ex. "Supermercado Extra").
- "valor": número decimal sem símbolo (ex. 27.50).
- "parcelas": EXATAMENTE "1" se à vista ou formato "N/T" (ex. "2/10").
- "data": formato EXATO "AAAA-MM-DD". Se não identificar, use {data_hoje}.
- "fonte": EXATAMENTE "Dinheiro" ou "Cartão Crédito". Padrão: "Dinheiro".
    PIX, débito, transferência → use "Dinheiro". Só "Cartão Crédito" se explicitamente indicado.
- "status": Se Saída → "Pago", "A pagar" ou "Atrasado". Se Entrada → "Recebido", "A receber" ou "Atrasado".
"""

    try:
        resposta = cliente.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[
                types.Part.from_bytes(data=bytes_imagem, mime_type=tipo_mime),
                prompt_texto,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )
    except Exception as err:
        raise RuntimeError(f"Falha ao chamar Gemini com imagem: {err}") from err

    texto_bruto = resposta.text

    try:
        dados = json.loads(texto_bruto)
    except json.JSONDecodeError as err:
        raise ValueError(f"Gemini devolveu JSON inválido:\n{texto_bruto}") from err

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