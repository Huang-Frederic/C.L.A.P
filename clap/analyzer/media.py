"""Accès aux médias via ffmpeg/ffprobe : métadonnées, frames basse résolution, audio mono."""
from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np

from clap.config import settings


@dataclass
class Probe:
    path: Path
    duration: float
    fps: float
    width: int
    height: int
    codec: str
    has_audio: bool
    created: str        # ISO 8601 (creation_time des métadonnées), "" si absent
    device: str         # ex. "DJI OsmoPocket3"


def _run(cmd: list[str]) -> bytes:
    return subprocess.run(cmd, check=True, capture_output=True).stdout


def probe(path: Path) -> Probe:
    out = json.loads(_run([
        settings.ffprobe, "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]))
    fmt = out.get("format", {})
    tags = {k.lower(): v for k, v in fmt.get("tags", {}).items()}
    streams = out.get("streams", [])
    # Le premier flux vidéo est le vrai ; DJI ajoute un flux MJPEG de couverture qu'on ignore.
    video = next((s for s in streams if s.get("codec_type") == "video"
                  and s.get("disposition", {}).get("attached_pic", 0) == 0), None)
    if video is None:
        raise ValueError("aucun flux vidéo (enregistrement probablement interrompu)")
    num, den = (video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1").split("/")
    fps = float(num) / float(den) if float(den) else 0.0
    return Probe(
        path=path,
        duration=float(fmt.get("duration") or video.get("duration") or 0.0),
        fps=round(fps, 3),
        width=int(video.get("width", 0)),
        height=int(video.get("height", 0)),
        codec=video.get("codec_name", ""),
        has_audio=any(s.get("codec_type") == "audio" for s in streams),
        created=tags.get("creation_time", ""),
        device=tags.get("encoder", ""),
    )


def _frame_cmd(path: Path, sample_fps: float, width: int, height: int, hwaccel: str) -> list[str]:
    cmd = [settings.ffmpeg, "-v", "error"]
    if hwaccel == "cuda":
        # tout reste sur la carte graphique jusqu'à la miniature : décodage 4K HEVC très rapide
        cmd += ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda", "-i", str(path),
                "-map", "0:v:0", "-an", "-sn", "-dn",
                "-vf", f"fps={sample_fps},scale_cuda={width}:{height}:format=nv12,hwdownload,format=nv12"]
    else:
        if hwaccel and hwaccel != "none":
            cmd += ["-hwaccel", hwaccel]
        cmd += ["-i", str(path), "-map", "0:v:0", "-an", "-sn", "-dn",
                "-vf", f"fps={sample_fps},scale={width}:{height}:flags=area"]
    return cmd + ["-f", "rawvideo", "-pix_fmt", "bgr24", "-"]


_decode_mode: str | None = None  # mode qui a marché sur la 1re vidéo, réutilisé ensuite


def decode_mode() -> str:
    if _decode_mode is None:
        return "cache"
    return "logiciel" if _decode_mode == "none" else f"matériel {_decode_mode}"


def iter_frames(path: Path, sample_fps: float, width: int) -> Iterator[tuple[float, np.ndarray]]:
    """Décode la vidéo à `sample_fps` images/s, redimensionnée à `width` px de large (BGR).

    Essaie d'abord le décodage matériel (CLAP_HWACCEL) ; s'il ne produit rien, repasse en logiciel
    et le signale une fois avec la raison donnée par ffmpeg.
    """
    global _decode_mode
    p = probe(path)
    height = int(round(p.height * width / p.width / 2) * 2)
    frame_bytes = width * height * 3
    if _decode_mode:
        modes = [_decode_mode]
    elif settings.hwaccel in ("", "none"):
        modes = ["none"]
    elif settings.hwaccel == "auto":
        # cuda d'abord : réduction des images sur la carte graphique (de loin le plus rapide)
        modes = ["cuda", "auto", "none"]
    else:
        modes = [settings.hwaccel, "none"]
    for mode in modes:
        err_file = tempfile.TemporaryFile()
        proc = subprocess.Popen(_frame_cmd(path, sample_fps, width, height, mode),
                                stdout=subprocess.PIPE, stderr=err_file)
        i = 0
        try:
            while True:
                buf = proc.stdout.read(frame_bytes)  # type: ignore[union-attr]
                if len(buf) < frame_bytes:
                    break
                yield i / sample_fps, np.frombuffer(buf, np.uint8).reshape(height, width, 3)
                i += 1
        finally:
            proc.kill()
            proc.wait()
        if i:
            if _decode_mode is None:
                _decode_mode = mode
                label = "logiciel (processeur)" if mode == "none" else f"matériel ({mode})"
                print(f"  -> décodage vidéo : {label}")
            err_file.close()
            return
        err_file.seek(0)
        reason = err_file.read().decode("utf-8", "replace").strip().splitlines()
        err_file.close()
        if mode != "none":
            print(f"  !! décodage {mode} indisponible, essai du mode suivant. ffmpeg dit :")
            for line in reason[-4:]:
                print(f"     {line}")


def read_audio(path: Path, sr: int = 16000) -> np.ndarray:
    """Audio mono float32 dans [-1, 1]. Tableau vide si pas de piste audio."""
    try:
        raw = _run([settings.ffmpeg, "-v", "error", "-i", str(path), "-map", "0:a:0",
                    "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"])
    except subprocess.CalledProcessError:
        return np.zeros(0, np.float32)
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
