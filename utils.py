"""
utils.py — Funções utilitárias compartilhadas pelo projeto.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Twilio — envio de lembretes via WhatsApp
# ---------------------------------------------------------------------------
_TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
_TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
_TWILIO_FROM = os.getenv("TWILIO_FROM", "whatsapp:+14155238886")
_TWILIO_CONTENT_SID = os.getenv("TWILIO_CONTENT_SID", "HXb5b62575e6e4ff6129ad7c8efe1f983e")

# Mapa responsável → número WhatsApp (configurar no .env)
_PHONES = {
    "Y": os.getenv("PHONE_Y", ""),
    "M": os.getenv("PHONE_M", ""),
    "MY": os.getenv("PHONE_Y", ""),  # envia para Y quando compartilhado
}


def enviar_lembrete_twilio(responsavel, data_str, descricao):
    """
    Envia lembrete via WhatsApp usando template Twilio.
    data_str: "DD/MM/YYYY", descricao: texto da transação.
    Retorna o SID da mensagem ou lança RuntimeError.
    """
    from twilio.rest import Client

    telefone = _PHONES.get(responsavel, "")
    if not telefone:
        raise RuntimeError(f"Número não configurado para responsável '{responsavel}'. "
                           "Adicione PHONE_Y / PHONE_M no .env.")
    if not _TWILIO_SID or not _TWILIO_TOKEN:
        raise RuntimeError("TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN não configurados no .env.")

    import json
    content_vars = json.dumps({"1": data_str, "2": descricao[:20]})

    try:
        client = Client(_TWILIO_SID, _TWILIO_TOKEN)
        msg = client.messages.create(
            from_=_TWILIO_FROM,
            content_sid=_TWILIO_CONTENT_SID,
            content_variables=content_vars,
            to=f"whatsapp:{telefone}",
        )
    except Exception as err:
        raise RuntimeError(f"Twilio: {err}") from err

    return msg.sid


def formatar_moeda(valor):
    """
    Formata número como moeda brasileira: R$ 1.234,56

    Truque: o Python formata como 1,234.56 (padrão americano).
    Trocamos os separadores usando um placeholder temporário.
    """
    if valor is None:
        return "R$ 0,00"
    texto = f"{valor:,.2f}"                # 1,234.56
    texto = texto.replace(",", "X")         # 1X234.56
    texto = texto.replace(".", ",")         # 1X234,56
    texto = texto.replace("X", ".")         # 1.234,56
    return f"R$ {texto}"