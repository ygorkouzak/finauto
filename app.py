import os
import requests as http_requests
from requests.auth import HTTPBasicAuth
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from ia import extrair_dados_com_ia, extrair_dados_com_ia_imagem
from db import inserir_transacao, listar_categorias

app = Flask(__name__)

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")


@app.route("/")
def pagina_inicial():
    return "Finauto online"


@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    mensagem_recebida = request.form.get("Body", "").strip()
    num_media = int(request.form.get("NumMedia", "0"))
    media_url = request.form.get("MediaUrl0", "")
    media_type = request.form.get("MediaContentType0", "image/jpeg")
    print(f"\n[APP] Nova mensagem: {mensagem_recebida} | imagens: {num_media}")

    if not mensagem_recebida and num_media == 0:
        return ("", 204)

    try:
        cats_saida = listar_categorias("Saída")
        cats_entrada = listar_categorias("Entrada")
        if num_media > 0 and media_url:
            if not TWILIO_SID or not TWILIO_TOKEN:
                raise RuntimeError(
                    "TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN não configurados no servidor. "
                    "Envie uma mensagem de texto para registrar."
                )
            r = http_requests.get(
                media_url,
                auth=HTTPBasicAuth(TWILIO_SID, TWILIO_TOKEN),
                timeout=15,
            )
            if r.status_code == 401:
                raise RuntimeError(
                    "Credenciais Twilio inválidas. Configure TWILIO_AUTH_TOKEN no servidor."
                )
            r.raise_for_status()
            dados = extrair_dados_com_ia_imagem(
                mensagem_recebida, r.content, media_type,
                categorias_saida=cats_saida, categorias_entrada=cats_entrada,
            )
        else:
            dados = extrair_dados_com_ia(
                mensagem_recebida,
                categorias_saida=cats_saida,
                categorias_entrada=cats_entrada,
            )
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
        texto_resposta = "Erro no servidor. Tente novamente em instantes."

    resposta = MessagingResponse()
    resposta.message(texto_resposta)
    return str(resposta)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)