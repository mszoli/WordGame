import random

# Hozzávetőleges magyar betűgyakoriság (a magyar Scrabble-készlet alapján,
# a kételemű betűkapcsolatok (cs, gy, ly, ny, sz, ty, zs) súlya a
# legközelebbi alapbetűbe olvasztva, hogy egyszerű, egykarakteres
# csempéket használhassunk).
LETTER_WEIGHTS: dict[str, int] = {
    "A": 9, "Á": 4, "B": 2, "C": 1, "D": 2, "E": 9, "É": 2, "F": 1, "G": 3,
    "H": 2, "I": 3, "Í": 1, "J": 2, "K": 4, "L": 4, "M": 3, "N": 4, "O": 4,
    "Ó": 1, "Ö": 2, "Ő": 1, "P": 2, "R": 3, "S": 4, "T": 4, "U": 1, "Ú": 1,
    "Ü": 1, "Ű": 1, "V": 2, "Z": 2,
}

_LETTERS = list(LETTER_WEIGHTS.keys())
_WEIGHTS = list(LETTER_WEIGHTS.values())


def draw_letters(n: int) -> list[str]:
    return random.choices(_LETTERS, weights=_WEIGHTS, k=n)
