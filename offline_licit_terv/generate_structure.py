"""
1. lepes: fix seeddel, egyszer legeneralja a teljes licit-menetrend betukeszletet
10 csapatra.

Ez teljesen fuggetlen a futo webapp-tol (offline tervezesre valo), de a
tenyleges jatekban hasznalt betusuly-logikat (app/letters.py) hasznalja fel,
hogy a papíron elore kiosztott betuk pontosan ugyanugy legyenek sulyozva,
mint amit a webapp maga is csinalna.

Kimenet: output/licit_menetrend.json
"""
import json
import random
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.letters import apportion_letters  # noqa: E402

OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# --- rogzitett parameterek ---
SEED = 424242
NUM_TEAMS = 10
NUM_ROOMS = 5

# A "Licitalos Szokirakos" hivatalos menetrendje szerint 6 licit kor van,
# a teljes (licit+szokirakas) menetrendben elfoglalt sorszamukkal egyutt:
#   1. licit (menetrend 1. kore)  - dupla
#   2. licit (menetrend 2. kore)  - szimpla
#   3. licit (menetrend 4. kore)  - dupla
#   4. licit (menetrend 6. kore)  - dupla
#   5. licit (menetrend 8. kore)  - dupla
#   6. licit (menetrend 10. kore) - szimpla
BID_ROUNDS = [
    {"licit_szam": 1, "menetrend_kor": 1, "tipus": "dupla"},
    {"licit_szam": 2, "menetrend_kor": 2, "tipus": "szimpla"},
    {"licit_szam": 3, "menetrend_kor": 4, "tipus": "dupla"},
    {"licit_szam": 4, "menetrend_kor": 6, "tipus": "dupla"},
    {"licit_szam": 5, "menetrend_kor": 8, "tipus": "dupla"},
    {"licit_szam": 6, "menetrend_kor": 10, "tipus": "szimpla"},
]


def build_structure() -> dict:
    random.seed(SEED)

    total_units = 0
    for rnd in BID_ROUNDS:
        unit_size = 2 if rnd["tipus"] == "dupla" else 1
        total_units += NUM_ROOMS * NUM_TEAMS * unit_size

    bag = apportion_letters(total_units)

    pos = 0
    rounds_out = []
    for rnd in BID_ROUNDS:
        unit_size = 2 if rnd["tipus"] == "dupla" else 1
        rooms_out = []
        for room in range(1, NUM_ROOMS + 1):
            chunk_size = NUM_TEAMS * unit_size
            chunk = bag[pos : pos + chunk_size]
            pos += chunk_size
            units = ["".join(chunk[i * unit_size : (i + 1) * unit_size]) for i in range(NUM_TEAMS)]
            rooms_out.append({"terem": room, "betuk": units})
        rounds_out.append(
            {
                "licit_szam": rnd["licit_szam"],
                "menetrend_kor": rnd["menetrend_kor"],
                "tipus": rnd["tipus"],
                "termek": rooms_out,
            }
        )

    assert pos == total_units, "nem hasznaltuk fel az osszes kihuzott betut"

    return {
        "seed": SEED,
        "csapatok_szama": NUM_TEAMS,
        "termek_szama": NUM_ROOMS,
        "osszes_betu": total_units,
        "korok": rounds_out,
    }


def main() -> None:
    structure = build_structure()
    out_path = OUTPUT_DIR / "licit_menetrend.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(structure, f, ensure_ascii=False, indent=2)
    print(f"Kesz: {out_path}")
    print(f"Seed: {structure['seed']}, osszes betu: {structure['osszes_betu']}")


if __name__ == "__main__":
    main()
