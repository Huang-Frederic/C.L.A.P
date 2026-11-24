"""CLI de C.L.A.P.

    clap smoke-test [dossier_videos] [--drafts DOSSIER]
    clap build <edl.json> [--drafts DOSSIER]
    clap analyze [dossier_rushs]          (à venir)

Les valeurs par défaut viennent du fichier .env (voir .env.example).
"""
from __future__ import annotations

import argparse
import sys

from clap.config import settings
from clap.edl import EDL, EDLError

DRAFTS_HELP = "dossier des brouillons CapCut (défaut : CAPCUT_DRAFTS_DIR du .env)"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="clap", description="C.L.A.P — Claude-Led Automated Production")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("smoke-test", help="vérifie que CapCut accepte un brouillon généré")
    s.add_argument("videos_dir", nargs="?", default=settings.rushes_dir,
                   help="dossier contenant quelques vidéos (défaut : CLAP_RUSHES_DIR du .env)")
    s.add_argument("--drafts", help=DRAFTS_HELP)

    b = sub.add_parser("build", help="EDL JSON -> brouillon CapCut")
    b.add_argument("edl", help="fichier EDL produit par Claude")
    b.add_argument("--drafts", help=DRAFTS_HELP)

    a = sub.add_parser("analyze", help="analyse un dossier de rushs -> rushes.json (à venir)")
    a.add_argument("rushes_dir", nargs="?", default=settings.rushes_dir)

    args = p.parse_args(argv)

    try:
        if args.cmd == "smoke-test":
            if not args.videos_dir:
                raise SystemExit("Donne un dossier de vidéos, ou renseigne CLAP_RUSHES_DIR dans .env.")
            from clap.builders.capcut import smoke_test
            out = smoke_test(settings.require_drafts_dir(args.drafts), args.videos_dir)
            print(f"OK : brouillon écrit dans {out}\nFerme puis rouvre CapCut et cherche « CLAP_SMOKE_TEST ».")
        elif args.cmd == "build":
            from clap.builders.capcut import build_draft
            edl = EDL.load(args.edl)
            out = build_draft(edl, settings.require_drafts_dir(args.drafts))
            print(f"OK : {len(edl.cuts)} plans, {edl.total_us / 1e6:.1f}s -> {out}")
        elif args.cmd == "analyze":
            print("L'analyseur n'est pas encore implémenté.", file=sys.stderr)
            return 2
    except EDLError as e:
        print(f"EDL invalide : {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
