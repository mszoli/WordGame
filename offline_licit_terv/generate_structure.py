"""
1. lepes: fix seeddel, egyszer legeneralja a teljes licit-menetrend betukeszletet
10 csapatra.

Ez teljesen fuggetlen a futo webapp-tol (offline tervezesre valo), de a
tenyleges jatekban hasznalt betusuly-logikat (app/letters.py) hasznalja fel,
hogy a papíron elore kiosztott betuk pontosan ugyanugy legyenek sulyozva,
mint amit a webapp maga is csinalna.

Kimenet: <output-dir>/licit_menetrend.json

Parameterek:
    --output-dir output2       hova irja a JSON-t (alapertelmezes: output)
    --schedule dupla,szimpla,dupla,dupla,szimpla
                                a licit korok tipusai sorrendben (ha nincs
                                megadva, az eredeti 6 koros menetrend ervenyes,
                                a teljes menetrendben elfoglalt sorszamukkal)
    --seed 424242               (alapertelmezes: 424242)
"""
import argparse
import json
import random
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.letters import apportion_letters  # noqa: E402

DEFAULT_SEED = 424242
NUM_TEAMS = 10
NUM_ROOMS = 5

# A "Licitalos Szokirakos" eredeti hivatalos menetrendje szerint 6 licit kor
# van, a teljes (licit+szokirakas) menetrendben elfoglalt sorszamukkal egyutt:
#   1. licit (menetrend 1. kore)  - dupla
#   2. licit (menetrend 2. kore)  - szimpla
#   3. licit (menetrend 4. kore)  - dupla
#   4. licit (menetrend 6. kore)  - dupla
#   5. licit (menetrend 8. kore)  - dupla
#   6. licit (menetrend 10. kore) - szimpla
DEFAULT_BID_ROUNDS = [
    {"licit_szam": 1, "menetrend_kor": 1, "tipus": "dupla"},
    {"licit_szam": 2, "menetrend_kor": 2, "tipus": "szimpla"},
    {"licit_szam": 3, "menetrend_kor": 4, "tipus": "dupla"},
    {"licit_szam": 4, "menetrend_kor": 6, "tipus": "dupla"},
    {"licit_szam": 5, "menetrend_kor": 8, "tipus": "dupla"},
    {"licit_szam": 6, "menetrend_kor": 10, "tipus": "szimpla"},
]


def build_structure(bid_rounds: list[dict], seed: int) -> dict:
    random.seed(seed)

    total_units = 0
    for rnd in bid_rounds:
        unit_size = 2 if rnd["tipus"] == "dupla" else 1
        total_units += NUM_ROOMS * NUM_TEAMS * unit_size

    bag = apportion_letters(total_units)

    pos = 0
    rounds_out = []
    for rnd in bid_rounds:
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
        "seed": seed,
        "csapatok_szama": NUM_TEAMS,
        "termek_szama": NUM_ROOMS,
        "osszes_betu": total_units,
        "korok": rounds_out,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="output")
    parser.add_argument(
        "--schedule",
        default=None,
        help="pl. 'dupla,szimpla,dupla,dupla,szimpla' - ha nincs megadva, az eredeti 6 koros menetrend",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()

    if args.schedule:
        types = [t.strip() for t in args.schedule.split(",") if t.strip()]
        bid_rounds = [
            {"licit_szam": i + 1, "menetrend_kor": None, "tipus": t} for i, t in enumerate(types)
        ]
    else:
        bid_rounds = DEFAULT_BID_ROUNDS

    output_dir = BASE_DIR / args.output_dir
    output_dir.mkdir(exist_ok=True)

    structure = build_structure(bid_rounds, args.seed)
    out_path = output_dir / "licit_menetrend.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(structure, f, ensure_ascii=False, indent=2)
    print(f"Kesz: {out_path}")
    print(f"Seed: {structure['seed']}, osszes betu: {structure['osszes_betu']}")


if __name__ == "__main__":
    main()
