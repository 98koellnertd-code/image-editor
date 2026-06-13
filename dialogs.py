"""Alle Dialoge für Image Editor Pro"""

import io
import tkinter as tk
from tkinter import ttk, colorchooser, messagebox
from pathlib import Path
from PIL import Image

from constants import (BG, PANEL, PANEL2, ACCENT, TEXT, TEXT_DIM, BORDER,
                        BTN, BTN_ACT, SOCIAL_PRESETS, SAVE_TYPES, BLEND_MODES)


def _safe_lbl(label: tk.Label, var, fmt: str = '{}'):
    try:
        label.config(text=fmt.format(var.get()))
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
#  BASIS-DIALOG
# ══════════════════════════════════════════════════════════════════════════════

class _Base(tk.Toplevel):
    def __init__(self, parent, title: str):
        super().__init__(parent)
        self.result = None
        self.title(title)
        self.configure(bg=PANEL)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self._build()
        self.wait_window()

    def _build(self): pass
    def _ok(self):     self.destroy()
    def _cancel(self): self.result = None; self.destroy()

    def _footer(self, parent):
        f = tk.Frame(parent, bg=PANEL)
        f.pack(fill=tk.X, padx=14, pady=(4, 12))
        tk.Button(f, text='Abbrechen', command=self._cancel,
                  bg=BTN, fg=TEXT, bd=0, padx=10, pady=4,
                  relief=tk.FLAT, font=('Segoe UI', 9)).pack(side=tk.RIGHT, padx=4)
        tk.Button(f, text='OK', command=self._ok,
                  bg=ACCENT, fg='#000', bd=0, padx=16, pady=4,
                  relief=tk.FLAT, font=('Segoe UI', 9, 'bold')).pack(side=tk.RIGHT, padx=4)

    def _lbl(self, p, text, dim=False):
        return tk.Label(p, text=text, bg=PANEL,
                        fg=TEXT_DIM if dim else TEXT, font=('Segoe UI', 9))

    def _entry(self, p, var, w=8):
        return ttk.Entry(p, textvariable=var, width=w)

    def _sep(self, p):
        tk.Frame(p, bg=BORDER, height=1).pack(fill=tk.X, padx=0, pady=8)

    def _slider_row(self, parent, label: str, var, mn, mx, fmt='{:.2f}'):
        tk.Label(parent, text=label, bg=PANEL, fg=TEXT,
                 font=('Segoe UI', 8, 'bold')).pack(anchor='w', pady=(6, 0))
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill=tk.X, pady=2)
        lbl = tk.Label(row, text=fmt.format(var.get()),
                       bg=PANEL, fg=TEXT_DIM, font=('Segoe UI', 8), width=6)
        lbl.pack(side=tk.RIGHT)
        ttk.Scale(row, from_=mn, to=mx, variable=var,
                  orient=tk.HORIZONTAL).pack(side=tk.LEFT, fill=tk.X, expand=True)
        var.trace_add('write', lambda *a, l=lbl, v=var, f=fmt: _safe_lbl(l, v, f))


# ══════════════════════════════════════════════════════════════════════════════
#  NEUES BILD
# ══════════════════════════════════════════════════════════════════════════════

class NewImageDialog(_Base):
    def _build(self):
        f = tk.Frame(self, bg=PANEL, padx=20, pady=14); f.pack()
        self._w = tk.IntVar(value=1920)
        self._h = tk.IntVar(value=1080)

        for lbl, var in [('Breite (px):', self._w), ('Höhe (px):', self._h)]:
            row = tk.Frame(f, bg=PANEL); row.pack(fill=tk.X, pady=3)
            self._lbl(row, lbl).pack(side=tk.LEFT, padx=(0, 6))
            self._entry(row, var).pack(side=tk.LEFT)

        self._sep(f)
        self._lbl(f, 'Vorlage wählen:', dim=True).pack(anchor='w', pady=(0, 4))

        scroll = tk.Frame(f, bg=PANEL)
        scroll.pack(fill=tk.X)
        for name, w, h in SOCIAL_PRESETS:
            tk.Button(scroll, text=f'{name}  ({w}×{h})',
                      command=lambda _w=w, _h=h: (self._w.set(_w), self._h.set(_h)),
                      bg=BTN, fg=TEXT, bd=0, padx=8, pady=3, anchor='w',
                      font=('Segoe UI', 8), relief=tk.FLAT,
                      cursor='hand2').pack(fill=tk.X, pady=1)
        self._footer(f)

    def _ok(self):
        try:
            w = max(1, min(self._w.get(), 16000))
            h = max(1, min(self._h.get(), 16000))
            self.result = (w, h, (255, 255, 255, 0))
        except Exception:
            pass
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
#  GRÖßE ÄNDERN
# ══════════════════════════════════════════════════════════════════════════════

class ResizeDialog(_Base):
    def __init__(self, parent, current_size):
        self._ow, self._oh = current_size
        super().__init__(parent, 'Bildgröße ändern')

    def _build(self):
        f = tk.Frame(self, bg=PANEL, padx=20, pady=14); f.pack()
        self._lbl(f, f'Aktuell: {self._ow} × {self._oh} px', dim=True).pack(anchor='w', pady=(0, 8))

        self._w      = tk.IntVar(value=self._ow)
        self._h      = tk.IntVar(value=self._oh)
        self._lock   = tk.BooleanVar(value=True)
        self._method = tk.StringVar(value='Lanczos')
        self._pct    = tk.IntVar(value=100)
        self._updating = [False]

        for lbl, var in [('Breite (px):', self._w), ('Höhe (px):', self._h)]:
            row = tk.Frame(f, bg=PANEL); row.pack(fill=tk.X, pady=3)
            self._lbl(row, lbl).pack(side=tk.LEFT, padx=(0, 6))
            self._entry(row, var).pack(side=tk.LEFT)

        ttk.Checkbutton(f, text='Seitenverhältnis beibehalten',
                        variable=self._lock).pack(anchor='w', pady=4)

        def on_w(*_):
            if self._updating[0] or not self._lock.get(): return
            try:
                self._updating[0] = True
                self._h.set(round(self._w.get() * self._oh / self._ow))
            except Exception: pass
            finally: self._updating[0] = False

        def on_h(*_):
            if self._updating[0] or not self._lock.get(): return
            try:
                self._updating[0] = True
                self._w.set(round(self._h.get() * self._ow / self._oh))
            except Exception: pass
            finally: self._updating[0] = False

        self._w.trace_add('write', on_w)
        self._h.trace_add('write', on_h)

        # Prozent-Eingabe
        pr = tk.Frame(f, bg=PANEL); pr.pack(fill=tk.X, pady=(6, 2))
        self._lbl(pr, 'Skalieren auf:').pack(side=tk.LEFT)
        self._entry(pr, self._pct, w=5).pack(side=tk.LEFT, padx=4)
        self._lbl(pr, '%').pack(side=tk.LEFT)
        tk.Button(pr, text='→', command=self._apply_pct,
                  bg=BTN, fg=TEXT, bd=0, padx=6, relief=tk.FLAT).pack(side=tk.LEFT, padx=4)

        # Interpolation
        self._lbl(f, 'Interpolation:', dim=True).pack(anchor='w', pady=(8, 2))
        ttk.Combobox(f, textvariable=self._method,
                     values=['Lanczos', 'Bicubic', 'Bilinear', 'Nächster Pixel'],
                     state='readonly', width=18).pack(anchor='w')

        # Social-Media-Presets
        self._sep(f)
        self._lbl(f, 'Social-Media-Vorlagen:', dim=True).pack(anchor='w', pady=(0, 4))

        inner = tk.Frame(f, bg=PANEL)
        inner.pack(fill=tk.X)
        for name, w, h in SOCIAL_PRESETS:
            tk.Button(inner, text=f'{name}  ({w}×{h})',
                      command=lambda _w=w, _h=h: (self._lock.set(False),
                                                   self._w.set(_w), self._h.set(_h)),
                      bg=BTN, fg=TEXT, bd=0, padx=6, pady=2, anchor='w',
                      font=('Segoe UI', 8), relief=tk.FLAT,
                      cursor='hand2').pack(fill=tk.X, pady=1)
        self._footer(f)

    def _apply_pct(self):
        try:
            p = self._pct.get() / 100
            self._w.set(round(self._ow * p))
            self._h.set(round(self._oh * p))
        except Exception:
            pass

    def _ok(self):
        try:
            self.result = (max(1, self._w.get()), max(1, self._h.get()), self._method.get())
        except Exception:
            pass
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
#  ARBEITSFLÄCHE
# ══════════════════════════════════════════════════════════════════════════════

class CanvasSizeDialog(_Base):
    def __init__(self, parent, current_size):
        self._ow, self._oh = current_size
        super().__init__(parent, 'Arbeitsfläche ändern')

    def _build(self):
        f = tk.Frame(self, bg=PANEL, padx=20, pady=14); f.pack()
        self._lbl(f, f'Aktuell: {self._ow} × {self._oh} px', dim=True).pack(anchor='w', pady=(0, 8))
        self._w  = tk.IntVar(value=self._ow)
        self._h  = tk.IntVar(value=self._oh)
        self._ah = tk.StringVar(value='mitte')
        self._av = tk.StringVar(value='mitte')

        for lbl, var in [('Breite (px):', self._w), ('Höhe (px):', self._h)]:
            row = tk.Frame(f, bg=PANEL); row.pack(fill=tk.X, pady=3)
            self._lbl(row, lbl).pack(side=tk.LEFT, padx=(0, 6))
            self._entry(row, var).pack(side=tk.LEFT)

        for lbl, var, vals in [
            ('Ankerpunkt H:', self._ah, ['links', 'mitte', 'rechts']),
            ('Ankerpunkt V:', self._av, ['oben',  'mitte', 'unten']),
        ]:
            row = tk.Frame(f, bg=PANEL); row.pack(fill=tk.X, pady=4)
            self._lbl(row, lbl).pack(side=tk.LEFT, padx=(0, 6))
            ttk.Combobox(row, textvariable=var, values=vals,
                         state='readonly', width=10).pack(side=tk.LEFT)
        self._footer(f)

    def _ok(self):
        try:
            self.result = (max(1, self._w.get()), max(1, self._h.get()),
                           self._ah.get(), self._av.get(), (255, 255, 255, 0))
        except Exception:
            pass
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
#  EXPORT
# ══════════════════════════════════════════════════════════════════════════════

class ExportDialog(_Base):
    def __init__(self, parent, path: Path, image: Image.Image, write_cb):
        self._path    = path
        self._image   = image
        self._write   = write_cb
        super().__init__(parent, f'Export: {path.name}')

    def _build(self):
        f = tk.Frame(self, bg=PANEL, padx=20, pady=14); f.pack()
        ext = self._path.suffix.lower()
        self._lbl(f, f'Format: {ext.upper().lstrip(".")}', dim=True).pack(anchor='w')

        self._quality  = tk.IntVar(value=92)
        self._lossless = tk.BooleanVar(value=False)
        self._size_lbl = tk.Label(f, text='', bg=PANEL, fg=ACCENT,
                                   font=('Segoe UI', 9))

        if ext in ('.jpg', '.jpeg', '.webp'):
            self._slider_row(f, 'Qualität', self._quality, 1, 100, '{}')
            self._quality.trace_add('write', lambda *a: self._update_size())

        if ext == '.webp':
            ttk.Checkbutton(f, text='Verlustfrei (lossless)',
                            variable=self._lossless).pack(anchor='w', pady=4)

        self._lbl(f, 'Geschätzte Dateigröße:', dim=True).pack(anchor='w', pady=(8, 0))
        self._size_lbl.pack(anchor='w')
        self._update_size()
        self._footer(f)

    def _update_size(self):
        try:
            import io as _io
            buf = _io.BytesIO()
            ext = self._path.suffix.lower()
            img = self._image.convert('RGB') if ext in ('.jpg', '.jpeg') else self._image
            if ext in ('.jpg', '.jpeg'):
                img.save(buf, 'JPEG', quality=self._quality.get())
            elif ext == '.webp':
                img.save(buf, 'WEBP', quality=self._quality.get(),
                         lossless=self._lossless.get())
            elif ext == '.png':
                img.save(buf, 'PNG')
            else:
                img.save(buf, ext.lstrip('.').upper())
            sz = buf.tell()
            txt = f'{sz/1_000_000:.2f} MB' if sz > 1e6 else f'{sz/1000:.0f} KB'
            self._size_lbl.config(text=txt)
        except Exception:
            self._size_lbl.config(text='—')

    def _ok(self):
        self._write(self._path,
                    quality=self._quality.get(),
                    webp_lossless=self._lossless.get())
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
#  ECKEN ABRUNDEN
# ══════════════════════════════════════════════════════════════════════════════

class RoundCornersDialog(_Base):
    def __init__(self, parent, image_size):
        self._iw, self._ih = image_size
        super().__init__(parent, 'Ecken abrunden')

    def _build(self):
        f = tk.Frame(self, bg=PANEL, padx=20, pady=14); f.pack()
        max_r = min(self._iw, self._ih) // 2
        self._lbl(f, f'Bildgröße: {self._iw}×{self._ih} px  (max. {max_r} px)', dim=True
                  ).pack(anchor='w', pady=(0, 8))

        self._radius = tk.IntVar(value=min(30, max_r))
        lbl = tk.Label(f, text=str(self._radius.get()), bg=PANEL,
                        fg=ACCENT, font=('Segoe UI', 12, 'bold'))
        lbl.pack()
        self._radius.trace_add('write', lambda *a: _safe_lbl(lbl, self._radius, '{}'))

        row = tk.Frame(f, bg=PANEL); row.pack(fill=tk.X, pady=4)
        ttk.Scale(row, from_=1, to=max_r, variable=self._radius,
                  orient=tk.HORIZONTAL, length=220).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._entry(row, self._radius, w=6).pack(side=tk.LEFT, padx=6)
        self._lbl(row, 'px').pack(side=tk.LEFT)

        # Schnellwahl
        self._lbl(f, 'Schnellwahl:', dim=True).pack(anchor='w', pady=(6, 3))
        qf = tk.Frame(f, bg=PANEL); qf.pack(fill=tk.X, pady=(0, 8))
        for pct, lbl_text in [(5, '5 %'), (10, '10 %'), (20, '20 %'), (50, '50 %')]:
            v = max(1, min(int(min(self._iw, self._ih) * pct / 100), max_r))
            tk.Button(qf, text=lbl_text, command=lambda _v=v: self._radius.set(_v),
                      bg=BTN, fg=TEXT, bd=0, padx=8, pady=3,
                      font=('Segoe UI', 8), relief=tk.FLAT,
                      cursor='hand2').pack(side=tk.LEFT, padx=2)

        # Ecken
        self._sep(f)
        self._lbl(f, 'Welche Ecken?').pack(anchor='w', pady=(0, 6))
        self._corners = {k: tk.BooleanVar(value=True) for k in
                          ['oben-links', 'oben-rechts', 'unten-links', 'unten-rechts']}
        LABELS = {'oben-links': '↖ Oben links', 'oben-rechts': '↗ Oben rechts',
                   'unten-links': '↙ Unten links', 'unten-rechts': '↘ Unten rechts'}
        g = tk.Frame(f, bg=PANEL); g.pack(anchor='w')
        for i, (k, v) in enumerate(self._corners.items()):
            ttk.Checkbutton(g, text=LABELS[k], variable=v).grid(
                row=i//2, column=i%2, sticky='w', padx=8, pady=2)

        bf = tk.Frame(f, bg=PANEL); bf.pack(anchor='w', pady=4)
        tk.Button(bf, text='Alle',  command=lambda: [v.set(True)  for v in self._corners.values()],
                  bg=BTN, fg=TEXT, bd=0, padx=8, pady=2, font=('Segoe UI',8), relief=tk.FLAT).pack(side=tk.LEFT, padx=2)
        tk.Button(bf, text='Keine', command=lambda: [v.set(False) for v in self._corners.values()],
                  bg=BTN, fg=TEXT, bd=0, padx=8, pady=2, font=('Segoe UI',8), relief=tk.FLAT).pack(side=tk.LEFT, padx=2)

        self._footer(f)

    def _ok(self):
        try:
            r = max(1, self._radius.get())
            selected = {k for k, v in self._corners.items() if v.get()}
            if not selected:
                messagebox.showwarning('Hinweis', 'Bitte mindestens eine Ecke auswählen.',
                                       parent=self); return
            self.result = (r, selected)
        except Exception:
            pass
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
#  KORREKTUREN (mehrstufig, live)
# ══════════════════════════════════════════════════════════════════════════════

class AdjustDialog(tk.Toplevel):
    """Korrekturen-Dialog mit Live-Anwenden."""
    def __init__(self, parent, sliders: list, apply_cb, title='Korrekturen'):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=PANEL)
        self.resizable(False, False)
        self.transient(parent)
        self._apply = apply_cb
        self._vars: list[tuple[tk.DoubleVar, type]] = []
        f = tk.Frame(self, bg=PANEL, padx=20, pady=16); f.pack()
        for label, Enh, mn, mx, default in sliders:
            var = tk.DoubleVar(value=default)
            self._vars.append((var, Enh))
            tk.Label(f, text=label, bg=PANEL, fg=TEXT,
                     font=('Segoe UI', 9, 'bold')).pack(anchor='w', pady=(6, 0))
            row = tk.Frame(f, bg=PANEL); row.pack(fill=tk.X, pady=2)
            lbl = tk.Label(row, text=f'{default:.2f}', bg=PANEL, fg=TEXT_DIM,
                           font=('Segoe UI', 8), width=5); lbl.pack(side=tk.RIGHT)
            ttk.Scale(row, from_=mn, to=mx, variable=var,
                      orient=tk.HORIZONTAL, length=270).pack(side=tk.LEFT, fill=tk.X, expand=True)
            var.trace_add('write', lambda *a, l=lbl, v=var: _safe_lbl(l, v, '{:.2f}'))
        bf = tk.Frame(f, bg=PANEL); bf.pack(fill=tk.X, pady=(12, 0))
        tk.Button(bf, text='Abbrechen', command=self.destroy,
                  bg=BTN, fg=TEXT, bd=0, padx=10, pady=4, relief=tk.FLAT).pack(side=tk.RIGHT, padx=4)
        tk.Button(bf, text='Anwenden', command=self._commit,
                  bg=ACCENT, fg='#000', bd=0, padx=14, pady=4,
                  relief=tk.FLAT, font=('Segoe UI', 9, 'bold')).pack(side=tk.RIGHT, padx=4)
        self.grab_set()

    def _commit(self):
        self._apply([(E, v.get()) for v, E in self._vars])
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
#  FARB-BALANCE
# ══════════════════════════════════════════════════════════════════════════════

class ColorBalanceDialog(tk.Toplevel):
    def __init__(self, parent, apply_cb):
        super().__init__(parent)
        self.title('Farb-Balance')
        self.configure(bg=PANEL)
        self.resizable(False, False)
        self.transient(parent)
        self._apply = apply_cb
        self._build()
        self.grab_set()

    def _build(self):
        f = tk.Frame(self, bg=PANEL, padx=20, pady=16); f.pack()

        self._r  = tk.IntVar(value=0)
        self._g  = tk.IntVar(value=0)
        self._b  = tk.IntVar(value=0)
        self._sh = tk.DoubleVar(value=0.0)
        self._hi = tk.DoubleVar(value=0.0)
        self._temp = tk.IntVar(value=0)

        for label, var, mn, mx, fmt, color in [
            ('Rot',          self._r,    -100, 100, '{}',    '#ff6666'),
            ('Grün',         self._g,    -100, 100, '{}',    '#66ff88'),
            ('Blau',         self._b,    -100, 100, '{}',    '#66aaff'),
            ('Schatten',     self._sh,   -1.0, 1.0, '{:.2f}','#aaaaaa'),
            ('Lichter',      self._hi,   -1.0, 1.0, '{:.2f}','#ffeeaa'),
            ('Farbtemperatur', self._temp,-100, 100, '{}',   '#ffcc88'),
        ]:
            tk.Label(f, text=label, bg=PANEL, fg=color,
                     font=('Segoe UI', 8, 'bold')).pack(anchor='w', pady=(6, 0))
            row = tk.Frame(f, bg=PANEL); row.pack(fill=tk.X, pady=2)
            lbl = tk.Label(row, text=fmt.format(var.get()), bg=PANEL, fg=TEXT_DIM,
                           font=('Segoe UI', 8), width=6); lbl.pack(side=tk.RIGHT)
            ttk.Scale(row, from_=mn, to=mx, variable=var,
                      orient=tk.HORIZONTAL, length=260).pack(side=tk.LEFT, fill=tk.X, expand=True)
            var.trace_add('write', lambda *a, l=lbl, v=var, fmt_=fmt: _safe_lbl(l, v, fmt_))

        bf = tk.Frame(f, bg=PANEL); bf.pack(fill=tk.X, pady=(12, 0))
        tk.Button(bf, text='Nullstellen', command=self._reset,
                  bg=BTN, fg=TEXT, bd=0, padx=8, pady=4, relief=tk.FLAT).pack(side=tk.LEFT)
        tk.Button(bf, text='Abbrechen', command=self.destroy,
                  bg=BTN, fg=TEXT, bd=0, padx=10, pady=4, relief=tk.FLAT).pack(side=tk.RIGHT, padx=4)
        tk.Button(bf, text='Anwenden', command=self._commit,
                  bg=ACCENT, fg='#000', bd=0, padx=14, pady=4,
                  relief=tk.FLAT, font=('Segoe UI', 9, 'bold')).pack(side=tk.RIGHT, padx=4)

    def _reset(self):
        for v in (self._r, self._g, self._b, self._temp): v.set(0)
        for v in (self._sh, self._hi): v.set(0.0)

    def _commit(self):
        self._apply(self._r.get(), self._g.get(), self._b.get(),
                    self._sh.get(), self._hi.get(), self._temp.get())
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
#  VIGNETTE
# ══════════════════════════════════════════════════════════════════════════════

class VignetteDialog(_Base):
    def _build(self):
        f = tk.Frame(self, bg=PANEL, padx=20, pady=14); f.pack()
        self._strength = tk.DoubleVar(value=0.6)
        self._slider_row(f, 'Stärke (0 = aus, 1 = stark)', self._strength, 0.0, 1.0)
        self._footer(f)

    def _ok(self):
        try: self.result = self._strength.get()
        except Exception: pass
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
#  WASSERZEICHEN
# ══════════════════════════════════════════════════════════════════════════════

class WatermarkDialog(_Base):
    def _build(self):
        f = tk.Frame(self, bg=PANEL, padx=20, pady=14); f.pack()
        self._text     = tk.StringVar(value='© Mein Name')
        self._position = tk.StringVar(value='Unten rechts')
        self._opacity  = tk.IntVar(value=60)
        self._size     = tk.IntVar(value=36)
        self._color    = '#ffffff'

        for lbl, var in [('Text:', self._text)]:
            row = tk.Frame(f, bg=PANEL); row.pack(fill=tk.X, pady=4)
            tk.Label(row, text=lbl, bg=PANEL, fg=TEXT, font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=(0, 6))
            ttk.Entry(row, textvariable=var, width=22).pack(side=tk.LEFT)

        tk.Label(f, text='Position:', bg=PANEL, fg=TEXT, font=('Segoe UI', 9)).pack(anchor='w', pady=(6, 2))
        ttk.Combobox(f, textvariable=self._position,
                     values=['Oben links', 'Oben rechts', 'Mitte', 'Unten links', 'Unten rechts'],
                     state='readonly', width=18).pack(anchor='w')

        self._slider_row(f, 'Deckkraft (%)', self._opacity, 1, 100, '{}')
        self._slider_row(f, 'Schriftgröße', self._size, 8, 200, '{}')

        cf = tk.Frame(f, bg=PANEL); cf.pack(fill=tk.X, pady=6)
        tk.Label(cf, text='Farbe:', bg=PANEL, fg=TEXT, font=('Segoe UI', 9)).pack(side=tk.LEFT)
        self._color_btn = tk.Button(cf, bg=self._color, width=4, bd=2, relief='solid',
                                     cursor='hand2', command=self._pick)
        self._color_btn.pack(side=tk.LEFT, padx=6)
        self._color_hex = tk.Label(cf, text=self._color, bg=PANEL, fg=TEXT_DIM,
                                    font=('Consolas', 9)); self._color_hex.pack(side=tk.LEFT)
        self._footer(f)

    def _pick(self):
        c = colorchooser.askcolor(color=self._color, parent=self)
        if c[1]: self._color = c[1]; self._color_btn.configure(bg=c[1]); self._color_hex.configure(text=c[1])

    def _ok(self):
        txt = self._text.get().strip()
        if not txt: messagebox.showwarning('Hinweis', 'Bitte Text eingeben.', parent=self); return
        self.result = {
            'text': txt, 'position': self._position.get(),
            'opacity': self._opacity.get(), 'font_size': self._size.get(), 'color': self._color,
        }
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
#  RAHMEN / BORDER
# ══════════════════════════════════════════════════════════════════════════════

class BorderDialog(_Base):
    def _build(self):
        f = tk.Frame(self, bg=PANEL, padx=20, pady=14); f.pack()
        self._size  = tk.IntVar(value=20)
        self._inner = tk.BooleanVar(value=False)
        self._color = '#ffffff'

        self._slider_row(f, 'Rahmenbreite (px)', self._size, 1, 200, '{}')
        ttk.Checkbutton(f, text='Innen (Bild nicht vergrößern)',
                        variable=self._inner).pack(anchor='w', pady=4)

        cf = tk.Frame(f, bg=PANEL); cf.pack(fill=tk.X, pady=6)
        tk.Label(cf, text='Farbe:', bg=PANEL, fg=TEXT, font=('Segoe UI', 9)).pack(side=tk.LEFT)
        self._btn = tk.Button(cf, bg=self._color, width=4, bd=2, relief='solid',
                               cursor='hand2', command=self._pick)
        self._btn.pack(side=tk.LEFT, padx=6)
        self._hex_lbl = tk.Label(cf, text=self._color, bg=PANEL, fg=TEXT_DIM,
                                  font=('Consolas', 9)); self._hex_lbl.pack(side=tk.LEFT)
        self._footer(f)

    def _pick(self):
        c = colorchooser.askcolor(color=self._color, parent=self)
        if c[1]: self._color = c[1]; self._btn.configure(bg=c[1]); self._hex_lbl.configure(text=c[1])

    def _ok(self):
        try: self.result = (max(1, self._size.get()), self._color, self._inner.get())
        except Exception: pass
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
#  DROP SHADOW
# ══════════════════════════════════════════════════════════════════════════════

class DropShadowDialog(_Base):
    def _build(self):
        f = tk.Frame(self, bg=PANEL, padx=20, pady=14); f.pack()
        self._ox      = tk.IntVar(value=8)
        self._oy      = tk.IntVar(value=8)
        self._blur    = tk.IntVar(value=12)
        self._opacity = tk.IntVar(value=80)
        self._color   = '#000000'

        self._slider_row(f, 'Versatz X (px)', self._ox,      -50, 50,  '{}')
        self._slider_row(f, 'Versatz Y (px)', self._oy,      -50, 50,  '{}')
        self._slider_row(f, 'Unschärfe (px)', self._blur,      0, 60,  '{}')
        self._slider_row(f, 'Deckkraft (%)',  self._opacity,   0, 100, '{}')

        cf = tk.Frame(f, bg=PANEL); cf.pack(fill=tk.X, pady=6)
        tk.Label(cf, text='Schattenfarbe:', bg=PANEL, fg=TEXT, font=('Segoe UI', 9)).pack(side=tk.LEFT)
        self._btn = tk.Button(cf, bg=self._color, width=4, bd=2, relief='solid',
                               cursor='hand2', command=self._pick)
        self._btn.pack(side=tk.LEFT, padx=6)
        self._footer(f)

    def _pick(self):
        c = colorchooser.askcolor(color=self._color, parent=self)
        if c[1]: self._color = c[1]; self._btn.configure(bg=c[1])

    def _ok(self):
        try:
            self.result = (self._ox.get(), self._oy.get(),
                           self._blur.get(), self._color, self._opacity.get())
        except Exception: pass
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
#  FARB-PALETTE
# ══════════════════════════════════════════════════════════════════════════════

class ColorPaletteDialog(tk.Toplevel):
    def __init__(self, parent, colors: list[str], set_fg_cb):
        super().__init__(parent)
        self.title('Farb-Palette')
        self.configure(bg=PANEL)
        self.resizable(False, False)
        self.transient(parent)
        self._set_fg = set_fg_cb
        self._build(colors)
        self.grab_set()

    def _build(self, colors):
        f = tk.Frame(self, bg=PANEL, padx=20, pady=16); f.pack()
        tk.Label(f, text='Dominante Farben im Bild', bg=PANEL, fg=TEXT_DIM,
                 font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 10))

        grid = tk.Frame(f, bg=PANEL); grid.pack()
        cols_per_row = 4
        for i, color in enumerate(colors):
            row, col = divmod(i, cols_per_row)
            cell = tk.Frame(grid, bg=PANEL)
            cell.grid(row=row, column=col, padx=6, pady=6)
            tk.Button(cell, bg=color, width=4, height=2, bd=2, relief='solid',
                      cursor='hand2',
                      command=lambda c=color: (self._set_fg(c), self.destroy())
                      ).pack()
            tk.Label(cell, text=color, bg=PANEL, fg=TEXT_DIM,
                     font=('Consolas', 8)).pack()

        tk.Button(f, text='Schließen', command=self.destroy,
                  bg=BTN, fg=TEXT, bd=0, padx=12, pady=4,
                  relief=tk.FLAT, font=('Segoe UI', 9)).pack(pady=(12, 0))


# ══════════════════════════════════════════════════════════════════════════════
#  EBENENMODUS (inline, kein Toplevel nötig)
# ══════════════════════════════════════════════════════════════════════════════

class LayerRenameDialog(_Base):
    def __init__(self, parent, current_name: str):
        self._current = current_name
        super().__init__(parent, 'Ebene umbenennen')

    def _build(self):
        f = tk.Frame(self, bg=PANEL, padx=20, pady=14); f.pack()
        self._name = tk.StringVar(value=self._current)
        tk.Label(f, text='Name:', bg=PANEL, fg=TEXT, font=('Segoe UI', 9)).pack(anchor='w')
        e = ttk.Entry(f, textvariable=self._name, width=24); e.pack(pady=4)
        e.select_range(0, tk.END); e.focus_set()
        self.bind('<Return>', lambda e: self._ok())
        self._footer(f)

    def _ok(self):
        n = self._name.get().strip()
        if n: self.result = n
        self.destroy()
