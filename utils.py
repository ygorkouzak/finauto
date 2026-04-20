"""
utils.py — Funções utilitárias compartilhadas pelo projeto.
"""


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