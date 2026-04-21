import os
import requests as http_requests
from requests.auth import HTTPBasicAuth
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from ia import extrair_dados_com_ia, extrair_dados_com_ia_imagem, extrair_dados_com_ia_audio
from db import inserir_transacao, listar_categorias, buscar_historico

app = Flask(__name__)

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")

# Mapa número → responsável (carregado uma vez na inicialização)
_PHONE_MAP = {}
for _resp, _env in [("Y", "PHONE_Y"), ("M", "PHONE_M")]:
    _num = os.getenv(_env, "").strip()
    if _num:
        _PHONE_MAP[_num] = _resp


@app.route("/")
def pagina_inicial():
    return "Finauto online"


@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    mensagem_recebida = request.form.get("Body", "").strip()
    num_media = int(request.form.get("NumMedia", "0"))
    media_url = request.form.get("MediaUrl0", "")
    media_type = request.form.get("MediaContentType0", "")
    from_numero = request.form.get("From", "").replace("whatsapp:", "").strip()
    responsavel = _PHONE_MAP.get(from_numero, "Y")
    print(f"\n[APP] Nova mensagem: {mensagem_recebida!r} | from: {from_numero} → {responsavel} | mídia: {num_media} {media_type}")

    if not mensagem_recebida and num_media == 0:
        return ("", 204)

    try:
        # Categorias e histórico — falhas não bloqueiam o registro
        try:
            cats_saida = listar_categorias("Saída")
            cats_entrada = listar_categorias("Entrada")
        except Exception as err:
            print(f"[APP] Aviso categorias: {err}")
            cats_saida, cats_entrada = [], []

        try:
            texto_busca = mensagem_recebida or ""
            historico = buscar_historico(texto_busca) if texto_busca else []
            if historico:
                print(f"[APP] Histórico encontrado: {[h.get('descricao') for h in historico]}")
        except Exception as err:
            print(f"[APP] Aviso histórico: {err}")
            historico = []

        kwargs_ia = dict(
            categorias_saida=cats_saida,
            categorias_entrada=cats_entrada,
            responsavel=responsavel,
            historico=historico or None,
        )

        if num_media > 0 and media_url:
            if not TWILIO_SID or not TWILIO_TOKEN:
                raise RuntimeError(
                    "TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN não configurados no servidor."
                )
            r = http_requests.get(
                media_url,
                auth=HTTPBasicAuth(TWILIO_SID, TWILIO_TOKEN),
                timeout=15,
            )
            if r.status_code == 401:
                raise RuntimeError("Credenciais Twilio inválidas (401).")
            r.raise_for_status()

            if media_type.startswith("audio/"):
                dados = extrair_dados_com_ia_audio(
                    mensagem_recebida, r.content, media_type, **kwargs_ia
                )
            else:
                dados = extrair_dados_com_ia_imagem(
                    mensagem_recebida, r.content, media_type or "image/jpeg", **kwargs_ia
                )
        else:
            dados = extrair_dados_com_ia(mensagem_recebida, **kwargs_ia)
        id_novo = inserir_transacao(dados)
        texto_resposta = (
            f"Registrado! (#{id_novo})\n"
            f"{dados['movimentacao']} de R$ {dados['valor']:.2f} "
            f"em {dados['categoria']} ({dados['descricao']})"
        )
    except ValueError as err:
        print(f"[APP] Dados inválidos: {err}")
        texto_resposta = "Não consegui entender a transação. Reformule a mensagem."
    except RuntimeError as err:
        print(f"[APP] Falha técnica: {err}")
        texto_resposta = f"Erro no servidor: {err}"
    except Exception as err:
        print(f"[APP] Erro inesperado ({type(err).__name__}): {err}")
        texto_resposta = f"Erro inesperado: {type(err).__name__}: {err}"

    resposta = MessagingResponse()
    resposta.message(texto_resposta)
    return str(resposta)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)