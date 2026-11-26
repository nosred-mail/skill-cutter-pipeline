#!/usr/bin/env python3
"""Instalador portavel da skill `cutter-pipeline` para multiplos agentes de IA.

Copia esta pasta de skill autocontida para os diretorios globais padrao:
- Antigravity / Gemini: ~/.gemini/config/skills/cutter-pipeline
- Agentes Universais (Codex, Cursor, Windsurf, Amp): ~/.agents/skills/cutter-pipeline
- Claude Code: ~/.claude/skills/cutter-pipeline
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

SKILL_SRC = Path(__file__).resolve().parent.parent
SKILL_NAME = "cutter-pipeline"

TARGETS = {
    "antigravity": Path.home() / ".gemini" / "config" / "skills" / SKILL_NAME,
    "agents": Path.home() / ".agents" / "skills" / SKILL_NAME,
    "claude": Path.home() / ".claude" / "skills" / SKILL_NAME,
}


def copy_skill(dest: Path) -> str:
    dest = dest.resolve()
    if dest == SKILL_SRC.resolve():
        return str(dest)
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        SKILL_SRC,
        dest,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".venv", "_tmp*", ".git"),
    )
    return str(dest)


def main() -> None:
    ap = argparse.ArgumentParser(description="Instala a skill cutter-pipeline nos diretorios globais de agentes de IA.")
    ap.add_argument(
        "--targets",
        default="antigravity,agents,claude",
        help="Lista separada por virgula: all, antigravity, agents, claude ou caminho customizado",
    )
    args = ap.parse_args()

    raw_targets = [x.strip() for x in args.targets.split(",") if x.strip()]
    if any(x.lower() == "all" for x in raw_targets):
        expanded = []
        for x in raw_targets:
            if x.lower() == "all":
                expanded.extend(TARGETS.keys())
            else:
                expanded.append(x)
        raw_targets = list(dict.fromkeys(expanded))

    instalados = []
    for raw in raw_targets:
        destino = TARGETS.get(raw.lower(), Path(raw))
        instalados.append({"target": raw, "path": copy_skill(destino)})

    print(json.dumps({"skill": SKILL_NAME, "installed": instalados}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
