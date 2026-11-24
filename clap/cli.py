"""CLI de C.L.A.P.

    clap smoke-test [dossier_videos] [--drafts DOSSIER]
    clap build <edl.json> [--drafts DOSSIER]
    clap analyze [dossier_rushs] [--limit N] [--force]
    clap beats <musique.mp3>

Les valeurs par défaut viennent de clap.toml (voir clap.example.toml).
"""
from __future__ import annotations

import argparse
import sys

from clap.config import settings
from clap.edl import EDL, EDLError

DRAFTS_HELP = "dossier des brouillons CapCut (défaut : [capcut] drafts_dir de clap.toml)"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="clap", description="C.L.A.P — Claude-Led Automated Production")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("smoke-test", help="vérifie que CapCut accepte un brouillon généré")
    s.add_argument("videos_dir", nargs="?", default=settings.rushes_dir,
                   help="dossier contenant quelques vidéos (défaut : [paths] rushes_dir de clap.toml)")
    s.add_argument("--drafts", help=DRAFTS_HELP)

    b = sub.add_parser("build", help="EDL JSON -> brouillon CapCut")
    b.add_argument("edl", help="fichier EDL produit par Claude")
    b.add_argument("--drafts", help=DRAFTS_HELP)

    a = sub.add_parser("analyze", help="analyse un dossier de rushs -> rushes.json + planches contact")
    a.add_argument("rushes_dir", nargs="?", default=settings.rushes_dir,
                   help="dossier de rushs (défaut : [paths] rushes_dir de clap.toml)")
    a.add_argument("--out", help="dossier de sortie (défaut : [paths] output_dir de clap.toml)")
    a.add_argument("--fps", type=float, default=4.0, help="images analysées par seconde (défaut 4)")
    a.add_argument("--limit", type=int, help="n'analyser que les N premières vidéos (pour tester)")
    a.add_argument("--force", action="store_true", help="ignorer le cache et tout réanalyser")

    m = sub.add_parser("beats", help="grille rythmique d'une musique (mode AMV)")
    m.add_argument("music", help="fichier audio (mp3, wav, m4a…)")
    m.add_argument("--out", help="fichier JSON de sortie (défaut : <musique>.beats.json)")

    args = p.parse_args(argv)

    try:
        if args.cmd == "smoke-test":
            if not args.videos_dir:
                raise SystemExit("Donne un dossier de vidéos, ou renseigne [paths] rushes_dir dans clap.toml.")
            from clap.builders.capcut import smoke_test
            out = smoke_test(settings.require_drafts_dir(args.drafts), args.videos_dir)
            print(f"OK : brouillon écrit dans {out}\nFerme puis rouvre CapCut et cherche « CLAP_SMOKE_TEST ».")
        elif args.cmd == "build":
            from clap.builders.capcut import build_draft
            edl = EDL.load(args.edl)
            out = build_draft(edl, settings.require_drafts_dir(args.drafts))
            print(f"OK : {len(edl.cuts)} plans, {edl.total_us / 1e6:.1f}s -> {out}")
        elif args.cmd == "analyze":
            if not args.rushes_dir:
                raise SystemExit("Donne un dossier de rushs, ou renseigne [paths] rushes_dir dans clap.toml.")
            from clap.analyzer.run import analyze_folder
            analyze_folder(args.rushes_dir, out_dir=args.out, sample_fps=args.fps,
                           limit=args.limit, force=args.force)
        elif args.cmd == "beats":
            from clap.analyzer.music import analyze_music
            analyze_music(args.music, args.out)
    except EDLError as e:
        print(f"EDL invalide : {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
