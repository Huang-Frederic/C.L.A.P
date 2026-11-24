"""Configuration de C.L.A.P, lue depuis le fichier .env (voir .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# .env à la racine du repo, puis celui du dossier courant (le second ne remplace pas le premier)
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")
load_dotenv()


def _expand(value: str) -> str:
    return os.path.expandvars(os.path.expanduser(value)) if value else ""


@dataclass(frozen=True)
class Settings:
    capcut_drafts_dir: str = _expand(os.getenv("CAPCUT_DRAFTS_DIR", ""))
    rushes_dir: str = _expand(os.getenv("CLAP_RUSHES_DIR", ""))
    output_dir: str = _expand(os.getenv("CLAP_OUTPUT_DIR", "output"))
    cache_dir: str = _expand(os.getenv("CLAP_CACHE_DIR", "cache"))

    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    claude_model: str = os.getenv("CLAP_CLAUDE_MODEL", "claude-haiku-5-5")

    whisper_model: str = os.getenv("CLAP_WHISPER_MODEL", "small")
    device: str = os.getenv("CLAP_DEVICE", "cuda")

    def require_drafts_dir(self, override: str | None = None) -> str:
        path = override or self.capcut_drafts_dir
        if not path:
            raise SystemExit("Dossier des brouillons CapCut inconnu : renseigne CAPCUT_DRAFTS_DIR "
                             "dans .env ou passe --drafts.")
        if not Path(path).is_dir():
            raise SystemExit(f"Dossier des brouillons CapCut introuvable : {path}")
        return path


settings = Settings()
