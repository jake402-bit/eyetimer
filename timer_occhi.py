#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
20-20-20 Eye Timer
Modern interface, external icon file, robust audio playback on Linux,
and multi-language support.

The 20-20-20 rule: every 20 minutes, look at something 20 feet (6
meters) away for 20 seconds.

--------------------------------------------------------------------
Translations
--------------------------------------------------------------------
All UI strings are translated through JSON files in the "locales/"
folder next to this script (one per language, e.g. "locales/it.json",
"locales/es.json"...). English is embedded in this file as a last-
resort fallback (see EMBEDDED_TRANSLATIONS below) so the app still
runs even if the "locales/" folder is missing entirely - but every
other language, including Italian, lives only in "locales/*.json".

To add a new language once this project is published on git: copy
"locales/en.json" (or write one from scratch), rename it with the
language code (e.g. "de.json"), and translate the values. No Python
code changes needed - the language automatically shows up in the
picker at the top-right of the window. See "locales/README.md" for
details.

--------------------------------------------------------------------
Icon
--------------------------------------------------------------------
The window/taskbar icon is loaded from an external "icon.png" file
that must sit next to this script. Nothing is embedded in the source
code, so the icon can be swapped or localized independently. If
"icon.png" is missing, the app still runs - it just falls back to the
platform's default window icon.
"""

import json
import locale
import math
import os
import shutil
import struct
import subprocess
import tempfile
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import wave
from tkinter import ttk

# --------------------------------------------------------------------------
# Embedded fallback translations - guarantees the app still runs (in
# English) even if the "locales/" folder is missing. Every other
# language, including Italian, is loaded exclusively from
# "locales/*.json" - see _load_translations() below.
# --------------------------------------------------------------------------
EMBEDDED_TRANSLATIONS = {
    "en": {
        "lang_name": "English",
        "app_title": "20-20-20 Eye Timer",
        "header_title": "Eye Timer",
        "subtitle": "Every {min} minutes, look at something 20 feet away for 20 seconds",
        "duration_label": "Duration:",
        "minutes_label": "minutes",
        "status_ready": "Ready to start",
        "status_running": "Counting down...",
        "status_paused": "Paused",
        "status_alert": "20-second break!",
        "btn_start": "Start",
        "btn_pause": "Pause",
        "btn_reset": "Reset",
        "footer_hint": "Tip: blink often while looking at the screen",
        "dialog_title": "Break time",
        "dialog_heading": "Time for a break!",
        "dialog_body": "Look at something 20 feet (6 meters) away\nfor 20 seconds.",
        "dialog_ok": "Done",
        "notif_title": "Eye Timer",
        "notif_body": "Look at something 20 feet (6 meters) away for 20 seconds.",
    },
}


# --------------------------------------------------------------------------
# Palette - high contrast, WCAG AA checked
# --------------------------------------------------------------------------
THEMES = {
    "dark": {
        "bg": "#0d1117",
        "surface": "#161b22",
        "fg": "#e6edf3",
        "muted": "#8b949e",
        "accent": "#58a6ff",
        "accent_hover": "#79c0ff",
        "btn_bg": "#21262d",
        "btn_fg": "#c9d1d9",
        "ring_track": "#21262d",
        "ring_progress": "#58a6ff",
        "status_ready": "#3fb950",
        "status_running": "#d29922",
        "status_paused": "#f85149",
        "status_alert": "#f778ba",
    },
    "light": {
        "bg": "#f6f8fa",
        "surface": "#ffffff",
        "fg": "#0d1117",
        "muted": "#57606a",
        "accent": "#0969da",
        "accent_hover": "#1a7fe0",
        "btn_bg": "#eaeef2",
        "btn_fg": "#24292f",
        "ring_track": "#d0d7de",
        "ring_progress": "#0969da",
        "status_ready": "#1a7f37",
        "status_running": "#9a6700",
        "status_paused": "#cf222e",
        "status_alert": "#bf3989",
    },
}

DURATION_OPTIONS = [5, 10, 15, 20, 25, 30]  # selectable minutes


def _pick_font(preferred, fallback="TkDefaultFont"):
    """Returns the first available font on the system among the
    preferred list."""
    try:
        available = set(tkfont.families())
    except Exception:
        return fallback
    for name in preferred:
        if name in available:
            return name
    return fallback


class EyeHealthTimer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.configure(bg="#0d1117")
        self.root.minsize(400, 460)
        self.root.resizable(False, False)

        # --- Language: must load before building the UI -------------
        self.LANGUAGES = self._load_translations()
        settings = self._load_settings()
        saved_language = settings.get("language")
        if saved_language in self.LANGUAGES:
            self.CURRENT_LANGUAGE = saved_language
        else:
            self.CURRENT_LANGUAGE = self._detect_initial_language()

        self.CURRENT_THEME = "dark"
        self.DURATION_MINUTES = 20
        self.INTERVAL = self.DURATION_MINUTES * 60
        self.REMAINING = self.INTERVAL
        self.RUNNING = False
        self._alert_active = False
        self._status_key = "status_ready"
        self._title_font = _pick_font(["Ubuntu", "Segoe UI", "DejaVu Sans", "Helvetica"])
        self._text_font = self._title_font
        self._timer_font = _pick_font(["Ubuntu Mono", "DejaVu Sans Mono", "Consolas", "monospace"])

        self._setup_icon()
        self._create_ui()
        self._apply_theme()
        self.root.title(self.t("app_title"))
        self._center_window()

    # ------------------------------------------------------------------
    # Localization
    # ------------------------------------------------------------------
    def t(self, key, **kwargs):
        """Returns the translated string for the current language, with
        a fallback to English and finally to the key itself if
        missing."""
        text = self.LANGUAGES.get(self.CURRENT_LANGUAGE, {}).get(key)
        if text is None:
            text = self.LANGUAGES.get("en", {}).get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except Exception:
                pass
        return text

    def _load_translations(self):
        """Starts from the embedded English fallback and enriches/
        extends it with any file found in locales/*.json. This means
        the project, once published on git, can gain new languages via
        pull request just by adding a file - no code changes needed.
        Italian (and every other non-English language) lives only in
        these external files."""
        languages = {code: dict(values) for code, values in EMBEDDED_TRANSLATIONS.items()}

        script_dir = os.path.dirname(os.path.abspath(__file__))
        locales_dir = os.path.join(script_dir, "locales")
        if os.path.isdir(locales_dir):
            for file_name in sorted(os.listdir(locales_dir)):
                if not file_name.lower().endswith(".json"):
                    continue
                code = file_name[:-5].lower()
                file_path = os.path.join(locales_dir, file_name)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception as e:
                    print(f"\u26A0 Could not read '{file_name}': {e}")
                    continue
                base = languages.get(code, dict(EMBEDDED_TRANSLATIONS.get("en", {})))
                base.update(data)
                languages[code] = base

        return languages

    def _detect_initial_language(self):
        """Uses the system language if it's among the translated ones,
        otherwise falls back to English."""
        system_code = ""
        try:
            system_code = (locale.getlocale()[0] or locale.getdefaultlocale()[0] or "")
        except Exception:
            pass
        short_code = system_code.split("_")[0].lower() if system_code else ""
        if short_code in self.LANGUAGES:
            return short_code
        if "en" in self.LANGUAGES:
            return "en"
        return next(iter(self.LANGUAGES), "en")

    def _settings_path(self):
        folder = os.path.join(os.path.expanduser("~"), ".config", "eye-timer")
        return os.path.join(folder, "settings.json")

    def _load_settings(self):
        try:
            with open(self._settings_path(), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_settings(self):
        path = self._settings_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"language": self.CURRENT_LANGUAGE}, f)
        except Exception as e:
            print(f"\u26A0 Could not save settings: {e}")

    def _show_language_menu(self):
        t = self._theme()
        menu = tk.Menu(
            self.root, tearoff=0, bg=t["btn_bg"], fg=t["fg"],
            activebackground=t["accent"], activeforeground="#ffffff",
            bd=0, relief="flat", font=(self._text_font, 10),
        )
        for code in sorted(self.LANGUAGES.keys()):
            name = self.LANGUAGES[code].get("lang_name", code.upper())
            mark = "\u2713 " if code == self.CURRENT_LANGUAGE else "    "
            menu.add_command(
                label=f"{mark}{name}", command=lambda c=code: self._change_language(c)
            )
        x = self.lang_btn.winfo_rootx()
        y = self.lang_btn.winfo_rooty() + self.lang_btn.winfo_height() + 2
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _change_language(self, code):
        if code == self.CURRENT_LANGUAGE or code not in self.LANGUAGES:
            return
        self.CURRENT_LANGUAGE = code
        self._save_settings()
        self._retranslate_ui()

    def _retranslate_ui(self):
        """Updates every visible string without recreating widgets."""
        self.root.title(self.t("app_title"))
        self.title_lbl.configure(text=f"\U0001F441  {self.t('header_title')}")
        self.subtitle_lbl.configure(text=self.t("subtitle", min=self.DURATION_MINUTES))
        self.duration_label.configure(text=self.t("duration_label"))
        self.duration_unit_label.configure(text=self.t("minutes_label"))
        self.canvas.itemconfig(self._minutes_text_id, text=self.t("minutes_label"))
        self.btn_start.configure(text=f"\u25B6  {self.t('btn_start')}")
        self.btn_pause.configure(text=f"\u23F8  {self.t('btn_pause')}")
        self.btn_reset.configure(text=f"\u21BA  {self.t('btn_reset')}")
        self.footer_lbl.configure(text=self.t("footer_hint"))
        self.lang_btn.configure(text=f"\U0001F310 {self.CURRENT_LANGUAGE.upper()}")
        self._update_status_label()

    # ------------------------------------------------------------------
    # Icon - always loaded from an external file, never embedded here
    # ------------------------------------------------------------------
    def _setup_icon(self):
        """
        Loads "icon.png" from the folder next to this script and
        applies it to the window/taskbar. The app runs fine without it
        - this is a nice-to-have, not a hard requirement, since the
        icon is intentionally kept outside the source code so it can
        be swapped or localized independently.
        """
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(script_dir, "icon.png")

        if os.path.exists(icon_path):
            try:
                img = tk.PhotoImage(file=icon_path)
                self._icon_img = img  # strong reference: prevents garbage collection
                self.root.iconphoto(True, img)
            except Exception as e:
                print(f"\u26A0 Could not load 'icon.png': {e}")
        else:
            print("\u2139 'icon.png' not found next to the script - using the default window icon.")

        # On many Linux window managers (X11) the taskbar icon is also
        # read from WM_CLASS: set it explicitly.
        try:
            self.root.wm_iconname("Eye Timer")
            self.root.tk.call("wm", "class", self.root._w, "EyeTimer")
        except Exception:
            pass

    def _center_window(self):
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x, y = (sw - w) // 2, (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _create_ui(self):
        self.main = tk.Frame(self.root, padx=30, pady=26)
        self.main.pack(expand=True, fill="both")

        # --- Header -----------------------------------------------------
        header = tk.Frame(self.main)
        header.pack(fill="x", pady=(0, 18))

        self.title_lbl = tk.Label(
            header, text=f"\U0001F441  {self.t('header_title')}", font=(self._title_font, 17, "bold"), anchor="w"
        )
        self.title_lbl.pack(side="left")

        self.theme_btn = tk.Button(
            header, text="\u2600", font=(self._text_font, 13), command=self._toggle_theme,
            cursor="hand2", bd=0, relief="flat", activeforeground="#ffffff",
            highlightthickness=0, padx=8, pady=2,
        )
        self.theme_btn.pack(side="right")

        self.lang_btn = tk.Button(
            header, text=f"\U0001F310 {self.CURRENT_LANGUAGE.upper()}", font=(self._text_font, 10, "bold"),
            command=self._show_language_menu, cursor="hand2", bd=0, relief="flat",
            activeforeground="#ffffff", highlightthickness=0, padx=8, pady=2,
        )
        self.lang_btn.pack(side="right", padx=(0, 8))

        self.subtitle_lbl = tk.Label(
            self.main, text=self.t("subtitle", min=self.DURATION_MINUTES),
            font=(self._text_font, 9),
        )
        self.subtitle_lbl.pack(anchor="w", pady=(0, 16))

        # --- Progress ring + time ----------------------------------------
        ring_wrap = tk.Frame(self.main)
        ring_wrap.pack(pady=(0, 18))

        self.ring_size = 220
        self.canvas = tk.Canvas(
            ring_wrap, width=self.ring_size, height=self.ring_size, highlightthickness=0, bd=0
        )
        self.canvas.pack()

        pad = 14
        self._ring_bbox = (pad, pad, self.ring_size - pad, self.ring_size - pad)
        self._ring_track_id = self.canvas.create_oval(*self._ring_bbox, width=10, outline="#000000")
        self._ring_arc_id = self.canvas.create_arc(
            *self._ring_bbox, start=90, extent=0, style="arc", width=10, outline="#000000"
        )
        self._time_text_id = self.canvas.create_text(
            self.ring_size / 2, self.ring_size / 2 - 8,
            text="20:00", font=(self._timer_font, 34, "bold"),
        )
        self._minutes_text_id = self.canvas.create_text(
            self.ring_size / 2, self.ring_size / 2 + 26,
            text=self.t("minutes_label"), font=(self._text_font, 9),
        )

        # --- Status -------------------------------------------------------
        self.status_lbl = tk.Label(self.main, text=self.t("status_ready"), font=(self._text_font, 10, "bold"))
        self.status_lbl.pack(pady=(0, 18))

        # --- Duration picker ------------------------------------------
        duration_frame = tk.Frame(self.main)
        duration_frame.pack(fill="x", pady=(0, 16))

        self.duration_label = tk.Label(duration_frame, text=self.t("duration_label"), font=(self._text_font, 9))
        self.duration_label.pack(side="left")

        self.duration_var = tk.StringVar(value=str(self.DURATION_MINUTES))
        self.duration_combo = ttk.Combobox(
            duration_frame, textvariable=self.duration_var, state="readonly", width=6,
            values=[str(m) for m in DURATION_OPTIONS], justify="center",
        )
        self.duration_combo.pack(side="left", padx=(8, 4))
        self.duration_combo.bind("<<ComboboxSelected>>", self._change_duration)

        self.duration_unit_label = tk.Label(duration_frame, text=self.t("minutes_label"), font=(self._text_font, 9))
        self.duration_unit_label.pack(side="left")

        # --- Buttons -----------------------------------------------------
        btn_frame = tk.Frame(self.main)
        btn_frame.pack(fill="x", pady=(4, 14))

        self.btn_start = ttk.Button(btn_frame, text=f"\u25B6  {self.t('btn_start')}", command=self.start_timer, style="Primary.TButton")
        self.btn_pause = ttk.Button(btn_frame, text=f"\u23F8  {self.t('btn_pause')}", command=self.pause_timer, state=tk.DISABLED, style="Secondary.TButton")
        self.btn_reset = ttk.Button(btn_frame, text=f"\u21BA  {self.t('btn_reset')}", command=self.reset_timer, style="Secondary.TButton")

        self.btn_start.pack(side="left", expand=True, fill="x", padx=(0, 6))
        self.btn_pause.pack(side="left", expand=True, fill="x", padx=6)
        self.btn_reset.pack(side="left", expand=True, fill="x", padx=(6, 0))

        self.footer_lbl = tk.Label(
            self.main, text=self.t("footer_hint"),
            font=(self._text_font, 8),
        )
        self.footer_lbl.pack(pady=(6, 0))

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------
    def _theme(self):
        return THEMES[self.CURRENT_THEME]

    def _apply_theme(self):
        t = self._theme()
        self.root.configure(bg=t["bg"])
        self.main.configure(bg=t["bg"])

        for widget in (self.title_lbl, self.subtitle_lbl, self.footer_lbl, self.theme_btn, self.lang_btn):
            widget.configure(bg=t["bg"], fg=t["muted"] if widget in (self.subtitle_lbl, self.footer_lbl) else t["fg"])

        self.theme_btn.configure(
            bg=t["btn_bg"], fg=t["fg"], activebackground=t["ring_track"],
            highlightbackground=t["bg"], highlightcolor=t["bg"],
            text="\u2600" if self.CURRENT_THEME == "dark" else "\U0001F319",
        )

        self.lang_btn.configure(
            bg=t["btn_bg"], fg=t["fg"], activebackground=t["ring_track"],
            highlightbackground=t["bg"], highlightcolor=t["bg"],
            text=f"\U0001F310 {self.CURRENT_LANGUAGE.upper()}",
        )

        for frame in self.main.winfo_children():
            if isinstance(frame, tk.Frame):
                frame.configure(bg=t["bg"])
                for child in frame.winfo_children():
                    if isinstance(child, tk.Label):
                        child.configure(bg=t["bg"], fg=t["muted"])

        self.canvas.configure(bg=t["bg"])
        self.canvas.itemconfig(self._ring_track_id, outline=t["ring_track"])
        self.canvas.itemconfig(self._time_text_id, fill=t["fg"])
        self.canvas.itemconfig(self._minutes_text_id, fill=t["muted"])

        self._update_status_color()
        self._update_button_style(t)
        self._update_ring()

    def _update_button_style(self, t):
        style = ttk.Style()
        theme_name = "EyeTimerModern" + ("Dark" if self.CURRENT_THEME == "dark" else "Light")
        try:
            style.theme_create(theme_name, parent="clam")
        except tk.TclError:
            pass
        style.theme_use(theme_name)

        style.configure(
            "Secondary.TButton", padding=(14, 10), font=(self._text_font, 10, "bold"),
            foreground=t["btn_fg"], background=t["btn_bg"], borderwidth=0, focusthickness=0,
        )
        style.map(
            "Secondary.TButton",
            background=[("active", t["ring_track"]), ("disabled", t["btn_bg"])],
            foreground=[("disabled", t["muted"])],
        )

        style.configure(
            "Primary.TButton", padding=(14, 10), font=(self._text_font, 10, "bold"),
            foreground="#ffffff", background=t["accent"], borderwidth=0, focusthickness=0,
        )
        style.map(
            "Primary.TButton",
            background=[("active", t["accent_hover"]), ("disabled", t["ring_track"])],
            foreground=[("disabled", t["muted"])],
        )

        style.configure(
            "TCombobox",
            padding=4,
            foreground=t["fg"],
            fieldbackground=t["btn_bg"],
            background=t["btn_bg"],
            arrowcolor=t["fg"],
            bordercolor=t["ring_track"],
            lightcolor=t["btn_bg"],
            darkcolor=t["btn_bg"],
            selectbackground=t["btn_bg"],
            selectforeground=t["fg"],
            insertcolor=t["fg"],
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", t["btn_bg"]), ("disabled", t["btn_bg"])],
            foreground=[("readonly", t["fg"]), ("disabled", t["muted"])],
            background=[("readonly", t["btn_bg"]), ("active", t["ring_track"])],
            arrowcolor=[("disabled", t["muted"])],
            bordercolor=[("focus", t["accent"])],
        )

        # The Combobox dropdown is a separate Tk Listbox: its colors
        # don't follow the ttk style and must be set via the option
        # database instead.
        self.root.option_add("*TCombobox*Listbox.background", t["btn_bg"])
        self.root.option_add("*TCombobox*Listbox.foreground", t["fg"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", t["accent"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        self.root.option_add("*TCombobox*Listbox.font", (self._text_font, 10))

    def _update_status_color(self):
        t = self._theme()
        if self._alert_active:
            color = t["status_alert"]
        elif not self.RUNNING and self.REMAINING == self.INTERVAL:
            color = t["status_ready"]
        elif not self.RUNNING:
            color = t["status_paused"]
        else:
            color = t["status_running"]
        self.status_lbl.configure(bg=t["bg"], fg=color)

    def _update_status_label(self):
        """Updates both text AND color of the status label based on the
        current `self._status_key` - used both by timer state changes
        and by a live language switch."""
        text = self.t(self._status_key)
        if self._status_key == "status_alert":
            text = f"\U0001F441  {text}"
        self.status_lbl.configure(text=text)
        self._update_status_color()

    def _toggle_theme(self):
        self.CURRENT_THEME = "light" if self.CURRENT_THEME == "dark" else "dark"
        self._apply_theme()

    # ------------------------------------------------------------------
    # Customizable duration
    # ------------------------------------------------------------------
    def _change_duration(self, _event=None):
        if self.RUNNING:
            return
        try:
            minutes = int(self.duration_var.get())
        except ValueError:
            return
        self.DURATION_MINUTES = minutes
        self.INTERVAL = minutes * 60
        self.REMAINING = self.INTERVAL
        self._update_display()
        self.subtitle_lbl.configure(text=self.t("subtitle", min=self.DURATION_MINUTES))

    # ------------------------------------------------------------------
    # Timer logic
    # ------------------------------------------------------------------
    def start_timer(self):
        if self.RUNNING:
            return
        self._alert_active = False
        self.RUNNING = True
        self.btn_start.configure(state=tk.DISABLED)
        self.btn_pause.configure(state=tk.NORMAL)
        self.duration_combo.configure(state=tk.DISABLED)
        self._status_key = "status_running"
        self._update_status_label()
        threading.Thread(target=self._countdown, daemon=True).start()

    def pause_timer(self):
        self.RUNNING = False
        self.btn_start.configure(state=tk.NORMAL)
        self.btn_pause.configure(state=tk.DISABLED)
        self.duration_combo.configure(state="readonly")
        self._status_key = "status_paused"
        self._update_status_label()

    def reset_timer(self):
        self.RUNNING = False
        self._alert_active = False
        self.REMAINING = self.INTERVAL
        self._update_display()
        self.btn_start.configure(state=tk.NORMAL)
        self.btn_pause.configure(state=tk.DISABLED)
        self.duration_combo.configure(state="readonly")
        self._status_key = "status_ready"
        self._update_status_label()

    def _countdown(self):
        """Runs on a background thread: it only touches plain
        attributes - every widget update goes through `root.after`
        instead, which is the only thread-safe way to talk to Tkinter."""
        while self.RUNNING and self.REMAINING > 0:
            time.sleep(1)
            if not self.RUNNING:
                return
            self.REMAINING -= 1
            self.root.after(0, self._update_display)

        if self.RUNNING and self.REMAINING == 0:
            self.root.after(0, self._trigger_alarm)

    def _update_display(self):
        m, s = divmod(self.REMAINING, 60)
        self.canvas.itemconfig(self._time_text_id, text=f"{m:02d}:{s:02d}")
        self._update_ring()

    def _update_ring(self):
        t = self._theme()
        if self.INTERVAL <= 0:
            fraction = 0
        else:
            fraction = 1 - (self.REMAINING / self.INTERVAL)
        extent = -360 * fraction  # clockwise
        color = t["status_alert"] if self._alert_active else t["ring_progress"]
        self.canvas.itemconfig(self._ring_arc_id, extent=extent, outline=color)

    # ------------------------------------------------------------------
    # Alarm: sound, desktop notification and dialog (all on the UI thread)
    # ------------------------------------------------------------------
    def _trigger_alarm(self):
        self.RUNNING = False
        self._alert_active = True
        self.btn_start.configure(state=tk.NORMAL)
        self.btn_pause.configure(state=tk.DISABLED)
        self._status_key = "status_alert"
        self._update_status_label()
        self._update_ring()

        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(400, lambda: self.root.attributes("-topmost", False))

        threading.Thread(target=self._sound_worker, daemon=True).start()
        self._desktop_notification()
        self._show_alarm_dialog()

    def _sound_path(self):
        return os.path.join(tempfile.gettempdir(), "eye_timer_alarm.wav")

    def _generate_alarm_sound(self, path):
        """Generates a pleasant two-tone 'ding' (with an envelope)
        instead of a single flat beep."""
        framerate = 44100
        duration = 0.9
        n_samples = int(framerate * duration)

        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(framerate)
            for i in range(n_samples):
                t_val = i / framerate
                envelope = math.exp(-3.2 * t_val)
                wave_value = 0.6 * math.sin(2 * math.pi * 880 * t_val)
                wave_value += 0.35 * math.sin(2 * math.pi * 1320 * t_val)
                sample = wave_value * envelope
                sample = max(-1.0, min(1.0, sample))
                value = int(32767 * sample)
                wf.writeframes(struct.pack("<h", value))

    def _sound_worker(self):
        """Runs on a background thread (never on the UI thread):
        generates the audio file and tries the available players in
        sequence, checking each one's actual outcome instead of just
        firing it blindly. If every player fails, the user is still
        warned via a visual flash of the window."""
        path = self._sound_path()
        try:
            # Regenerated on every alarm: avoids ever getting stuck on a
            # file left corrupted/incomplete by a previous run.
            self._generate_alarm_sound(path)
        except Exception as e:
            print(f"\u26A0 Could not generate the audio file: {e}")
            path = None

        candidates = [
            ("pw-play", ["pw-play", path]),
            ("paplay", ["paplay", path]),
            ("aplay", ["aplay", "-q", path]),
            ("mpg123", ["mpg123", "-q", path]),
            ("canberra-gtk-play", ["canberra-gtk-play", "-f", path]),
            # ffplay last: on some setups it returns exit code 0 even
            # when the audio device never actually opened.
            ("ffplay", ["ffplay", "-nodisp", "-autoexit", "-loglevel", "warning", path]),
        ]

        error_hints = (
            "couldn't open audio device", "cannot open", "failed to open",
            "no such file", "no such device", "connection refused",
            "device or resource busy", "unable to open",
        )

        if path:
            for name, cmd in candidates:
                executable = shutil.which(name)
                if not executable:
                    continue
                try:
                    result = subprocess.run(
                        cmd, capture_output=True, timeout=4,
                    )
                    stderr_txt = (result.stderr or b"").decode("utf-8", "ignore").lower()
                    failed = result.returncode != 0 or any(hint in stderr_txt for hint in error_hints)
                    if not failed:
                        return  # sound played successfully
                    print(f"\u26A0 {name} did not play the sound (exit code {result.returncode}), trying the next one")
                except subprocess.TimeoutExpired:
                    return  # likely still playing: treat this as success
                except Exception as e:
                    print(f"\u26A0 {name} is not usable ({e}), trying the next one")
                    continue

        # No working audio player found: terminal bell (audible only if
        # launched from a console) + a visual fallback, so the user
        # still notices the alarm either way.
        try:
            print("\a", end="", flush=True)
        except Exception:
            pass
        print("\u26A0 No working audio player found "
              "(try installing 'pulseaudio-utils' or 'alsa-utils').")
        self.root.after(0, self._flash_window)

    def _flash_window(self, count=6):
        """Visual fallback for when audio isn't available: briefly
        flashes the window background."""
        if count <= 0:
            self._apply_theme()
            return
        t = self._theme()
        color = t["status_alert"] if count % 2 == 0 else t["bg"]
        self.root.configure(bg=color)
        self.main.configure(bg=color)
        self.root.after(180, lambda: self._flash_window(count - 1))

    def _desktop_notification(self):
        if shutil.which("notify-send"):
            try:
                subprocess.Popen(
                    ["notify-send", "-t", "5000",
                     f"\U0001F441 {self.t('notif_title')}", self.t("notif_body")],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass

    def _show_alarm_dialog(self):
        """Custom dialog matching the app's theme, replacing the
        system messagebox which would clash with the app's style."""
        t = self._theme()
        dialog = tk.Toplevel(self.root)
        dialog.title(self.t("dialog_title"))
        dialog.configure(bg=t["surface"])
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        w, h = 320, 190
        self.root.update_idletasks()
        rx, ry = self.root.winfo_x(), self.root.winfo_y()
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        x = rx + (rw - w) // 2
        y = ry + (rh - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")

        tk.Label(
            dialog, text="\U0001F441", font=(self._title_font, 30), bg=t["surface"], fg=t["fg"]
        ).pack(pady=(20, 4))
        tk.Label(
            dialog, text=self.t("dialog_heading"), font=(self._title_font, 13, "bold"),
            bg=t["surface"], fg=t["fg"],
        ).pack()
        tk.Label(
            dialog, text=self.t("dialog_body"),
            font=(self._text_font, 10), bg=t["surface"], fg=t["muted"], justify="center",
        ).pack(pady=(6, 16))

        ok_btn = tk.Button(
            dialog, text=self.t("dialog_ok"), command=dialog.destroy,
            font=(self._text_font, 11, "bold"),
            bg=t["accent"], fg="#ffffff",
            activebackground=t["accent_hover"], activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2",
            highlightthickness=0, padx=18, pady=10,
        )
        ok_btn.pack(pady=(0, 4), ipadx=6)
        ok_btn.focus_set()

        def _on_hover(_e):
            ok_btn.configure(bg=t["accent_hover"])

        def _on_leave(_e):
            ok_btn.configure(bg=t["accent"])

        ok_btn.bind("<Enter>", _on_hover)
        ok_btn.bind("<Leave>", _on_leave)

        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.bind("<Return>", lambda _e: dialog.destroy())
        dialog.wait_window()

        self._alert_active = False
        self.reset_timer()

    # ------------------------------------------------------------------
    def on_close(self):
        self.RUNNING = False
        self.root.destroy()


if __name__ == "__main__":
    app = EyeHealthTimer()
    app.root.protocol("WM_DELETE_WINDOW", app.on_close)
    app.root.mainloop()
