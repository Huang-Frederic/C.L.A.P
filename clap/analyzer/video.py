"""Analyse d'une vidéo : métriques par échantillon, découpage en plans, temps forts.

Toutes les métriques sont calculées sur des frames basse résolution (320 px) :
  - sharp   : netteté (variance du laplacien) — la neige est peu texturée, donc on compare
              surtout au sein d'une même vidéo ;
  - bright  : luminosité moyenne 0-255 ;
  - hi/lo   : part des pixels cramés (>250) / bouchés (<5) ;
  - motion  : changement d'image entre deux échantillons (contenu + caméra) ;
  - cam     : vitesse de la caméra (déplacement global du décor, px/échantillon) :
              fixe / lent / rapide — un panoramique rapide est utile en AMV, un plan fixe en vlog ;
  - audio   : niveau sonore en dB.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from clap.analyzer.media import Probe, iter_frames, probe, read_audio

ANALYSIS_WIDTH = 320
CAM_SLOW_PX, CAM_FAST_PX = 3.0, 15.0  # seuils de vitesse caméra (px sur 320 px, entre deux échantillons)


@dataclass
class Samples:
    t: np.ndarray
    sharp: np.ndarray
    bright: np.ndarray
    clip_hi: np.ndarray
    clip_lo: np.ndarray
    motion: np.ndarray
    cam: np.ndarray
    hist_diff: np.ndarray
    audio_db: np.ndarray
    thumbs: list[np.ndarray] = field(default_factory=list)


def _sample(path: Path, sample_fps: float) -> Samples:
    t, sharp, bright, chi, clo, motion, shift, hdiff, thumbs = [], [], [], [], [], [], [], [], []
    prev_gray, prev_hist = None, None
    for ts, frame in iter_frames(path, sample_fps, ANALYSIS_WIDTH):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [16, 8], [0, 180, 0, 256])
        cv2.normalize(hist, hist)

        t.append(ts)
        sharp.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
        bright.append(float(gray.mean()))
        chi.append(float((gray > 250).mean()))
        clo.append(float((gray < 5).mean()))
        if prev_gray is None:
            motion.append(0.0)
            shift.append((0.0, 0.0))
            hdiff.append(0.0)
        else:
            motion.append(float(cv2.absdiff(cv2.GaussianBlur(gray, (5, 5), 0),
                                            cv2.GaussianBlur(prev_gray, (5, 5), 0)).mean()))
            shift.append(_camera_shift(prev_gray, gray))
            hdiff.append(float(1.0 - cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL)))
        prev_gray, prev_hist = gray, hist
        thumbs.append(frame)

    cam = np.linalg.norm(np.array(shift, np.float32).reshape(-1, 2), axis=1)

    ta = np.array(t, np.float32)
    return Samples(
        t=ta, sharp=np.array(sharp), bright=np.array(bright),
        clip_hi=np.array(chi), clip_lo=np.array(clo),
        motion=np.array(motion), cam=cam, hist_diff=np.array(hdiff),
        audio_db=_audio_levels(path, ta, sample_fps), thumbs=thumbs,
    )


def _camera_shift(prev: np.ndarray, cur: np.ndarray) -> tuple[float, float]:
    """Déplacement global de la caméra entre deux images (px).

    Points suivis par flot optique + RANSAC : les personnes qui bougent sont des valeurs
    aberrantes, seul le mouvement du décor (donc de la caméra) est retenu.
    """
    pts = cv2.goodFeaturesToTrack(prev, maxCorners=200, qualityLevel=0.01, minDistance=8)
    if pts is None or len(pts) < 8:
        return 0.0, 0.0
    nxt, st, _ = cv2.calcOpticalFlowPyrLK(prev, cur, pts, None, winSize=(21, 21), maxLevel=3)
    ok = st.reshape(-1) == 1
    if ok.sum() < 8:
        return 0.0, 0.0
    m, _ = cv2.estimateAffinePartial2D(pts[ok], nxt[ok], method=cv2.RANSAC, ransacReprojThreshold=2.0)
    if m is None:
        return 0.0, 0.0
    return float(m[0, 2]), float(m[1, 2])


def _audio_levels(path: Path, t: np.ndarray, sample_fps: float) -> np.ndarray:
    audio = read_audio(path)
    if audio.size == 0 or t.size == 0:
        return np.full(t.shape, -90.0, np.float32)
    sr = 16000
    half = int(sr / sample_fps / 2)
    out = np.empty(t.shape, np.float32)
    for i, ts in enumerate(t):
        c = int(ts * sr + sr / sample_fps / 2)
        w = audio[max(0, c - half): c + half]
        rms = float(np.sqrt(np.mean(w ** 2))) if w.size else 0.0
        out[i] = 20 * np.log10(max(rms, 1e-5))
    return out


def _shots(s: Samples, duration: float, min_len: float = 1.0) -> list[tuple[float, float]]:
    """Découpe en plans : coupure quand l'histogramme de couleurs change brutalement."""
    if s.t.size == 0:
        return [(0.0, duration)]
    thr = max(0.35, float(np.median(s.hist_diff) + 6 * np.std(s.hist_diff)))
    cuts = [0.0]
    for ts, d in zip(s.t, s.hist_diff):
        if d > thr and ts - cuts[-1] >= min_len:
            cuts.append(float(ts))
    cuts.append(duration)
    return [(a, b) for a, b in zip(cuts, cuts[1:]) if b - a > 0.05]


def _rank01(x: np.ndarray) -> np.ndarray:
    """Normalisation robuste dans [0, 1] (percentiles 5-95)."""
    if x.size == 0:
        return x
    lo, hi = np.percentile(x, 5), np.percentile(x, 95)
    return np.clip((x - lo) / (hi - lo + 1e-6), 0, 1)


def _scores(s: Samples) -> tuple[np.ndarray, np.ndarray]:
    """(qualité, intérêt) par échantillon, dans [0, 1]."""
    exposure_ok = 1.0 - np.clip(np.maximum(40 - s.bright, s.bright - 225) / 40, 0, 1)
    exposure_ok *= 1.0 - np.clip((s.clip_hi + s.clip_lo) / 0.3, 0, 1)
    sharp = _rank01(np.log1p(s.sharp))
    quality = np.clip(0.55 * sharp + 0.45 * exposure_ok, 0, 1)

    loud = np.clip((s.audio_db - np.median(s.audio_db)) / 15.0, 0, 1)
    motion = np.clip(s.motion / 25.0, 0, 1)
    interest = np.clip(0.6 * motion + 0.4 * loud, 0, 1)
    return quality, interest


def _highlights(s: Samples, quality: np.ndarray, interest: np.ndarray, sample_fps: float,
                max_n: int = 3, min_len: float = 1.5, max_len: float = 6.0) -> list[dict]:
    """Fenêtres les plus intéressantes parmi celles de qualité correcte."""
    if s.t.size < 3:
        return []
    score = interest * (0.4 + 0.6 * quality)
    win = max(1, int(round(min_len * sample_fps)))
    smooth = np.convolve(score, np.ones(win) / win, mode="same")
    taken = np.zeros_like(smooth, bool)
    out = []
    for idx in np.argsort(smooth)[::-1]:
        if len(out) >= max_n or smooth[idx] < 0.25:
            break
        if taken[idx]:
            continue
        # étend autour du pic tant que le score reste au-dessus de 60 % du pic
        lo = hi = int(idx)
        limit = int(max_len * sample_fps)
        while lo > 0 and not taken[lo - 1] and smooth[lo - 1] >= 0.6 * smooth[idx] and hi - lo < limit:
            lo -= 1
        while hi < len(smooth) - 1 and not taken[hi + 1] and smooth[hi + 1] >= 0.6 * smooth[idx] and hi - lo < limit:
            hi += 1
        start, end = float(s.t[lo]), float(s.t[hi]) + 1 / sample_fps
        if end - start < min_len:
            continue
        taken[max(0, lo - win): hi + win + 1] = True
        why = []
        if s.motion[lo:hi + 1].mean() > 12:
            why.append("beaucoup de mouvement")
        if (s.audio_db[lo:hi + 1].max() - np.median(s.audio_db)) > 10:
            why.append("pic sonore")
        if quality[lo:hi + 1].mean() > 0.7:
            why.append("image propre")
        out.append({"start": round(start, 2), "end": round(end, 2),
                    "score": round(float(smooth[idx]), 2), "why": why})
    return sorted(out, key=lambda h: h["start"])


def _camera(cam: np.ndarray) -> str:
    if cam.size == 0:
        return "fixe"
    v = float(np.median(cam))
    return "fixe" if v < CAM_SLOW_PX else "lent" if v < CAM_FAST_PX else "rapide"


def _flags(s: Samples, a: int, b: int, quality: np.ndarray) -> list[str]:
    f = []
    if s.bright[a:b].mean() < 35 or s.clip_lo[a:b].mean() > 0.25:
        f.append("sombre")
    elif s.bright[a:b].mean() > 220 or s.clip_hi[a:b].mean() > 0.25:
        f.append("surexposé")
    if quality[a:b].mean() < 0.35:
        f.append("qualité faible")
    if s.motion[a:b].mean() < 1.5:
        f.append("statique")
    return f


def analyze_video(path: Path, sample_fps: float = 4.0) -> tuple[dict, Samples]:
    """Renvoie (résumé JSON-sérialisable pour Claude, échantillons bruts pour les planches)."""
    p: Probe = probe(path)
    s = _sample(path, sample_fps)
    quality, interest = _scores(s)

    shots = []
    for i, (a, b) in enumerate(_shots(s, p.duration)):
        ia = int(np.searchsorted(s.t, a))
        ib = max(ia + 1, int(np.searchsorted(s.t, b)))
        shots.append({
            "id": i,
            "start": round(a, 2),
            "end": round(b, 2),
            "quality": round(float(quality[ia:ib].mean()), 2) if s.t.size else None,
            "motion": round(float(s.motion[ia:ib].mean()), 1) if s.t.size else None,
            "camera": _camera(s.cam[ia + 1:ib]) if s.t.size else None,
            "audio_db": round(float(s.audio_db[ia:ib].mean()), 1) if s.t.size else None,
            "flags": _flags(s, ia, ib, quality) if s.t.size else [],
        })

    summary = {
        "file": path.name,
        "duration": round(p.duration, 2),
        "fps": p.fps,
        "resolution": f"{p.width}x{p.height}",
        "orientation": "vertical" if p.height > p.width else "horizontal",
        "created": p.created,
        "device": p.device,
        "has_audio": p.has_audio,
        "quality": round(float(quality.mean()), 2) if s.t.size else None,
        "shots": shots,
        "highlights": _highlights(s, quality, interest, sample_fps),
    }
    return summary, s
