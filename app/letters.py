import random

# Hozzávetőleges magyar betűgyakoriság (a magyar Scrabble-készlet alapján,
# a kételemű betűkapcsolatok (cs, gy, ly, ny, sz, ty, zs) súlya a
# legközelebbi alapbetűbe olvasztva, hogy egyszerű, egykarakteres
# csempéket használhassunk).
LETTER_WEIGHTS: dict[str, int] = {
    "A": 9, "Á": 4, "B": 2, "C": 1, "D": 2, "E": 9, "É": 2, "F": 1, "G": 3,
    "H": 2, "I": 3, "Í": 1, "J": 2, "K": 4, "L": 4, "M": 3, "N": 4, "O": 4,
    "Ó": 1, "Ö": 2, "Ő": 1, "P": 2, "R": 3, "S": 4, "T": 4, "U": 1, "Ú": 1,
    "Ü": 1, "Ű": 1, "V": 2, "W": 1, "X": 1, "Y": 5, "Z": 2, "Q": 1,
}
# "Y" önálló betűként nem létezik a magyarban, de a gy/ly/ny/ty
# betűkapcsolatok második tagjaként rendkívül gyakori (pl. "Magyarország",
# "Gyula") — mivel ezeket a kapcsolatokat nem külön csempeként kezeljük,
# hanem a két alapbetűjükre bontva, Y nélkül ezek a szavak kirakhatatlanok
# lennének. "W", "X" és "Q" csak néhány idegen eredetű szóhoz/névhez kell
# (pl. "Botswana", "Xenon", "Squeak"), ezért nagyon alacsony súllyal.

def apportion_letters(total: int) -> list[str]:
    """A megadott összdarabszámra előre, egyszerre kiszámolja a súlyok szerint
    pontosan hány darab legyen az egyes betűkből (legnagyobb maradék /
    Hamilton-módszer, hogy az összeg pontosan `total` legyen), majd a teljes
    listát egyben megkeveri.

    Ezt egyszer hívjuk meg az egész játékra előre (nem körönként, nem
    húzásonként), utána a visszaadott listát sorban osztjuk szét a körök/
    termek/játékosok között. Így összesítve pontosan a súlyoknak megfelelő
    lesz az elosztás, nem független véletlen húzásokra hagyatkozunk körről
    körre — az korábban hosszú távon egyenetlenségeket okozhatott (pl. egy
    magas súlyú betű, mint az "A", véletlenül sok körön át kimaradhatott).
    """
    if total <= 0:
        return []
    total_weight = sum(LETTER_WEIGHTS.values())
    exact = {letter: total * weight / total_weight for letter, weight in LETTER_WEIGHTS.items()}
    counts = {letter: int(value) for letter, value in exact.items()}
    remainder = total - sum(counts.values())
    # a legnagyobb (lekerekítéssel elveszett) törtrésszel rendelkező betűk
    # kapják meg a maradék egységeket, hogy az összeg pontosan kijöjjön
    by_fraction = sorted(LETTER_WEIGHTS, key=lambda letter: exact[letter] - counts[letter], reverse=True)
    for letter in by_fraction[:remainder]:
        counts[letter] += 1
    bag = [letter for letter, count in counts.items() for _ in range(count)]
    random.shuffle(bag)
    return bag
