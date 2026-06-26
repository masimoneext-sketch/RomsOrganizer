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
from functools import partial

import pygame

from ..core import scanner, dedup, backup, tidy, config
from . import audio, controls, theme
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
        self.music = audio.Music()

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
        self.msg_sub = ""           # seconda riga informativa opzionale

        # lavoro a blocchi con barra di avanzamento
        self.jobs: list = []
        self.jobs_total = 0
        self.jobs_done = 0
        self.jobs_result = 0
        self.jobs_label = ""        # cosa sta facendo (testo)
        self.jobs_current = ""      # elemento in lavorazione (nome file)
        self.jobs_msg_key = "applied"
        self.jobs_next = "main"
        self.jobs_msg_sub = ""       # seconda riga del messaggio finale
        self.jobs_on_done = None     # callback opzionale a fine job (invece del msg)

        # rilevamento duplicati esatti (lazy: hashing solo quando si apre)
        self._exact_candidates: list = []
        self._exact_hashes: dict = {}

        # setup controller
        self.setup_step = 0

    # ===================================================================
    # LOOP PRINCIPALE
    # ===================================================================
    def run(self) -> None:
        while self.running:
            self.handle_events()
            if self.state == "progress":
                self._tick_jobs()      # avanza il lavoro a piccoli blocchi
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
    MAIN_ITEMS = ["menu_scan", "menu_tidy", "menu_restore",
                  "menu_music", "menu_lang", "menu_quit"]

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
            elif choice == "menu_music":
                self.music.toggle()
            elif choice == "menu_lang":
                lang = toggle_lang()
                cfg = config.load_settings(); cfg["lang"] = lang; config.save_settings(cfg)
            elif choice == "menu_quit":
                self.running = False

    def draw_main(self) -> None:
        theme.draw_logo(self.screen, self.W // 2, int(self.H * 0.20), self.s * 0.8)
        labels = []
        for key in self.MAIN_ITEMS:
            if key == "menu_music":
                state = t("on") if self.music.enabled else t("off")
                labels.append(f"{t('menu_music')}: {state}")
            else:
                labels.append(t(key))
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
                 ("region", "cat_region"), ("gamelist", "cat_gamelist"),
                 ("exact", "cat_exact")]

    def on_scan_results(self, action: str) -> None:
        self.move(len(self.SCAN_CATS), action)
        if action == BACK:
            self.state, self.menu_index = "main", 0
            return
        if action not in (CONFIRM, SELECT):
            return
        cat, _ = self.SCAN_CATS[self.menu_index]
        # Duplicati esatti: calcolo pigro (hashing solo ora che l'utente apre).
        if cat == "exact" and "exact" not in self.scan:
            candidates = dedup.find_exact_candidates(self.systems)
            if not candidates:
                self.scan["exact"] = []
                self._flash(t("none_found"), "scan_results")
                return
            self._exact_candidates = candidates
            self._exact_hashes = {}
            jobs = [partial(self._job_hash, rf) for rf in candidates]
            self._run_jobs(jobs, t("working_hash"), next_state="scan_results",
                           on_done=self._finish_exact)
            return
        items = self.scan.get(cat, [])
        if not items:
            self._flash(t("none_found"), "scan_results")
            return
        if cat == "gamelist":
            self._ask(t("will_remove_entries", n=len(items)),
                      self._apply_gamelist_fix, "scan_results")
            return
        if action == CONFIRM:
            # AUTOMATICO: usa i suggerimenti (compresso / nome pulito / regione
            # preferita) e va dritto all'anteprima. Un colpo solo per migliaia di ROM.
            self.groups = items
            n = sum(len(g.to_remove()) for g in items)
            self._ask(t("will_move", n=n), self._apply_resolve, "scan_results")
        else:
            # A MANO: la vecchia revisione gruppo per gruppo, per chi vuole controllare.
            self.groups = items
            self.gi = 0
            self.highlight = items[0].keep_index
            self.state = "resolve"

    def draw_scan_results(self) -> None:
        labels = []
        for cat, key in self.SCAN_CATS:
            if cat == "exact" and "exact" not in self.scan:
                labels.append(f"{t(key)}  [{t('scan_hint')}]")
            else:
                labels.append(f"{t(key)}  [{len(self.scan.get(cat, []))}]")
        self._draw_list(t("scan_done"), labels, self.menu_index, top=int(self.H * 0.22))
        self._hint([t("hint_move"), t("hint_auto"), t("hint_manual"), t("hint_back")])

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
                   "region": "cat_region", "exact": "cat_exact"}.get(group.kind, "cat_region")
        theme.neon_text(self.screen, self.f_mid, t(cat_key),
                        center=(self.W // 2, int(self.H * 0.10)), color=theme.NEON_PINK)
        theme.neon_text(self.screen, self.f_small,
                        f"{t('system')}: {group.system}   ({self.gi + 1}/{len(self.groups)})",
                        center=(self.W // 2, int(self.H * 0.18)), color=theme.DIM, glow=False)
        theme.neon_text(self.screen, self.f_small, t("choose_keep"),
                        center=(self.W // 2, int(self.H * 0.25)), color=theme.NEON_TEAL, glow=False)

        top = int(self.H * 0.34)
        pad = int(12 * self.s)
        theme.draw_panel(self.screen, (int(self.W * 0.08), top - pad,
                                       int(self.W * 0.84),
                                       len(group.candidates) * self.row_h + pad * 2))
        for i, rf in enumerate(group.candidates):
            y = top + i * self.row_h
            selected = (i == self.highlight)
            tag = f"[{t('keep_label')}] " if selected else "       "
            color = theme.NEON_GREEN if selected else theme.WHITE
            if selected:
                pygame.draw.rect(self.screen, theme.SELECT_BG,
                                 (int(self.W * 0.10), y - 2, int(self.W * 0.80), self.row_h),
                                 border_radius=6)
            # La dimensione e il tag [TIENI] restano sempre leggibili: troncare il
            # solo NOME (con '...') se il rigo eccede la larghezza interna del pannello.
            suffix = f"   ({config.human_size(rf.size)})"
            max_w = int(self.W * 0.80) - pad
            name = theme.fit_text(self.f_small, rf.name,
                                  max_w - self.f_small.size(tag + suffix)[0])
            label = f"{tag}{name}{suffix}"
            theme.neon_text(self.screen, self.f_small, label,
                            topleft=(int(self.W * 0.10), y), color=color, glow=selected)
        self._hint([t("hint_move"), t("hint_select"), t("hint_back")])

    # --- motore dei job a blocchi (mantiene viva la UI durante i lavori lunghi) -
    def _run_jobs(self, jobs: list, label: str, msg_key: str = "applied",
                  next_state: str = "main", on_done=None, msg_sub: str = "") -> None:
        self.jobs = jobs
        self.jobs_total = len(jobs)
        self.jobs_done = 0
        self.jobs_result = 0
        self.jobs_label = label
        self.jobs_current = ""
        self.jobs_msg_key = msg_key
        self.jobs_next = next_state
        self.jobs_msg_sub = msg_sub
        self.jobs_on_done = on_done
        if not jobs:
            if on_done:
                on_done()
            else:
                self._flash(t("none_found"), next_state)
            return
        self.state = "progress"

    def _tick_jobs(self) -> None:
        """Esegue un blocco di operazioni per frame, poi torna a disegnare."""
        chunk = 40
        for _ in range(chunk):
            if self.jobs_done >= self.jobs_total:
                break
            try:
                self.jobs_result += int(self.jobs[self.jobs_done]() or 0)
            except Exception:
                pass
            self.jobs_done += 1
        if self.jobs_done >= self.jobs_total:
            if self.jobs_on_done:
                cb = self.jobs_on_done
                self.jobs_on_done = None
                cb()
            else:
                self._flash(t(self.jobs_msg_key, n=self.jobs_result),
                            self.jobs_next, sub=self.jobs_msg_sub)

    # singole unita' di lavoro: aggiornano jobs_current (cosa si sta facendo) e
    # restituiscono quante 'operazioni' valgono (per il conteggio finale).
    def _job_move(self, rf, kind):
        self.jobs_current = rf.name
        backup.move_to_backup(rf, reason=kind)
        return 1

    def _job_tidy_gl(self, system, gl):
        self.jobs_current = system
        r = tidy.tidy_gamelist(gl)
        return r["removed_dup"] + r["removed_orphan"]

    def _job_fix_mis(self, m):
        self.jobs_current = m["rom"].name
        return 1 if tidy.fix_misplaced(m) else 0

    def _job_clean_names(self, system, gl):
        self.jobs_current = system
        return len(tidy.clean_display_names({system: gl}, dry_run=False))

    def _job_restore(self, e):
        self.jobs_current = e.get("name", "")
        return 1 if backup.restore(e) else 0

    def _job_hash(self, rf):
        self.jobs_current = rf.name
        try:
            self._exact_hashes[str(rf.path)] = dedup.hash_file(rf.path)
        except OSError:
            pass
        return 0

    def _finish_exact(self) -> None:
        """Costruisce i gruppi di duplicati esatti dagli hash appena calcolati."""
        groups = dedup.group_exact(self._exact_candidates, self._exact_hashes)
        self.scan["exact"] = groups
        msg = t("groups_found", n=len(groups)) if groups else t("none_found")
        self._flash(msg, "scan_results")

    def _apply_resolve(self) -> None:
        jobs = [partial(self._job_move, rf, g.kind)
                for g in self.groups for rf in g.to_remove()]
        self._run_jobs(jobs, t("working_move"), "applied", "main",
                       msg_sub=t("backup_location", path=str(config.backup_dir())))

    def _apply_gamelist_fix(self) -> None:
        jobs = [partial(self._job_tidy_gl, s, gl) for s, gl in self.gamelists.items()]
        self._run_jobs(jobs, t("working_gamelist"), "applied", "main")

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
        jobs = [partial(self._job_clean_names, s, gl) for s, gl in self.gamelists.items()]
        self._run_jobs(jobs, t("working_names"), "applied", "main")

    def _tidy_misplaced(self) -> None:
        self.systems = scanner.scan_systems()
        mis = tidy.find_misplaced(self.systems)
        if not mis:
            self._flash(t("none_found"), "tidy"); return
        self._mis = mis
        self._ask(t("will_move_misplaced", n=len(mis)), self._run_misplaced, "tidy")

    def _run_misplaced(self) -> None:
        jobs = [partial(self._job_fix_mis, m) for m in self._mis]
        self._run_jobs(jobs, t("working_misplaced"), "applied", "main")

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
        jobs = [partial(self._job_tidy_gl, s, gl) for s, gl in self.gamelists.items()]
        self._run_jobs(jobs, t("working_gamelist"), "applied", "main")

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
                jobs = [partial(self._job_restore, e) for e in entries]
                self.menu_index = 0
                self._run_jobs(jobs, t("working_restore"), "restored", "restore")
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
        theme.neon_text(self.screen, self.f_small, str(config.backup_dir()),
                        center=(self.W // 2, int(self.H * 0.25)), color=theme.NEON_TEAL, glow=False)
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
        theme.draw_panel(self.screen, (int(self.W * 0.15), int(self.H * 0.24),
                                       int(self.W * 0.70), int(self.H * 0.46)),
                         border=theme.NEON_PINK)
        theme.neon_text(self.screen, self.f_mid, t("dry_run_title"),
                        center=(self.W // 2, int(self.H * 0.30)), color=theme.NEON_PINK)
        theme.neon_text(self.screen, self.f_mid, self.pending_text,
                        center=(self.W // 2, int(self.H * 0.46)), color=theme.WHITE)
        theme.neon_text(self.screen, self.f_small, t("confirm_apply"),
                        center=(self.W // 2, int(self.H * 0.62)), color=theme.NEON_GREEN)
        self._hint([t("hint_confirm"), t("hint_back")])

    def _flash(self, text: str, next_state: str, sub: str = "") -> None:
        self.msg = text
        self.msg_sub = sub
        self.msg_next = next_state
        self.state = "message"

    def on_message(self, action: str) -> None:
        if action in (CONFIRM, BACK, SELECT):
            self.state = self.msg_next
            self.menu_index = 0

    def draw_message(self) -> None:
        cy = self.H // 2 if not self.msg_sub else int(self.H * 0.45)
        theme.neon_text(self.screen, self.f_mid, self.msg,
                        center=(self.W // 2, cy), color=theme.NEON_TEAL)
        if self.msg_sub:
            theme.neon_text(self.screen, self.f_small, self.msg_sub,
                            center=(self.W // 2, cy + int(50 * self.s)),
                            color=theme.DIM, glow=False)
        self._hint([t("hint_confirm")])

    def draw_progress(self) -> None:
        theme.draw_panel(self.screen, (int(self.W * 0.12), int(self.H * 0.22),
                                       int(self.W * 0.76), int(self.H * 0.46)))
        # cosa sta facendo
        theme.neon_text(self.screen, self.f_mid, self.jobs_label or t("working"),
                        center=(self.W // 2, int(self.H * 0.30)), color=theme.NEON_GREEN)
        # elemento in lavorazione (nome file/sistema), troncato se lungo
        cur = self.jobs_current
        if len(cur) > 48:
            cur = cur[:45] + "..."
        if cur:
            theme.neon_text(self.screen, self.f_small, cur,
                            center=(self.W // 2, int(self.H * 0.40)),
                            color=theme.WHITE, glow=False)
        # barra di avanzamento
        bw, bh = int(self.W * 0.6), int(28 * self.s)
        bx, by = (self.W - bw) // 2, int(self.H * 0.50)
        pygame.draw.rect(self.screen, theme.NEON_TEAL, (bx, by, bw, bh), 2)
        frac = self.jobs_done / self.jobs_total if self.jobs_total else 0
        if frac > 0:
            pygame.draw.rect(self.screen, theme.NEON_GREEN,
                             (bx + 3, by + 3, int((bw - 6) * frac), bh - 6))
        # percentuale + conteggio
        theme.neon_text(self.screen, self.f_small,
                        f"{int(frac * 100)}%   ({self.jobs_done}/{self.jobs_total})",
                        center=(self.W // 2, by + bh + int(28 * self.s)),
                        color=theme.NEON_PINK, glow=False)

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
                            center=(self.W // 2, top - int(self.row_h * 1.7)),
                            color=theme.NEON_GREEN)
        # finestra scorrevole
        start = max(0, min(index - max_rows // 2, max(0, len(labels) - max_rows)))
        visible = labels[start:start + max_rows]
        # pannello neon dietro la lista
        pad = int(12 * self.s)
        px = int(self.W * 0.12)
        pw = int(self.W * 0.76)
        ph = len(visible) * self.row_h + pad * 2
        theme.draw_panel(self.screen, (px, top - pad, pw, ph))
        for i, label in enumerate(visible):
            real = start + i
            y = top + i * self.row_h
            sel = (real == index)
            if sel:
                pygame.draw.rect(self.screen, theme.SELECT_BG,
                                 (px + int(6 * self.s), y - 2, pw - int(12 * self.s), self.row_h),
                                 border_radius=6)
                pygame.draw.rect(self.screen, theme.NEON_GREEN,
                                 (px + int(6 * self.s), y - 2, int(5 * self.s), self.row_h))
            full = theme.fit_text(self.f_mid, ("> " if sel else "  ") + label,
                                  pw - int(44 * self.s))
            theme.neon_text(self.screen, self.f_mid, full,
                            topleft=(px + int(24 * self.s), y),
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
