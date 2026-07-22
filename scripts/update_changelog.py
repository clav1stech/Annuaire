"""Idempotent CHANGELOG.md updater.

Insère une nouvelle entrée de version en tête du fichier si elle est absente ;
ne touche jamais aux entrées déjà présentes. Usage :

    python scripts/update_changelog.py 1.1.0 "Résumé du changement"

Sans résumé fourni, lit VERSION à la racine et exige un résumé en argument.
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG_PATH = ROOT / "CHANGELOG.md"
HEADER = "# Changelog"


def add_entry(version: str, summary: str, changelog_path: Path = CHANGELOG_PATH) -> bool:
    """Insert a `## version - date` entry if missing. Return True if inserted."""
    text = changelog_path.read_text(encoding="utf-8") if changelog_path.exists() else f"{HEADER}\n\n"

    if re.search(rf"^## {re.escape(version)}\b", text, flags=re.MULTILINE):
        return False

    entry = f"## {version} - {date.today().isoformat()}\n- {summary}\n"

    if HEADER in text:
        head, _, rest = text.partition(HEADER)
        rest = rest.lstrip("\n")
        new_text = f"{head}{HEADER}\n\n{entry}\n{rest}"
    else:
        new_text = f"{HEADER}\n\n{entry}\n{text}"

    changelog_path.write_text(new_text, encoding="utf-8")
    return True


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python scripts/update_changelog.py <version> <résumé>", file=sys.stderr)
        return 1

    version, summary = sys.argv[1], sys.argv[2]
    inserted = add_entry(version, summary)
    print(f"{'Ajouté' if inserted else 'Déjà présent, inchangé'} : {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
