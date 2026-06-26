"""Tema grafico: palette neon arcade '80, font e disegno del logo cartuccia.

Il logo e' disegnato in modo PROCEDURALE (rettangoli e linee) invece di caricare
un PNG: cosi' scala con qualsiasi risoluzione dello schermo Batocera e non
dipende da file binari. Stessa cartuccia neon verde scelta nei mockup.
"""
from __future__ import annotations

from pathlib import Path

import pygame

_ASSETS = Path(__file__).resolve().parent.parent / "assets"
_logo_img: pygame.Surface | None = None
_logo_loaded = False

# Palette neon synthwave
BG_TOP = (10, 0, 20)
BG_BOTTOM = (19, 0, 43)
NEON_GREEN = (57, 255, 20)
NEON_TEAL = (29, 233, 182)
NEON_PINK = (255, 43, 214)
NEON_CYAN = (0, 229, 255)
WHITE = (235, 235, 245)
DIM = (120, 120, 150)
SELECT_BG = (40, 10, 70)


def make_font(size: int, bold: bool = True) -> pygame.font.Font:
    """Font monospace (vibe terminale arcade); fallback al default di pygame."""
    try:
        return pygame.font.SysFont("couriernew,dejavusansmono,monospace", size, bold=bold)
    except Exception:
        return pygame.font.Font(None, size)


def draw_background(surf: pygame.Surface) -> None:
    """Sfondo a gradiente verticale + scanline CRT."""
    w, h = surf.get_size()
    for y in range(h):
        f = y / max(1, h - 1)
        col = tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * f) for i in range(3))
        pygame.draw.line(surf, col, (0, y), (w, y))
    scan = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(0, h, 3):
        pygame.draw.line(scan, (29, 233, 182, 12), (0, y), (w, y))
    surf.blit(scan, (0, 0))


def neon_text(surf: pygame.Surface, font: pygame.font.Font, text: str,
              center=None, topleft=None, color=NEON_GREEN, glow=True):
    """Testo con alone neon: lo stesso testo disegnato dietro, scuro e 'spostato'."""
    if glow:
        halo = font.render(text, True, tuple(c // 3 for c in color))
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            r = halo.get_rect()
            if center:
                r.center = (center[0] + dx, center[1] + dy)
            else:
                r.topleft = (topleft[0] + dx, topleft[1] + dy)
            surf.blit(halo, r)
    img = font.render(text, True, color)
    r = img.get_rect()
    if center:
        r.center = center
    else:
        r.topleft = topleft
    surf.blit(img, r)
    return r


def _load_logo() -> pygame.Surface | None:
    """Carica una volta sola il logo PNG ufficiale dagli asset (se presente)."""
    global _logo_img, _logo_loaded
    if _logo_loaded:
        return _logo_img
    _logo_loaded = True
    png = _ASSETS / "logo.png"
    if png.is_file():
        try:
            img = pygame.image.load(str(png))
            _logo_img = img.convert_alpha()
        except pygame.error:
            _logo_img = None
    return _logo_img


def draw_logo(surf: pygame.Surface, cx: int, cy: int, scale: float = 1.0) -> None:
    """Mostra il logo ufficiale (PNG) centrato in (cx, cy).

    Se il PNG non e' caricabile, ripiega sul disegno procedurale della cartuccia
    cosi' l'app resta usabile comunque.
    """
    img = _load_logo()
    if img is not None:
        target_w = int(360 * scale)
        ratio = img.get_height() / img.get_width()
        scaled = pygame.transform.smoothscale(img, (target_w, int(target_w * ratio)))
        surf.blit(scaled, scaled.get_rect(center=(cx, cy)))
        return
    _draw_logo_vector(surf, cx, cy, scale)


def _draw_logo_vector(surf: pygame.Surface, cx: int, cy: int, scale: float = 1.0) -> None:
    """Fallback: cartuccia ROM neon verde disegnata a runtime."""
    w = int(260 * scale)
    h = int(180 * scale)
    x = cx - w // 2
    y = cy - h // 2
    lw = max(2, int(4 * scale))

    # corpo cartuccia
    body = pygame.Rect(x, y, w, h)
    pygame.draw.rect(surf, NEON_GREEN, body, lw, border_radius=int(14 * scale))
    # etichetta interna
    label = pygame.Rect(x + int(18 * scale), y + int(16 * scale),
                        w - int(36 * scale), int(90 * scale))
    pygame.draw.rect(surf, NEON_TEAL, label, max(2, int(3 * scale)),
                     border_radius=int(6 * scale))
    # pin del chip
    pin_y = y + h - int(26 * scale)
    for i in range(7):
        px = x + int(22 * scale) + i * int(22 * scale)
        pygame.draw.line(surf, NEON_GREEN, (px, pin_y), (px, pin_y + int(16 * scale)), lw)

    # testo sull'etichetta
    f1 = make_font(int(30 * scale))
    f2 = make_font(int(20 * scale))
    neon_text(surf, f1, "ROMS", center=(cx, y + int(40 * scale)), color=NEON_GREEN)
    neon_text(surf, f2, "ORGANIZER", center=(cx, y + int(72 * scale)), color=NEON_TEAL)
