import base64
import json
import os
import re
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# ---------------------------------------------------------------------------
# Clientes de IA — Gemini (primário) e Groq (fallback automático no 429)
# ---------------------------------------------------------------------------
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY não encontrada no .env")

cliente_gemini = genai.Client(api_key=API_KEY)

try:
    from groq import Groq as _Groq
    _groq_api_key = os.getenv("GROQ_API_KEY")
    cliente_groq = _Groq(api_key=_groq_api_key) if _groq_api_key else None
except ImportError:
    cliente_groq = None

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


class PrecisaPerguntar(Exception):
    """Sinaliza que a IA devolveu {"precisa_perguntar": true, "pergunta": ...}."""
    def __init__(self, pergunta):
        super().__init__(pergunta)
        self.pergunta = pergunta


def _validar(dados):
    """Confere o dict contra o schema. Devolve lista de problemas (vazia = OK)."""
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

    try:
        datetime.strptime(str(dados["data"]), "%Y-%m-%d")
    except ValueError:
        problemas.append(f"data fora do formato AAAA-MM-DD: {dados['data']!r}")

    if not isinstance(dados["valor"], (int, float)):
        problemas.append(f"valor precisa ser número: {dados['valor']!r}")

    parcelas = str(dados["parcelas"])
    if parcelas != "1" and not re.fullmatch(r"\d+/\d+", parcelas):
        problemas.append(f"parcelas fora do padrão '1' ou 'N/T': {parcelas!r}")

    return problemas


def _instrucoes_enum(data_hoje, cats_saida, cats_entrada, responsavel, historico,
                     permitir_pergunta=True):
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

    if permitir_pergunta:
        pergunta_bloco = """
POLÍTICA DE PERGUNTAS DE VOLTA:
Antes de perguntar qualquer coisa, você DEVE tentar, nesta ordem:
  1. Aplicar os defaults já listados: responsavel injetado, fonte="Dinheiro", status="Pago"/"Recebido", data=hoje, parcelas="1", tipo="P. Unico"/"Receita Variável".
  2. Casar a descrição com o HISTÓRICO acima.
  3. Inferir categoria a partir do vocabulário (mercado→Alimentação, ifood→Alimentação, posto/gasolina→Transporte, Spotify/Canva/iCloud→Assinaturas, etc).
Se — e SOMENTE se — ainda assim faltar um dado essencial que mude a classificação (tipicamente o valor, ou em casos ambíguos a categoria), devolva EXATAMENTE este JSON:
  {"precisa_perguntar": true, "pergunta": "<pergunta curta em português, com 2-3 opções quando fizer sentido>"}
Regras da pergunta:
  - Uma pergunta só. Direta. Sem saudação, sem desculpa.
  - Nunca pergunte algo que um default resolve.
  - Nunca pergunte mais de um campo por vez.
  - Se a mensagem já tem tudo, NÃO pergunte — devolva o JSON completo da transação."""
    else:
        pergunta_bloco = """
POLÍTICA: esta é a ÚLTIMA tentativa. É PROIBIDO devolver {"precisa_perguntar": ...}.
Aplique defaults e chute a melhor opção válida dentro dos enums e categorias permitidas. Entregue o JSON completo da transação, custe o que custar."""

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
{historico_bloco}
{pergunta_bloco}"""


# ---------------------------------------------------------------------------
# Funções de chamada Groq (fallback)
# ---------------------------------------------------------------------------

def _groq_texto(prompt: str) -> str:
    """Chama Groq (Llama-3.3) para texto. Retorna string JSON."""
    if cliente_groq is None:
        raise RuntimeError("Groq indisponível: instale 'groq' e defina GROQ_API_KEY no .env")
    resp = cliente_groq.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    return resp.choices[0].message.content


def _groq_audio(bytes_audio: bytes, tipo_mime: str, prompt_texto: str) -> str:
    """Transcreve áudio com Whisper (Groq) e classifica com Llama. Retorna string JSON."""
    if cliente_groq is None:
        raise RuntimeError("Groq indisponível: instale 'groq' e defina GROQ_API_KEY no .env")
    ext = tipo_mime.split("/")[-1]  # ex: "ogg", "mp4", "mpeg"
    transcricao = cliente_groq.audio.transcriptions.create(
        file=(f"audio.{ext}", bytes_audio, tipo_mime),
        model="whisper-large-v3",
        language="pt",
    )
    print(f"[IA/Groq] Transcrição: {transcricao.text}")
    prompt_com_texto = prompt_texto.replace(
        "Transcreva o áudio e extraia a transação financeira mencionada.",
        f'O áudio foi transcrito: "{transcricao.text}". Extraia a transação financeira.',
    )
    return _groq_texto(prompt_com_texto)


def _groq_imagem(bytes_imagem: bytes, tipo_mime: str, prompt_texto: str) -> str:
    """Analisa imagem com Llama-4 Vision (Groq). Retorna string JSON."""
    if cliente_groq is None:
        raise RuntimeError("Groq indisponível: instale 'groq' e defina GROQ_API_KEY no .env")
    img_b64 = base64.b64encode(bytes_imagem).decode()
    resp = cliente_groq.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:{tipo_mime};base64,{img_b64}"}},
            {"type": "text", "text": prompt_texto},
        ]}],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    return resp.choices[0].message.content


# ---------------------------------------------------------------------------
# Núcleo: chama Gemini → fallback Groq no 429 → parseia → valida
# ---------------------------------------------------------------------------

def _e_erro_429(err: Exception) -> bool:
    return "429" in str(err) or "RESOURCE_EXHAUSTED" in str(err)


def _parsear_e_validar(texto_json: str, categorias_saida, categorias_entrada, provedor: str):
    """Parseia o JSON retornado pela IA, valida e devolve o dict da transação."""
    print(f"[IA/{provedor}] Resposta bruta: {texto_json[:300]}")
    try:
        dados = json.loads(texto_json)
    except json.JSONDecodeError as err:
        raise ValueError(f"{provedor} devolveu JSON inválido:\n{texto_json}") from err

    while isinstance(dados, list):
        if not dados:
            raise ValueError(f"{provedor} devolveu lista vazia.")
        dados = dados[0]

    if isinstance(dados, dict) and dados.get("precisa_perguntar") is True:
        pergunta = dados.get("pergunta")
        if not isinstance(pergunta, str) or not pergunta.strip():
            raise ValueError("IA marcou precisa_perguntar mas não enviou pergunta.")
        raise PrecisaPerguntar(pergunta.strip())

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


def _chamar_com_fallback(
    gemini_contents,
    categorias_saida,
    categorias_entrada,
    tipo_midia: str,
    # Parâmetros extras usados apenas no fallback Groq para áudio/imagem:
    prompt_texto: str = None,
    bytes_midia: bytes = None,
    tipo_mime_midia: str = None,
):
    """
    Tenta Gemini primeiro. Se receber 429, cai automaticamente para Groq.
    Devolve dict validado da transação ou levanta PrecisaPerguntar/ValueError/RuntimeError.
    """
    # --- Tentativa Gemini ---
    try:
        resposta = cliente_gemini.models.generate_content(
            model="gemini-2.0-flash",
            contents=gemini_contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )
        return _parsear_e_validar(resposta.text, categorias_saida, categorias_entrada, "Gemini")

    except (PrecisaPerguntar, ValueError):
        raise  # erros de validação/schema sobem direto

    except Exception as err:
        if not _e_erro_429(err):
            raise RuntimeError(f"Falha ao chamar Gemini com {tipo_midia}: {err}") from err
        print(f"[IA] Gemini 429 — ativando fallback Groq ({tipo_midia})")

    # --- Fallback Groq ---
    try:
        if tipo_midia == "áudio" and bytes_midia is not None:
            texto_json = _groq_audio(bytes_midia, tipo_mime_midia, prompt_texto)
        elif tipo_midia == "imagem" and bytes_midia is not None:
            texto_json = _groq_imagem(bytes_midia, tipo_mime_midia, prompt_texto)
        else:
            # Para texto, gemini_contents é a string do prompt
            texto_json = _groq_texto(
                gemini_contents if isinstance(gemini_contents, str) else prompt_texto
            )
        return _parsear_e_validar(texto_json, categorias_saida, categorias_entrada, "Groq")

    except (PrecisaPerguntar, ValueError):
        raise

    except Exception as groq_err:
        raise RuntimeError(
            f"Gemini (429) e Groq falharam para {tipo_midia}: {groq_err}"
        ) from groq_err


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def extrair_dados_com_ia(mensagem, categorias_saida=None, categorias_entrada=None,
                         responsavel=None, historico=None, permitir_pergunta=True):
    """Recebe mensagem em português e devolve um dict validado com a transação."""
    if not mensagem or not mensagem.strip():
        raise ValueError("Mensagem vazia.")

    data_hoje = datetime.now().strftime("%Y-%m-%d")
    instrucoes = _instrucoes_enum(data_hoje, categorias_saida, categorias_entrada,
                                  responsavel, historico, permitir_pergunta)

    prompt = f"""Você é um assistente financeiro. Extraia a transação da mensagem abaixo e devolva APENAS um JSON válido.
Hoje é {data_hoje}.

Mensagem: "{mensagem}"
{instrucoes}
Exemplos:
Entrada "gastei 27,50 no ifood hoje" → {{"movimentacao":"Saída","responsavel":"Y","tipo":"P. Unico","categoria":"Alimentação","descricao":"iFood","valor":27.50,"parcelas":"1","data":"{data_hoje}","fonte":"Dinheiro","status":"Pago"}}
Entrada "comprei fone 800 em 4x no cartão" → {{"movimentacao":"Saída","responsavel":"Y","tipo":"Parcelado","categoria":"Compras On","descricao":"Fone","valor":200.00,"parcelas":"1/4","data":"{data_hoje}","fonte":"Cartão Crédito","status":"Pago"}}
Entrada "recebi 1900 da Alvank" → {{"movimentacao":"Entrada","responsavel":"Y","tipo":"Receita Variável","categoria":"Freelancer","descricao":"Alvank","valor":1900.00,"parcelas":"1","data":"{data_hoje}","fonte":"Dinheiro","status":"Recebido"}}
Pergunta "gastei uns trocados no Arthur" → {{"precisa_perguntar":true,"pergunta":"Quanto você gastou com o Arthur? (valor em R$)"}}
"""

    return _chamar_com_fallback(
        prompt, categorias_saida, categorias_entrada, "texto",
        prompt_texto=prompt,
    )


def extrair_dados_com_ia_imagem(mensagem, bytes_imagem, tipo_mime="image/jpeg",
                                categorias_saida=None, categorias_entrada=None,
                                responsavel=None, historico=None, permitir_pergunta=True):
    """Extrai dados de transação a partir de bytes de imagem (nota fiscal, comprovante)."""
    data_hoje = datetime.now().strftime("%Y-%m-%d")
    instrucoes = _instrucoes_enum(data_hoje, categorias_saida, categorias_entrada,
                                  responsavel, historico, permitir_pergunta)
    prompt_texto = (
        f"Você é um assistente financeiro. Analise a imagem (nota fiscal, comprovante ou foto de despesa).\n"
        f"Hoje é {data_hoje}. Mensagem adicional: \"{mensagem}\"\n"
        f"Devolva APENAS um JSON válido.\n{instrucoes}"
    )
    return _chamar_com_fallback(
        [types.Part.from_bytes(data=bytes_imagem, mime_type=tipo_mime), prompt_texto],
        categorias_saida, categorias_entrada, "imagem",
        prompt_texto=prompt_texto,
        bytes_midia=bytes_imagem,
        tipo_mime_midia=tipo_mime,
    )


def extrair_dados_com_ia_audio(mensagem, bytes_audio, tipo_mime="audio/ogg",
                               categorias_saida=None, categorias_entrada=None,
                               responsavel=None, historico=None, permitir_pergunta=True):
    """Extrai dados de transação a partir de áudio (mensagem de voz do WhatsApp)."""
    data_hoje = datetime.now().strftime("%Y-%m-%d")
    instrucoes = _instrucoes_enum(data_hoje, categorias_saida, categorias_entrada,
                                  responsavel, historico, permitir_pergunta)
    prompt_texto = (
        f"Você é um assistente financeiro. Transcreva o áudio e extraia a transação financeira mencionada.\n"
        f"Hoje é {data_hoje}. Texto adicional do usuário: \"{mensagem}\"\n"
        f"Devolva APENAS um JSON válido.\n{instrucoes}"
    )
    return _chamar_com_fallback(
        [types.Part.from_bytes(data=bytes_audio, mime_type=tipo_mime), prompt_texto],
        categorias_saida, categorias_entrada, "áudio",
        prompt_texto=prompt_texto,
        bytes_midia=bytes_audio,
        tipo_mime_midia=tipo_mime,
    )


if __name__ == "__main__":
    mensagens_teste = [
        "gastei 50 reais no mercado hoje",
        "paguei 1200 de aluguel ontem",
        "recebi 3000 de salário",
        "comprei um celular de 3600 em 12x",
        "paguei 80 de uber pra balada",
    ]
    for msg in mensagens_teste:
        print(f"\n>>> {msg}")
        try:
            resultado = extrair_dados_com_ia(msg)
            print(f"✅ {resultado}")
        except (ValueError, RuntimeError) as err:
            print(f"❌ {err}")
