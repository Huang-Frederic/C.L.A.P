"""`clap analyze` : dossier de rushs -> output/<dossier>/rushes.json + planches contact.

Reprise sur interruption : chaque vidéo analysée est mise en cache (clé = nom + taille + date de
modification), donc relancer la commande ne refait que les vidéos nouvelles ou modifiées.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2

from clap.analyzer.media import decode_mode
from clap.analyzer.sheets import overview_sheets, video_sheet
from clap.analyzer.video import analyze_video
from clap.config import settings

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".m4v"}
SCHEMA_VERSION = 3


def _cache_key(p: Path) -> str:
    st = p.stat()
    return f"{p.stem}_{st.st_size}_{int(st.st_mtime)}_v{SCHEMA_VERSION}"


def _day(created: str) -> str:
    return created[:10] if created else ""


def analyze_folder(rushes_dir: str | Path, *, out_dir: str | Path | None = None, sample_fps: float = 4.0,
                   limit: int | None = None, force: bool = False) -> Path:
    rushes = Path(rushes_dir)
    if not rushes.is_dir():
        raise SystemExit(f"Dossier de rushs introuvable : {rushes}")
    videos = sorted(p for p in rushes.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXT)
    if limit:
        videos = videos[:limit]
    if not videos:
        raise SystemExit(f"Aucune vidéo dans {rushes}")

    out = Path(out_dir or settings.output_dir) / rushes.name
    cache = Path(settings.cache_dir) / "analysis"
    sheets_dir = out / "contact"
    cache.mkdir(parents=True, exist_ok=True)
    sheets_dir.mkdir(parents=True, exist_ok=True)

    files, overview = [], []
    analysed = 0
    t0 = time.time()
    for n, path in enumerate(videos, 1):
        key = _cache_key(path)
        cjson, cthumb = cache / f"{key}.json", cache / f"{key}.jpg"
        sheet = sheets_dir / f"{path.stem}.jpg"
        tag = "cache"
        if force or not cjson.exists() or not sheet.exists():
            tag = "analyse"
            analysed += 1
            try:
                summary, samples = analyze_video(path, sample_fps)
            except Exception as e:  # une vidéo corrompue ne doit pas bloquer les 400 autres
                print(f"[{n}/{len(videos)}] {path.name} : ERREUR {e}")
                continue
            video_sheet(f"#{n} {path.name}", samples.t, samples.thumbs, sheet)
            if samples.thumbs:
                cv2.imwrite(str(cthumb), samples.thumbs[len(samples.thumbs) // 2])
            cjson.write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
        summary = json.loads(cjson.read_text(encoding="utf-8"))
        summary["index"] = n
        summary["day"] = _day(summary.get("created", ""))
        summary["contact_sheet"] = f"contact/{sheet.name}"
        files.append(summary)
        if cthumb.exists():
            overview.append((n, path.name, cv2.imread(str(cthumb))))
        print(f"[{n}/{len(videos)}] {path.name} ({summary['duration']:.1f}s) : {tag}")

    overview_paths = overview_sheets(overview, out / "overview")

    days: dict[str, list[int]] = {}
    for f in files:
        days.setdefault(f["day"] or "inconnu", []).append(f["index"])

    doc = {
        "schema": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rushes_dir": str(rushes.resolve()),
        "sample_fps": sample_fps,
        "totals": {
            "videos": len(files),
            "duration_s": round(sum(f["duration"] for f in files), 1),
            "days": {d: len(v) for d, v in sorted(days.items())},
        },
        "overview_sheets": [f"overview/{p.name}" for p in overview_paths],
        "legend": {
            "quality": "0-1 : netteté + exposition (netteté relative à la vidéo)",
            "camera": "mouvement de caméra : fixe | lent | rapide",
            "motion": "changement d'image moyen (0 = fixe, >15 = très dynamique)",
            "audio_db": "niveau sonore moyen en dB (pics = cris, rires, voix)",
            "highlights": "fenêtres candidates triées par intérêt (mouvement + son) et qualité",
            "flags": "sombre | surexposé | qualité faible | statique",
        },
        "files": files,
    }
    out_json = out / "rushes.json"
    out_json.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    elapsed = time.time() - t0
    speed = f", {doc['totals']['duration_s'] / elapsed:.1f}x le temps réel" if elapsed > 1 and analysed else ""
    print(f"\n{len(files)} vidéos, {doc['totals']['duration_s'] / 60:.1f} min de rushs, "
          f"analysées en {elapsed:.0f}s (décodage : {decode_mode()}{speed}) -> {out_json}")
    return out_json
