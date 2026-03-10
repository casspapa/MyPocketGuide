#!/usr/bin/env python3
"""
Add Visual Identification sections to exhibit markdown files.
Run from repo root: python3 scripts/add_visual_ids.py

Inserts a ## Visual Identification section between the header metadata
(Connected Exhibits line) and the ## Overview section.

Safe to run multiple times — skips files that already have the section.
"""

import re
from pathlib import Path

EXHIBITS_DIR = Path(__file__).parent.parent / "data" / "exhibits"

VISUAL_DATA = {
    "really_good": {
        "keywords": "giant bronze hand, thumbs up, elongated thumb, dark patina, plinth",
        "commonly_called": '"The Thumb", "the big thumb", "thumbs up sculpture", "Shrigley thumb", "giant thumbs up"',
        "visual_cues": (
            "7-metre bronze hand with disproportionately long thumb giving a "
            "thumbs-up gesture. Dark patina finish matching 19th century statuary. "
            "Displayed on a plinth."
        ),
    },
    "warhol_marilyn": {
        "keywords": "silkscreen print, Marilyn Monroe face, pop art, bright colours, misregistered ink",
        "commonly_called": '"Marilyn", "Warhol Marilyn", "the Marilyn print", "pop art Marilyn"',
        "visual_cues": (
            "Brightly coloured silkscreen print of Marilyn Monroe's face from a "
            "publicity photo. Flat areas of vivid colour (yellow hair, pink face, "
            "red lips) with deliberately misaligned ink layers creating a blurred "
            "effect. Square canvas format."
        ),
    },
    "mona_lisa": {
        "keywords": "oil painting, woman portrait, enigmatic smile, sfumato, dark background, landscape",
        "commonly_called": '"Mona Lisa", "La Gioconda", "the Leonardo", "the woman with the smile"',
        "visual_cues": (
            "Small oil painting (77×53cm) of a seated woman with a faint smile. "
            "Dark clothing against a misty landscape background. Warm brown tones "
            "with soft, blended edges (sfumato technique). Noticeably smaller than "
            "expected."
        ),
    },
    "trevi_fountain_painting": {
        "keywords": "oil painting, Baroque fountain, Roman architecture, veduta, crowd scene, water",
        "commonly_called": '"Trevi Fountain painting", "the Panini", "the Rome painting", "the fountain painting"',
        "visual_cues": (
            "Large oil painting depicting the Trevi Fountain in Rome with surrounding "
            "architecture and figures. Warm Mediterranean light, detailed architectural "
            "perspective, crowd of small figures around the monumental fountain."
        ),
    },
    "hope_blue_whale": {
        "keywords": "whale skeleton, suspended ceiling, bones, massive, Hintze Hall",
        "commonly_called": '"Hope", "the whale", "blue whale", "the whale skeleton", "the big skeleton on the ceiling"',
        "visual_cues": (
            "Enormous 25.2-metre whale skeleton suspended from the ceiling. Long "
            "jawbones, visible ribcage, vertebral column stretching the full length. "
            "Cream/white bones. Dominates the entire hall."
        ),
    },
    "dippy_diplodocus": {
        "keywords": "dinosaur skeleton, long neck, long tail, sauropod, plaster cast, Diplodocus",
        "commonly_called": '"Dippy", "the dinosaur", "the diplodocus", "the long-necked dinosaur"',
        "visual_cues": (
            "26-metre plaster cast dinosaur skeleton with extremely long neck and "
            "whip-like tail. Four-legged stance, relatively small skull. Off-white "
            "colour. Takes up most of the floor space."
        ),
    },
    "coelacanth": {
        "keywords": "preserved fish, lobe fins, fleshy fins, dark blue-grey, preservation specimen",
        "commonly_called": '"the coelacanth", "the living fossil", "the prehistoric fish", "the lobe-finned fish"',
        "visual_cues": (
            "Preserved fish specimen, dark blue-grey colour, approximately 2 metres "
            "long. Distinctive fleshy, limb-like lobe fins. Large heavy scales."
        ),
    },
    "caryatid": {
        "keywords": "marble female figure, draped robes, architectural column, Greek sculpture, basket on head",
        "commonly_called": '"the caryatid", "the Greek woman", "the column woman", "the marble lady"',
        "visual_cues": (
            "2.3-metre marble sculpture of a standing woman in flowing draped robes. "
            "Carries a basket (kalathos) on her head. One leg bears weight with thick "
            "vertical drapery folds. White Pentelic marble, classical Greek style."
        ),
    },
    "parthenon_frieze": {
        "keywords": "marble relief, procession, horses, chariots, Greek figures, low relief, carved panel",
        "commonly_called": '"the Parthenon Frieze", "Elgin Marbles", "the Greek frieze", "the marble relief"',
        "visual_cues": (
            "Continuous band of carved marble relief approximately 1 metre high. "
            "Depicts figures in procession — humans on foot and horseback, chariots, "
            "animals. Low relief carving in white/cream Pentelic marble."
        ),
    },
    "antikythera_mechanism": {
        "keywords": "bronze geared device, corroded metal, ancient mechanism, green patina, gears, shoebox-sized",
        "commonly_called": '"the Antikythera Mechanism", "the ancient computer", "the Greek computer", "the gear device"',
        "visual_cues": (
            "Heavily corroded bronze fragments showing interlocking gears and "
            "inscriptions. Green patina from centuries underwater. Approximately "
            "shoebox-sized. Visible gear teeth and dial markings. Precision replica."
        ),
    },
    "willamette_meteorite": {
        "keywords": "large iron meteorite, metallic, bowl-shaped cavities, dark metal, massive",
        "commonly_called": '"the meteorite", "the Willamette Meteorite", "the space rock", "Tomanowos"',
        "visual_cues": (
            "Massive 2.1-metre-tall iron-nickel meteorite. Dark metallic surface with "
            "distinctive bowl-shaped cavities. Irregular rounded shape, 15.5 tonnes."
        ),
    },
    "apollo_11": {
        "keywords": "conical spacecraft, command module, heat shield, scorched exterior, capsule",
        "commonly_called": '"Apollo 11", "Columbia", "the command module", "the Moon capsule", "the space capsule"',
        "visual_cues": (
            "Conical spacecraft capsule approximately 3.9 metres tall and wide. "
            "Scorched and ablated heat shield on the base. Metallic silver/grey body "
            "with visible hatches and windows. Full-scale replica."
        ),
    },
    "hubble_telescope": {
        "keywords": "cylindrical telescope, solar panels, silver and gold foil, space telescope",
        "commonly_called": '"Hubble", "the Hubble telescope", "the space telescope"',
        "visual_cues": (
            "Full-scale cylindrical telescope replica, 13.2m long, 4.2m diameter. "
            "Silver/metallic body with gold thermal insulation foil. Two large "
            "rectangular solar panel wings. Aperture door at one end."
        ),
    },
    "giant_squid": {
        "keywords": "preserved squid, tentacles, glass tank, formalin, large invertebrate, eyes",
        "commonly_called": '"the giant squid", "the squid", "the kraken", "the sea monster"',
        "visual_cues": (
            "Preserved giant squid specimen in a 9-metre formalin tank. Long tentacles "
            "and eight arms. Very large eyes. Pale/translucent body with elongated "
            "torpedo-shaped mantle."
        ),
    },
    "megalodon_jaw": {
        "keywords": "massive shark jaw, large teeth, jaw reconstruction, triangular teeth, open mouth",
        "commonly_called": '"the Megalodon", "the shark jaw", "the Megalodon jaw", "the giant shark teeth"',
        "visual_cues": (
            "Full-scale jaw reconstruction approximately 3 metres in diameter. Rows of "
            "large triangular teeth up to 18cm each. Open jaw formation. Could fit "
            "several people standing inside."
        ),
    },
    "hms_challenger": {
        "keywords": "Victorian instruments, specimen jars, dredging equipment, nautical collection",
        "commonly_called": '"the Challenger collection", "HMS Challenger", "the expedition collection"',
        "visual_cues": (
            "Collection display: Victorian-era dredging equipment, glass specimen jars "
            "with preserved marine specimens, brass scientific instruments, and nautical "
            "charts. Period brass and wood aesthetic."
        ),
    },
}


def build_section(data: dict) -> str:
    """Build the ## Visual Identification markdown section."""
    return (
        f"\n## Visual Identification\n"
        f"Keywords: {data['keywords']}\n"
        f"Commonly called: {data['commonly_called']}\n"
        f"Visual cues: {data['visual_cues']}\n"
    )


def patch_file(filepath: Path, exhibit_id: str) -> bool:
    """Insert Visual Identification section into an exhibit file.
    Returns True if modified, False if skipped.
    """
    if exhibit_id not in VISUAL_DATA:
        print(f"  ⚠ No visual data for {exhibit_id}, skipping")
        return False

    content = filepath.read_text(encoding="utf-8")

    # Skip if already patched
    if "## Visual Identification" in content:
        print(f"  ⏭ {filepath.name} already has Visual Identification, skipping")
        return False

    # Insert before ## Overview
    section = build_section(VISUAL_DATA[exhibit_id])

    if "## Overview" in content:
        content = content.replace("## Overview", f"{section}\n## Overview", 1)
    else:
        # Fallback: insert after the last **Connected Exhibits** line
        lines = content.split("\n")
        insert_idx = None
        for i, line in enumerate(lines):
            if line.startswith("**Connected Exhibits"):
                insert_idx = i + 1
        if insert_idx:
            lines.insert(insert_idx, section)
            content = "\n".join(lines)
        else:
            print(f"  ⚠ No anchor found in {filepath.name}, appending at end")
            content += "\n" + section

    filepath.write_text(content, encoding="utf-8")
    return True


def main():
    if not EXHIBITS_DIR.exists():
        print(f"Exhibits directory not found: {EXHIBITS_DIR}")
        return

    md_files = sorted(EXHIBITS_DIR.glob("*.md"))
    print(f"Found {len(md_files)} exhibit files in {EXHIBITS_DIR}\n")

    modified = 0
    for filepath in md_files:
        exhibit_id = filepath.stem
        print(f"Processing: {filepath.name}")
        if patch_file(filepath, exhibit_id):
            print(f"  ✅ Visual Identification added")
            modified += 1

    print(f"\nDone. Modified {modified}/{len(md_files)} files.")
    print("\n⚠ Remember to re-ingest into RAG after this:")
    print("  python3 scripts/ingest.py")


if __name__ == "__main__":
    main()