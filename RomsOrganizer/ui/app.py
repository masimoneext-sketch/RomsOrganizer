"""Applicazione pygame: splash, setup controller, menu e schermate operative.

Architettura a 'stati': self.state dice quale schermata e' attiva; ogni stato ha
un gestore di azioni (on_<stato>) e un disegnatore (draw_<stato>). Le azioni sono
astratte (UP/DOWN/CONFIRM/BACK/SELECT), tradotte da controls.InputManager, quindi
tastiera e controller percorrono lo stesso identico codice.

Regola di sicurezza ovunque: si mostra sempre un'ANTEPRIMA (dry-run) e si agisce
solo dopo CONFERMA. Nessuna cancellazione: i file vanno in 'ROM eliminate'.
"""
from __future__ import annotations

import os

import pygame

from ..core import scanner, dedup, backup, tidy, config
from . import controls, theme
from .strings import t, set_lang, toggle_lang
from .controls import UP, DOWN, CONFIRM, BACK, SELECT, QUIT


class App:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("RomsOrganizer")
        if os.environ.get("ROMSORG_WINDOWED"):
            self.screen = pygame.display.set_mode((1024, 640))
        else:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        self.W, self.H = self.screen.get_size()
        self.clock = pygame.time.Clock()

        s = max(0.6, self.H / 720)  # fattore scala in base alla risoluzione
        self.f_big = theme.make_font(int(44 * s))
        self.f_mid = theme.make_font(int(28 * s))
        self.f_small = theme.make_font(int(22 * s), bold=False)
        self.row_h = int(40 * s)
        self.s = s

        settings = config.load_settings()
        set_lang(settings.get("lang", "it"))
        self.input = controls.InputManager()

        self.running = True
        self.state = "splash"
        self.menu_index = 0

        # dati di lavoro
        self.systems: dict = {}
        self.gamelists: dict = {}
        self.scan: dict = {}
        self.groups: list = []      # gruppi della categoria in risoluzione
        self.gi = 0                 # indice gruppo corrente
        self.highlight = 0          # candidato evidenziato nel gruppo
        self.pending = None         # azione in attesa di conferma (callable)
        self.pending_text = ""
        self.msg = ""
        self.msg_next = "main"

        # setup controller
        self.setup_step = 0

    # ===================================================================
    # LOOP PRINCIPALE
    # ===================================================================
    def run(self) -> None:
        while self.running:
            self.handle_events()
            self.draw()
            self.clock.tick(60)
        pygame.quit()

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if self.state == "controller_setup":
                self._setup_event(event)
                continue
            action = self.input.translate(event)
            if action == QUIT:
                self.running = False
            elif action:
                self.dispatch(action)

    def dispatch(self, action: str) -> None:
        handler = getattr(self, f"on_{self.state}", None)
        if handler:
            handler(action)

    # piccolo aiuto per i menu a lista
    def move(self, n_items: int, action: str) -> None:
        if action == UP:
            self.menu_index = (self.menu_index - 1) % n_items
        elif action == DOWN:
            self.menu_index = (self.menu_index + 1) % n_items

    # ===================================================================
    # SPLASH
    # ===================================================================
    def on_splash(self, action: str) -> None:
        if action in (CONFIRM, BACK, SELECT, UP, DOWN):
            # primo avvio col pad e senza mapping -> configurazione controller
            if self.input.has_joystick() and not self.input.mapping_exists():
                self.state = "controller_setup"
                self.setup_step = 0
            else:
                self.state = "main"
                self.menu_index = 0

    def draw_splash(self) -> None:
        theme.draw_logo(self.screen, self.W // 2, int(self.H * 0.40), self.s * 1.3)
        theme.neon_text(self.screen, self.f_small, t("app_subtitle"),
                        center=(self.W // 2, int(self.H * 0.62)), color=theme.NEON_PINK)
        if pygame.time.get_ticks() // 600 % 2:  # lampeggio
            theme.neon_text(self.screen, self.f_mid, t("press_any"),
                            center=(self.W // 2, int(self.H * 0.80)), color=theme.WHITE,
                            glow=False)

    # ===================================================================
    # SETUP CONTROLLER (legge eventi raw del joystick)
    # ===================================================================
    def _setup_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._flash(t("controller_skip"), "main")
            return
        if event.type == pygame.JOYBUTTONDOWN:
            action_key = controls.SETUP_STEPS[self.setup_step][0]
            self.input.mapping[action_key] = event.button
            self.setup_step += 1
            if self.setup_step >= len(controls.SETUP_STEPS):
                self.input.save_mapping()
                self._flash(t("controller_saved"), "main")

    def draw_controller_setup(self) -> None:
        theme.neon_text(self.screen, self.f_big, t("controller_setup"),
                        center=(self.W // 2, int(self.H * 0.22)), color=theme.NEON_GREEN)
        theme.neon_text(self.screen, self.f_small, t("controller_intro"),
                        center=(self.W // 2, int(self.H * 0.34)), color=theme.DIM, glow=False)
        if self.input.has_joystick():
            theme.neon_text(self.screen, self.f_small, self.input.joystick_name(),
                            center=(self.W // 2, int(self.H * 0.42)), color=theme.NEON_TEAL,
                            glow=False)
        act = controls.SETUP_STEPS[self.setup_step][1]
        theme.neon_text(self.screen, self.f_mid, t("press_for", action=t(act)),
                        center=(self.W // 2, int(self.H * 0.58)), color=theme.WHITE)
        theme.neon_text(self.screen, self.f_small,
                        f"{self.setup_step + 1} / {len(controls.SETUP_STEPS)}",
                        center=(self.W // 2, int(self.H * 0.70)), color=theme.NEON_PINK,
                        glow=False)

    # ===================================================================
    # MENU PRINCIPALE
    # ===================================================================
    MAIN_ITEMS = ["menu_scan", "menu_tidy", "menu_restore", "menu_lang", "menu_quit"]

    def on_main(self, action: str) -> None:
        self.move(len(self.MAIN_ITEMS), action)
        if action == BACK:
            self.menu_index = len(self.MAIN_ITEMS) - 1
        elif action == CONFIRM:
            choice = self.MAIN_ITEMS[self.menu_index]
            if choice == "menu_scan":
                self.do_scan()
            elif choice == "menu_tidy":
                self.state, self.menu_index = "tidy", 0
            elif choice == "menu_restore":
                self.state, self.menu_index = "restore", 0
            elif choice == "menu_lang":
                lang = toggle_lang()
                cfg = config.load_settings(); cfg["lang"] = lang; config.save_settings(cfg)
            elif choice == "menu_quit":
                self.running = False

    def draw_main(self) -> None:
        theme.draw_logo(self.screen, self.W // 2, int(self.H * 0.20), self.s * 0.8)
        # menu_lang mostra gia' la lingua attiva nella stringa tradotta
        labels = [t(key) for key in self.MAIN_ITEMS]
        self._draw_list(t("menu_title"), labels, self.menu_index, top=int(self.H * 0.40))
        self._hint([t("hint_move"), t("hint_confirm"), t("hint_back")])

    # ===================================================================
    # SCANSIONE + RISULTATI
    # ===================================================================
    def do_scan(self) -> None:
        self._draw_centered_msg(t("scanning"))
        pygame.display.flip()
        self.systems = scanner.scan_systems()
        self.gamelists = scanner.find_gamelists()
        self.scan = {
            "same_name": dedup.find_same_name(self.systems),
            "format": dedup.find_format_variants(self.systems),
            "region": dedup.find_region_variants(self.systems),
            "gamelist": dedup.find_gamelist_issues(self.gamelists),
        }
        self.state, self.menu_index = "scan_results", 0

    SCAN_CATS = [("same_name", "cat_same_name"), ("format", "cat_format"),
                 ("region", "cat_region"), ("gamelist", "cat_gamelist")]

    def on_scan_results(self, action: str) -> None:
        self.move(len(self.SCAN_CATS), action)
        if action == BACK:
            self.state, self.menu_index = "main", 0
        elif action == CONFIRM:
            cat, _ = self.SCAN_CATS[self.menu_index]
            items = self.scan.get(cat, [])
            if not items:
                self._flash(t("none_found"), "scan_results")
                return
            if cat == "gamelist":
                n = len(items)
                self._ask(t("will_remove_entries", n=n), self._apply_gamelist_fix, "scan_results")
            else:
                self.groups = items
                self.gi = 0
                self.highlight = items[0].keep_index
                self.state = "resolve"

    def draw_scan_results(self) -> None:
        labels = []
        for cat, key in self.SCAN_CATS:
            items = self.scan.get(cat, [])
            labels.append(f"{t(key)}  [{len(items)}]")
        self._draw_list(t("scan_done"), labels, self.menu_index, top=int(self.H * 0.22))
        self._hint([t("hint_move"), t("hint_confirm"), t("hint_back")])

    # ===================================================================
    # RISOLUZIONE GRUPPI (scelta manuale del 'tieni')
    # ===================================================================
    def on_resolve(self, action: str) -> None:
        group = self.groups[self.gi]
        n = len(group.candidates)
        if action == UP:
            self.highlight = (self.highlight - 1) % n
        elif action == DOWN:
            self.highlight = (self.highlight + 1) % n
        elif action in (SELECT, CONFIRM):
            group.keep_index = self.highlight      # registra la scelta
            self._next_group()
        elif action == BACK:
            if self.gi > 0:
                self.gi -= 1
                self.highlight = self.groups[self.gi].keep_index
            else:
                self.state, self.menu_index = "scan_results", 0

    def _next_group(self) -> None:
        if self.gi + 1 < len(self.groups):
            self.gi += 1
            self.highlight = self.groups[self.gi].keep_index
        else:
            # fine: anteprima e conferma
            n = sum(len(g.to_remove()) for g in self.groups)
            self._ask(t("will_move", n=n), self._apply_resolve, "scan_results")

    def draw_resolve(self) -> None:
        group = self.groups[self.gi]
        cat_key = {"same_name": "cat_same_name", "format": "cat_format",
                   "region": "cat_region"}.get(group.kind, "cat_region")
        theme.neon_text(self.screen, self.f_mid, t(cat_key),
                        center=(self.W // 2, int(self.H * 0.10)), color=theme.NEON_PINK)
        theme.neon_text(self.screen, self.f_small,
                        f"{t('system')}: {group.system}   ({self.gi + 1}/{len(self.groups)})",
                        center=(self.W // 2, int(self.H * 0.18)), color=theme.DIM, glow=False)
        theme.neon_text(self.screen, self.f_small, t("choose_keep"),
                        center=(self.W // 2, int(self.H * 0.25)), color=theme.NEON_TEAL, glow=False)

        top = int(self.H * 0.34)
        for i, rf in enumerate(group.candidates):
            y = top + i * self.row_h
            selected = (i == self.highlight)
            tag = f"[{t('keep_label')}] " if selected else "       "
            color = theme.NEON_GREEN if selected else theme.WHITE
            if selected:
                pygame.draw.rect(self.screen, theme.SELECT_BG,
                                 (int(self.W * 0.08), y - 4, int(self.W * 0.84), self.row_h))
            label = f"{tag}{rf.name}   ({config.human_size(rf.size)})"
            theme.neon_text(self.screen, self.f_small, label,
                            topleft=(int(self.W * 0.10), y), color=color, glow=selected)
        self._hint([t("hint_move"), t("hint_select"), t("hint_back")])

    def _apply_resolve(self) -> None:
        count = 0
        for g in self.groups:
            for rf in g.to_remove():
                backup.move_to_backup(rf, reason=g.kind)
                count += 1
        self._flash(t("applied", n=count), "main")

    def _apply_gamelist_fix(self) -> None:
        count = 0
        for system, gl in self.gamelists.items():
            r = tidy.tidy_gamelist(gl)
            count += r["removed_dup"] + r["removed_orphan"]
        self._flash(t("applied", n=count), "main")

    # ===================================================================
    # RIORDINA
    # ===================================================================
    TIDY_ITEMS = [("tidy_names", "_tidy_names"),
                  ("tidy_misplaced", "_tidy_misplaced"),
                  ("tidy_gamelist", "_tidy_gamelists")]

    def on_tidy(self, action: str) -> None:
        self.move(len(self.TIDY_ITEMS), action)
        if action == BACK:
            self.state, self.menu_index = "main", 0
        elif action == CONFIRM:
            getattr(self, self.TIDY_ITEMS[self.menu_index][1])()

    def draw_tidy(self) -> None:
        labels = [t(k) for k, _ in self.TIDY_ITEMS]
        self._draw_list(t("tidy_title"), labels, self.menu_index, top=int(self.H * 0.28))
        self._hint([t("hint_move"), t("hint_confirm"), t("hint_back")])

    def _tidy_names(self) -> None:
        self.gamelists = scanner.find_gamelists()
        changes = tidy.clean_display_names(self.gamelists, dry_run=True)
        if not changes:
            self._flash(t("none_found"), "tidy"); return
        self._ask(t("will_rename", n=len(changes)),
                  lambda: self._run_clean_names(), "tidy")

    def _run_clean_names(self) -> None:
        n = len(tidy.clean_display_names(self.gamelists, dry_run=False))
        self._flash(t("applied", n=n), "main")

    def _tidy_misplaced(self) -> None:
        self.systems = scanner.scan_systems()
        mis = tidy.find_misplaced(self.systems)
        if not mis:
            self._flash(t("none_found"), "tidy"); return
        self._mis = mis
        self._ask(t("will_move_misplaced", n=len(mis)), self._run_misplaced, "tidy")

    def _run_misplaced(self) -> None:
        n = sum(1 for m in self._mis if tidy.fix_misplaced(m))
        self._flash(t("applied", n=n), "main")

    def _tidy_gamelists(self) -> None:
        self.gamelists = scanner.find_gamelists()
        total = 0
        for gl in self.gamelists.values():
            r = tidy.tidy_gamelist(gl, dry_run=True)
            total += r["removed_dup"] + r["removed_orphan"]
        if total == 0:
            self._flash(t("none_found"), "tidy"); return
        self._ask(t("will_remove_entries", n=total), self._run_tidy_gamelists, "tidy")

    def _run_tidy_gamelists(self) -> None:
        n = 0
        for gl in self.gamelists.values():
            r = tidy.tidy_gamelist(gl, dry_run=False)
            n += r["removed_dup"] + r["removed_orphan"]
        self._flash(t("applied", n=n), "main")

    # ===================================================================
    # RIPRISTINA BACKUP
    # ===================================================================
    def on_restore(self, action: str) -> None:
        entries = backup.list_backup()
        items = (["__all__"] + entries) if entries else []
        n = len(items)
        if action == BACK or n == 0:
            if action == BACK:
                self.state, self.menu_index = "main", 0
            return
        self.move(n, action)
        if action == CONFIRM:
            sel = items[self.menu_index]
            if sel == "__all__":
                done = backup.restore_all()
            else:
                done = 1 if backup.restore(sel) else 0
            self.menu_index = 0
            self._flash(t("restored", n=done), "restore")

    def draw_restore(self) -> None:
        entries = backup.list_backup()
        summ = backup.backup_summary()
        theme.neon_text(self.screen, self.f_big, t("restore_title"),
                        center=(self.W // 2, int(self.H * 0.12)), color=theme.NEON_GREEN)
        theme.neon_text(self.screen, self.f_small,
                        t("backup_info", n=summ["count"], size=config.human_size(summ["bytes"])),
                        center=(self.W // 2, int(self.H * 0.20)), color=theme.DIM, glow=False)
        if not entries:
            theme.neon_text(self.screen, self.f_mid, t("restore_empty"),
                            center=(self.W // 2, int(self.H * 0.45)), color=theme.WHITE)
            self._hint([t("hint_back")])
            return
        labels = [t("restore_all", n=len(entries))] + [e["name"] for e in entries]
        # finestra scorrevole se troppi
        self._draw_list("", labels, self.menu_index, top=int(self.H * 0.30), max_rows=10)
        self._hint([t("hint_move"), t("hint_confirm"), t("hint_back")])

    # ===================================================================
    # CONFERMA (anteprima dry-run) e MESSAGGIO
    # ===================================================================
    def _ask(self, text: str, action_callable, back_state: str) -> None:
        self.pending = action_callable
        self.pending_text = text
        self.pending_back = back_state
        self.state = "confirm"

    def on_confirm(self, action: str) -> None:
        if action == CONFIRM:
            cb = self.pending
            self.pending = None
            if cb:
                cb()
        elif action == BACK:
            self.state = self.pending_back

    def draw_confirm(self) -> None:
        theme.neon_text(self.screen, self.f_mid, t("dry_run_title"),
                        center=(self.W // 2, int(self.H * 0.30)), color=theme.NEON_PINK)
        theme.neon_text(self.screen, self.f_mid, self.pending_text,
                        center=(self.W // 2, int(self.H * 0.46)), color=theme.WHITE)
        theme.neon_text(self.screen, self.f_small, t("confirm_apply"),
                        center=(self.W // 2, int(self.H * 0.62)), color=theme.NEON_GREEN)
        self._hint([t("hint_confirm"), t("hint_back")])

    def _flash(self, text: str, next_state: str) -> None:
        self.msg = text
        self.msg_next = next_state
        self.state = "message"

    def on_message(self, action: str) -> None:
        if action in (CONFIRM, BACK, SELECT):
            self.state = self.msg_next
            self.menu_index = 0

    def draw_message(self) -> None:
        theme.neon_text(self.screen, self.f_mid, self.msg,
                        center=(self.W // 2, self.H // 2), color=theme.NEON_TEAL)
        self._hint([t("hint_confirm")])

    # ===================================================================
    # PRIMITIVE DI DISEGNO
    # ===================================================================
    def draw(self) -> None:
        theme.draw_background(self.screen)
        drawer = getattr(self, f"draw_{self.state}", None)
        if drawer:
            drawer()
        pygame.display.flip()

    def _draw_list(self, title: str, labels: list[str], index: int,
                   top: int, max_rows: int = 12) -> None:
        if title:
            theme.neon_text(self.screen, self.f_big, title,
                            center=(self.W // 2, top - int(self.row_h * 1.6)),
                            color=theme.NEON_GREEN)
        # finestra scorrevole
        start = max(0, min(index - max_rows // 2, max(0, len(labels) - max_rows)))
        visible = labels[start:start + max_rows]
        for i, label in enumerate(visible):
            real = start + i
            y = top + i * self.row_h
            sel = (real == index)
            if sel:
                pygame.draw.rect(self.screen, theme.SELECT_BG,
                                 (int(self.W * 0.15), y - 4, int(self.W * 0.70), self.row_h))
            theme.neon_text(self.screen, self.f_mid,
                            ("> " if sel else "  ") + label,
                            topleft=(int(self.W * 0.18), y),
                            color=theme.NEON_GREEN if sel else theme.WHITE, glow=sel)

    def _draw_centered_msg(self, text: str) -> None:
        theme.draw_background(self.screen)
        theme.neon_text(self.screen, self.f_mid, text,
                        center=(self.W // 2, self.H // 2), color=theme.NEON_TEAL)

    def _hint(self, parts: list[str]) -> None:
        text = "   |   ".join(parts)
        theme.neon_text(self.screen, self.f_small, text,
                        center=(self.W // 2, int(self.H * 0.94)), color=theme.DIM, glow=False)


def run() -> None:
    App().run()
