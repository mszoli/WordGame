"""
Kivágható betűcsempe-lapok generálása nyomtatáshoz.

Minden A4-es lap egy 5x5-ös rácsot tartalmaz (25 cella = 25 betű), a teljes
oldalt kitöltve, vastag vonalakkal a könnyű kivágáshoz.

Használat (előbb csak egy mintaoldal, teszt-betűkkel):
    python generate_tiles.py --sample
Utána a végleges, a licit_menetrend.json-ban rögzített teljes 500 betűből
generált, 20 oldalas nyomtatható PDF (előbb futtasd le a
generate_structure.py-t, hogy legyen output/licit_menetrend.json):
    python generate_tiles.py
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

COLS = 5
ROWS = 5
CELL_W_CM = 3.6
CELL_H_CM = 5.1
# nyomtatasbiztos szel - sok nyomtato nem tud a lap szelere nyomtatni;
# fent/lent kicsit tobb, mint oldalt, hogy a racs biztosan ne csusszon
# ki fugolegesen sem
MARGIN_SIDE_CM = 1.2
MARGIN_TOPBOTTOM_CM = 1.6


def escape_latex(s: str) -> str:
    return s.replace("&", r"\&").replace("%", r"\%").replace("#", r"\#")


def build_page_tikz(letters: list[str]) -> str:
    """Egy A4 oldalnyi (5x5=25 cellás) TikZ racsot epit fel a megadott
    (pontosan 25 db) betubol."""
    assert len(letters) == COLS * ROWS, f"pontosan {COLS * ROWS} betu kell egy laphoz, kaptunk: {len(letters)}"

    nodes = []
    for row in range(ROWS):
        for col in range(COLS):
            idx = row * COLS + col
            letter = escape_latex(letters[idx])
            # a cellak KOZEPpontjat ugy toljuk el, hogy a racs teteje pontosan
            # a jelenlegi (0,0) alapvonalnal kezdodjon, ne loggyon ki felig
            # fole - igy nincs rejtett ures sav a lap tetejen/aljan
            x = col * CELL_W_CM + CELL_W_CM / 2
            y = -(row * CELL_H_CM + CELL_H_CM / 2)
            # \vphantom{ŐQ}: a "Ő" adja a legmagasabb ekezetet, a "Q" a
            # legmelyebb lelogo reszt - ezt a lathatatlan "vonalzot" tesszuk
            # minden cellaba a tenyleges betu melle, hogy a tikz node
            # mindig UGYANAHHOZ a (konstans) magassaghoz/melyseghez
            # kepest kozepitsen, ne az adott betu sajat (valtozo) ekezet-
            # magassagahoz - igy minden betu alapvonala azonos szinten all.
            nodes.append(
                rf"\node[draw, line width=1pt, minimum width={CELL_W_CM}cm, "
                rf"minimum height={CELL_H_CM}cm, inner sep=0pt, "
                rf"font=\fontsize{{100}}{{100}}\selectfont] at ({x}cm,{y}cm) "
                rf"{{\vphantom{{ŐQ}}{letter}}};"
            )

    return "\n".join(nodes)


def build_document(pages: list[list[str]]) -> str:
    page_blocks = []
    for letters in pages:
        tikz_nodes = build_page_tikz(letters)
        page_blocks.append(
            rf"""\begin{{tikzpicture}}[remember picture]
{tikz_nodes}
\end{{tikzpicture}}
\newpage"""
        )

    body = "\n".join(page_blocks)

    return rf"""\documentclass[12pt]{{article}}
\usepackage{{fontspec}}
\usepackage[a4paper,left={MARGIN_SIDE_CM}cm,right={MARGIN_SIDE_CM}cm,top={MARGIN_TOPBOTTOM_CM}cm,bottom={MARGIN_TOPBOTTOM_CM}cm]{{geometry}}
\usepackage{{tikz}}
\pagestyle{{empty}}
\setlength{{\parindent}}{{0pt}}
\setlength{{\parskip}}{{0pt}}
\begin{{document}}
\noindent
{body}
\end{{document}}
"""


def compile_pdf(tex_path: Path) -> bool:
    xelatex = shutil.which("xelatex")
    if not xelatex:
        print("FIGYELEM: xelatex nem található.")
        return False
    result = subprocess.run(
        [xelatex, "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
        cwd=str(tex_path.parent),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("HIBA a PDF fordítása közben:")
        print(result.stdout[-3000:])
        return False
    for ext in (".aux", ".log", ".out"):
        p = tex_path.with_suffix(ext)
        if p.exists():
            p.unlink()
    return True


def load_all_letters(output_dir: Path) -> list[str]:
    """A licit_menetrend.json-ban mar rogzitett teljes betukeszletet egyetlen
    listava lapitja (minden betupar 2 kulon beture bontva) - igy a kivagando
    csempek pontosan ugyanazt a betukeszletet tartalmazzak, mint a
    nyomtatott menetrend-tablazat."""
    menetrend_path = output_dir / "licit_menetrend.json"
    if not menetrend_path.exists():
        print(f"HIBA: {menetrend_path} nem talalhato - eloszor futtasd le a generate_structure.py-t.")
        sys.exit(1)
    with open(menetrend_path, encoding="utf-8") as f:
        structure = json.load(f)
    letters: list[str] = []
    for rnd in structure["korok"]:
        for room in rnd["termek"]:
            for unit in room["betuk"]:
                letters.extend(list(unit))
    return letters


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", action="store_true", help="csak egy mintaoldal teszt-betukkel")
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args()
    output_dir = BASE_DIR / args.output_dir
    output_dir.mkdir(exist_ok=True)

    if args.sample:
        sample_letters = ["A", "Á", "B", "C", "D", "E", "É", "F", "G", "H",
                           "I", "Í", "J", "K", "L", "M", "N", "O", "Ó", "Ö",
                           "Ő", "P", "Q", "R", "S"]
        pages = [sample_letters]
        out_name = "betu_lapok_minta"
    else:
        letters = load_all_letters(output_dir)
        per_page = COLS * ROWS
        if len(letters) % per_page != 0:
            print(f"FIGYELEM: {len(letters)} betu nem oszthato {per_page}-tel maradek nelkul.")
        num_pages = len(letters) // per_page
        pages = [letters[i * per_page : (i + 1) * per_page] for i in range(num_pages)]
        out_name = "betu_lapok_teljes"
        print(f"Osszes betu: {len(letters)}, oldalak szama: {num_pages} (egyenkent {per_page} betu)")

    tex = build_document(pages)
    tex_path = output_dir / f"{out_name}.tex"
    tex_path.write_text(tex, encoding="utf-8")
    print(f"Kesz: {tex_path}")

    if compile_pdf(tex_path):
        print(f"Kesz: {output_dir / (out_name + '.pdf')}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
