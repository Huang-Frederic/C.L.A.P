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

```powershell
pip install -e .
copy .env.example .env   # puis adapte les chemins
```

Le `.env` contient tes chemins (brouillons CapCut, rushs) et réglages (modèle Whisper, GPU, clé API optionnelle). Il n'est jamais commité ; `.env.example` sert de modèle.

## Utilisation

```powershell
# 1. Vérifier que ta version de CapCut accepte les brouillons générés
clap smoke-test                     # utilise CLAP_RUSHES_DIR du .env
clap smoke-test "D:\autre\dossier"  # ou un dossier précis

# 2. Transformer une EDL en brouillon CapCut
clap build examples/amv_example.json   # écrit dans CAPCUT_DRAFTS_DIR
```

Le dossier des brouillons (`CAPCUT_DRAFTS_DIR`) se trouve dans CapCut, à **Paramètres > Emplacement des brouillons**. `--drafts` permet de le remplacer ponctuellement. Après un build, ferme puis rouvre CapCut pour voir le nouveau brouillon.

## Feuille de route

- [x] Format EDL et builder CapCut (pyCapCut)
- [ ] Analyseur : plans, qualité, mouvement, audio, transcription, planches contact
- [ ] Grille rythmique de la musique pour le mode AMV
- [ ] Prompts « réalisateur » pour Vlog, Clips et AMV
- [ ] Serveur MCP, pour l'utiliser depuis Claude Desktop ou Claude Code
- [ ] Recadrage intelligent 16:9 → 9:16, sous-titres
- [ ] Plan B : export vers DaVinci Resolve (FCPXML/OTIO)
