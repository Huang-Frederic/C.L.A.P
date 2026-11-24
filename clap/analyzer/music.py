"""`clap beats` : grille rythmique d'un morceau pour le mode AMV.

Produit beats (s), temps forts (1er temps de chaque mesure, en 4/4), énergie par beat et sections
(calme / montée / drop). Claude raisonne en index de beats ; le builder convertit en microsecondes.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def analyze_music(path: str | Path, out: str | Path | None = None) -> Path:
    import librosa  # import local : dépendance optionnelle (pip install -e ".[analyze]")

    path = Path(path)
    y, sr = librosa.load(str(path), sr=22050, mono=True)
    duration = len(y) / sr

    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, beat_frames = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr, units="frames", trim=False)
    beats = librosa.frames_to_time(beat_frames, sr=sr)
    tempo = float(np.atleast_1d(tempo)[0])

    # énergie par beat (RMS entre deux beats), normalisée 0-1
    rms = librosa.feature.rms(y=y)[0]
    rms_t = librosa.times_like(rms, sr=sr)
    edges = np.append(beats, duration)
    energy = np.array([rms[(rms_t >= a) & (rms_t < b)].mean() if np.any((rms_t >= a) & (rms_t < b)) else 0.0
                       for a, b in zip(edges[:-1], edges[1:])])
    if energy.size:
        energy = (energy - energy.min()) / (np.ptp(energy) + 1e-9)

    # temps forts : phase (0-3) dont les beats ont le plus d'attaque
    strength = onset_env[np.clip(beat_frames, 0, len(onset_env) - 1)] if beat_frames.size else np.zeros(0)
    phase = int(np.argmax([strength[k::4].mean() if strength[k::4].size else 0 for k in range(4)])) if strength.size else 0
    downbeats = list(range(phase, len(beats), 4))

    # sections par mesure : énergie moyenne de chaque mesure (normalisée 0-1), puis 3 niveaux
    sections = []
    if energy.size:
        starts = ([0] if phase else []) + downbeats
        bars = [(a, min(b, len(beats))) for a, b in zip(starts, starts[1:] + [len(beats)]) if b > a]
        bar_e = np.array([energy[a:b].mean() for a, b in bars])
        bar_e = (bar_e - bar_e.min()) / (np.ptp(bar_e) + 1e-9)
        prev_e = None
        for (a, b), e in zip(bars, bar_e):
            lab = "calme" if e < 0.33 else "fort" if e > 0.66 else "moyen"
            jump = prev_e is not None and e - prev_e > 0.35
            if sections and sections[-1]["energy"] == lab and not jump:
                sections[-1]["end_beat"] = b
            else:
                sections.append({"start_beat": a, "end_beat": b, "energy": lab})
                if jump and lab == "fort":
                    sections[-1]["drop"] = True  # passage brutal vers « fort » : le moment du gros plan
            prev_e = e

    doc = {
        "path": str(path.resolve()),
        "duration": round(duration, 3),
        "tempo_bpm": round(tempo, 1),
        "beats": [round(float(b), 3) for b in beats],
        "downbeats": downbeats,
        "beat_energy": [round(float(e), 2) for e in energy],
        "sections": sections,
    }
    out_path = Path(out) if out else path.with_suffix(".beats.json")
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(beats)} beats, {tempo:.0f} BPM, {len(sections)} sections -> {out_path}")
    return out_path
