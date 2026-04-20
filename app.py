from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from ia import extrair_dados_com_ia
from db import inserir_transacao

app = Flask(__name__)


@app.route("/")
def pagina_inicial():
    return "Finauto online"


@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    mensagem_recebida = request.form.get("Body", "").strip()
    print(f"\n[APP] Nova mensagem: {mensagem_recebida}")

    if not mensagem_recebida:
        return ("", 204)

    try:
        dados = extrair_dados_com_ia(mensagem_recebida)
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