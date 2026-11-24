"""Planches contact : ce que Claude regarde pour « voir » les rushs sans recevoir la vidéo.

  - planche par vidéo   : jusqu'à 12 miniatures horodatées ;
  - planches d'ensemble : une miniature par vidéo, numérotée, 30 vidéos par planche.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

FONT = cv2.FONT_HERSHEY_SIMPLEX


def _label(img: np.ndarray, text: str, *, top: bool = False) -> np.ndarray:
    img = img.copy()
    h, w = img.shape[:2]
    (tw, th), _ = cv2.getTextSize(text, FONT, 0.5, 1)
    y0 = 0 if top else h - th - 8
    cv2.rectangle(img, (0, y0), (min(w, tw + 8), y0 + th + 8), (0, 0, 0), -1)
    cv2.putText(img, text, (4, y0 + th + 3), FONT, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    return img


def _fit(img: np.ndarray, box: tuple[int, int]) -> np.ndarray:
    """Place l'image dans une case de taille fixe sans la déformer (bandes noires)."""
    bw, bh = box
    h, w = img.shape[:2]
    k = min(bw / w, bh / h)
    small = cv2.resize(img, (max(1, int(w * k)), max(1, int(h * k))), interpolation=cv2.INTER_AREA)
    out = np.zeros((bh, bw, 3), np.uint8)
    y, x = (bh - small.shape[0]) // 2, (bw - small.shape[1]) // 2
    out[y:y + small.shape[0], x:x + small.shape[1]] = small
    return out


def _grid(tiles: list[np.ndarray], cols: int, header: str) -> np.ndarray:
    h, w = tiles[0].shape[:2]
    rows = (len(tiles) + cols - 1) // cols
    pad, head = 4, 28
    sheet = np.full((head + rows * (h + pad) + pad, cols * (w + pad) + pad, 3), 24, np.uint8)
    cv2.putText(sheet, header, (pad + 2, 20), FONT, 0.6, (230, 230, 230), 1, cv2.LINE_AA)
    for i, tile in enumerate(tiles):
        r, c = divmod(i, cols)
        y, x = head + pad + r * (h + pad), pad + c * (w + pad)
        sheet[y:y + h, x:x + w] = tile[:h, :w]
    return sheet


def _tc(t: float) -> str:
    m, s = divmod(t, 60)
    return f"{int(m):02d}:{s:05.2f}"


def video_sheet(name: str, t: np.ndarray, thumbs: list[np.ndarray], out: Path, max_tiles: int = 12) -> Path | None:
    if not thumbs:
        return None
    n = min(max_tiles, len(thumbs))
    idx = np.linspace(0, len(thumbs) - 1, n).round().astype(int)
    tiles = [_label(thumbs[i], _tc(float(t[i]))) for i in idx]
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), _grid(tiles, cols=4, header=name), [cv2.IMWRITE_JPEG_QUALITY, 80])
    return out


def overview_sheets(entries: list[tuple[int, str, np.ndarray]], out_dir: Path, per_sheet: int = 30) -> list[Path]:
    """entries = [(numéro, nom de fichier, miniature)]."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for k in range(0, len(entries), per_sheet):
        chunk = entries[k:k + per_sheet]
        tiles = [_label(_label(_fit(img, (288, 180)), f"#{n}", top=True), name.replace("DJI_", "")[:22])
                 for n, name, img in chunk]
        p = out_dir / f"overview_{k // per_sheet + 1:02d}.jpg"
        header = f"Vue d'ensemble {k // per_sheet + 1} - videos #{chunk[0][0]} a #{chunk[-1][0]}"
        cv2.imwrite(str(p), _grid(tiles, cols=6, header=header), [cv2.IMWRITE_JPEG_QUALITY, 80])
        paths.append(p)
    return paths
