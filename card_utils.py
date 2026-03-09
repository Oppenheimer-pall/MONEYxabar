"""
💳 Card utilities - karta yordamchi funksiyalari
"""


def format_card_number(number: str) -> str:
    """16 raqamli kartani formatlash: XXXX XXXX XXXX XXXX"""
    clean = ''.join(filter(str.isdigit, number))
    return ' '.join(clean[i:i+4] for i in range(0, 16, 4))


def mask_card(number: str) -> str:
    """Kartani yashirish: **** **** **** 1234"""
    clean = ''.join(filter(str.isdigit, number))
    return f"**** **** **** {clean[-4:]}"


def validate_card(number: str) -> bool:
    """Luhn algoritmi orqali karta validatsiyasi"""
    clean = ''.join(filter(str.isdigit, number))
    if len(clean) != 16:
        return False

    total = 0
    reverse = clean[::-1]
    for i, digit in enumerate(reverse):
        n = int(digit)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def get_card_type(number: str) -> str:
    """Karta turini aniqlash"""
    clean = ''.join(filter(str.isdigit, number))
    if not clean:
        return "Unknown"

    prefix2 = clean[:2]
    prefix4 = clean[:4]
    prefix6 = clean[:6]

    # O'zbek kartalari
    if prefix4 in ('9860',):
        return "Humo"
    if prefix4 in ('8600',):
        return "Uzcard"

    # Xalqaro kartalar
    if clean[0] == '4':
        return "Visa"
    if prefix2 in [str(n) for n in range(51, 56)] or prefix4 in [
        str(n) for n in range(2221, 2721)
    ]:
        return "Mastercard"
    if prefix2 in ('34', '37'):
        return "Amex"
    if prefix4 == '6011' or prefix2 == '65':
        return "Discover"

    return "Unknown"


def calculate_commission(amount: float, card_type: str = "Unknown") -> float:
    """
    Komissiya hisoblash:
    - Humo/Uzcard: 0.3%, min 300, max 3000
    - Boshqalar: 0.5%, min 500, max 5000
    """
    if card_type in ("Humo", "Uzcard"):
        rate, min_fee, max_fee = 0.003, 300, 3000
    else:
        rate, min_fee, max_fee = 0.005, 500, 5000

    fee = amount * rate
    return round(min(max(fee, min_fee), max_fee), 0)
