"""Builder CapCut : transforme une EDL en brouillon CapCut éditable (via pyCapCut).

Le brouillon s'ouvre dans CapCut Windows, où chaque piste reste modifiable à la main.
"""
from __future__ import annotations

from pathlib import Path

import pycapcut as cc
from pycapcut import Timerange

from clap.edl import EDL, US, EDLError

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".m4v"}


def build_draft(edl: EDL, drafts_dir: str | Path, *, replace: bool = True) -> Path:
    folder = cc.DraftFolder(str(drafts_dir))
    script = folder.create_draft(edl.title, edl.width, edl.height, fps=edl.fps, allow_replace=replace)

    script.add_track(cc.TrackType.video)
    materials: dict[Path, cc.VideoMaterial] = {}

    for i, (cut, start, dur) in enumerate(edl.timeline()):
        path = edl.resolve_path(cut.clip)
        if not path.exists():
            raise EDLError(f"cut #{i}: rush introuvable : {path}")
        mat = materials.get(path) or materials.setdefault(path, cc.VideoMaterial(str(path)))

        src_start = round(cut.src_in * US)
        src_dur = round(dur * cut.speed)
        if src_start + src_dur > mat.duration:
            raise EDLError(
                f"cut #{i}: {path.name} dure {mat.duration / US:.2f}s, "
                f"impossible de lire {cut.src_in:.2f}s + {src_dur / US:.2f}s"
            )
        script.add_segment(cc.VideoSegment(
            mat,
            Timerange(start, dur),
            source_timerange=Timerange(src_start, src_dur),
            volume=0.0 if edl.music and edl.mode == "amv" else cut.volume,
        ))

    if edl.music:
        music = Path(edl.music.path)
        if not music.is_absolute() and edl.rushes_dir:
            music = Path(edl.rushes_dir) / music
        amat = cc.AudioMaterial(str(music))
        total = min(edl.total_us, amat.duration - round(edl.music.offset * US))
        script.add_track(cc.TrackType.audio)
        script.add_segment(cc.AudioSegment(
            amat,
            Timerange(0, total),
            source_timerange=Timerange(round(edl.music.offset * US), total),
            volume=edl.music.volume,
        ))

    if edl.texts:
        script.add_track(cc.TrackType.text)
        for t in edl.texts:
            script.add_segment(cc.TextSegment(t.text, Timerange(round(t.start * US), round(t.duration * US))))

    script.save()
    return Path(drafts_dir) / edl.title


def smoke_test(drafts_dir: str | Path, videos_dir: str | Path, n_clips: int = 3, clip_len: float = 3.0) -> Path:
    """Vérifie que ta version de CapCut accepte un brouillon écrit par script."""
    videos = sorted(p for p in Path(videos_dir).iterdir() if p.suffix.lower() in VIDEO_EXT)[:n_clips]
    if not videos:
        raise SystemExit(f"Aucune vidéo trouvée dans {videos_dir}")

    cuts = []
    for v in videos:
        dur = cc.VideoMaterial(str(v)).duration / US
        length = min(clip_len, dur)
        cuts.append({"clip": str(v), "src_in": max(0.0, (dur - length) / 2), "duration": length})

    edl = EDL.from_dict({
        "mode": "clips",
        "title": "CLAP_SMOKE_TEST",
        "cuts": cuts,
        "texts": [{"text": "C.L.A.P ✔", "start": 0, "duration": sum(c["duration"] for c in cuts)}],
    })
    return build_draft(edl, drafts_dir)
