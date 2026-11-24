"""Analyseur : dossier de rushs -> rushes.json + planches contact (aucun LLM ici).

  - media.py  : ffprobe / décodage basse résolution (CUDA si dispo) / audio mono
  - video.py  : métriques par échantillon, plans, temps forts
  - sheets.py : planches contact horodatées et vues d'ensemble
  - run.py    : `clap analyze`, avec cache pour reprendre là où on s'est arrêté
  - music.py  : `clap beats`, grille rythmique pour le mode AMV

À venir : transcription horodatée (faster-whisper), recherche de plans par description (CLIP).
"""
