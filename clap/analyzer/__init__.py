"""Analyseur : dossier de rushs -> rushes.json + planches contact (aucun LLM ici).

Prévu :
  - métadonnées (ffprobe) : durée, fps, date, GPS, télémétrie GoPro/DJI
  - découpage en plans (PySceneDetect)
  - qualité par plan : flou, secousses, exposition (OpenCV)
  - intensité de mouvement, pics audio
  - transcription horodatée (faster-whisper)
  - planches contact avec timecodes incrustés, pour que Claude "voie" les rushs
  - grille rythmique de la musique (librosa) pour le mode AMV
"""
