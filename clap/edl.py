"""
EDL (Edit Decision List) de C.L.A.P : le contrat entre Claude (le réalisateur) et le builder.

Claude choisit QUOI montrer ; ce module calcule QUAND, au microseconde près.
Deux façons de placer un plan :
  - en secondes : `duration` (les plans s'enchaînent dans l'ordre de la liste) ;
  - en beats    : `beat_start` / `beat_end`, convertis via `music.beats` (mode AMV).

Le format complet est décrit dans schemas/edl.schema.json.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

US = 1_000_000  # CapCut travaille en microsecondes

MODES = {"vlog", "clips", "amv"}


class EDLError(ValueError):
    pass


@dataclass
class Cut:
    clip: str
    src_in: float = 0.0
    duration: float | None = None
    beat_start: int | None = None
    beat_end: int | None = None
    speed: float = 1.0
    volume: float = 1.0
    note: str = ""


@dataclass
class Text:
    text: str
    start: float
    duration: float


@dataclass
class Music:
    path: str = ""
    beats: list[float] = field(default_factory=list)
    offset: float = 0.0   # où commencer dans le morceau (s)
    volume: float = 1.0
    beats_file: str = ""  # sortie de `clap beats` : fournit path + beats si absents

    def __post_init__(self) -> None:
        if self.beats_file:
            grid = json.loads(Path(self.beats_file).read_text(encoding="utf-8"))
            self.path = self.path or grid["path"]
            self.beats = self.beats or grid["beats"]
        if not self.path:
            raise EDLError("music : il faut path ou beats_file")


@dataclass
class EDL:
    mode: str
    title: str
    width: int = 1080
    height: int = 1920
    fps: int = 30
    rushes_dir: str = ""
    music: Music | None = None
    cuts: list[Cut] = field(default_factory=list)
    texts: list[Text] = field(default_factory=list)

    # ---------- chargement ----------
    @classmethod
    def load(cls, path: str | Path) -> "EDL":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, d: dict) -> "EDL":
        mode = d.get("mode")
        if mode not in MODES:
            raise EDLError(f"mode doit être l'un de {sorted(MODES)}, reçu {mode!r}")
        canvas = d.get("canvas", {})
        music = Music(**d["music"]) if d.get("music") else None
        edl = cls(
            mode=mode,
            title=d.get("title", f"CLAP_{mode}"),
            width=canvas.get("width", 1080),
            height=canvas.get("height", 1920),
            fps=canvas.get("fps", 30),
            rushes_dir=d.get("rushes_dir", ""),
            music=music,
            cuts=[Cut(**c) for c in d.get("cuts", [])],
            texts=[Text(**t) for t in d.get("texts", [])],
        )
        edl.validate()
        return edl

    # ---------- validation ----------
    def validate(self) -> None:
        if not self.cuts:
            raise EDLError("l'EDL ne contient aucun plan (cuts)")
        for i, c in enumerate(self.cuts):
            by_beat = c.beat_start is not None or c.beat_end is not None
            if by_beat:
                if c.beat_start is None or c.beat_end is None:
                    raise EDLError(f"cut #{i}: beat_start et beat_end vont ensemble")
                if not self.music or not self.music.beats:
                    raise EDLError(f"cut #{i}: placé en beats mais music.beats est vide")
                if not (0 <= c.beat_start < c.beat_end < len(self.music.beats)):
                    raise EDLError(f"cut #{i}: beats {c.beat_start}->{c.beat_end} hors de la grille "
                                   f"(0..{len(self.music.beats) - 1})")
            elif c.duration is None or c.duration <= 0:
                raise EDLError(f"cut #{i}: il faut soit duration > 0, soit beat_start/beat_end")
            if c.speed <= 0:
                raise EDLError(f"cut #{i}: speed doit être > 0")

    # ---------- placement ----------
    def resolve_path(self, clip: str) -> Path:
        p = Path(clip)
        return p if p.is_absolute() or not self.rushes_dir else Path(self.rushes_dir) / p

    def timeline(self) -> list[tuple[Cut, int, int]]:
        """Renvoie [(cut, start_us, duration_us)] sur la timeline finale.

        Les plans en secondes s'enchaînent ; un plan en beats est posé exactement sur sa grille
        (et le suivant en secondes repart de sa fin).
        """
        out: list[tuple[Cut, int, int]] = []
        cursor = 0
        for c in self.cuts:
            if c.beat_start is not None:
                beats = self.music.beats  # type: ignore[union-attr]
                start = round((beats[c.beat_start] - self.music.offset) * US)  # type: ignore[union-attr]
                dur = round((beats[c.beat_end] - beats[c.beat_start]) * US)
                end = start + dur
                if start < 50_000:  # beat à moins de 50 ms du début : on colle le plan à 0
                    start = 0
                dur = end - max(start, 0)
                start = max(start, 0)
            else:
                start = cursor
                dur = round(c.duration * US)  # type: ignore[operator]
            out.append((c, start, dur))
            cursor = start + dur
        return out

    @property
    def total_us(self) -> int:
        tl = self.timeline()
        return max(s + d for _, s, d in tl)
