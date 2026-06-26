"""Genera il VIDEO di anteprima animato per il menu PORTS (come RGSX).

EmulationStation riproduce in loop il <video> del gioco selezionato: e' quello
che rende l'anteprima "viva". Qui costruiamo un mp4 partendo dal logo, con:
  - griglia synthwave che scorre verso l'orizzonte,
  - logo che "respira" (leggero zoom sinusoidale),
  - cornice neon animata attorno che pulsa e vira ciano<->magenta.

Renderizziamo i frame con pygame OFFSCREEN (driver video 'dummy', cosi' non
disturba EmulationStation che sta usando lo schermo) e li montiamo con ffmpeg.
Tutto gira sul Batocera in fase di installazione. Se pygame/ffmpeg mancano o
qualcosa va storto, esce senza errori fatali: resta l'immagine statica.
"""
from __future__ import annotations

import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")   # nessun display reale
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

ASSETS = Path(__file__).resolve().parent.parent / "assets"
PORTS = Path(os.environ.get("ROMSORG_PORTS_DIR", "/userdata/roms/ports"))
OUT = PORTS / "videos" / "romsorganizer.mp4"

W = H = 480
FPS = 25
SECONDS = 4
N = FPS * SECONDS

BG = (8, 6, 16)
CYAN = (0, 229, 255)
MAGENTA = (255, 43, 214)
PINK = (255, 43, 214)


def _lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _draw_grid(surf, phase):
    """Griglia synthwave: verticali fisse + orizzontali che scorrono (loop)."""
    horizon = int(H * 0.52)
    grid = pygame.Surface((W, H), pygame.SRCALPHA)
    vp = (W // 2, horizon)
    for i in range(-8, 9):
        x = W // 2 + i * (W // 8)
        pygame.draw.line(grid, (*MAGENTA, 70), (x, H), vp, 1)
    num = 14
    for k in range(num):
        p = ((k + phase) % num) / num      # scorre e si richiude su se stesso
        y = horizon + int((H - horizon) * (p * p))
        a = int(30 + 90 * p)
        pygame.draw.line(grid, (*CYAN, a), (0, y), (W, y), 1)
    pygame.draw.line(grid, (*MAGENTA, 130), (0, horizon), (W, horizon), 2)
    surf.blit(grid, (0, 0))


def _draw_neon_frame(surf, rect, color, glow):
    """Cornice neon con alone pulsante (glow 0..1)."""
    overlay = pygame.Surface((W, H), pygame.SRCALPHA)
    for k in range(6, 0, -1):
        a = int(glow * (46 - k * 6))
        if a <= 0:
            continue
        r = rect.inflate(k * 4, k * 4)
        pygame.draw.rect(overlay, (*color, a), r, 2, border_radius=18)
    surf.blit(overlay, (0, 0))
    pygame.draw.rect(surf, color, rect, 3, border_radius=16)


def main() -> int:
    if shutil.which("ffmpeg") is None:
        print("[make_preview] ffmpeg assente: salto il video.")
        return 0
    logo_path = ASSETS / "logo.png"
    if not logo_path.is_file():
        print("[make_preview] logo.png assente: salto il video.")
        return 0

    try:
        pygame.init()
        pygame.display.set_mode((W, H))   # serve per convert_alpha col driver dummy
        logo = pygame.image.load(str(logo_path)).convert_alpha()
    except pygame.error as e:
        print("[make_preview] pygame non disponibile:", e)
        return 0

    base_w = int(W * 0.62)
    ratio = logo.get_height() / logo.get_width()
    tmp = Path(tempfile.mkdtemp(prefix="romsorg_vid_"))
    try:
        for i in range(N):
            t = i / N                       # fase 0..1 del loop
            wave = math.sin(2 * math.pi * t)
            surf = pygame.Surface((W, H))
            surf.fill(BG)
            _draw_grid(surf, t)

            breathe = 1.0 + 0.05 * wave
            lw = int(base_w * breathe)
            scaled = pygame.transform.smoothscale(logo, (lw, int(lw * ratio)))
            rect = scaled.get_rect(center=(W // 2, int(H * 0.42)))

            glow = 0.5 + 0.5 * wave
            color = _lerp(CYAN, MAGENTA, (wave + 1) / 2)
            frame_rect = rect.inflate(16, 16)
            pygame.draw.rect(surf, (6, 4, 12), frame_rect, 0, border_radius=16)
            surf.blit(scaled, rect)
            _draw_neon_frame(surf, frame_rect, color, glow)

            pygame.image.save(surf, str(tmp / f"f_{i:04d}.png"))

        OUT.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-framerate", str(FPS), "-i", str(tmp / "f_%04d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(OUT),
        ]
        subprocess.run(cmd, check=True)
        print("[make_preview] video creato:", OUT)
    except Exception as e:
        print("[make_preview] errore generazione video:", e)
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
