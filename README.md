# C.L.A.P — Claude-Led Automated Production

Un dossier de rushs en entrée, un projet CapCut monté en sortie.
C.L.A.P analyse les vidéos, Claude joue le réalisateur, et le résultat arrive sous forme de brouillon CapCut qu'on peut encore retoucher à la main.

## Les trois modes

| Mode | Ce que fait Claude | Calage du temps |
|---|---|---|
| **Vlog** | Raconte une histoire (par jour, par lieu), garde les moments de parole | Coupes sur les phrases et les silences |
| **Clips** | Sélectionne des temps forts autonomes, en 9:16 pour TikTok | Durée cible de 15 à 40 s |
| **AMV** | Associe l'énergie des plans à celle de la musique | Coupes exactement sur les beats |

## Architecture

```
rushs/ ──► [1. Analyseur] ──► rushes.json + planches contact
                                   │
                                   ▼
                          [2. Claude, le réalisateur] ──► edl.json
                                   │
                                   ▼
                          [3. Builder CapCut] ──► brouillon CapCut éditable
```

Le principe : **Claude choisit, le code calcule.** Claude ne donne jamais de timecode à la frame près. En mode AMV, il raisonne en index de beats (« ce plan du beat 64 au beat 68 »), et le builder convertit ça en microsecondes à partir de la grille calculée par l'analyseur.

Le format de l'EDL est décrit dans [`schemas/edl.schema.json`](schemas/edl.schema.json), avec un exemple dans [`examples/amv_example.json`](examples/amv_example.json).

## Installation (Windows)

Prérequis : Python 3.11+ et ffmpeg dans le PATH (`winget install Gyan.FFmpeg`).

```powershell
pip install -e ".[analyze]"
copy clap.example.toml clap.toml   # puis adapte les chemins
```

Configuration :
- **`clap.toml`** contient les chemins (brouillons CapCut, rushs, sorties) et les réglages (décodage, Whisper, modèle Claude). Il n'est pas versionné, et `clap.example.toml` sert de modèle.
- **`.env`** ne sert qu'aux secrets (`ANTHROPIC_API_KEY`, pour le futur mode automatique via l'API).
- **Une variable d'environnement** remplace ponctuellement un réglage, par exemple `$env:CLAP_HWACCEL="none"; clap analyze`.

## Utilisation

```powershell
# 1. Vérifier que ta version de CapCut accepte les brouillons générés
clap smoke-test                     # utilise [paths] rushes_dir de clap.toml
clap smoke-test "D:\autre\dossier"  # ou un dossier précis

# 2. Analyser un dossier de rushs -> output/<dossier>/rushes.json + planches contact
clap analyze --limit 20                # pour tester sur 20 vidéos
clap analyze                           # tout le dossier (reprend là où il s'est arrêté)

# 3. Grille rythmique d'une musique (mode AMV)
clap beats D:\musique\track.mp3       # -> track.beats.json

# 4. Transformer une EDL en brouillon CapCut
clap build examples/amv_example.json   # écrit dans [capcut] drafts_dir
```

### Ce que produit `clap analyze`

```
output/ski_huang_2026/
  rushes.json          # le dossier de rushs que Claude lit
  overview/            # une miniature par vidéo, numérotée, 30 par planche
  contact/             # une planche par vidéo, 12 miniatures horodatées
```

Pour chaque vidéo : durée, date et jour, orientation (horizontale/verticale), plans avec qualité (netteté + exposition), mouvement, mouvement de caméra (fixe/lent/rapide), niveau sonore, alertes (sombre, surexposé…), et jusqu'à 3 **temps forts** candidats avec leur raison (« beaucoup de mouvement », « pic sonore », « image propre »).

L'analyse se fait sur des miniatures 320 px à 4 images/s. Avec `hwaccel = 'auto'` ou `'cuda'`, le décodage de la 4K HEVC passe par la carte graphique ; si ça échoue, C.L.A.P repasse automatiquement en décodage logiciel. Chaque vidéo analysée est mise en cache : on peut interrompre et relancer sans tout refaire.

### Ce que produit `clap beats`

Le tempo, les beats (en secondes), les temps forts de chaque mesure, l'énergie de chaque beat et les sections du morceau (calme / moyen / fort, avec les **drops** marqués). Dans l'EDL, `"music": {"beats_file": "track.beats.json"}` suffit : Claude place les plans par index de beat (`beat_start` / `beat_end`).

Le dossier des brouillons (`[capcut] drafts_dir`) se trouve dans CapCut, à **Paramètres > Emplacement des brouillons**. `--drafts` permet de le remplacer ponctuellement. Après un build, ferme puis rouvre CapCut pour voir le nouveau brouillon.

## Feuille de route

- [x] Format EDL et builder CapCut (pyCapCut)
- [x] Analyseur : plans, qualité, mouvement, audio, temps forts, planches contact
- [x] Grille rythmique de la musique pour le mode AMV
- [ ] Transcription horodatée (Whisper) pour le mode Vlog
- [ ] Recherche de plans par description (CLIP)
- [ ] Prompts « réalisateur » pour Vlog, Clips et AMV
- [ ] Serveur MCP, pour l'utiliser depuis Claude Desktop ou Claude Code
- [ ] Recadrage intelligent 16:9 → 9:16, sous-titres
- [ ] Plan B : export vers DaVinci Resolve (FCPXML/OTIO)
