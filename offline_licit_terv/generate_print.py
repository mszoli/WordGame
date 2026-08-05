"""
2. lepes: a mar legeneralt licit_menetrend.json alapjan letrehoz egy
konnyen vegigolvashato Markdown tablazatot, valamint egy A4-es (fekvo)
nyomtathato PDF-et (xelatex-szel forditva).

Kimenet:
  output/licit_menetrend.md
  output/licit_menetrend.tex
  output/licit_menetrend.pdf
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.letters import hungarian_sort_key  # noqa: E402

ROUND_TYPE_LABEL = {"dupla": "Dupla betűs", "szimpla": "Szimpla betűs"}


def load_structure(output_dir: Path) -> dict:
    with open(output_dir / "licit_menetrend.json", encoding="utf-8") as f:
        return json.load(f)


def build_markdown(structure: dict) -> str:
    lines = []
    lines.append("# Licitálós Szókirakós — teljes licit-menetrend")
    lines.append("")
    lines.append(
        f"*(seed: {structure['seed']} — ugyanezzel a seeddel újra legenerálva mindig "
        "ugyanez jön ki, tehát ez a végleges, rögzített menetrend)*"
    )
    lines.append("")
    lines.append(
        f"{structure['csapatok_szama']} csapat, {structure['termek_szama']} terem/licit, "
        f"{len(structure['korok'])} licit kör."
    )
    lines.append("")

    for rnd in structure["korok"]:
        type_label = ROUND_TYPE_LABEL[rnd["tipus"]]
        cim = f"## {rnd['licit_szam']}. licit kör — {type_label}"
        if rnd.get("menetrend_kor") is not None:
            cim += f" (a teljes menetrend {rnd['menetrend_kor']}. köre)"
        lines.append(cim)
        lines.append("")
        lines.append("| Terem | Betűk (licitálható egységek) |")
        lines.append("|---|---|")
        for room in rnd["termek"]:
            units = sorted(room["betuk"], key=hungarian_sort_key)
            lines.append(f"| {room['terem']}. terem | {' · '.join(units)} |")
        lines.append("")

    return "\n".join(lines)


def escape_latex(s: str) -> str:
    return s.replace("&", r"\&").replace("%", r"\%").replace("#", r"\#")


def build_latex(structure: dict) -> str:
    rounds = structure["korok"]
    num_rooms = structure["termek_szama"]

    # lathatatlan "strut"-ok, hogy a cellak tartalma sose erjen hozza
    # kozvetlenul a felette/alatta levo \hline-hoz
    tstrut = r"\rule{0pt}{3.4ex}"
    bstrut = r"\rule[-1.4ex]{0pt}{0pt}"

    col_spec = "l" + "c" * len(rounds)

    def header_cell(r: dict) -> str:
        lines = [rf"\textbf{{{r['licit_szam']}. licit kör}}", ROUND_TYPE_LABEL[r["tipus"]]]
        if r.get("menetrend_kor") is not None:
            lines.append(f"(menetrend {r['menetrend_kor']}. köre)")
        return rf"\shortstack{{{tstrut}" + r" \\ ".join(lines) + rf"{bstrut}}}"

    header_cells = " & ".join(header_cell(r) for r in rounds)

    body_rows = []
    for room_idx in range(num_rooms):
        room_num = room_idx + 1
        cells = []
        for rnd in rounds:
            units = sorted(rnd["termek"][room_idx]["betuk"], key=hungarian_sort_key)
            escaped = [escape_latex(u) for u in units]
            # ket sorban, egyenkent 5 egyseg, hogy a cella kompakt es olvashato maradjon
            row1 = "~".join(escaped[:5])
            row2 = "~".join(escaped[5:])
            cell = rf"\shortstack{{{tstrut}{row1} \\ {row2}{bstrut}}}"
            cells.append(cell)
        body_rows.append(f"\\textbf{{{tstrut}{room_num}. terem{bstrut}}} & " + " & ".join(cells) + r" \\ \hline")

    body = "\n".join(body_rows)

    tex = rf"""\documentclass[11pt]{{extarticle}}
\usepackage{{fontspec}}
\usepackage[a4paper,landscape,margin=1.1cm]{{geometry}}
\usepackage{{array}}
\usepackage{{longtable}}
\renewcommand{{\arraystretch}}{{2.2}}
\setlength{{\tabcolsep}}{{12pt}}
\pagestyle{{empty}}
\begin{{document}}

\begin{{center}}
{{\Large \textbf{{Licitálós Szókirakós -- teljes licit-menetrend}}}}\\[4pt]
{{\small {structure['csapatok_szama']} csapat, {structure['termek_szama']} terem/licit}}
\end{{center}}
\vspace{{8pt}}

\begin{{center}}
\begin{{tabular}}{{|{col_spec}|}}
\hline
 & {header_cells} \\ \hline
{body}
\end{{tabular}}
\end{{center}}

\vspace{{6pt}}
{{\footnotesize Minden cellában a 10 licitálható egység (dupla licitnél betűpár, szimplánál
önálló betű) látható, ábécésorrendben. A licit lezárása után a legtöbbet fizető választ
elsőként az adott terem egységei közül, utána a második legtöbbet fizető, stb. -- holtverseny
esetén a választás sorrendjét a teremben sorsolják.}}

\end{{document}}
"""
    return tex


def compile_pdf(tex_path: Path) -> bool:
    xelatex = shutil.which("xelatex")
    if not xelatex:
        print("FIGYELEM: xelatex nem található, a PDF nem készült el (a .tex fájl megvan).")
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
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args()
    output_dir = BASE_DIR / args.output_dir

    structure = load_structure(output_dir)

    md = build_markdown(structure)
    md_path = output_dir / "licit_menetrend.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"Kesz: {md_path}")

    tex = build_latex(structure)
    tex_path = output_dir / "licit_menetrend.tex"
    tex_path.write_text(tex, encoding="utf-8")
    print(f"Kesz: {tex_path}")

    if compile_pdf(tex_path):
        print(f"Kesz: {output_dir / 'licit_menetrend.pdf'}")
        # takaritas: latex mellektermekek torlese
        for ext in (".aux", ".log", ".out"):
            p = tex_path.with_suffix(ext)
            if p.exists():
                p.unlink()
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
