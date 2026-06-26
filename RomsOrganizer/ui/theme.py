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

# Palette neon synthwave, base NERA per agganciarsi al fondo del logo.
BG = (8, 6, 16)
BG_GLOW = (24, 10, 40)
NEON_GREEN = (57, 255, 20)
NEON_TEAL = (29, 233, 182)
NEON_PINK = (255, 43, 214)
NEON_CYAN = (0, 229, 255)
NEON_PURPLE = (138, 43, 226)
WHITE = (235, 235, 245)
DIM = (130, 120, 160)
SELECT_BG = (60, 16, 90)
PANEL_FILL = (16, 10, 28)


def make_font(size: int, bold: bool = True) -> pygame.font.Font:
    """Font monospace (vibe terminale arcade); fallback al default di pygame."""
    try:
        return pygame.font.SysFont("couriernew,dejavusansmono,monospace", size, bold=bold)
    except Exception:
        return pygame.font.Font(None, size)


_bg_cache: pygame.Surface | None = None


def draw_background(surf: pygame.Surface) -> None:
    """Sfondo nero con griglia synthwave neon + scanline (coerente col logo).

    Lo sfondo e' statico: lo disegno una volta e lo metto in cache, cosi' ogni
    frame e' solo un blit (veloce anche durante i lavori con la barra).
    """
    global _bg_cache
    w, h = surf.get_size()
    if _bg_cache is None or _bg_cache.get_size() != (w, h):
        _bg_cache = _build_background(w, h)
    surf.blit(_bg_cache, (0, 0))


def _build_background(w: int, h: int) -> pygame.Surface:
    bg = pygame.Surface((w, h))
    bg.fill(BG)

    # alone in alto al centro
    glow = pygame.Surface((w, h), pygame.SRCALPHA)
    cx, cy = w // 2, int(h * 0.18)
    for r in range(int(h * 0.5), 0, -8):
        a = max(0, 30 - r * 30 // int(h * 0.5))
        pygame.draw.circle(glow, (*BG_GLOW, a), (cx, cy), r)
    bg.blit(glow, (0, 0))

    # pavimento synthwave: griglia in prospettiva nella meta' bassa
    grid = pygame.Surface((w, h), pygame.SRCALPHA)
    horizon = int(h * 0.56)
    vp = (w // 2, horizon)
    # linee verticali che convergono al punto di fuga
    for i in range(-12, 13):
        x_bottom = w // 2 + i * (w // 12)
        pygame.draw.line(grid, (*NEON_PINK, 60), (x_bottom, h), vp, 1)
    # linee orizzontali sempre piu' fitte verso l'orizzonte
    t = 0.0
    while t < 1.0:
        y = horizon + int((h - horizon) * (t * t))
        a = int(30 + 70 * t)
        pygame.draw.line(grid, (*NEON_CYAN, a), (0, y), (w, y), 1)
        t += 0.06
    # linea orizzonte marcata
    pygame.draw.line(grid, (*NEON_PINK, 120), (0, horizon), (w, horizon), 2)
    bg.blit(grid, (0, 0))

    # scanline CRT leggere su tutto
    scan = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(0, h, 3):
        pygame.draw.line(scan, (0, 0, 0, 40), (0, y), (w, y))
    bg.blit(scan, (0, 0))
    return bg


def fit_text(font: pygame.font.Font, text: str, max_w: int) -> str:
    """Tronca il testo con '...' se supera max_w pixel, cosi' non esce dal pannello."""
    if font.size(text)[0] <= max_w:
        return text
    ell = "..."
    s = text
    while s and font.size(s + ell)[0] > max_w:
        s = s[:-1]
    return (s + ell) if s else ell


def draw_panel(surf: pygame.Surface, rect, border=NEON_TEAL) -> None:
    """Pannello scuro semi-trasparente con bordo neon e angoli arrotondati."""
    rect = pygame.Rect(rect)
    fill = pygame.Surface(rect.size, pygame.SRCALPHA)
    fill.fill((*PANEL_FILL, 210))
    surf.blit(fill, rect.topleft)
    pygame.draw.rect(surf, border, rect, 2, border_radius=10)


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
        rect = scaled.get_rect(center=(cx, cy))
        # Il PNG ha fondo nero pieno: lo incornicio come un 'monitor' neon cosi'
        # non stacca male sulla griglia dello sfondo.
        frame = rect.inflate(int(14 * scale), int(14 * scale))
        pygame.draw.rect(surf, (6, 4, 12), frame, 0, border_radius=int(16 * scale))
        surf.blit(scaled, rect)
        pygame.draw.rect(surf, NEON_PINK, frame, max(2, int(3 * scale)),
                         border_radius=int(16 * scale))
        pygame.draw.rect(surf, NEON_CYAN, frame, 1, border_radius=int(16 * scale))
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
