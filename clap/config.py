"""Configuration de C.L.A.P.

Ordre de priorité, du plus fort au plus faible :
  1. variables d'environnement du terminal (CLAP_HWACCEL=none clap analyze …), pour un essai ponctuel ;
  2. clap.toml à la racine du repo (réglages et chemins, non versionné — modèle : clap.example.toml) ;
  3. valeurs par défaut ci-dessous.

Le fichier .env ne sert qu'aux secrets (ANTHROPIC_API_KEY) : il n'est jamais lu pour le reste.
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = Path(os.getenv("CLAP_CONFIG", ROOT / "clap.toml"))

# (section toml, clé toml, variable d'environnement, défaut)
_FIELDS = {
    "capcut_drafts_dir": ("capcut", "drafts_dir", "CAPCUT_DRAFTS_DIR", ""),
    "rushes_dir": ("paths", "rushes_dir", "CLAP_RUSHES_DIR", ""),
    "output_dir": ("paths", "output_dir", "CLAP_OUTPUT_DIR", "output"),
    "cache_dir": ("paths", "cache_dir", "CLAP_CACHE_DIR", "cache"),
    "ffmpeg": ("analyze", "ffmpeg", "CLAP_FFMPEG", "ffmpeg"),
    "ffprobe": ("analyze", "ffprobe", "CLAP_FFPROBE", "ffprobe"),
    "hwaccel": ("analyze", "hwaccel", "CLAP_HWACCEL", "auto"),
    "whisper_model": ("analyze", "whisper_model", "CLAP_WHISPER_MODEL", "small"),
    "device": ("analyze", "device", "CLAP_DEVICE", "cuda"),
    "claude_model": ("claude", "model", "CLAP_CLAUDE_MODEL", "claude-haiku-5-5"),
}
_PATHS = {"capcut_drafts_dir", "rushes_dir", "output_dir", "cache_dir"}


def _expand(value: str) -> str:
    return os.path.expandvars(os.path.expanduser(value)) if value else ""


def _load_toml() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    with CONFIG_FILE.open("rb") as f:
        return tomllib.load(f)


@dataclass(frozen=True)
class Settings:
    capcut_drafts_dir: str
    rushes_dir: str
    output_dir: str
    cache_dir: str
    ffmpeg: str
    ffprobe: str
    hwaccel: str
    whisper_model: str
    device: str
    claude_model: str
    anthropic_api_key: str

    @classmethod
    def load(cls) -> "Settings":
        toml = _load_toml()
        values = {}
        for name, (section, key, env, default) in _FIELDS.items():
            raw = os.environ.get(env) or str(toml.get(section, {}).get(key, "")) or default
            if name in _PATHS:
                raw = _expand(raw)
                # chemins relatifs (output, cache) : par rapport à la racine du repo
                if raw and not Path(raw).is_absolute():
                    raw = str(ROOT / raw)
            values[name] = raw
        secrets = dotenv_values(ROOT / ".env")
        values["anthropic_api_key"] = os.environ.get("ANTHROPIC_API_KEY") or secrets.get("ANTHROPIC_API_KEY") or ""
        return cls(**values)

    def require_drafts_dir(self, override: str | None = None) -> str:
        path = override or self.capcut_drafts_dir
        if not path:
            raise SystemExit(f"Dossier des brouillons CapCut inconnu : renseigne [capcut] drafts_dir "
                             f"dans {CONFIG_FILE.name} ou passe --drafts.")
        p = Path(path)
        if not p.is_dir():
            existing = next((a for a in p.parents if a.is_dir()), None)
            hint = f" (le dernier dossier existant sur ce chemin est {existing})" if existing else ""
            raise SystemExit(f"Dossier des brouillons CapCut introuvable : {path}{hint}")
        return path


settings = Settings.load()
