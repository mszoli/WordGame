"""
3. lepes: a mar legeneralt licit_menetrend.json alapjan statisztikat keszit
arrol, hogy osszesen hanyszor szerepel az egesz menetrendben az egyes betuk
mindegyike - ellenorzeskepp, hogy az osszeg valoban annyi, amennyinek lennie
kell (10 csapat x 10 betu/csapat/terem x 5 terem = 500).

Kimenet: <output-dir>/betu_statisztika.txt
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.letters import LETTER_WEIGHTS  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args()
    output_dir = BASE_DIR / args.output_dir

    with open(output_dir / "licit_menetrend.json", encoding="utf-8") as f:
        structure = json.load(f)

    counts = Counter()
    for rnd in structure["korok"]:
        for room in rnd["termek"]:
            for unit in room["betuk"]:
                counts.update(unit)

    total = sum(counts.values())
    total_weight = sum(LETTER_WEIGHTS.values())

    lines = []
    lines.append("BETŰSTATISZTIKA - Licitálós Szókirakós menetrend")
    lines.append(f"(seed: {structure['seed']}, csapatok: {structure['csapatok_szama']})")
    lines.append("=" * 60)
    lines.append(f"{'Betű':<6}{'Súly':>6}{'Várható':>12}{'Tényleges':>12}{'Eltérés':>10}")
    lines.append("-" * 60)

    for letter in sorted(LETTER_WEIGHTS, key=lambda l: (-LETTER_WEIGHTS[l], l)):
        weight = LETTER_WEIGHTS[letter]
        expected = total * weight / total_weight
        actual = counts.get(letter, 0)
        deviation = actual - expected
        lines.append(f"{letter:<6}{weight:>6}{expected:>12.2f}{actual:>12d}{deviation:>+10.2f}")

    lines.append("-" * 60)
    lines.append(f"{'ÖSSZESEN':<6}{'':>6}{'':>12}{total:>12d}")
    lines.append("")
    betu_per_csapat_per_terem = sum(2 if r["tipus"] == "dupla" else 1 for r in structure["korok"])
    expected_total = structure["csapatok_szama"] * structure["termek_szama"] * betu_per_csapat_per_terem
    lines.append(
        f"Ellenőrzés: {structure['csapatok_szama']} csapat x {structure['termek_szama']} terem x "
        f"{betu_per_csapat_per_terem} betű/csapat/terem = {expected_total} → tényleges összeg: {total} "
        f"({'OK, egyezik' if total == expected_total else 'ELTÉRÉS, ELLENŐRIZD!'})"
    )

    missing = [l for l in LETTER_WEIGHTS if counts.get(l, 0) == 0]
    lines.append("")
    lines.append(
        "Hiányzó betűk (0x fordul elő): " + (", ".join(missing) if missing else "nincs - mind a 34 betű szerepel")
    )

    out_path = output_dir / "betu_statisztika.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("\n".join(lines))
    print(f"\nKesz: {out_path}")


if __name__ == "__main__":
    main()
