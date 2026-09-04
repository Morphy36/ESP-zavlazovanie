#!/usr/bin/env python3
"""
Zloží meteostanica.yaml + packages/*.yaml do jedného súboru
`meteostanica-single.yaml`, ktorý stačí prekopírovať do ESPHome dashboardu.

Použitie:
    python3 build_single_file.py

Modulárna verzia je zdroj pravdy — po každej zmene v packages/ spusti tento
skript znova. Komentáre aj poradie sa zachovávajú, `${substitúcie}` a `!secret`
ostávajú nedotknuté (v jednom súbore fungujú rovnako).
"""

import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
MAIN = HERE / "meteostanica.yaml"
OUT = HERE / "meteostanica-single.yaml"

# Poradie, v akom sa kľúče zapíšu do výsledného súboru.
KEY_ORDER = [
    "esphome", "esp32", "logger",
    "wifi", "api", "ota",
    "i2c", "deep_sleep", "output",
    "globals",
    "sensor", "binary_sensor", "text_sensor",
    "switch", "button", "number",
    "script",
]

TOP_KEY = re.compile(r"^([a-z_][a-z_0-9]*):\s*$")


def split_blocks(text):
    """Rozdelí súbor na (kľúč, komentáre_pred_ním, telo_bez_riadku_s_kľúčom)."""
    lines = text.splitlines()
    blocks, pending, current = [], [], None

    for line in lines:
        m = TOP_KEY.match(line)
        if m:
            if current:
                blocks.append(current)
            current = {"key": m.group(1), "lead": pending, "body": []}
            pending = []
            continue
        if current is None:
            pending.append(line)          # hlavička súboru pred prvým kľúčom
        elif line.strip().startswith("#") or not line.strip():
            pending.append(line)          # môže patriť až nasledujúcemu kľúču
        else:
            current["body"].extend(pending)
            pending = []
            current["body"].append(line)

    if current:
        current["body"].extend(l for l in pending if l.strip().startswith("#"))
        blocks.append(current)
    return blocks


def trim(lines):
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def main():
    main_text = MAIN.read_text(encoding="utf-8")

    packages = re.findall(r"^\s+\w+:\s*!include\s+(\S+)\s*$", main_text, re.M)
    if not packages:
        sys.exit("Nenašiel som žiadne !include v meteostanica.yaml")

    # Substitúcie z hlavného súboru (bez sekcie packages:).
    subs = re.search(r"^substitutions:\n(.*?)(?=^\S)", main_text, re.M | re.S)
    if not subs:
        sys.exit("Nenašiel som sekciu substitutions:")

    buckets = {}
    for rel in packages:
        path = HERE / rel
        for block in split_blocks(path.read_text(encoding="utf-8")):
            buckets.setdefault(block["key"], []).append((path.name, block))

    unknown = set(buckets) - set(KEY_ORDER)
    if unknown:
        sys.exit(f"Neznámy kľúč najvyššej úrovne: {sorted(unknown)} — doplň ho do KEY_ORDER")

    out = [
        "# " + "=" * 75,
        "#  VONKAJŠIA METEOSTANICA — ESPHome v3.0.0 (jednosúborová verzia)",
        "# " + "=" * 75,
        "#",
        "#  AUTOMATICKY VYGENEROVANÉ — needituj tento súbor.",
        "#  Zdroj: meteostanica.yaml + packages/*.yaml",
        "#  Regenerácia: python3 build_single_file.py",
        "#",
        "#  Do ESPHome dashboardu stačí prekopírovať tento jeden súbor a mať",
        "#  vyplnený secrets.yaml (šablóna je v secrets.yaml.example).",
        "# " + "=" * 75,
        "",
        "substitutions:",
        subs.group(1).rstrip(),
        "",
    ]

    for key in KEY_ORDER:
        if key not in buckets:
            continue
        out.append("")
        out.append("# " + "=" * 75)
        out.append(f"#  {key.upper()}")
        out.append("# " + "=" * 75)
        out.append(f"{key}:")
        for src, block in buckets[key]:
            out.append(f"  # ── packages/{src} " + "─" * max(3, 56 - len(src)))
            # Z hlavičiek balíčkov necháme len text, oddeľovacie riadky zahodíme
            # a všetko odsadíme, nech je vidieť, že patrí do tejto sekcie.
            for line in trim([l for l in block["lead"] if l.strip().startswith("#")]):
                stripped = line.strip().lstrip("#").strip()
                if stripped and set(stripped) <= {"=", "-", "─"}:
                    continue
                out.append(("  # " + stripped).rstrip())
            out.extend(trim(list(block["body"])))
            out.append("")

    OUT.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    n = len(OUT.read_text(encoding="utf-8").splitlines())
    print(f"Zapísané: {OUT.name} ({n} riadkov, {len(packages)} balíčkov)")


if __name__ == "__main__":
    main()
