#!/usr/bin/env python3
"""Image Editor Pro v2 — mit Ebenen-System"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser, simpledialog
import tkinter.font as tkfont
import json, os, io, math, threading, sys, subprocess
from pathlib import Path
from PIL import Image, ImageTk, ImageDraw, ImageFilter, ImageEnhance, ImageOps, ImageChops

# ── Eigene Module ──────────────────────────────────────────────────────────────
from constants import *
from layers    import Layer, composite, blend_layers
import effects  as fx
from dialogs   import (NewImageDialog, ResizeDialog, CanvasSizeDialog,
                        ExportDialog, RoundCornersDialog, AdjustDialog,
                        ColorBalanceDialog, VignetteDialog, WatermarkDialog,
                        BorderDialog, DropShadowDialog, ColorPaletteDialog,
                        LayerRenameDialog, _safe_lbl)

# ── Optionale Pakete (nur Verfügbarkeit prüfen – kein Import beim Start!) ───────
import importlib.util as _ilu

REMBG_AVAIL    = _ilu.find_spec('rembg') is not None

# cairosvg braucht die native Cairo-DLL – nur verfügbar wenn import wirklich klappt
def _check_cairosvg() -> bool:
    try:
        import cairosvg  # noqa
        return True
    except Exception:
        return False

CAIROSVG_AVAIL = _check_cairosvg()
PYMUPDF_AVAIL  = _ilu.find_spec('fitz') is not None or _ilu.find_spec('pymupdf') is not None
SVGLIB_AVAIL   = _ilu.find_spec('svglib') is not None and _ilu.find_spec('reportlab') is not None
PSDTOOLS_AVAIL = _ilu.find_spec('psd_tools') is not None

_rembg_remove   = None   # wird beim ersten Aufruf geladen
_rembg_new_sess = None    # rembg.new_session
_rembg_sessions = {}      # model_name -> session (gecacht)

# Standardmodell: isnet-general-use trennt Illustrationen/Logos deutlich
# sauberer als das alte u2net (kaum dunkle Halo-Reste).
DEFAULT_BG_MODEL = 'isnet-general-use'


def _load_rembg():
    """Lädt rembg lazy beim ersten Aufruf (~1 s nur einmal)."""
    global _rembg_remove, _rembg_new_sess
    if _rembg_remove is not None:
        return True
    try:
        os.environ['ORT_DISABLE_ALL_CUDA_PROVIDERS'] = '1'
        import logging; logging.getLogger('onnxruntime').setLevel(logging.ERROR)
        # stderr unterdrücken (C++-Ausgaben von onnxruntime)
        devnull = os.open(os.devnull, os.O_WRONLY)
        saved   = os.dup(2)
        os.dup2(devnull, 2)
        os.close(devnull)
        try:
            from rembg import remove as _fn, new_session as _ns
            _rembg_remove   = _fn
            _rembg_new_sess = _ns
        finally:
            os.dup2(saved, 2)
            os.close(saved)
        return True
    except Exception:
        return False


def _rembg_session(model_name: str):
    """Gecachte rembg-Session für ein Modell (Download beim ersten Mal)."""
    if model_name not in _rembg_sessions:
        _rembg_sessions[model_name] = _rembg_new_sess(model_name)
    return _rembg_sessions[model_name]


def _rembg_cutout(img: Image.Image,
                  model_name: str = DEFAULT_BG_MODEL,
                  alpha_matting: bool = True) -> Image.Image:
    """
    Hintergrund entfernen mit wählbarem Modell + Alpha-Matting.

    Alpha-Matting glättet die Kante und entfernt dunkle Halo-/Geisterpixel,
    die das nackte u2net sonst als Vordergrund stehen lässt.
    """
    try:
        session = _rembg_session(model_name)
    except Exception:
        session = None
    kwargs = {}
    if session is not None:
        kwargs['session'] = session
    if alpha_matting:
        kwargs.update(
            alpha_matting=True,
            alpha_matting_foreground_threshold=240,
            alpha_matting_background_threshold=20,
            alpha_matting_erode_size=11,
        )
    return _rembg_remove(img, **kwargs)


def _load_cairosvg():
    try:
        import cairosvg as _cs
        return _cs
    except Exception:
        return None


def resource_path(rel: str) -> str:
    """Pfad zu einer mitgelieferten Datei – funktioniert im Dev-Modus UND im
    PyInstaller-onefile-Bundle (dort wird alles nach sys._MEIPASS entpackt)."""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


# ══════════════════════════════════════════════════════════════════════════════
#  RUNDER BUTTON  (Tk kann Widgets nicht abrunden → auf Canvas selbst zeichnen)
# ══════════════════════════════════════════════════════════════════════════════

class RoundedButton(tk.Canvas):
    """Flacher Button mit abgerundeten Ecken, Hover- und Aktiv-Zustand."""

    def __init__(self, parent, text='', command=None, *, width=120, height=34,
                 radius=11, fill=BTN, hover=BTN_HOVER, fg=TEXT,
                 active_fill=BTN_ACT, active_fg=ACCENT, container_bg=PANEL,
                 font=('Segoe UI', 10), anchor='center', accent_bar=False):
        super().__init__(parent, width=width, height=height, bd=0,
                         highlightthickness=0, bg=container_bg, takefocus=0)
        self._cmd        = command
        self._radius     = radius
        self._fill       = fill
        self._hover      = hover
        self._fg         = fg
        self._active_fill = active_fill
        self._active_fg   = active_fg
        self._font       = font
        self._text       = text
        self._anchor     = anchor
        self._accent_bar = accent_bar
        self._active     = False
        self.configure(cursor='hand2')
        self.bind('<Configure>', lambda e: self._redraw())
        self.bind('<Enter>',     lambda e: (not self._active) and self._redraw(self._hover))
        self.bind('<Leave>',     lambda e: (not self._active) and self._redraw())
        self.bind('<Button-1>',  lambda e: self._cmd() if self._cmd else None)

    def _rrect(self, x1, y1, x2, y2, r, **kw):
        r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.create_polygon(pts, smooth=True, **kw)

    def _redraw(self, fill=None):
        self.delete('all')
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 1: w = int(self['width'])
        if h <= 1: h = int(self['height'])
        if fill is None:
            fill = self._active_fill if self._active else self._fill
        fg = self._active_fg if self._active else self._fg
        self._rrect(1, 1, w - 1, h - 1, self._radius, fill=fill, outline='')
        if self._accent_bar and self._active:
            self._rrect(3, 6, 6, h - 6, 1, fill=ACCENT, outline='')
        weight = 'bold' if self._active else 'normal'
        if self._anchor == 'w':
            self.create_text(16, h // 2, text=self._text, fill=fg, anchor='w',
                             font=(self._font[0], self._font[1], weight))
        else:
            self.create_text(w // 2, h // 2, text=self._text, fill=fg,
                             font=(self._font[0], self._font[1], weight))

    def set_active(self, on):
        self._active = bool(on)
        self._redraw()

    def configure_text(self, text):
        self._text = text
        self._redraw()


# ══════════════════════════════════════════════════════════════════════════════
#  HAUPTANWENDUNG
# ══════════════════════════════════════════════════════════════════════════════

class ImageEditorApp(tk.Tk):

    MAX_UNDO = 30

    def __init__(self):
        super().__init__()

        # ── Ebenen-Zustand ────────────────────────────────────────────────────
        self.layers:    list[Layer] = []
        self.active_idx: int        = 0
        self.canvas_w:   int        = 800
        self.canvas_h:   int        = 600

        # ── Datei ─────────────────────────────────────────────────────────────
        self.file_path: Path | None = None

        # ── Undo/Redo ─────────────────────────────────────────────────────────
        self.undo_stack: list = []
        self.redo_stack: list = []

        # ── Zoom / Pan ────────────────────────────────────────────────────────
        self.zoom      = 1.0
        self.offset_x  = 0
        self.offset_y  = 0
        self._fit_once = True
        self._pan_data: tuple | None = None   # für mittlere Maustaste
        self._fast_render   = False           # True während Zoom/Pan → NEAREST
        self._quality_after = None            # geplanter scharfer Nachzieh-Render
        self._comp_cache: Image.Image | None = None  # Ebenen-Composite (Pan/Zoom-Cache)

        # ── Werkzeuge ─────────────────────────────────────────────────────────
        self.tool        = tk.StringVar(value='brush')
        self.brush_size  = tk.IntVar(value=10)
        self.brush_opac  = tk.IntVar(value=100)
        self.fg_color    = '#000000'
        self.bg_color    = '#ffffff'
        self._drawing    = False
        self._painting   = False   # True während Pinsel-Drag → NEAREST resampling
        self._last_xy: tuple | None = None
        self._last_mouse: tuple | None = None   # letzte Cursor-Position (Widget-Koord.)
        self._paint_render_pending = False      # gedrosselter Render während des Malens
        self._syncing_controls = False           # True während Panel-Sync (Trace stumm)

        # ── Render-Cache ─────────────────────────────────────────────────────
        self._checker_key: tuple | None = None
        self._checker_img: Image.Image | None = None
        self._patch_imgs: list = []               # PhotoImage-Refs der Mal-Patches
        self._stroke_dirty: tuple | None = None   # bemalter Bereich seit letztem Frame (Bildkoord.)
        self._zoom_render_pending = False         # gedrosselter Zoom-Render (Mausrad)
        self._pan_render_pending  = False         # gedrosselter Pan-Render

        # ── Auswahl ───────────────────────────────────────────────────────────
        self._sel_start: tuple | None        = None
        self._sel_bbox:  tuple | None        = None
        self._sel_mask:  Image.Image | None  = None  # 'L'-Maske für Zauberstab

        # ── Verschieben (Ebene) ──────────────────────────────────────────────
        self._move_start: tuple | None = None  # (ix, iy, layer.ox, layer.oy) bei Drag-Start
        self._resize_start: tuple | None = None  # (handle, ox0, oy0, w0, h0, orig_img) bei Skalieren

        # ── Zauberstab ────────────────────────────────────────────────────────
        self._wand_tol         = tk.IntVar(value=30)
        self._wand_contiguous  = tk.BooleanVar(value=True)
        self._wand_last: tuple | None = None   # letzter Klickpunkt → Live-Toleranz
        self._wand_after = None                # Debounce für Live-Toleranz

        # ── BG-Remover ────────────────────────────────────────────────────────
        self._bg_alpha_thresh  = tk.IntVar(value=10)   # 0=alles behalten, 200=aggressiv

        # ── SEO ───────────────────────────────────────────────────────────────
        self.seo = {k: '' for k in ['alt_text','meta_title','meta_description',
                                     'keywords','tags','author','copyright','category']}
        # .seo.json-Sidecar NUR auf ausdrücklichen Wunsch mitspeichern (Default: aus)
        self._seo_sidecar = tk.BooleanVar(value=False)

        # ── UI ────────────────────────────────────────────────────────────────
        self._layer_thumbs: list = []   # Thumbnails am Leben halten
        self._build_ui()
        self._bind_keys()
        # Pinselgröße/Opazität ändern → Cursor-Ring sofort an letzter Position neu zeichnen
        self.brush_size.trace_add('write', lambda *a: self._refresh_cursor_ring())
        self._update_title()
        self.set_status('Bereit  –  Ctrl+O öffnen  |  Ctrl+N neues Bild')

    # ══════════════════════════════════════════════════════════════════════════
    #  image-Property (Kompatibilität: alle Ops arbeiten auf der aktiven Ebene)
    # ══════════════════════════════════════════════════════════════════════════

    @property
    def active_layer(self) -> 'Layer | None':
        if not self.layers or self.active_idx >= len(self.layers):
            return None
        return self.layers[self.active_idx]

    def _canvas2local(self, x, y):
        """Canvas-Koordinaten → lokale Koordinaten der aktiven Ebene
        (berücksichtigt deren Position ox/oy, falls sie nicht bei (0,0) liegt)."""
        layer = self.active_layer
        if layer is None:
            return x, y
        return x - layer.ox, y - layer.oy

    @property
    def image(self) -> Image.Image | None:
        if not self.layers or self.active_idx >= len(self.layers):
            return None
        return self.layers[self.active_idx].image

    @image.setter
    def image(self, val: Image.Image | None):
        if val is None:
            return
        img = val if val.mode == 'RGBA' else val.convert('RGBA')
        if not self.layers:
            self.canvas_w, self.canvas_h = img.size
            self.layers.append(Layer(img, 'Hintergrund'))
            self.active_idx = 0
        else:
            self.layers[self.active_idx].image = img
            if len(self.layers) == 1:
                self.canvas_w, self.canvas_h = img.size

    # ══════════════════════════════════════════════════════════════════════════
    #  UI AUFBAU
    # ══════════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        self.title('Image Editor Pro')
        self.geometry('1480x920')
        self.minsize(960, 600)
        self.configure(bg=BG)
        self._apply_icon()
        self._ttk_style()
        self._build_menu()
        self._build_toolbar()
        body = tk.Frame(self, bg=BG)
        body.pack(fill=tk.BOTH, expand=True)
        self._build_tools_panel(body)
        self._build_canvas_area(body)
        self._build_right_panel(body)
        self._build_statusbar()
        # Programm immer maximiert starten
        self.after(0, self._maximize)

    def _maximize(self):
        try:
            self.state('zoomed')          # Windows / die meisten Linux-WMs
        except Exception:
            try:
                self.attributes('-zoomed', True)
            except Exception:
                pass
        # Taskleisten-Icon ERST NACH dem Maximieren setzen – der state('zoomed')-
        # Wechsel setzt das Fenster-Icon sonst wieder zurück. Zur Sicherheit zweifach.
        if sys.platform == 'win32':
            self.after(250, self._apply_win_icon)
            self.after(900, self._apply_win_icon)

    def _apply_icon(self):
        """Titelleisten-Icon über Tk (iconbitmap, bewusst NICHT iconphoto).
        Das Taskleisten-Icon wird separat in _apply_win_icon nach dem Maximieren
        gesetzt – Wichtigster Punkt: icon.ico muss überhaupt gefunden werden
        (resource_path findet es auch im PyInstaller-Bundle)."""
        ico = resource_path('icon.ico')
        self._ico_path = ico if os.path.exists(ico) else None
        if not self._ico_path:
            return
        try:
            self.iconbitmap(default=self._ico_path)
        except Exception:
            try:
                self.iconbitmap(self._ico_path)
            except Exception:
                pass

    def _apply_win_icon(self):
        """Taskleisten-/Alt-Tab-Icon robust per WinAPI: WM_SETICON + Klassen-Icon
        (NICHT iconphoto). Idempotent – Icon-Handles werden einmal geladen/gecacht."""
        if sys.platform != 'win32' or not getattr(self, '_ico_path', None):
            return
        try:
            import ctypes
            from ctypes import wintypes
            # Eigene App-ID → Windows behandelt uns als eigenständige App
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    'SiteForge.ImageEditorPro')
            except Exception:
                pass
            # winfo_id() liefert das Tk-Kindfenster – das echte Top-Level ist der Parent
            hwnd = self.winfo_id()
            GetParent = ctypes.windll.user32.GetParent
            GetParent.restype  = wintypes.HWND
            GetParent.argtypes = [wintypes.HWND]
            top = GetParent(hwnd) or hwnd

            # Icons nur EINMAL laden und cachen (verhindert GDI-Handle-Leck bei Re-Aufruf)
            if not getattr(self, '_ico_handles', None):
                IMAGE_ICON      = 1
                LR_LOADFROMFILE = 0x00000010
                LR_DEFAULTSIZE  = 0x00000040
                load = ctypes.windll.user32.LoadImageW
                load.restype  = wintypes.HANDLE
                load.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                                 ctypes.c_int, ctypes.c_int, wintypes.UINT]
                big   = load(None, self._ico_path, IMAGE_ICON, 0,  0,  LR_LOADFROMFILE | LR_DEFAULTSIZE)
                small = load(None, self._ico_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
                self._ico_handles = (big, small)
            big, small = self._ico_handles

            WM_SETICON = 0x0080
            ICON_SMALL, ICON_BIG = 0, 1
            # argtypes/restype zwingend setzen – sonst schneidet ctypes HWND/Handle
            # auf 64-Bit-Windows auf 32 Bit ab und die Nachricht trifft ins Leere.
            send = ctypes.windll.user32.SendMessageW
            send.restype  = wintypes.LPARAM
            send.argtypes = [wintypes.HWND, wintypes.UINT,
                             wintypes.WPARAM, wintypes.LPARAM]
            if big:
                send(top, WM_SETICON, ICON_BIG,   big)
            if small:
                send(top, WM_SETICON, ICON_SMALL, small)

            # Klassen-Icon setzen → bleibt dauerhaft an Taskleiste/Alt-Tab hängen
            GCLP_HICON, GCLP_HICONSM = -14, -34
            setcls = getattr(ctypes.windll.user32, 'SetClassLongPtrW',
                             ctypes.windll.user32.SetClassLongW)
            setcls.restype  = ctypes.c_void_p
            setcls.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
            if big:
                setcls(top, GCLP_HICON,   big)
            if small:
                setcls(top, GCLP_HICONSM, small)
        except Exception:
            pass

    # ── TTK Style ─────────────────────────────────────────────────────────────

    def _ttk_style(self):
        s = ttk.Style(self)
        s.theme_use('clam')
        s.configure('TFrame',        background=PANEL)
        s.configure('TLabel',        background=PANEL, foreground=TEXT, font=('Segoe UI', 9))
        s.configure('TButton',       background=BTN, foreground=TEXT, borderwidth=0,
                    focuscolor=PANEL, padding=(10, 7), font=('Segoe UI', 9),
                    relief='flat')
        s.map('TButton',             background=[('active', BTN_HOVER), ('pressed', BTN_ACT)],
                                     foreground=[('active', ACCENT)])
        s.configure('Accent.TButton', background=ACCENT, foreground='#ffffff',
                    borderwidth=0, padding=(10, 7), font=('Segoe UI', 9, 'bold'))
        s.map('Accent.TButton',      background=[('active', '#6366f1'), ('pressed', '#4338ca')],
                                     foreground=[('active', '#ffffff')])
        s.configure('TCheckbutton',  background=PANEL, foreground=TEXT, font=('Segoe UI', 9))
        s.map('TCheckbutton',        background=[('active', PANEL)],
                                     foreground=[('active', ACCENT)])
        s.configure('TScale',        background=PANEL, troughcolor=BORDER,
                    sliderlength=14, sliderrelief='flat')
        s.map('TScale',              background=[('active', PANEL)])
        s.configure('TCombobox',     fieldbackground=BTN, background=BTN,
                    foreground=TEXT, selectbackground=ACCENT, selectforeground='#ffffff',
                    arrowcolor=TEXT_DIM)
        s.map('TCombobox',           fieldbackground=[('readonly', BTN)],
                                     foreground=[('readonly', TEXT)])
        s.configure('TEntry',        fieldbackground=PANEL2, foreground=TEXT,
                    insertcolor=ACCENT, borderwidth=1, relief='flat')
        s.configure('TNotebook',     background=PANEL, borderwidth=0, tabmargins=0)
        s.configure('TNotebook.Tab', background=BTN, foreground=TEXT_DIM,
                    padding=(12, 5), font=('Segoe UI', 9))
        s.map('TNotebook.Tab',       background=[('selected', PANEL)],
                                     foreground=[('selected', ACCENT)])
        s.configure('Vertical.TScrollbar',   background=BTN, troughcolor=BG,
                    borderwidth=0, arrowcolor=TEXT_DIM, relief='flat')
        s.configure('Horizontal.TScrollbar', background=BTN, troughcolor=BG,
                    borderwidth=0, arrowcolor=TEXT_DIM, relief='flat')

    # ── Menü ──────────────────────────────────────────────────────────────────

    def _build_menu(self):
        def m(parent, label):
            mn = tk.Menu(parent, bg=PANEL, fg=TEXT, activebackground=BTN_ACT,
                         activeforeground=TEXT, borderwidth=0, tearoff=False)
            parent.add_cascade(label=label, menu=mn)
            return mn

        mb = tk.Menu(self, bg=PANEL, fg=TEXT, activebackground=BTN_ACT,
                     activeforeground=TEXT, borderwidth=0, tearoff=False)
        self.configure(menu=mb)

        fm = m(mb, 'Datei')
        fm.add_command(label='Neu…',             accelerator='Ctrl+N', command=self.cmd_new)
        fm.add_command(label='Öffnen…',          accelerator='Ctrl+O', command=self.cmd_open)
        fm.add_separator()
        fm.add_command(label='Speichern',        accelerator='Ctrl+S', command=self.cmd_save)
        fm.add_command(label='Speichern unter…', accelerator='Ctrl+Shift+S', command=self.cmd_save_as)
        fm.add_command(label='Exportieren als…', accelerator='Ctrl+E', command=self.cmd_export)
        fm.add_separator()
        fm.add_command(label='Aus Zwischenablage einfügen', accelerator='Ctrl+V', command=self.cmd_paste_clipboard)
        fm.add_separator()
        fm.add_command(label='Beenden', command=self.destroy)

        em = m(mb, 'Bearbeiten')
        em.add_command(label='Rückgängig',        accelerator='Ctrl+Z', command=self.cmd_undo)
        em.add_command(label='Wiederholen',       accelerator='Ctrl+Y', command=self.cmd_redo)
        em.add_separator()
        em.add_command(label='Alles auswählen',     accelerator='Ctrl+A',  command=self.cmd_select_all)
        em.add_command(label='Auswahl aufheben',    accelerator='Esc',     command=self.cmd_deselect)
        em.add_command(label='Auswahl löschen',     accelerator='Delete',  command=self.cmd_delete_selection)
        em.add_command(label='Auswahl umkehren',    accelerator='Ctrl+I',  command=self.cmd_invert_selection)
        em.add_command(label='Auswahl zuschneiden (aktive Ebene)',         command=self.cmd_crop_selection)

        bm = m(mb, 'Bild')
        bm.add_command(label='Größe ändern…',       command=self.cmd_resize)
        bm.add_command(label='Arbeitsfläche…',      command=self.cmd_canvas_size)
        bm.add_separator()
        bm.add_command(label='90° rechts',          command=lambda: self.cmd_rotate(90))
        bm.add_command(label='90° links',           command=lambda: self.cmd_rotate(-90))
        bm.add_command(label='180°',                command=lambda: self.cmd_rotate(180))
        bm.add_command(label='Benutzerdefiniert…',  command=self.cmd_rotate_custom)
        bm.add_separator()
        bm.add_command(label='Horizontal spiegeln', command=lambda: self.cmd_flip('h'))
        bm.add_command(label='Vertikal spiegeln',   command=lambda: self.cmd_flip('v'))
        bm.add_separator()
        bm.add_command(label='Graustufen',              command=self.cmd_grayscale)
        bm.add_command(label='Invertieren',             command=self.cmd_invert)
        bm.add_command(label='Ecken abrunden…',         command=self.cmd_round_corners)
        bm.add_command(label='Hintergrund entfernen…',  command=self.cmd_remove_bg)
        bm.add_command(label='Alpha-Kante verfeinern…', command=self.cmd_refine_alpha)
        bm.add_command(label='Kanten glätten…',          command=self.cmd_smooth_edges)

        adj = m(mb, 'Korrekturen')
        adj.add_command(label='Helligkeit / Kontrast…', command=self.dlg_brightness)
        adj.add_command(label='Sättigung / Schärfe…',   command=self.dlg_saturation)
        adj.add_command(label='Farb-Balance…',          command=self.dlg_color_balance)
        adj.add_command(label='Weißabgleich…',          command=self.dlg_white_balance)
        adj.add_command(label='Weichzeichner…',         command=self.cmd_blur)
        adj.add_command(label='Unscharf-Maske…',        command=self.cmd_unsharp_mask)
        adj.add_command(label='Rauschreduzierung',      command=self.cmd_denoise)
        adj.add_separator()
        adj.add_command(label='Auto-Kontrast',          command=self.cmd_auto_contrast)
        adj.add_command(label='Farben angleichen',      command=self.cmd_equalize)

        fx_m = m(mb, 'Effekte')
        fx_m.add_command(label='Vignette…',       command=self.dlg_vignette)
        fx_m.add_command(label='Wasserzeichen…',  command=self.dlg_watermark)
        fx_m.add_command(label='Rahmen…',         command=self.dlg_border)
        fx_m.add_command(label='Schlagschatten…', command=self.dlg_drop_shadow)
        fx_m.add_separator()
        fx_m.add_command(label='Sepia',                command=self.cmd_sepia)
        fx_m.add_command(label='Posterisieren…',       command=self.cmd_posterize)
        fx_m.add_command(label='Schwellenwert (S/W)…', command=self.cmd_threshold)
        fx_m.add_command(label='Farbton verschieben…', command=self.cmd_hue_shift)
        fx_m.add_separator()
        fx_m.add_command(label='Verpixeln / Mosaik…',  command=self.cmd_pixelate)
        fx_m.add_command(label='Bewegungsunschärfe…',  command=self.cmd_motion_blur)
        fx_m.add_separator()
        fx_m.add_command(label='Emboss (Relief)',      command=self.cmd_emboss)
        fx_m.add_command(label='Kanten finden',        command=self.cmd_find_edges)
        fx_m.add_command(label='Bleistift-Skizze',     command=self.cmd_sketch)
        fx_m.add_command(label='Ölgemälde…',           command=self.cmd_oil_paint)
        fx_m.add_separator()
        fx_m.add_command(label='Farb-Palette anzeigen', command=self.cmd_color_palette)

        em2 = m(mb, 'Ebenen')
        em2.add_command(label='Neue Ebene',        accelerator='Ctrl+Shift+N', command=self.cmd_new_layer)
        em2.add_command(label='Ebene duplizieren', command=self.cmd_duplicate_layer)
        em2.add_command(label='Ebene löschen',     command=self.cmd_delete_layer)
        em2.add_separator()
        em2.add_command(label='Ebene skalieren…', command=self.cmd_resize_layer)
        em2.add_separator()
        em2.add_command(label='Nach oben',          command=self.cmd_layer_up)
        em2.add_command(label='Nach unten',         command=self.cmd_layer_down)
        em2.add_separator()
        em2.add_command(label='Mit unterer zusammenführen', command=self.cmd_merge_down)
        em2.add_command(label='Alle zusammenführen',        command=self.cmd_flatten)

        vm = m(mb, 'Ansicht')
        vm.add_command(label='Einzoomen',          accelerator='Ctrl++', command=self.zoom_in)
        vm.add_command(label='Auszoomen',          accelerator='Ctrl+-', command=self.zoom_out)
        vm.add_command(label='An Fenster anpassen',accelerator='Ctrl+0', command=self.zoom_fit)
        vm.add_command(label='100 %',              accelerator='Ctrl+1', command=self.zoom_actual)

        sm = m(mb, 'SEO')
        sm.add_command(label='SEO-Panel', command=self._focus_seo)
        sm.add_command(label='Metadaten importieren…', command=self.cmd_import_seo)
        sm.add_command(label='Metadaten exportieren…', command=self.cmd_export_seo)

        hm = m(mb, 'Hilfe')
        hm.add_command(label='Pakete installieren (rembg / cairosvg)', command=self.cmd_install_deps)
        hm.add_command(label='Über…', command=self.cmd_about)

    # ── Toolbar ───────────────────────────────────────────────────────────────

    def _build_toolbar(self):
        tb = tk.Frame(self, bg=TOOLBAR, height=46)
        tb.pack(fill=tk.X, side=tk.TOP)
        tb.pack_propagate(False)
        # Accent-Linie unter Toolbar
        tk.Frame(self, bg=ACCENT, height=1).pack(fill=tk.X, side=tk.TOP)

        tb_font = ('Segoe UI', 9)
        _meas   = tkfont.Font(family='Segoe UI', size=9)

        def btn(txt, cmd, tip=''):
            w = _meas.measure(txt) + 22
            b = RoundedButton(tb, text=txt, command=cmd, width=w, height=32,
                              radius=9, fill=TOOLBAR, hover=BTN_HOVER, fg=TEXT,
                              container_bg=TOOLBAR, font=tb_font)
            b.pack(side=tk.LEFT, padx=2, pady=7)
            if tip:
                self._tooltip(b, tip)
            return b

        def sep():
            tk.Frame(tb, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=10)

        btn('📄 Neu',          self.cmd_new,          'Neu (Ctrl+N)')
        btn('📂 Öffnen',       self.cmd_open,         'Öffnen (Ctrl+O)')
        btn('💾 Speichern',    self.cmd_save,         'Speichern (Ctrl+S)')
        btn('📤 Export',       self.cmd_export,       'Exportieren (Ctrl+E)')
        sep()
        btn('↩ Undo',          self.cmd_undo,         'Rückgängig (Ctrl+Z)')
        btn('↪ Redo',          self.cmd_redo,         'Wiederholen (Ctrl+Y)')
        sep()
        btn('🔍+',              self.zoom_in,          'Einzoomen (Ctrl++)')
        btn('🔍–',              self.zoom_out,         'Auszoomen (Ctrl+-)')
        btn('⊞ Fit',           self.zoom_fit,         'An Fenster (Ctrl+0)')
        sep()
        btn('✂ Crop',          self.cmd_crop_selection, 'Auswahl zuschneiden (aktive Ebene)')
        btn('↕ Größe',         self.cmd_resize,       'Größe ändern')
        btn('🪄 BG entfernen', self.cmd_remove_bg,    'Hintergrund entfernen (KI)')
        btn('✨ Kanten',       self.cmd_smooth_edges, 'Kanten glätten (Freisteller-Antialiasing)')
        btn('⬛ Radius',       self.cmd_round_corners,'Ecken abrunden')
        sep()
        btn('🌫 Vignette',     self.dlg_vignette,     'Vignette hinzufügen')
        btn('💧 Schatten',     self.dlg_drop_shadow,  'Schlagschatten')
        btn('🏷 Wasserzeichen',self.dlg_watermark,    'Wasserzeichen')
        btn('🧹 Meta entfernen', self.cmd_strip_metadata,
            'Alle Metadaten löschen (SEO-Felder + eingebettete Tags)')

        self._zoom_lbl = tk.Label(tb, text='100 %', bg=TOOLBAR, fg=ACCENT,
                                   font=('Segoe UI', 9, 'bold'))
        self._zoom_lbl.pack(side=tk.RIGHT, padx=12)

    # ── Werkzeug-Panel (links) ─────────────────────────────────────────────────

    @staticmethod
    def _sec(parent, text):
        """Farbiger Abschnitts-Header für Panels."""
        tk.Frame(parent, bg=BORDER, height=1).pack(fill=tk.X, padx=4, pady=(6, 0))
        tk.Label(parent, text=text, bg=PANEL, fg=ACCENT,
                 font=('Segoe UI', 7, 'bold')).pack(anchor='w', padx=8, pady=(3, 2))

    def _build_tools_panel(self, parent):
        f = tk.Frame(parent, bg=PANEL, width=185)
        f.pack(side=tk.LEFT, fill=tk.Y)
        f.pack_propagate(False)

        self._sec(f, 'WERKZEUGE')

        TOOLS = [
            ('cursor',     '↖',  'Auswahl (Rechteck)'),
            ('magic_wand', '⚡', 'Zauberstab (Farbauswahl)'),
            ('brush',      '🖌', 'Pinsel'),
            ('eraser',     '◻',  'Radierer'),
            ('fill',       '🪣', 'Füllen'),
            ('eyedrop',    '🔬', 'Pipette'),
            ('text',       'T',   'Text'),
            ('crop',       '⊹',  'Zuschneiden'),
            ('move',       '✥',  'Verschieben (aktive Ebene)'),
        ]
        LABELS = {'cursor': 'Auswahl', 'magic_wand': 'Zauber', 'brush': 'Pinsel',
                  'eraser': 'Radierer', 'fill': 'Füllen', 'eyedrop': 'Pipette',
                  'text': 'Text', 'crop': 'Crop', 'move': 'Verschieben'}
        self._tool_btns: dict[str, RoundedButton] = {}
        for name, icon, tip in TOOLS:
            b = RoundedButton(f, text=f'{icon}   {LABELS.get(name, "")}', anchor='w',
                              command=lambda n=name: self._select_tool(n),
                              width=116, height=38, radius=12,
                              fill=BTN, hover=BTN_HOVER, fg=TEXT,
                              active_fill=BTN_ACT, active_fg=ACCENT,
                              container_bg=PANEL, font=('Segoe UI', 10),
                              accent_bar=True)
            b.pack(fill=tk.X, padx=8, pady=3)
            b.set_active(name == self.tool.get())
            self._tool_btns[name] = b
            self._tooltip(b, tip)

        # Farb-Swatches (abgerundet, auf Canvas gezeichnet) + Hex-Eingabe
        self._sec(f, 'FARBE')
        sw = tk.Canvas(f, bg=PANEL, width=66, height=58, bd=0,
                       highlightthickness=0, cursor='hand2')
        sw.pack(pady=4)
        self._swatch = sw
        sw.bind('<Button-1>', self._swatch_click)
        self._draw_swatches()

        tk.Label(f, text='Vordergrund', bg=PANEL, fg=TEXT_DIM, font=('Segoe UI', 7)).pack(pady=(2,0))
        self._fg_hex = tk.StringVar(value=self.fg_color)
        e1 = tk.Entry(f, textvariable=self._fg_hex, width=9, bg=PANEL2, fg=ACCENT,
                       insertbackground=ACCENT, bd=1, relief='flat',
                       font=('Consolas', 9), justify='center')
        e1.pack(padx=6, pady=1)
        e1.bind('<Return>',   lambda _: self._apply_hex_fg())
        e1.bind('<FocusOut>', lambda _: self._apply_hex_fg())

        tk.Label(f, text='Hintergrund', bg=PANEL, fg=TEXT_DIM, font=('Segoe UI', 7)).pack(pady=(4,0))
        self._bg_hex = tk.StringVar(value=self.bg_color)
        e2 = tk.Entry(f, textvariable=self._bg_hex, width=9, bg=PANEL2, fg=TEXT_DIM,
                       insertbackground=TEXT, bd=1, relief='flat',
                       font=('Consolas', 9), justify='center')
        e2.pack(padx=6, pady=1)
        e2.bind('<Return>',   lambda _: self._apply_hex_bg())
        e2.bind('<FocusOut>', lambda _: self._apply_hex_bg())

        # Pinsel
        self._sec(f, 'PINSEL')
        for lbl, var in [('Größe', self.brush_size), ('Opazität', self.brush_opac)]:
            tk.Label(f, text=lbl, bg=PANEL, fg=TEXT_DIM, font=('Segoe UI', 7)).pack(pady=(4,0))
            self._stepper_row(f, var, 1, (200 if lbl == 'Größe' else 100))

        # Zauberstab
        self._sec(f, 'ZAUBERSTAB')
        tk.Label(f, text='Toleranz', bg=PANEL, fg=TEXT_DIM, font=('Segoe UI', 7)).pack(pady=(4,0))
        self._stepper_row(f, self._wand_tol, 0, 255)
        self._wand_tol.trace_add('write', lambda *a: self._wand_live_update())
        ttk.Checkbutton(f, text='Zusammenhängend',
                        variable=self._wand_contiguous,
                        command=self._wand_live_update).pack(padx=6, anchor='w', pady=2)
        tk.Button(f, text='Auswahl löschen  Del',
                  command=self.cmd_delete_selection,
                  bg=BTN, fg=TEXT, bd=0, padx=4, pady=3,
                  font=('Segoe UI', 7), relief=tk.FLAT, cursor='hand2'
                  ).pack(fill=tk.X, padx=6, pady=2)

    def _stepper_row(self, parent, var, mn, mx):
        """Schieber + Zahl-Eingabefeld + −/+ Schrittknöpfe für eine IntVar.

        Erlaubt drei Bedienarten: Ziehen am Schieber, exakte Zahl ins Feld
        tippen (Return/Verlassen übernimmt) oder schrittweise mit − / +.
        """
        row = tk.Frame(parent, bg=PANEL); row.pack(fill=tk.X, padx=6, pady=1)

        def clamp(v):
            try:
                v = int(round(float(v)))
            except (TypeError, ValueError):
                return None
            return max(mn, min(mx, v))

        def step(d):
            cur = clamp(var.get())
            nv  = clamp((mn if cur is None else cur) + d)
            if nv is not None:
                var.set(nv)

        def from_entry(_=None):
            nv = clamp(ent_var.get())
            if nv is not None:
                var.set(nv)
            ent_var.set(str(var.get()))          # Eingabe normalisieren

        bcfg = dict(bg=BTN, fg=TEXT, bd=0, width=2, font=('Segoe UI', 9, 'bold'),
                    relief=tk.FLAT, cursor='hand2', activebackground=BORDER)
        tk.Button(row, text='−', command=lambda: step(-1), **bcfg).pack(side=tk.LEFT)
        ttk.Scale(row, from_=mn, to=mx, variable=var,
                  orient=tk.HORIZONTAL).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        tk.Button(row, text='+', command=lambda: step(1), **bcfg).pack(side=tk.LEFT)

        ent_var = tk.StringVar(value=str(var.get()))
        ent = tk.Entry(row, textvariable=ent_var, width=4, bg=PANEL2, fg=ACCENT,
                       insertbackground=ACCENT, bd=1, relief='flat',
                       font=('Consolas', 9), justify='center')
        ent.pack(side=tk.LEFT, padx=(4, 0))
        ent.bind('<Return>',   from_entry)
        ent.bind('<FocusOut>', from_entry)

        # Schieber-/Knopf-Änderungen ins Eingabefeld spiegeln (nur wenn nicht
        # gerade dort getippt wird, sonst springt der Cursor)
        def _mirror(*_):
            if parent.focus_get() is not ent:
                ent_var.set(str(var.get()))
        var.trace_add('write', _mirror)
        return row

    # ── Canvas-Bereich ─────────────────────────────────────────────────────────

    def _build_canvas_area(self, parent):
        frame = tk.Frame(parent, bg=BG)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._canvas = tk.Canvas(frame, bg=CANVAS_BG, bd=0,
                                  highlightthickness=0, cursor='crosshair')
        vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL,   command=self._canvas.yview)
        hsb = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=self._canvas.xview)
        self._canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self._canvas.pack(fill=tk.BOTH, expand=True)
        self._canvas.create_text(400, 255,
            text='Image Editor Pro',
            fill=ACCENT, font=('Segoe UI', 22, 'bold'), justify=tk.CENTER, tags='welcome')
        self._canvas.create_text(400, 292,
            text='Bild öffnen   Ctrl+O     Neues Bild   Ctrl+N\nZwischenablage   Ctrl+V',
            fill=TEXT_DIM, font=('Segoe UI', 10), justify=tk.CENTER, tags='welcome')

    # ── Rechtes Panel ─────────────────────────────────────────────────────────

    def _build_right_panel(self, parent):
        f = tk.Frame(parent, bg=PANEL, width=300)
        f.pack(side=tk.RIGHT, fill=tk.Y)
        f.pack_propagate(False)
        # Rechte Seite 50/50 vertikal teilen (wie in Photoshop):
        #   oben  → Infos/Korrekturen/SEO als Reiter
        #   unten → das Ebenen-Panel, dauerhaft sichtbar
        f.columnconfigure(0, weight=1)
        f.rowconfigure(0, weight=1, uniform='rp')
        f.rowconfigure(1, weight=1, uniform='rp')

        top = tk.Frame(f, bg=PANEL)
        top.grid(row=0, column=0, sticky='nsew')
        nb = ttk.Notebook(top)
        nb.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._right_nb = nb
        self._build_info_tab(nb)
        self._build_adjust_tab(nb)
        self._build_seo_tab(nb)

        bottom = tk.Frame(f, bg=PANEL)
        bottom.grid(row=1, column=0, sticky='nsew')
        self._build_layers_panel(bottom)

    def _build_info_tab(self, nb):
        tab = tk.Frame(nb, bg=PANEL); nb.add(tab, text=' Info ')
        self._info_v: dict[str, tk.Label] = {}
        for i, (lbl, key) in enumerate([
            ('Datei', 'file'), ('Format', 'fmt'), ('Abmessungen', 'dim'),
            ('Farbmodus', 'mode'), ('Dateigröße', 'fsize'), ('Zoom', 'zoom'),
            ('Ebenen', 'layers'),
        ]):
            tk.Label(tab, text=lbl+':', bg=PANEL, fg=TEXT_DIM,
                     font=('Segoe UI', 8, 'bold'), anchor='w'
                     ).grid(row=i, column=0, sticky='w', padx=10, pady=4)
            lbl2 = tk.Label(tab, text='—', bg=PANEL, fg=TEXT,
                            font=('Segoe UI', 8), anchor='w', wraplength=160)
            lbl2.grid(row=i, column=1, sticky='w', padx=4, pady=4)
            self._info_v[key] = lbl2

    def _build_layers_panel(self, parent):
        tab = tk.Frame(parent, bg=PANEL); tab.pack(fill=tk.BOTH, expand=True)
        self._layers_tab = tab

        # Eigener Titel, da das Panel kein Reiter mehr ist
        hdr = tk.Frame(tab, bg=PANEL); hdr.pack(fill=tk.X, padx=6, pady=(6, 0))
        tk.Label(hdr, text='Ebenen', bg=PANEL, fg=TEXT,
                 font=('Segoe UI', 9, 'bold'), anchor='w').pack(side=tk.LEFT)
        tk.Frame(tab, bg=BORDER, height=1).pack(fill=tk.X, padx=6, pady=(4, 0))

        # Blend-Modus + Deckkraft
        ctrl = tk.Frame(tab, bg=PANEL); ctrl.pack(fill=tk.X, padx=6, pady=4)
        tk.Label(ctrl, text='Modus:', bg=PANEL, fg=TEXT_DIM, font=('Segoe UI', 8)).pack(side=tk.LEFT)
        self._blend_var = tk.StringVar(value='Normal')
        ttk.Combobox(ctrl, textvariable=self._blend_var, values=BLEND_MODES,
                     state='readonly', width=14).pack(side=tk.LEFT, padx=4)
        self._blend_var.trace_add('write', lambda *a: self._on_blend_changed())

        orow = tk.Frame(tab, bg=PANEL); orow.pack(fill=tk.X, padx=6)
        tk.Label(orow, text='Deckkraft:', bg=PANEL, fg=TEXT_DIM, font=('Segoe UI', 8)).pack(side=tk.LEFT)
        self._layer_opac = tk.IntVar(value=100)
        self._opac_lbl   = tk.Label(orow, text='100 %', bg=PANEL, fg=TEXT_DIM, font=('Segoe UI', 8), width=5)
        self._opac_lbl.pack(side=tk.RIGHT)
        ttk.Scale(orow, from_=0, to=100, variable=self._layer_opac,
                  orient=tk.HORIZONTAL).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self._layer_opac.trace_add('write', lambda *a: self._on_layer_opac_changed())

        # Buttons
        bf = tk.Frame(tab, bg=PANEL); bf.pack(fill=tk.X, padx=6, pady=4)
        for txt, cmd, tip in [
            ('+',  self.cmd_new_layer,       'Neue Ebene'),
            ('🗑', self.cmd_delete_layer,    'Löschen'),
            ('⎘',  self.cmd_duplicate_layer, 'Duplizieren'),
            ('↑',  self.cmd_layer_up,        'Nach oben'),
            ('↓',  self.cmd_layer_down,      'Nach unten'),
            ('⬇', self.cmd_merge_down,       'Mit unterer zusammenführen'),
            ('⊞',  self.cmd_flatten,         'Alle zusammenführen'),
        ]:
            b = tk.Button(bf, text=txt, command=cmd, bg=BTN, fg=TEXT,
                          bd=0, padx=5, pady=2, font=('Segoe UI', 10),
                          relief=tk.FLAT, cursor='hand2')
            b.pack(side=tk.LEFT, padx=1)
            self._tooltip(b, tip)

        tk.Frame(tab, bg=BORDER, height=1).pack(fill=tk.X, padx=6, pady=2)

        # Ebenen-Liste
        lf = tk.Frame(tab, bg=PANEL); lf.pack(fill=tk.BOTH, expand=True)
        self._layer_canvas = tk.Canvas(lf, bg=PANEL, highlightthickness=0)
        lvsb = ttk.Scrollbar(lf, orient=tk.VERTICAL, command=self._layer_canvas.yview)
        self._layer_canvas.configure(yscrollcommand=lvsb.set)
        lvsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._layer_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._layer_list = tk.Frame(self._layer_canvas, bg=PANEL)
        self._layer_canvas.create_window((0, 0), window=self._layer_list, anchor='nw', tags='lw')
        self._layer_list.bind('<Configure>', lambda e: (
            self._layer_canvas.configure(scrollregion=self._layer_canvas.bbox('all'))))
        self._layer_canvas.bind('<Configure>', lambda e:
            self._layer_canvas.itemconfig('lw', width=e.width))

    def _build_adjust_tab(self, nb):
        tab = tk.Frame(nb, bg=PANEL); nb.add(tab, text=' Korrekturen ')
        f = tk.Frame(tab, bg=PANEL); f.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        self._adj_vars: dict[str, tk.DoubleVar] = {}
        for lbl, key, mn, mx in [
            ('Helligkeit',  'brightness',  0.1, 3.0),
            ('Kontrast',    'contrast',    0.1, 3.0),
            ('Sättigung',   'saturation',  0.0, 3.0),
            ('Schärfe',     'sharpness',   0.0, 3.0),
        ]:
            tk.Label(f, text=lbl, bg=PANEL, fg=TEXT,
                     font=('Segoe UI', 8, 'bold')).pack(anchor='w', pady=(6, 0))
            row = tk.Frame(f, bg=PANEL); row.pack(fill=tk.X, pady=2)
            var = tk.DoubleVar(value=1.0)
            self._adj_vars[key] = var
            lbl2 = tk.Label(row, text='1.00', bg=PANEL, fg=TEXT_DIM,
                            font=('Segoe UI', 8), width=5); lbl2.pack(side=tk.RIGHT)
            ttk.Scale(row, from_=mn, to=mx, variable=var,
                      orient=tk.HORIZONTAL).pack(side=tk.LEFT, fill=tk.X, expand=True)
            var.trace_add('write', lambda *a, l=lbl2, v=var: _safe_lbl(l, v, '{:.2f}'))
        tk.Frame(f, bg=BORDER, height=1).pack(fill=tk.X, pady=8)
        ttk.Button(f, text='✔  Anwenden',   command=self.cmd_apply_adj).pack(fill=tk.X)
        ttk.Button(f, text='↺  Zurücksetzen', command=self._reset_adj).pack(fill=tk.X, pady=4)
        ttk.Button(f, text='🎨  Farb-Balance…', command=self.dlg_color_balance).pack(fill=tk.X)

    def _build_seo_tab(self, nb):
        tab = tk.Frame(nb, bg=PANEL); nb.add(tab, text=' SEO ')
        self._seo_tab = tab
        outer = tk.Canvas(tab, bg=PANEL, highlightthickness=0)
        vsb   = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=outer.yview)
        outer.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        inner = tk.Frame(outer, bg=PANEL)
        outer.create_window((0, 0), window=inner, anchor='nw', tags='sw')
        inner.bind('<Configure>', lambda e: outer.configure(scrollregion=outer.bbox('all')))
        outer.bind('<Configure>', lambda e: outer.itemconfig('sw', width=e.width))

        self._seo_w: dict[str, tk.Widget] = {}
        FIELDS = [
            ('Alt-Text',          'alt_text',         'entry', 'Bildbeschreibung für Suchmaschinen'),
            ('Meta-Titel',        'meta_title',        'entry', 'Seitentitel (≤ 60 Zeichen)'),
            ('Meta-Beschreibung', 'meta_description',  'text',  'Kurzbeschreibung (≤ 160 Zeichen)'),
            ('Keywords',          'keywords',          'entry', 'Kommagetrennte Schlüsselwörter'),
            ('Tags',              'tags',              'entry', 'Bildtags (kommagetrennt)'),
            ('Autor',             'author',            'entry', 'Name des Urhebers'),
            ('Copyright',         'copyright',         'entry', '© Jahr Name'),
            ('Kategorie',         'category',          'entry', 'z. B. Produkt, Natur …'),
        ]
        for label, key, wtype, hint in FIELDS:
            rf = tk.Frame(inner, bg=PANEL); rf.pack(fill=tk.X, padx=8, pady=5)
            tk.Label(rf, text=label, bg=PANEL, fg=TEXT,
                     font=('Segoe UI', 8, 'bold'), anchor='w').pack(anchor='w')
            tk.Label(rf, text=hint, bg=PANEL, fg=TEXT_DIM,
                     font=('Segoe UI', 7), anchor='w').pack(anchor='w')
            if wtype == 'entry':
                var = tk.StringVar(value=self.seo.get(key, ''))
                var.trace_add('write', lambda *a, k=key, v=var: self.seo.__setitem__(k, v.get()))
                ttk.Entry(rf, textvariable=var).pack(fill=tk.X, pady=2)
                self._seo_w[key] = var
            else:
                t = tk.Text(rf, height=3, bg=PANEL2, fg=TEXT, insertbackground=TEXT,
                            bd=1, relief='flat', font=('Segoe UI', 9), wrap=tk.WORD)
                t.pack(fill=tk.X, pady=2)
                t.bind('<KeyRelease>', lambda e, k=key, w=t:
                       self.seo.__setitem__(k, w.get('1.0', tk.END).strip()))
                self._seo_w[key] = t
        tk.Frame(inner, bg=BORDER, height=1).pack(fill=tk.X, padx=8, pady=8)
        ttk.Checkbutton(
            inner, variable=self._seo_sidecar,
            text='Beim Speichern .seo.json-Datei mit anlegen'
            ).pack(anchor='w', padx=8, pady=2)
        tk.Label(inner, text='(Standard: aus – es wird sonst keine Begleitdatei erzeugt)',
                 bg=PANEL, fg=TEXT_DIM, font=('Segoe UI', 7),
                 anchor='w', wraplength=250).pack(anchor='w', padx=8, pady=(0, 4))
        ttk.Button(inner, text='💾 SEO-JSON speichern',
                   command=self.cmd_export_seo).pack(fill=tk.X, padx=8, pady=4)
        ttk.Button(inner, text='📂 SEO-JSON laden',
                   command=self.cmd_import_seo).pack(fill=tk.X, padx=8, pady=2)

    def _build_statusbar(self):
        tk.Frame(self, bg=BORDER, height=1).pack(fill=tk.X, side=tk.BOTTOM)
        sb = tk.Frame(self, bg=TOOLBAR, height=22)
        sb.pack(fill=tk.X, side=tk.BOTTOM)
        sb.pack_propagate(False)
        self._status = tk.Label(sb, text='', bg=TOOLBAR, fg=TEXT_DIM,
                                 font=('Segoe UI', 8), anchor='w')
        self._status.pack(side=tk.LEFT, padx=10)
        self._pos_lbl = tk.Label(sb, text='', bg=TOOLBAR, fg=TEXT_DIM,
                                  font=('Consolas', 8))
        self._pos_lbl.pack(side=tk.RIGHT, padx=10)

    # ══════════════════════════════════════════════════════════════════════════
    #  BINDINGS
    # ══════════════════════════════════════════════════════════════════════════

    def _bind_keys(self):
        self.bind('<Control-n>', lambda e: self.cmd_new())
        self.bind('<Control-o>', lambda e: self.cmd_open())
        self.bind('<Control-s>', lambda e: self.cmd_save())
        self.bind('<Control-S>', lambda e: self.cmd_save_as())
        self.bind('<Control-e>', lambda e: self.cmd_export())
        self.bind('<Control-z>', lambda e: self.cmd_undo())
        self.bind('<Control-y>', lambda e: self.cmd_redo())
        self.bind('<Control-v>', lambda e: self.cmd_paste_clipboard())
        self.bind('<Control-a>', lambda e: self.cmd_select_all())
        self.bind('<Escape>',    lambda e: self.cmd_deselect())
        self.bind('<Delete>',    lambda e: self.cmd_delete_selection())
        self.bind('<Control-i>', lambda e: self.cmd_invert_selection())
        self.bind('<Control-plus>',      lambda e: self.zoom_in())
        self.bind('<Control-minus>',     lambda e: self.zoom_out())
        self.bind('<Control-0>',         lambda e: self.zoom_fit())
        self.bind('<Control-1>',         lambda e: self.zoom_actual())
        self.bind('<Control-Shift-N>',   lambda e: self.cmd_new_layer())

        c = self._canvas
        c.bind('<Button-1>',        self._on_down)
        c.bind('<B1-Motion>',       self._on_drag)
        c.bind('<ButtonRelease-1>', self._on_up)
        c.bind('<Motion>',          self._on_move)
        c.bind('<MouseWheel>',         self._on_wheel)          # normal: vertikal scrollen
        c.bind('<Control-MouseWheel>', self._on_wheel_zoom)     # Strg: zoomen
        c.bind('<Alt-MouseWheel>',     self._on_wheel_hscroll)  # Alt: horizontal scrollen
        # Linux: Mausrad kommt als Button-4/5 statt <MouseWheel>
        c.bind('<Button-4>',           lambda e: self._on_wheel(e, 120))
        c.bind('<Button-5>',           lambda e: self._on_wheel(e, -120))
        c.bind('<Control-Button-4>',   lambda e: self._on_wheel_zoom(e, 120))
        c.bind('<Control-Button-5>',   lambda e: self._on_wheel_zoom(e, -120))
        c.bind('<Alt-Button-4>',       lambda e: self._on_wheel_hscroll(e, 120))
        c.bind('<Alt-Button-5>',       lambda e: self._on_wheel_hscroll(e, -120))
        c.bind('<Button-2>',        self._on_pan_start)
        c.bind('<B2-Motion>',       self._on_pan_drag)
        c.bind('<Configure>',       self._on_canvas_cfg)
        c.bind('<Enter>',           self._on_enter)
        c.bind('<Leave>',           self._on_leave)

    # ══════════════════════════════════════════════════════════════════════════
    #  RENDERING
    # ══════════════════════════════════════════════════════════════════════════

    # ── Checker-Cache ──────────────────────────────────────────────────────────

    def _get_checker(self, dw: int, dh: int, cs: int) -> Image.Image:
        key = (dw, dh, cs)
        if self._checker_key != key:
            self._checker_key = key
            self._checker_img = self._make_checker(dw, dh, cs)
        return self._checker_img

    @staticmethod
    def _make_checker(dw: int, dh: int, cs: int) -> Image.Image:
        """Schachbrettmuster als PIL-Bild – O(W/cs + H/cs) statt O(W*H) Python-Loops."""
        c1, c2 = (249, 249, 251), (214, 216, 221)
        ts = cs * 2
        tile = Image.new('RGB', (ts, ts))
        tile.paste(Image.new('RGB', (cs, cs), c1), (0,  0))
        tile.paste(Image.new('RGB', (cs, cs), c2), (cs, 0))
        tile.paste(Image.new('RGB', (cs, cs), c2), (0,  cs))
        tile.paste(Image.new('RGB', (cs, cs), c1), (cs, cs))
        cols = (dw + ts - 1) // ts + 1
        wide = Image.new('RGB', (cols * ts, ts))
        for col in range(cols):
            wide.paste(tile, (col * ts, 0))
        wide = wide.crop((0, 0, dw, ts))
        result = Image.new('RGB', (dw, dh))
        y = 0
        while y < dh:
            h = min(ts, dh - y)
            result.paste(wide.crop((0, 0, dw, h)), (0, y))
            y += ts
        return result

    def _render(self):
        if not self.layers:
            return
        # Einzelne, normale Ebene → direkt verwenden (kein Voll-Composite nötig).
        # Das spart beim Malen pro Frame eine komplette Leinwand-Komposition.
        vis = [l for l in self.layers if l.visible]
        single = (len(vis) == 1 and vis[0].opacity == 100
                  and vis[0].blend_mode == 'Normal'
                  and vis[0].image.size == (self.canvas_w, self.canvas_h)
                  and vis[0].ox == 0 and vis[0].oy == 0)
        if single:
            comp = vis[0].image
        elif (self._fast_render and self._comp_cache is not None
                and self._comp_cache.size == (self.canvas_w, self.canvas_h)):
            # Pan/Zoom ändern keine Pixel → Composite wiederverwenden
            comp = self._comp_cache
        else:
            comp = composite(self.layers, self.canvas_w, self.canvas_h)
        self._comp_cache = comp
        c    = self._canvas
        c.delete('img'); c.delete('sel'); c.delete('welcome'); c.delete('movebox')
        # Mal-Patches verwerfen – das frische Vollbild enthält bereits alle Striche
        c.delete('paintpatch')
        self._patch_imgs.clear()
        self._stroke_dirty = None

        z      = self.zoom
        ox, oy = self.offset_x, self.offset_y
        vw = max(c.winfo_width(), 1)
        vh = max(c.winfo_height(), 1)

        # Sichtbarer Bereich in Canvas-Koordinaten (berücksichtigt Scrollbars)
        vx0, vy0 = c.canvasx(0),  c.canvasy(0)
        vx1, vy1 = c.canvasx(vw), c.canvasy(vh)

        # → nur den TATSÄCHLICH sichtbaren Bildausschnitt skalieren.
        #   Das verhindert das Einfrieren bei hohem Zoom (sonst würde das
        #   komplette Bild auf riesige dw×dh hochskaliert).
        ix0 = max(0,             int(math.floor((vx0 - ox) / z)))
        iy0 = max(0,             int(math.floor((vy0 - oy) / z)))
        ix1 = min(self.canvas_w, int(math.ceil ((vx1 - ox) / z)))
        iy1 = min(self.canvas_h, int(math.ceil ((vy1 - oy) / z)))

        if ix1 > ix0 and iy1 > iy0:
            crop = comp.crop((ix0, iy0, ix1, iy1))
            dw = max(1, int(round((ix1 - ix0) * z)))
            dh = max(1, int(round((iy1 - iy0) * z)))

            cs      = max(8, min(20, int(12 * min(z, 1.5))))
            checker = self._get_checker(dw, dh, cs).copy()

            # Schnelles NEAREST bei Zoom/Pan/Pinsel oder extremem Zoom; sonst scharf
            fast = self._fast_render or self._painting or z > 8
            rs   = Image.NEAREST if fast else Image.LANCZOS
            disp = crop.resize((dw, dh), rs)

            # Zauberstab-Auswahl: EXAKTE Form als Tönung + Kontur einblenden
            # (statt nur das grobe Begrenzungsrechteck).
            if self._sel_mask is not None:
                m = self._sel_mask.crop((ix0, iy0, ix1, iy1)).resize((dw, dh), Image.NEAREST)
                r, g, b = self._hex2rgb(ACCENT)
                overlay = Image.new('RGBA', (dw, dh), (0, 0, 0, 0))
                overlay.paste(Image.new('RGBA', (dw, dh), (r, g, b, 80)), mask=m)
                edge = m.filter(ImageFilter.FIND_EDGES)
                overlay.paste(Image.new('RGBA', (dw, dh), (r, g, b, 255)), mask=edge)
                disp = Image.alpha_composite(disp.convert('RGBA'), overlay)

            checker.paste(disp, mask=disp.split()[3])

            self.photo_img = ImageTk.PhotoImage(checker)
            c.create_image(ox + ix0 * z, oy + iy0 * z, anchor='nw',
                           image=self.photo_img, tags='img')

        # Rechteck-Auswahl (Auswahl-Werkzeug) als gestrichelter Rahmen.
        # Bei der Zauberstab-Maske zeigt stattdessen die Tönung oben die Form.
        if self._sel_mask is None and self._sel_bbox is not None:
            x1, y1, x2, y2 = self._sel_bbox
            c.create_rectangle(
                x1 * z + ox, y1 * z + oy, x2 * z + ox, y2 * z + oy,
                outline=ACCENT, width=1, dash=(4, 3), tags='sel')

        # Verschieben/Skalieren-Werkzeug: Rahmen + Eck-Griffe der aktiven Ebene
        if self.tool.get() == 'move':
            layer = self.active_layer
            if layer is not None:
                lox1, loy1 = layer.ox, layer.oy
                lox2, loy2 = lox1 + layer.image.width, loy1 + layer.image.height
                sx1, sy1 = lox1 * z + ox, loy1 * z + oy
                sx2, sy2 = lox2 * z + ox, loy2 * z + oy
                c.create_rectangle(sx1, sy1, sx2, sy2,
                                    outline=ACCENT, width=1, dash=(4, 3), tags='movebox')
                hs = 5  # Griffgröße (Bildschirm-Pixel)
                for hx, hy in ((sx1, sy1), (sx2, sy1), (sx1, sy2), (sx2, sy2)):
                    c.create_rectangle(hx-hs, hy-hs, hx+hs, hy+hs,
                                        fill=ACCENT, outline=PANEL, width=1, tags='movebox')

        # Cursor-Ring zuletzt neu zeichnen, damit er beim Malen NICHT verdeckt wird
        if self._last_mouse is not None:
            self._draw_cursor_ring(*self._last_mouse)

        full_w = self.canvas_w * z
        full_h = self.canvas_h * z
        c.configure(scrollregion=(
            min(0, ox), min(0, oy),
            max(vw, full_w + ox), max(vh, full_h + oy)))

        self._update_info()
        # _update_layer_panel_controls() NICHT hier aufrufen – das setzt
        # _blend_var/_layer_opac, deren Traces erneut _render() auslösen
        # (Feedback-Schleife → ~45 ms pro Frame, Pinsel ruckelt). Es wird
        # stattdessen bei Ebenenwechsel über _refresh_layer_list() aktualisiert.

    def _schedule_quality_render(self, delay=140):
        """Nach Zoom/Pan kurz warten und dann scharf (LANCZOS) nachzeichnen."""
        if self._quality_after is not None:
            try: self.after_cancel(self._quality_after)
            except Exception: pass
        def finish():
            self._quality_after = None
            self._fast_render = False
            self._render()
        self._quality_after = self.after(delay, finish)

    def _c2i(self, cx, cy):
        # Widget- → Canvas-Koordinaten (Scrollbars) → Bild-Koordinaten
        cx = self._canvas.canvasx(cx)
        cy = self._canvas.canvasy(cy)
        return (cx - self.offset_x) / self.zoom, (cy - self.offset_y) / self.zoom

    def _i2s(self, ix, iy):
        """Bild-Koordinaten → Canvas-Koordinaten (Zoom/Pan, OHNE Scrollbar-Versatz –
        passend zu den Koordinaten, die create_rectangle()/create_image() erwarten)."""
        return ix * self.zoom + self.offset_x, iy * self.zoom + self.offset_y

    def _move_handle_at(self, wx, wy):
        """Liefert 'nw'/'ne'/'sw'/'se', wenn (wx, wy) (Widget-Koordinaten) auf einem
        Skalier-Griff der aktiven Ebene liegt, sonst None."""
        layer = self.active_layer
        if layer is None:
            return None
        cx, cy = self._canvas.canvasx(wx), self._canvas.canvasy(wy)
        lox1, loy1 = layer.ox, layer.oy
        lox2, loy2 = lox1 + layer.image.width, loy1 + layer.image.height
        sx1, sy1 = self._i2s(lox1, loy1)
        sx2, sy2 = self._i2s(lox2, loy2)
        tol = 8
        for name, hx, hy in (('nw', sx1, sy1), ('ne', sx2, sy1),
                              ('sw', sx1, sy2), ('se', sx2, sy2)):
            if abs(cx - hx) <= tol and abs(cy - hy) <= tol:
                return name
        return None

    def _point_in_active_layer_box(self, ix, iy):
        """Prüft, ob Bild-Koordinaten (ix, iy) innerhalb der aktiven Ebene liegen."""
        layer = self.active_layer
        if layer is None:
            return False
        return (layer.ox <= ix < layer.ox + layer.image.width
                and layer.oy <= iy < layer.oy + layer.image.height)

    # ══════════════════════════════════════════════════════════════════════════
    #  MAUS
    # ══════════════════════════════════════════════════════════════════════════

    def _on_down(self, ev):
        self._last_mouse = (ev.x, ev.y)
        if not self.layers:
            return
        ix, iy = self._c2i(ev.x, ev.y)
        tool = self.tool.get()
        if tool in ('brush', 'eraser'):
            self._push_undo()
            self._drawing = True
            self._last_xy = (ix, iy)
            self._paint_dot(ix, iy, tool)
            self._render()
        elif tool == 'fill':
            self._push_undo()
            self._flood_fill(int(ix), int(iy))
        elif tool == 'eyedrop':
            self._eyedrop(int(ix), int(iy))
        elif tool == 'cursor':
            self._sel_start = (ix, iy)
            self._sel_bbox  = None
            self._sel_mask  = None
        elif tool == 'magic_wand':
            self._magic_wand_select(int(ix), int(iy))
        elif tool == 'text':
            self._add_text(ix, iy)
        elif tool == 'move':
            layer = self.active_layer
            if layer is None:
                return
            if layer.locked:
                self.set_status('Ebene ist gesperrt – kann nicht verschoben werden')
                return
            handle = self._move_handle_at(ev.x, ev.y)
            self._push_undo()
            if handle is not None:
                self._resize_start = (handle, layer.ox, layer.oy,
                                       layer.image.width, layer.image.height,
                                       layer.image)
                self._move_start = None
            else:
                self._resize_start = None
                self._move_start = (ix, iy, layer.ox, layer.oy)

    def _on_drag(self, ev):
        self._last_mouse = (ev.x, ev.y)
        if not self.layers:
            return
        ix, iy = self._c2i(ev.x, ev.y)
        tool = self.tool.get()
        if tool in ('brush', 'eraser') and self._drawing and self._last_xy:
            self._painting = True
            x0, y0 = self._last_xy
            self._paint_line(x0, y0, ix, iy, tool)
            self._accumulate_dirty(x0, y0, ix, iy)
            self._last_xy = (ix, iy)
            # Strich ist gezeichnet – Anzeige nur gedrosselt aktualisieren,
            # damit sich bei schneller Bewegung keine Renders stauen (kein Ruckeln).
            self._request_paint_render()
        elif tool == 'cursor' and self._sel_start:
            sx, sy = self._sel_start
            self._sel_bbox = (min(sx, ix), min(sy, iy), max(sx, ix), max(sy, iy))
            self._sel_mask = None
            self._render()
        elif tool == 'move' and self._resize_start:
            handle, ox0, oy0, w0, h0, orig_img = self._resize_start
            layer = self.active_layer
            if layer is not None:
                ix_r, iy_r = round(ix), round(iy)
                if handle == 'nw':
                    ax, ay = ox0 + w0, oy0 + h0
                    nx1, ny1 = min(ix_r, ax - 1), min(iy_r, ay - 1)
                    nw, nh = ax - nx1, ay - ny1
                elif handle == 'ne':
                    ax, ay = ox0, oy0 + h0
                    nx1, ny1 = ax, min(iy_r, ay - 1)
                    nw, nh = max(1, ix_r - ax), ay - ny1
                elif handle == 'sw':
                    ax, ay = ox0 + w0, oy0
                    nx1, ny1 = min(ix_r, ax - 1), ay
                    nw, nh = ax - nx1, max(1, iy_r - ay)
                else:  # 'se'
                    ax, ay = ox0, oy0
                    nx1, ny1 = ax, ay
                    nw, nh = max(1, ix_r - ax), max(1, iy_r - ay)
                nw, nh = max(1, nw), max(1, nh)
                layer.ox, layer.oy = nx1, ny1
                layer.image = orig_img.resize((nw, nh), Image.NEAREST)
                self._comp_cache = None
                self._render()
        elif tool == 'move' and self._move_start:
            sx, sy, sox, soy = self._move_start
            layer = self.active_layer
            if layer is not None:
                layer.ox = sox + round(ix - sx)
                layer.oy = soy + round(iy - sy)
                self._comp_cache = None
                self._render()

    def _request_paint_render(self):
        """Render während eines Pinselstrichs zusammenfassen → max. ~1 pro 20 ms.
        Verhindert das Stauen vieler teurer Renders bei schneller Mausbewegung."""
        # Ring sofort an die neue Position setzen (fühlt sich direkt an)
        if self._last_mouse is not None:
            self._draw_cursor_ring(*self._last_mouse)
        if self._paint_render_pending:
            return
        self._paint_render_pending = True
        self.after(20, self._do_paint_render)

    def _do_paint_render(self):
        self._paint_render_pending = False
        # Nur den bemalten Bereich nachziehen (billig). Geht das nicht
        # (Mehrebenen, Fehler, zu viele Patches) → sicherer voller Render.
        if not self._blit_dirty_patch():
            self._render()

    def _accumulate_dirty(self, x0, y0, x1, y1):
        """Bemalten Bereich dieses Segments zum Dirty-Rechteck dazurechnen (Bildkoord.)."""
        r = max(1, self.brush_size.get() // 2) + 2   # +2 px Rand gegen Skalierungs-Nähte
        nx0, ny0 = min(x0, x1) - r, min(y0, y1) - r
        nx1, ny1 = max(x0, x1) + r, max(y0, y1) + r
        if self._stroke_dirty is None:
            self._stroke_dirty = (nx0, ny0, nx1, ny1)
        else:
            ox0, oy0, ox1, oy1 = self._stroke_dirty
            self._stroke_dirty = (min(ox0, nx0), min(oy0, ny0),
                                  max(ox1, nx1), max(oy1, ny1))

    def _direct_comp(self):
        """Composite-Bild, falls genau EINE normale, deckende Ebene in Leinwandgröße
        gezeigt wird – dann ist das Ebenenbild selbst das Composite (Voraussetzung
        fürs schnelle Patch-Rendern). Sonst None → voller Render nötig."""
        vis = [l for l in self.layers if l.visible]
        if (len(vis) == 1 and vis[0].opacity == 100
                and vis[0].blend_mode == 'Normal'
                and vis[0].image.size == (self.canvas_w, self.canvas_h)
                and vis[0].ox == 0 and vis[0].oy == 0):
            return vis[0].image
        return None

    def _blit_dirty_patch(self) -> bool:
        """Zeichnet nur das seit dem letzten Frame bemalte Rechteck als kleines
        Bild über die Leinwand (statt den ganzen Viewport neu aufzubauen).
        Tk repaintet dabei nur diese kleine Fläche → kein Ruckeln.
        Liefert False, wenn ein voller Render nötig/sicherer ist."""
        bb = self._stroke_dirty
        if bb is None:
            return True                      # nichts Neues zu zeigen
        comp = self._direct_comp()
        if comp is None:
            return False                     # Mehrebenen → voller Render
        # Patches nicht unbegrenzt anhäufen: ab und zu flach rendern.
        if len(self._patch_imgs) >= 48:
            return False
        self._stroke_dirty = None
        try:
            c = self._canvas
            z = self.zoom
            ox, oy = self.offset_x, self.offset_y
            bx0 = max(0, int(math.floor(bb[0])))
            by0 = max(0, int(math.floor(bb[1])))
            bx1 = min(self.canvas_w, int(math.ceil(bb[2])))
            by1 = min(self.canvas_h, int(math.ceil(bb[3])))
            if bx1 <= bx0 or by1 <= by0:
                return True
            crop = comp.crop((bx0, by0, bx1, by1))
            dw = max(1, int(round((bx1 - bx0) * z)))
            dh = max(1, int(round((by1 - by0) * z)))
            disp = crop.resize((dw, dh), Image.NEAREST)
            cs   = max(8, min(20, int(12 * min(z, 1.5))))
            checker = self._make_checker(dw, dh, cs)   # frisch, ohne den Cache zu stören
            if disp.mode == 'RGBA':
                checker.paste(disp, mask=disp.split()[3])
            else:
                checker.paste(disp)
            ph = ImageTk.PhotoImage(checker)
            self._patch_imgs.append(ph)
            c.create_image(ox + bx0 * z, oy + by0 * z, anchor='nw',
                           image=ph, tags='paintpatch')
            c.tag_raise('cursor_ring')        # Pinsel-Ring bleibt oben
            return True
        except Exception:
            return False                     # bei jedem Fehler → voller Render

    def _on_up(self, ev):
        was_painting = self._painting
        self._drawing  = False
        self._painting = False
        self._last_xy  = None
        if self.tool.get() == 'cursor':
            self._sel_start = None
        if self.tool.get() == 'move':
            if self._resize_start:
                handle, ox0, oy0, w0, h0, orig_img = self._resize_start
                layer = self.active_layer
                if layer is not None and layer.image.size != orig_img.size:
                    # Finaler hochwertiger Resize-Pass (während des Ziehens wurde
                    # zur Performance mit NEAREST skaliert)
                    layer.image = orig_img.resize(layer.image.size, Image.LANCZOS)
                    self._comp_cache = None
                    self._render()
                    self.set_status(f'Ebene "{layer.name}" skaliert: '
                                     f'{layer.image.width} × {layer.image.height} px')
            self._resize_start = None
            self._move_start = None
        if was_painting:
            # ausstehenden gedrosselten Render verwerfen, einmal scharf nachzeichnen
            self._paint_render_pending = False
            self._render()

    def _on_move(self, ev):
        self._last_mouse = (ev.x, ev.y)
        if not self.layers:
            return
        ix, iy = self._c2i(ev.x, ev.y)
        ix_i, iy_i = int(ix), int(iy)
        if 0 <= ix_i < self.canvas_w and 0 <= iy_i < self.canvas_h:
            try:
                lx, ly = self._canvas2local(ix_i, iy_i)
                if 0 <= lx < self.image.width and 0 <= ly < self.image.height:
                    px = self.image.getpixel((lx, ly))
                    self._pos_lbl.config(text=f'X:{ix_i}  Y:{iy_i}    {px}')
                else:
                    self._pos_lbl.config(text=f'X:{ix_i}  Y:{iy_i}')
            except Exception:
                self._pos_lbl.config(text=f'X:{ix_i}  Y:{iy_i}')
        self._draw_cursor_ring(ev.x, ev.y)

    def _draw_cursor_ring(self, sx, sy):
        """Zeigt bei Pinsel/Radierer einen Kreis in Pinselgröße am Cursor."""
        c = self._canvas
        c.delete('cursor_ring')
        if not self.layers or self.tool.get() not in ('brush', 'eraser'):
            return
        cx, cy = c.canvasx(sx), c.canvasy(sy)
        r = max(1, self.brush_size.get() / 2) * self.zoom
        col = ACCENT2 if self.tool.get() == 'eraser' else CURSOR_RING
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      outline=col, width=1, tags='cursor_ring')
        c.create_line(cx - 4, cy, cx + 4, cy, fill=col, tags='cursor_ring')
        c.create_line(cx, cy - 4, cx, cy + 4, fill=col, tags='cursor_ring')

    def _refresh_cursor_ring(self):
        """Ring an der letzten Mausposition neu zeichnen (z. B. nach Größenänderung)."""
        if self._last_mouse is not None:
            self._draw_cursor_ring(*self._last_mouse)

    def _on_enter(self, ev):
        """Maus betritt die Leinwand → Pinsel-Ring sofort zeigen (nicht erst
        beim ersten Bewegen)."""
        self._last_mouse = (ev.x, ev.y)
        self._draw_cursor_ring(ev.x, ev.y)   # zeichnet nur bei Pinsel/Radierer

    def _on_leave(self, ev):
        self._last_mouse = None
        self._canvas.delete('cursor_ring')

    # Mausrad – Schrittweite pro „Rasterung" (delta ist auf Windows ein Vielfaches von 120)
    _WHEEL_STEP = 80          # Pixel pro Rad-Tick beim Scrollen

    def _on_wheel(self, ev, delta=None):
        """Normales Scrollen → Bild hoch/runter."""
        d = ev.delta if delta is None else delta
        self._pan_by(0, (d / 120) * self._WHEEL_STEP)

    def _on_wheel_hscroll(self, ev, delta=None):
        """Alt + Scrollen → Bild nach links/rechts."""
        d = ev.delta if delta is None else delta
        self._pan_by((d / 120) * self._WHEEL_STEP, 0)

    def _on_wheel_zoom(self, ev, delta=None):
        """Strg + Scrollen → zum Mauszeiger ein-/auszoomen."""
        d = ev.delta if delta is None else delta
        self._zoom_at(ev.x, ev.y, 1.15 if d > 0 else 1 / 1.15)

    def _pan_by(self, dx, dy):
        """Bildausschnitt um (dx, dy) Canvas-Pixel verschieben. Rad hoch = Bild runter."""
        self.offset_x += dx
        self.offset_y += dy
        self._fast_render = True
        self._request_pan_render()

    def _zoom_at(self, sx, sy, factor):
        """Zoom zum Mauszeiger – der Punkt unter dem Cursor bleibt fix."""
        old = self.zoom
        new = max(0.02, min(32.0, old * factor))
        if abs(new - old) < 1e-9:
            return
        cx, cy = self._canvas.canvasx(sx), self._canvas.canvasy(sy)
        ix = (cx - self.offset_x) / old
        iy = (cy - self.offset_y) / old
        self.offset_x = cx - ix * new
        self.offset_y = cy - iy * new
        self.zoom = new
        self._zoom_lbl.config(text=f'{self.zoom * 100:.0f} %')
        self._last_mouse = (sx, sy)
        self._fast_render = True
        # Mehrere Mausrad-Ticks zu EINEM Render bündeln (die Rechnung oben ist
        # billig; nur der teure Neuaufbau wird gebündelt) → kein Stau beim schnellen Scrollen.
        self._request_zoom_render()

    def _request_zoom_render(self):
        if self._zoom_render_pending:
            return
        self._zoom_render_pending = True
        self.after_idle(self._do_zoom_render)

    def _do_zoom_render(self):
        self._zoom_render_pending = False
        self._render()
        if self._last_mouse is not None:
            self._draw_cursor_ring(*self._last_mouse)
        self._schedule_quality_render()

    def _on_pan_start(self, ev):
        self._pan_data = (ev.x, ev.y, self.offset_x, self.offset_y)

    def _on_pan_drag(self, ev):
        if self._pan_data:
            sx, sy, ox, oy = self._pan_data
            self.offset_x = ox + (ev.x - sx)
            self.offset_y = oy + (ev.y - sy)
            self._fast_render = True
            # Pan-Bewegungen bündeln, damit sich bei schnellem Ziehen keine Renders stauen.
            self._request_pan_render()

    def _request_pan_render(self):
        if self._pan_render_pending:
            return
        self._pan_render_pending = True
        self.after_idle(self._do_pan_render)

    def _do_pan_render(self):
        self._pan_render_pending = False
        self._render()
        self._schedule_quality_render()

    def _on_canvas_cfg(self, ev):
        if self.layers and self._fit_once:
            self._fit_once = False
            self.after(60, self.zoom_fit)

    # ══════════════════════════════════════════════════════════════════════════
    #  ZEICHENWERKZEUGE
    # ══════════════════════════════════════════════════════════════════════════

    def _paint_dot(self, x, y, tool):
        x, y = self._canvas2local(x, y)
        r2 = max(1, self.brush_size.get() // 2)
        draw = ImageDraw.Draw(self.image)
        draw.ellipse([x-r2, y-r2, x+r2, y+r2], fill=self._tool_fill(tool))

    def _paint_line(self, x0, y0, x1, y1, tool):
        x0, y0 = self._canvas2local(x0, y0)
        x1, y1 = self._canvas2local(x1, y1)
        fill = self._tool_fill(tool)
        r2   = max(1, self.brush_size.get() // 2)
        draw = ImageDraw.Draw(self.image)
        steps = max(1, int(math.hypot(x1-x0, y1-y0) * 1.5))
        for i in range(steps + 1):
            t = i / steps
            px = x0 + (x1-x0)*t
            py = y0 + (y1-y0)*t
            draw.ellipse([px-r2, py-r2, px+r2, py+r2], fill=fill)

    def _tool_fill(self, tool):
        if tool == 'eraser':
            return (0, 0, 0, 0) if self.image.mode == 'RGBA' else self._hex2rgb(self.bg_color)
        op  = int(self.brush_opac.get() / 100 * 255)
        r, g, b = self._hex2rgb(self.fg_color)
        return (r, g, b, op) if self.image.mode == 'RGBA' else (r, g, b)

    def _flood_fill(self, x, y):
        if self.image is None:
            return
        lx, ly = self._canvas2local(x, y)
        if not (0 <= lx < self.image.width and 0 <= ly < self.image.height):
            self.set_status('Außerhalb der Ebene')
            return
        import numpy as np
        r, g, b = self._hex2rgb(self.fg_color)
        rgba = self.image.mode == 'RGBA'
        fill = (r, g, b, 255) if rgba else (r, g, b)
        try:
            tol = self._wand_tol.get()
            # Gleiche Vergleichslogik wie der Zauberstab → Transparenz wird korrekt
            # als Grenze erkannt (premultipliziertes Alpha), Toleranz-Regler greift.
            cmp_arr = self._wand_compare_arr(self.image)       # (h, w, C)
            target  = cmp_arr[ly, lx].astype(np.int16)
            match   = np.abs(cmp_arr - target).max(axis=2) <= tol
            region  = self._flood_bool(match, lx, ly)          # zusammenhängend ab Klick
            px   = np.array(self.image)                        # (h, w, C)
            px[region] = fill
            self.image = Image.fromarray(px, self.image.mode)
            n = int(region.sum())
            self.set_status(f'Füllen: {n:,} Pixel  (Toleranz {tol})')
        except Exception as e:
            self.set_status(f'Füllen: {e}')
        self._render()

    @staticmethod
    def _wand_compare_arr(img):
        """Array für den Farbvergleich (Zauberstab & Füllen).

        RGBA → premultipliziertes RGB + Alpha als 4. Kanal: voll-transparente Pixel
        werden dadurch alle zu (0,0,0,0) und vergleichen sich gleich, unabhängig vom
        RGB-„Müll" unter der Transparenz. Sonstige Modi → reines RGB.
        """
        import numpy as np
        if img.mode == 'RGBA':
            a   = np.asarray(img, dtype=np.int16)              # (h, w, 4)
            rgb = a[..., :3]
            alpha = a[..., 3:4]                                # (h, w, 1)
            premult = (rgb * alpha) // 255                     # transparent → (0,0,0)
            return np.concatenate([premult, alpha], axis=2)    # (h, w, 4)
        return np.asarray(img.convert('RGB'), dtype=np.int16)  # (h, w, 3)

    def _magic_wand_select(self, x: int, y: int):
        """Pixel mit ähnlicher Farbe auswählen (BFS bei zusammenhängend, sonst global).
        x, y sind Canvas-Koordinaten; die Auswahl wird auf der aktiven Ebene berechnet
        und danach an deren Position (ox/oy) in eine canvas-große Maske eingebettet."""
        if self.image is None:
            return
        layer = self.active_layer
        lx, ly = self._canvas2local(x, y)
        if not (0 <= lx < self.image.width and 0 <= ly < self.image.height):
            self.set_status('Außerhalb der Ebene')
            return
        import numpy as np
        img      = self.image
        tol      = self._wand_tol.get()
        contig   = self._wand_contiguous.get()
        w, h     = img.size
        self._wand_last = (x, y)   # Canvas-Koordinaten, für Live-Aktualisierung beim Tolerieren

        # Vergleichs-Array bauen. Wichtig: bei RGBA-Bildern MUSS der Alpha-Kanal
        # mitgerechnet werden, sonst behalten wegradierte (transparente) Pixel ihre
        # rohen RGB-Werte – z. B. (0,0,0) beim Radierer – und werden je nach Klickfarbe
        # selbst bei hoher Toleranz fälschlich aus-/eingeschlossen.
        # Premultipliziertes Alpha macht alle voll-transparenten Pixel identisch (0,0,0)
        # und behandelt eine Transparenz-Kante sauber als Grenze.
        arr = self._wand_compare_arr(img)                      # (h, w, C) int16
        target = arr[ly, lx].astype(np.int16)

        # Max-Kanal-Differenz (Chebyshev): Regler 0–255 = „erlaubte Abweichung
        # pro Farbkanal" – das ist intuitiv und trifft Flächen sauberer als die
        # alte aufsummierte Manhattan-Distanz.
        dist  = np.abs(arr - target).max(axis=2)
        match = dist <= tol                                    # bool (h, w)

        if contig:
            # Nur die mit dem Startpunkt zusammenhängende Region behalten
            try:
                from scipy.ndimage import label
                lbl, _ = label(match)                          # 4er-Nachbarschaft
                sel = lbl == lbl[ly, lx]
            except Exception:
                # Fallback ohne scipy: numpy-basiertes Flood-Fill über die bool-Maske
                sel = self._flood_bool(match, lx, ly)
        else:
            sel = match

        local_mask = Image.fromarray(np.where(sel, 255, 0).astype('uint8'), 'L')
        # Auf Canvas-Größe einbetten, damit _sel_mask wie gewohnt Canvas-Koordinaten hat
        # (Render-Overlay und _effective_mask gehen davon aus).
        mask = Image.new('L', (self.canvas_w, self.canvas_h), 0)
        mask.paste(local_mask, (layer.ox, layer.oy))
        n = int(sel.sum())

        self._sel_mask = mask
        self._sel_bbox = None
        self.set_status(f'Zauberstab: {n:,} Pixel ausgewählt  (Toleranz {tol})')
        self._render()

    def _wand_live_update(self):
        """Toleranz-Regler bewegt → Auswahl am letzten Klickpunkt neu berechnen."""
        if self._wand_last is None or not self.layers:
            return
        if self._wand_after is not None:
            try: self.after_cancel(self._wand_after)
            except Exception: pass
        def run():
            self._wand_after = None
            if self._wand_last:
                self._magic_wand_select(*self._wand_last)
        self._wand_after = self.after(60, run)

    @staticmethod
    def _flood_bool(match, x, y):
        """Zusammenhängende True-Region in einer bool-Maske ab (x, y) – numpy-Fallback."""
        import numpy as np
        h, w = match.shape
        sel  = np.zeros_like(match)
        if not match[y, x]:
            return sel
        stack = [(y, x)]
        while stack:
            cy, cx = stack.pop()
            if sel[cy, cx] or not match[cy, cx]:
                continue
            sel[cy, cx] = True
            if cx + 1 < w:  stack.append((cy, cx + 1))
            if cx - 1 >= 0: stack.append((cy, cx - 1))
            if cy + 1 < h:  stack.append((cy + 1, cx))
            if cy - 1 >= 0: stack.append((cy - 1, cx))
        return sel

    def _eyedrop(self, x, y):
        if self.image is None:
            return
        lx, ly = self._canvas2local(x, y)
        if not (0 <= lx < self.image.width and 0 <= ly < self.image.height):
            self.set_status('Außerhalb der Ebene')
            return
        px = self.image.getpixel((lx, ly))
        r, g, b = (int(px[0]), int(px[1]), int(px[2])) if isinstance(px, tuple) else (int(px),)*3
        self._set_fg(f'#{r:02x}{g:02x}{b:02x}')
        self.set_status(f'Farbe aufgenommen: {self.fg_color}')

    def _add_text(self, x, y):
        text = simpledialog.askstring('Text', 'Text eingeben:', parent=self)
        if not text:
            return
        self._push_undo()
        x, y = self._canvas2local(x, y)
        r, g, b = self._hex2rgb(self.fg_color)
        fill = (r, g, b, int(self.brush_opac.get()/100*255)) if self.image.mode == 'RGBA' else (r,g,b)
        size = max(12, self.brush_size.get() * 2)
        draw = ImageDraw.Draw(self.image)
        try:
            from PIL import ImageFont
            font = ImageFont.truetype('arialbd.ttf', size)
        except Exception:
            font = None
        draw.text((x, y), text, fill=fill, font=font)
        self._render()

    # ══════════════════════════════════════════════════════════════════════════
    #  ZOOM
    # ══════════════════════════════════════════════════════════════════════════

    def _set_zoom(self, z):
        self.zoom = max(0.02, min(32.0, z))
        self._zoom_lbl.config(text=f'{self.zoom * 100:.0f} %')
        self._render()

    def zoom_in(self):  self._zoom_center(1.25)
    def zoom_out(self): self._zoom_center(1 / 1.25)
    def zoom_actual(self):  self._set_zoom(1.0)

    def _zoom_center(self, factor):
        c = self._canvas
        self._zoom_at(c.winfo_width() // 2, c.winfo_height() // 2, factor)

    def zoom_fit(self):
        if not self.layers:
            return
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if cw <= 1 or ch <= 1:
            return
        z = min(cw / self.canvas_w, ch / self.canvas_h) * 0.92
        self.offset_x = int((cw - self.canvas_w * z) / 2)
        self.offset_y = int((ch - self.canvas_h * z) / 2)
        self._set_zoom(z)

    # ══════════════════════════════════════════════════════════════════════════
    #  DATEI
    # ══════════════════════════════════════════════════════════════════════════

    def cmd_new(self):
        dlg = NewImageDialog(self)
        if dlg.result:
            w, h, color = dlg.result
            Layer._counter = 0
            self.layers    = [Layer(Image.new('RGBA', (w, h), color), 'Hintergrund')]
            self.active_idx = 0
            self.canvas_w, self.canvas_h = w, h
            self.file_path = None
            self.undo_stack.clear(); self.redo_stack.clear()
            self._sel_bbox = None; self._fit_once = True
            self.after(60, self.zoom_fit)
            self._render(); self._refresh_layer_list()
            self._update_title()

    def cmd_open(self):
        path = filedialog.askopenfilename(title='Bild öffnen', filetypes=OPEN_TYPES)
        if path:
            self._load(Path(path))

    # Extension → Pillow-Format-Name (verhindert falsche Handler-Auswahl)
    _EXT_FMT = {
        '.webp': 'WEBP', '.png': 'PNG',  '.jpg': 'JPEG', '.jpeg': 'JPEG',
        '.bmp':  'BMP',  '.gif': 'GIF',  '.tiff': 'TIFF', '.tif': 'TIFF',
        '.ico':  'ICO',  '.ppm': 'PPM',
    }

    def _load(self, path: Path):
        ext = path.suffix.lower()
        try:
            if ext == '.psd':
                if self._open_psd(path):       # füllt self.layers selbst
                    return
                img = None
            elif ext == '.svg':
                img = self._open_svg(path)
            elif ext == '.eps':
                img = self._open_eps(path)
            else:
                # formats=[...] erzwingt den richtigen Handler –
                # verhindert dass Pillow bei unklaren Dateien den EPS/Ghostscript-
                # Handler aufruft und einen irreführenden Fehler produziert.
                fmt  = self._EXT_FMT.get(ext)
                raw  = Image.open(path, formats=[fmt] if fmt else None)
                try:
                    # Animierte Formate (WebP-anim, GIF): seek VOR load
                    if getattr(raw, 'n_frames', 1) > 1:
                        raw.seek(0)
                except (AttributeError, EOFError):
                    pass
                raw.load()
                img = raw.copy()
                try:
                    raw.close()
                except Exception:
                    pass
            if img is None:
                return
            img = img.convert('RGBA')
            Layer._counter = 0
            self.layers     = [Layer(img, path.stem)]
            self.active_idx = 0
            self.canvas_w, self.canvas_h = img.size
            self._post_load(path)
        except Exception as e:
            messagebox.showerror('Fehler beim Öffnen', str(e))

    def _post_load(self, path: Path):
        """Gemeinsamer Abschluss nach dem Setzen von self.layers / canvas_w/h."""
        self.file_path = path
        self.undo_stack.clear(); self.redo_stack.clear()
        self._sel_bbox = None; self._sel_mask = None
        self._wand_last = None; self._fit_once = True
        self._checker_key = None   # Checker-Cache ungültig machen
        self._load_seo(path)
        self.after(60, self.zoom_fit)
        self._render(); self._refresh_layer_list()
        self._update_title()
        self.set_status(
            f'Geöffnet: {path.name}   {self.canvas_w}×{self.canvas_h} px'
            f'   ({len(self.layers)} Ebene(n))')

    def _open_psd(self, path) -> bool:
        """PSD öffnen. Mit psd-tools bleiben die Ebenen erhalten; sonst Fallback
        auf das von Pillow zusammengefasste Gesamtbild."""
        if PSDTOOLS_AVAIL:
            try:
                from psd_tools import PSDImage
                psd = PSDImage.open(str(path))
                W, H = psd.width, psd.height
                layers: list[Layer] = []
                Layer._counter = 0
                # psd-tools liefert Ebenen von unten nach oben
                for lyr in psd:
                    try:
                        pil = lyr.composite()
                    except Exception:
                        pil = None
                    if pil is None:
                        continue
                    pil = pil.convert('RGBA')
                    # Ebene auf volle Leinwandgröße an ihrer Position einbetten
                    canvas = Image.new('RGBA', (W, H), (0, 0, 0, 0))
                    off = getattr(lyr, 'offset', (0, 0)) or (0, 0)
                    canvas.paste(pil, (int(off[0]), int(off[1])))
                    layers.append(Layer(canvas, lyr.name or None,
                                        visible=bool(getattr(lyr, 'visible', True))))
                if not layers:                       # nur ein zusammengefasstes Bild
                    comp = psd.composite().convert('RGBA')
                    layers = [Layer(comp, path.stem)]
                self.layers     = layers
                self.active_idx = len(layers) - 1
                self.canvas_w, self.canvas_h = W, H
                self._post_load(path)
                return True
            except Exception as e:
                messagebox.showwarning(
                    'PSD', f'psd-tools-Import fehlgeschlagen, nutze Gesamtbild.\n{e}')
        # Fallback: Pillow liest das zusammengefasste Vorschaubild
        try:
            raw = Image.open(path, formats=['PSD']); raw.load()
            img = raw.convert('RGBA')
            Layer._counter = 0
            self.layers     = [Layer(img, path.stem)]
            self.active_idx = 0
            self.canvas_w, self.canvas_h = img.size
            if not PSDTOOLS_AVAIL:
                self.set_status('PSD zusammengefasst geöffnet – für Ebenen: '
                                'pip install psd-tools')
            self._post_load(path)
            return True
        except Exception as e:
            messagebox.showerror('PSD-Fehler', str(e))
            return False

    def _open_svg(self, path):
        # 1) PyMuPDF/fitz – komplett eigenständige Windows-Wheels, KEINE native DLL nötig.
        try:
            import fitz
            doc = fitz.open(str(path))
            pdfbytes = doc.convert_to_pdf()
            pdf = fitz.open('pdf', pdfbytes)
            pix = pdf[0].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=True)
            mode = 'RGBA' if pix.alpha else 'RGB'
            return Image.frombytes(mode, (pix.width, pix.height), pix.samples).convert('RGBA')
        except Exception:
            pass
        # 2) cairosvg (beste Qualität, braucht aber natives Cairo)
        cs = _load_cairosvg()
        if cs:
            try:
                data = cs.svg2png(url=str(path), scale=2.0)
                return Image.open(io.BytesIO(data)).convert('RGBA')
            except Exception:
                pass
        messagebox.showwarning(
            'SVG',
            'Zum Öffnen von SVG wird PyMuPDF benötigt (ohne Zusatz-DLL):\n\n'
            '       pip install pymupdf\n\n'
            'Menü „Hilfe -> Pakete installieren" erledigt das automatisch.')
        return None

    def _open_eps(self, path):
        try:
            img = Image.open(path); img.load(); return img
        except Exception as e:
            messagebox.showwarning('EPS', f'Ghostscript benötigt.\n{e}'); return None

    def cmd_save(self):
        if self.file_path is None:
            self.cmd_save_as()
        else:
            self._write(self.file_path)

    def cmd_save_as(self):
        if not self.layers:
            return
        path = filedialog.asksaveasfilename(
            title='Speichern unter', defaultextension='.png', filetypes=SAVE_TYPES,
            initialfile=self.file_path.stem if self.file_path else 'bild')
        if path:
            self.file_path = Path(path)
            self._write(self.file_path)
            self._update_title()

    def cmd_export(self):
        if not self.layers:
            return
        path = filedialog.asksaveasfilename(
            title='Exportieren als', filetypes=SAVE_TYPES, defaultextension='.png')
        if path:
            ExportDialog(self, Path(path), self._get_flat(), self._write)

    def _get_flat(self) -> Image.Image:
        """Alle Ebenen zu einem Bild zusammenführen."""
        return composite(self.layers, self.canvas_w, self.canvas_h)

    def _write(self, path: Path, quality: int = 92, webp_lossless: bool = False):
        img  = self._get_flat()
        ext  = path.suffix.lower()
        try:
            if ext in ('.jpg', '.jpeg'):
                bg = Image.new('RGB', img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3])
                bg.save(path, 'JPEG', quality=quality, optimize=True, progressive=True)
            elif ext == '.png':
                img.save(path, 'PNG', optimize=True)
            elif ext == '.webp':
                img.save(path, 'WEBP', quality=quality, lossless=webp_lossless)
            elif ext in ('.tiff', '.tif'):
                img.save(path, 'TIFF')
            elif ext == '.bmp':
                img.convert('RGB').save(path, 'BMP')
            elif ext == '.ico':
                ico = img
                sizes = [s for s in [256,128,64,48,32,16] if s <= max(img.size)]
                imgs  = [ico.resize((s,s), Image.LANCZOS) for s in sizes]
                imgs[0].save(path, 'ICO', sizes=[i.size for i in imgs])
            elif ext == '.gif':
                img.convert('P', palette=Image.ADAPTIVE).save(path, 'GIF')
            elif ext == '.ppm':
                img.convert('RGB').save(path, 'PPM')
            elif ext == '.svg':
                self._write_svg(path, img)
            else:
                img.save(path)
            self._save_seo(path)
            self.set_status(f'Gespeichert: {path.name}')
        except Exception as e:
            messagebox.showerror('Speicherfehler', str(e))

    def _write_svg(self, path: Path, img: Image.Image):
        """SVG speichern. Da dies ein Raster-Editor ist, wird das fertige Bild
        verlustfrei als PNG in einen SVG-Container eingebettet (base64). Das
        Ergebnis ist eine gueltige .svg, die ueberall oeffnet – ohne Zusatzpakete."""
        import base64
        buf = io.BytesIO()
        img.save(buf, 'PNG', optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode('ascii')
        w, h = img.size
        svg = (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n'
            f'  <image width="{w}" height="{h}" '
            f'xlink:href="data:image/png;base64,{b64}"/>\n'
            f'</svg>\n'
        )
        path.write_text(svg, encoding='utf-8')

    def cmd_paste_clipboard(self):
        """Bild aus der Windows-Zwischenablage einfügen."""
        import tempfile
        fd, tmp_str = tempfile.mkstemp(suffix='.png')
        os.close(fd)
        tmp = Path(tmp_str)
        try:
            ps_cmd = (
                f"Add-Type -AssemblyName System.Windows.Forms; "
                f"$img = [System.Windows.Forms.Clipboard]::GetImage(); "
                f"if ($img) {{ $img.Save('{tmp_str.replace(chr(92), '/')}') }} else {{ exit 1 }}"
            )
            result = subprocess.run(['powershell', '-Command', ps_cmd],
                                    capture_output=True, timeout=10)
            if result.returncode == 0 and tmp.exists() and tmp.stat().st_size > 0:
                self._load(tmp)
                self.set_status('Bild aus Zwischenablage eingefügt')
            else:
                self.set_status('Kein Bild in der Zwischenablage')
        except Exception as e:
            self.set_status(f'Zwischenablage: {e}')
        finally:
            tmp.unlink(missing_ok=True)

    # ══════════════════════════════════════════════════════════════════════════
    #  UNDO / REDO
    # ══════════════════════════════════════════════════════════════════════════

    def _push_undo(self):
        if not self.layers:
            return
        snap = ([l.copy() for l in self.layers], self.active_idx,
                self.canvas_w, self.canvas_h)
        self.undo_stack.append(snap)
        if len(self.undo_stack) > self.MAX_UNDO:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def cmd_undo(self):
        if not self.undo_stack:
            return
        self.redo_stack.append(([l.copy() for l in self.layers], self.active_idx,
                                 self.canvas_w, self.canvas_h))
        layers, idx, cw, ch = self.undo_stack.pop()
        self.layers, self.active_idx = layers, idx
        self.canvas_w, self.canvas_h = cw, ch
        self._render(); self._refresh_layer_list()
        self.set_status('Rückgängig')

    def cmd_redo(self):
        if not self.redo_stack:
            return
        self.undo_stack.append(([l.copy() for l in self.layers], self.active_idx,
                                 self.canvas_w, self.canvas_h))
        layers, idx, cw, ch = self.redo_stack.pop()
        self.layers, self.active_idx = layers, idx
        self.canvas_w, self.canvas_h = cw, ch
        self._render(); self._refresh_layer_list()
        self.set_status('Wiederholt')

    # ══════════════════════════════════════════════════════════════════════════
    #  BILD-OPERATIONEN (wirken auf aktive Ebene)
    # ══════════════════════════════════════════════════════════════════════════

    def cmd_rotate(self, deg):
        if self.image is None: return
        self._push_undo()
        self.image = self.image.rotate(-deg, expand=True)
        self._render()

    def cmd_rotate_custom(self):
        if self.image is None: return
        a = simpledialog.askfloat('Drehen', 'Winkel (Grad):', parent=self)
        if a is not None:
            self._push_undo()
            self.image = self.image.rotate(-a, expand=True, resample=Image.BICUBIC)
            self._render()

    def cmd_flip(self, d):
        if self.image is None: return
        self._push_undo()
        self.image = ImageOps.mirror(self.image) if d == 'h' else ImageOps.flip(self.image)
        self._render()

    def cmd_grayscale(self):
        if self.image is None: return
        self._push_undo()
        a = self.image.split()[3]
        gray = ImageOps.grayscale(self.image).convert('RGB')
        rgba = gray.convert('RGBA'); rgba.putalpha(a)
        self.image = rgba; self._render()

    def cmd_invert(self):
        if self.image is None: return
        self._push_undo()
        r, g, b, a = self.image.split()
        inv = ImageOps.invert(Image.merge('RGB', (r,g,b)))
        self.image = Image.merge('RGBA', (*inv.split(), a))
        self._render()

    def cmd_auto_contrast(self):
        if self.image is None: return
        self._push_undo()
        r, g, b, a = self.image.split()
        rgb = ImageOps.autocontrast(Image.merge('RGB', (r,g,b)), cutoff=1)
        self.image = Image.merge('RGBA', (*rgb.split(), a)); self._render()

    def cmd_equalize(self):
        if self.image is None: return
        self._push_undo()
        r, g, b, a = self.image.split()
        rgb = ImageOps.equalize(Image.merge('RGB', (r,g,b)))
        self.image = Image.merge('RGBA', (*rgb.split(), a)); self._render()

    def cmd_resize(self):
        if not self.layers:
            self.set_status('Kein Bild geöffnet'); return
        dlg = ResizeDialog(self, (self.canvas_w, self.canvas_h))
        if not dlg.result:
            return
        w, h, method = dlg.result
        w, h = max(1, int(w)), max(1, int(h))
        if (w, h) == (self.canvas_w, self.canvas_h):
            self.set_status('Größe unverändert'); return
        self._push_undo()
        rs = {'Lanczos': Image.LANCZOS, 'Bicubic': Image.BICUBIC,
              'Bilinear': Image.BILINEAR, 'Nächster Pixel': Image.NEAREST
              }.get(method, Image.LANCZOS)
        # Alle Ebenen mitskalieren – Größe UND Position proportional anpassen,
        # damit zugeschnittene/verschobene Ebenen relativ zueinander stimmen.
        sx, sy = w / self.canvas_w, h / self.canvas_h
        for layer in self.layers:
            new_w = max(1, round(layer.image.width * sx))
            new_h = max(1, round(layer.image.height * sy))
            layer.image = layer.image.resize((new_w, new_h), rs)
            layer.ox = round(layer.ox * sx)
            layer.oy = round(layer.oy * sy)
        self.canvas_w, self.canvas_h = w, h
        self._sel_bbox = None; self._sel_mask = None; self._wand_last = None
        self._checker_key = None
        self.zoom_fit(); self._render()
        self.set_status(f'Bildgröße geändert: {w} × {h} px')

    def cmd_resize_layer(self):
        """Skaliert NUR die aktive Ebene – Canvas-Größe und alle anderen
        Ebenen bleiben unverändert. Position (oben-links) bleibt fix."""
        layer = self.active_layer
        if layer is None:
            self.set_status('Kein Bild geöffnet'); return
        dlg = ResizeDialog(self, layer.image.size, title='Ebenengröße ändern')
        if not dlg.result:
            return
        w, h, method = dlg.result
        w, h = max(1, int(w)), max(1, int(h))
        if (w, h) == layer.image.size:
            self.set_status('Größe unverändert'); return
        self._push_undo()
        rs = {'Lanczos': Image.LANCZOS, 'Bicubic': Image.BICUBIC,
              'Bilinear': Image.BILINEAR, 'Nächster Pixel': Image.NEAREST
              }.get(method, Image.LANCZOS)
        layer.image = layer.image.resize((w, h), rs)
        self._render()
        self.set_status(f'Ebene "{layer.name}" skaliert: {w} × {h} px')

    def cmd_canvas_size(self):
        if not self.layers: return
        dlg = CanvasSizeDialog(self, (self.canvas_w, self.canvas_h))
        if dlg.result:
            nw, nh, ah, av, fill = dlg.result
            self._push_undo()
            xm = {'links': 0, 'mitte': (nw-self.canvas_w)//2, 'rechts': nw-self.canvas_w}
            ym = {'oben': 0,  'mitte': (nh-self.canvas_h)//2, 'unten':  nh-self.canvas_h}
            for layer in self.layers:
                new_img = Image.new('RGBA', (nw, nh), fill)
                # Bisherige Ebenen-Position (ox/oy) beim Einfügen berücksichtigen,
                # dann auf das neue Canvas „backen" (Ebene wird wieder canvas-groß).
                new_img.paste(layer.image, (xm.get(ah,0) + layer.ox, ym.get(av,0) + layer.oy))
                layer.image = new_img
                layer.ox = layer.oy = 0
            self.canvas_w, self.canvas_h = nw, nh
            self._checker_key = None
            self.zoom_fit(); self._render()

    def cmd_crop_selection(self):
        """Schneidet NUR die aktive Ebene auf die Auswahl zu – Canvas-Größe und
        alle anderen Ebenen bleiben unverändert."""
        if self.image is None:
            self.set_status('Kein Bild geöffnet'); return
        bbox = self._sel_bbox
        if bbox is None and self._sel_mask is not None:
            bbox = self._sel_mask.getbbox()
        if bbox is None:
            self.set_status('Keine Auswahl – Auswahl-Werkzeug verwenden'); return
        x1, y1, x2, y2 = bbox
        x1, y1 = max(0, int(x1)), max(0, int(y1))
        x2, y2 = min(self.canvas_w, int(x2)), min(self.canvas_h, int(y2))

        layer = self.active_layer
        lx1, ly1 = layer.ox, layer.oy
        lx2, ly2 = lx1 + layer.image.width, ly1 + layer.image.height
        # Auswahl mit dem aktuellen Bereich der aktiven Ebene schneiden
        # (Auswahl kann über die Ebene hinausragen).
        nx1, ny1 = max(x1, lx1), max(y1, ly1)
        nx2, ny2 = min(x2, lx2), min(y2, ly2)
        if nx2 <= nx1 or ny2 <= ny1:
            self.set_status('Auswahl liegt außerhalb der aktiven Ebene'); return

        self._push_undo()
        layer.image = layer.image.crop((nx1 - lx1, ny1 - ly1, nx2 - lx1, ny2 - ly1))
        layer.ox, layer.oy = nx1, ny1
        self._sel_bbox = None
        self._sel_mask = None
        self._render()
        self.set_status(f'Ebene "{layer.name}" zugeschnitten: {nx2-nx1} × {ny2-ny1} px')

    def cmd_select_all(self):
        if self.layers:
            self._sel_bbox = (0, 0, self.canvas_w, self.canvas_h)
            self._sel_mask = None
            self._render()

    def cmd_deselect(self):
        self._sel_bbox = None
        self._sel_mask = None
        self._wand_last = None
        self._render()

    def cmd_delete_selection(self):
        """Ausgewählte Pixel der AKTIVEN Ebene transparent machen – andere Ebenen
        bleiben unberührt."""
        if self.image is None:
            return
        canvas_mask = self._effective_mask()
        if canvas_mask is None:
            return
        layer = self.active_layer
        lx, ly = layer.ox, layer.oy
        lw, lh = layer.image.size
        # Canvas-Maske auf den lokalen Bereich der aktiven Ebene zuschneiden
        # (PIL füllt Bereiche außerhalb der Quelle automatisch mit 0).
        mask = canvas_mask.crop((lx, ly, lx + lw, ly + lh))
        self._push_undo()
        img = self.image.copy()
        r, g, b, a = img.split()
        # Wo Maske = 255 (ausgewählt), alpha auf 0 setzen
        new_a = ImageChops.multiply(a, mask.point(lambda x: 255 - x))
        self.image = Image.merge('RGBA', (r, g, b, new_a))
        self.set_status('Auswahl gelöscht')
        self._render()

    def cmd_invert_selection(self):
        """Auswahl umkehren."""
        if self.image is None:
            return
        w, h = self.canvas_w, self.canvas_h
        if self._sel_mask is not None:
            inv = self._sel_mask.point(lambda x: 255 - x)
            self._sel_mask = inv
            self._sel_bbox = None
        elif self._sel_bbox is not None:
            # Bbox-Auswahl in Maske umwandeln und invertieren
            m = Image.new('L', (w, h), 0)
            x1,y1,x2,y2 = [int(v) for v in self._sel_bbox]
            m.paste(255, (x1,y1,x2,y2))
            self._sel_mask = m.point(lambda x: 255 - x)
            self._sel_bbox = None
        else:
            # Nichts ausgewählt → alles auswählen
            self._sel_mask = Image.new('L', (w, h), 255)
        self._render()
        self.set_status('Auswahl umgekehrt')

    def _effective_mask(self) -> Image.Image | None:
        """Gibt eine 'L'-Maske zurück – aus sel_mask oder sel_bbox, oder None."""
        if self._sel_mask is not None:
            return self._sel_mask
        if self._sel_bbox is not None:
            w, h = self.canvas_w, self.canvas_h
            m = Image.new('L', (w, h), 0)
            x1,y1,x2,y2 = [int(v) for v in self._sel_bbox]
            m.paste(255, (max(0,x1), max(0,y1), min(w,x2), min(h,y2)))
            return m
        return None

    def cmd_round_corners(self):
        if self.image is None: return
        dlg = RoundCornersDialog(self, self.image.size)
        if dlg.result is None: return
        radius, corners = dlg.result
        self._push_undo()
        img = self.image
        w, h = img.size
        r = min(radius, w//2, h//2)
        mask = Image.new('L', (w, h), 255)
        draw = ImageDraw.Draw(mask)
        for corner in ('oben-links','oben-rechts','unten-links','unten-rechts'):
            if corner not in corners: continue
            if corner == 'oben-links':
                draw.rectangle([0,0,r,r], fill=0)
                draw.ellipse([0,0,r*2,r*2], fill=255)
            elif corner == 'oben-rechts':
                draw.rectangle([w-r-1,0,w-1,r], fill=0)
                draw.ellipse([w-r*2-1,0,w-1,r*2], fill=255)
            elif corner == 'unten-links':
                draw.rectangle([0,h-r-1,r,h-1], fill=0)
                draw.ellipse([0,h-r*2-1,r*2,h-1], fill=255)
            elif corner == 'unten-rechts':
                draw.rectangle([w-r-1,h-r-1,w-1,h-1], fill=0)
                draw.ellipse([w-r*2-1,h-r*2-1,w-1,h-1], fill=255)
        r2, g2, b2, a = img.split()
        new_a = ImageChops.multiply(a, mask)
        self.image = Image.merge('RGBA', (r2,g2,b2,new_a))
        self._render()
        self.set_status(f'Ecken abgerundet – Radius: {r} px')

    def cmd_remove_bg(self):
        if self.image is None: return
        if not REMBG_AVAIL:
            if messagebox.askyesno('rembg fehlt', 'rembg installieren?\npip install rembg'):
                self.cmd_install_deps()
            return
        dlg = _BgRemoveOptionsDialog(self)
        if not dlg.result:
            return
        alpha_thresh, post_blur, model_name, alpha_matting = dlg.result
        self.set_status('Hintergrund wird entfernt … (KI, bitte warten)')
        self._push_undo()
        img_copy = self.image.copy()

        def worker():
            try:
                if not _load_rembg():
                    self.after(0, lambda: messagebox.showerror('rembg', 'Laden fehlgeschlagen'))
                    return
                result = _rembg_cutout(img_copy, model_name, alpha_matting)
                result = _apply_alpha_threshold(result, alpha_thresh, post_blur)
                self.after(0, lambda: (setattr(self, 'image', result),
                                       self._render(),
                                       self.set_status('Hintergrund entfernt ✔')))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror('rembg', str(e)))
        threading.Thread(target=worker, daemon=True).start()

    def cmd_refine_alpha(self):
        """Alpha-Kante einer bereits freigestellten Ebene nachträglich anpassen."""
        if self.image is None: return
        dlg = _AlphaRefineDialog(self)
        if dlg.result is None: return
        alpha_thresh, post_blur = dlg.result
        self._push_undo()
        self.image = _apply_alpha_threshold(self.image, alpha_thresh, post_blur)
        self._render()
        self.set_status('Alpha-Kante verfeinert')

    def cmd_smooth_edges(self):
        """Ausgefranste Freisteller-Kanten weich glätten (echtes Antialiasing)."""
        if self.image is None: return
        dlg = _SmoothEdgesDialog(self)
        if dlg.result is None: return
        strength, tighten = dlg.result
        self._push_undo()
        self.image = fx.apply_smooth_edges(self.image, strength, tighten)
        self._render()
        self.set_status('Kanten geglättet')

    # ══════════════════════════════════════════════════════════════════════════
    #  KORREKTUREN
    # ══════════════════════════════════════════════════════════════════════════

    def dlg_brightness(self):
        if self.image is None: return
        AdjustDialog(self, [
            ('Helligkeit', ImageEnhance.Brightness, 0.1, 3.0, 1.0),
            ('Kontrast',   ImageEnhance.Contrast,   0.1, 3.0, 1.0),
        ], self._apply_enhance, 'Helligkeit / Kontrast')

    def dlg_saturation(self):
        if self.image is None: return
        AdjustDialog(self, [
            ('Sättigung', ImageEnhance.Color,     0.0, 3.0, 1.0),
            ('Schärfe',   ImageEnhance.Sharpness, 0.0, 3.0, 1.0),
        ], self._apply_enhance, 'Sättigung / Schärfe')

    def _apply_enhance(self, pairs):
        self._push_undo()
        img = self.image.copy()
        for Enh, fac in pairs:
            img = Enh(img).enhance(fac)
        self.image = img; self._render()

    def cmd_apply_adj(self):
        if self.image is None: return
        MAP = {'brightness': ImageEnhance.Brightness, 'contrast': ImageEnhance.Contrast,
               'saturation': ImageEnhance.Color, 'sharpness': ImageEnhance.Sharpness}
        pairs = [(E, self._adj_vars[k].get()) for k, E in MAP.items()
                 if self._adj_vars[k].get() != 1.0]
        if pairs: self._apply_enhance(pairs)
        self._reset_adj()

    def _reset_adj(self):
        for v in self._adj_vars.values(): v.set(1.0)

    def dlg_color_balance(self):
        if self.image is None: return
        def apply(r, g, b, sh, hi, temp):
            self._push_undo()
            img = fx.apply_color_balance(self.image, r, g, b, sh, hi)
            if temp != 0:
                img = fx.apply_white_balance(img, temp)
            self.image = img; self._render()
        ColorBalanceDialog(self, apply)

    def dlg_white_balance(self):
        if self.image is None: return
        t = simpledialog.askinteger('Weißabgleich',
            'Farbtemperatur (-100 = kälter/blauer, +100 = wärmer/oranger):',
            initialvalue=0, minvalue=-100, maxvalue=100, parent=self)
        if t is not None:
            self._push_undo()
            self.image = fx.apply_white_balance(self.image, t)
            self._render()

    def cmd_blur(self):
        if self.image is None: return
        r = simpledialog.askfloat('Weichzeichner', 'Radius:', parent=self,
                                   initialvalue=2.0, minvalue=0.1, maxvalue=30.0)
        if r:
            self._push_undo()
            self.image = self.image.filter(ImageFilter.GaussianBlur(radius=r))
            self._render()

    def cmd_unsharp_mask(self):
        if self.image is None: return
        r = simpledialog.askfloat('Unscharf-Maske', 'Radius (empfohlen: 1-3):', parent=self,
                                   initialvalue=2.0, minvalue=0.1, maxvalue=20.0)
        if r:
            self._push_undo()
            self.image = fx.apply_unsharp_mask(self.image, radius=r)
            self._render()

    def cmd_denoise(self):
        if self.image is None: return
        self._push_undo()
        self.image = fx.apply_denoise(self.image)
        self._render()
        self.set_status('Rauschen reduziert')

    # ══════════════════════════════════════════════════════════════════════════
    #  EFFEKTE
    # ══════════════════════════════════════════════════════════════════════════

    def dlg_vignette(self):
        if self.image is None: return
        dlg = VignetteDialog(self, 'Vignette')
        if dlg.result is not None:
            self._push_undo()
            self.image = fx.apply_vignette(self.image, strength=dlg.result)
            self._render()

    def dlg_watermark(self):
        if self.image is None: return
        dlg = WatermarkDialog(self, 'Wasserzeichen')
        if dlg.result:
            self._push_undo()
            self.image = fx.apply_watermark(self.image, **dlg.result)
            self._render()

    def dlg_border(self):
        if self.image is None: return
        dlg = BorderDialog(self, 'Rahmen hinzufügen')
        if dlg.result:
            size, color, inner = dlg.result
            self._push_undo()
            self.image = fx.apply_border(self.image, size=size, color=color, inner=inner)
            self._render(); self.zoom_fit()

    def dlg_drop_shadow(self):
        if self.image is None: return
        dlg = DropShadowDialog(self, 'Schlagschatten')
        if dlg.result:
            ox, oy, blur, color, opacity = dlg.result
            self._push_undo()
            self.image = fx.apply_drop_shadow(self.image, ox, oy, blur, color, opacity)
            self._render(); self.zoom_fit()

    def cmd_color_palette(self):
        if self.image is None: return
        self.set_status('Farb-Palette wird berechnet …')
        colors = fx.extract_palette(self.image, count=10)
        ColorPaletteDialog(self, colors, self._set_fg)
        self.set_status(f'{len(colors)} Farben extrahiert')

    # ── Ton-Effekte ───────────────────────────────────────────────────────────

    def cmd_sepia(self):
        if self.image is None: return
        self._push_undo()
        self.image = fx.apply_sepia(self.image)
        self._render(); self.set_status('Sepia angewendet')

    def cmd_posterize(self):
        if self.image is None: return
        bits = simpledialog.askinteger('Posterisieren',
            'Farbstufen pro Kanal (1–8 Bit, weniger = plakativer):',
            initialvalue=3, minvalue=1, maxvalue=8, parent=self)
        if bits:
            self._push_undo()
            self.image = fx.apply_posterize(self.image, bits)
            self._render(); self.set_status(f'Posterisiert ({bits} Bit)')

    def cmd_threshold(self):
        if self.image is None: return
        lvl = simpledialog.askinteger('Schwellenwert',
            'Schwelle (0–255): heller = mehr Weiß',
            initialvalue=128, minvalue=0, maxvalue=255, parent=self)
        if lvl is not None:
            self._push_undo()
            self.image = fx.apply_threshold(self.image, lvl)
            self._render(); self.set_status(f'Schwellenwert {lvl}')

    def cmd_hue_shift(self):
        if self.image is None: return
        deg = simpledialog.askinteger('Farbton verschieben',
            'Farbton-Drehung (0–360°):',
            initialvalue=180, minvalue=0, maxvalue=360, parent=self)
        if deg is not None:
            self._push_undo()
            self.image = fx.apply_hue_shift(self.image, deg)
            self._render(); self.set_status(f'Farbton +{deg}°')

    # ── Verpixeln / Bewegungsunschärfe ──────────────────────────────────────────

    def cmd_pixelate(self):
        if self.image is None: return
        block = simpledialog.askinteger('Verpixeln / Mosaik',
            'Blockgröße in Pixel (größer = gröber):',
            initialvalue=12, minvalue=2, maxvalue=200, parent=self)
        if block:
            self._push_undo()
            self.image = fx.apply_pixelate(self.image, block)
            self._render(); self.set_status(f'Verpixelt (Block {block} px)')

    def cmd_motion_blur(self):
        if self.image is None: return
        dist = simpledialog.askinteger('Bewegungsunschärfe',
            'Stärke / Distanz in Pixel:',
            initialvalue=15, minvalue=1, maxvalue=100, parent=self)
        if dist:
            ang = simpledialog.askinteger('Bewegungsunschärfe',
                'Richtung (Winkel 0–360°, 0 = horizontal):',
                initialvalue=0, minvalue=0, maxvalue=360, parent=self)
            self._push_undo()
            self.image = fx.apply_motion_blur(self.image, dist, ang or 0)
            self._render(); self.set_status('Bewegungsunschärfe angewendet')

    # ── Stilisieren ─────────────────────────────────────────────────────────────

    def cmd_emboss(self):
        if self.image is None: return
        self._push_undo()
        self.image = fx.apply_emboss(self.image)
        self._render(); self.set_status('Emboss (Relief)')

    def cmd_find_edges(self):
        if self.image is None: return
        self._push_undo()
        self.image = fx.apply_find_edges(self.image)
        self._render(); self.set_status('Kanten gefunden')

    def cmd_sketch(self):
        if self.image is None: return
        self._push_undo()
        self.image = fx.apply_sketch(self.image)
        self._render(); self.set_status('Bleistift-Skizze')

    def cmd_oil_paint(self):
        if self.image is None: return
        size = simpledialog.askinteger('Ölgemälde',
            'Pinselgröße (3–15, größer = gröber):',
            initialvalue=5, minvalue=3, maxvalue=15, parent=self)
        if size:
            self.set_status('Ölgemälde wird berechnet …'); self.update_idletasks()
            self._push_undo()
            self.image = fx.apply_oil_paint(self.image, size)
            self._render(); self.set_status('Ölgemälde-Look')

    # ══════════════════════════════════════════════════════════════════════════
    #  EBENEN-SYSTEM
    # ══════════════════════════════════════════════════════════════════════════

    def cmd_new_layer(self):
        if not self.layers: return
        self._push_undo()
        new = Layer(Image.new('RGBA', (self.canvas_w, self.canvas_h), (0,0,0,0)))
        self.layers.insert(self.active_idx + 1, new)
        self.active_idx += 1
        self._render(); self._refresh_layer_list()

    def cmd_delete_layer(self):
        if len(self.layers) <= 1:
            self.set_status('Mindestens eine Ebene erforderlich'); return
        self._push_undo()
        self.layers.pop(self.active_idx)
        self.active_idx = min(self.active_idx, len(self.layers) - 1)
        self._render(); self._refresh_layer_list()

    def cmd_duplicate_layer(self):
        if not self.layers: return
        self._push_undo()
        dup = self.layers[self.active_idx].copy()
        dup.name = dup.name + ' (Kopie)'
        self.layers.insert(self.active_idx + 1, dup)
        self.active_idx += 1
        self._render(); self._refresh_layer_list()

    def cmd_layer_up(self):
        i = self.active_idx
        if i >= len(self.layers) - 1: return
        self._push_undo()
        self.layers[i], self.layers[i+1] = self.layers[i+1], self.layers[i]
        self.active_idx = i + 1
        self._render(); self._refresh_layer_list()

    def cmd_layer_down(self):
        i = self.active_idx
        if i <= 0: return
        self._push_undo()
        self.layers[i], self.layers[i-1] = self.layers[i-1], self.layers[i]
        self.active_idx = i - 1
        self._render(); self._refresh_layer_list()

    def cmd_merge_down(self):
        i = self.active_idx
        if i <= 0:
            self.set_status('Keine Ebene darunter'); return
        self._push_undo()
        top    = self.layers[i]
        bottom = self.layers[i-1]
        merged_img = blend_layers(bottom.image, top.image, top.blend_mode)
        bottom.image = merged_img
        self.layers.pop(i)
        self.active_idx = i - 1
        self._render(); self._refresh_layer_list()
        self.set_status('Ebenen zusammengeführt')

    def cmd_flatten(self):
        if len(self.layers) <= 1: return
        self._push_undo()
        flat = composite(self.layers, self.canvas_w, self.canvas_h)
        self.layers = [Layer(flat, 'Hintergrund')]
        self.active_idx = 0
        self._render(); self._refresh_layer_list()
        self.set_status('Alle Ebenen zusammengeführt')

    def _select_layer(self, idx: int):
        self.active_idx = idx
        self._render(); self._refresh_layer_list()

    def _toggle_layer_vis(self, idx: int):
        self.layers[idx].visible = not self.layers[idx].visible
        self._render(); self._refresh_layer_list()

    def _rename_layer(self, idx: int):
        dlg = LayerRenameDialog(self, self.layers[idx].name)
        if dlg.result:
            self.layers[idx].name = dlg.result
            self._refresh_layer_list()

    def _on_blend_changed(self):
        if not self.layers or self._syncing_controls: return
        self.layers[self.active_idx].blend_mode = self._blend_var.get()
        self._render()

    def _on_layer_opac_changed(self):
        if not self.layers or self._syncing_controls: return
        try:
            v = self._layer_opac.get()
            self.layers[self.active_idx].opacity = v
            self._opac_lbl.config(text=f'{v} %')
            self._render()
        except Exception:
            pass

    def _update_layer_panel_controls(self):
        if not self.layers or self.active_idx >= len(self.layers):
            return
        layer = self.layers[self.active_idx]
        # Während des Setzens die Traces stummschalten (sonst lösen sie _render aus)
        self._syncing_controls = True
        try:
            self._blend_var.set(layer.blend_mode)
            self._layer_opac.set(layer.opacity)
        except Exception:
            pass
        finally:
            self._syncing_controls = False

    def _refresh_layer_list(self):
        """Ebenen-Panel neu aufbauen (Ebenen in umgekehrter Reihenfolge wie Photoshop)."""
        self._update_layer_panel_controls()
        for w in self._layer_list.winfo_children():
            w.destroy()
        self._layer_thumbs.clear()

        for i, layer in enumerate(reversed(self.layers)):
            real_idx = len(self.layers) - 1 - i
            active   = (real_idx == self.active_idx)

            row_bg   = '#e0e7ff' if active else PANEL2   # helles Indigo (passt zum hellen Theme)
            row_fg   = ACCENT    if active else TEXT
            row      = tk.Frame(self._layer_list, bg=row_bg, cursor='hand2',
                                highlightthickness=1 if active else 0,
                                highlightbackground=ACCENT)
            row.pack(fill=tk.X, padx=4, pady=1)

            # Sichtbarkeit
            vis_txt = '👁' if layer.visible else '◌'
            tk.Button(row, text=vis_txt, bg=row_bg, fg=ACCENT if layer.visible else TEXT_DIM,
                      bd=0, padx=5, font=('Segoe UI', 10), relief=tk.FLAT,
                      activebackground=row_bg, activeforeground=ACCENT,
                      command=lambda i=real_idx: self._toggle_layer_vis(i)
                      ).pack(side=tk.LEFT)

            # Thumbnail
            try:
                thumb = layer.image.copy()
                thumb.thumbnail((36, 30), Image.NEAREST)
                bg_th = Image.new('RGBA', (36, 30), (236, 238, 242, 255))
                bg_th.paste(thumb, mask=thumb.split()[3] if thumb.mode == 'RGBA' else None)
                ph = ImageTk.PhotoImage(bg_th.convert('RGB'))
                self._layer_thumbs.append(ph)
                tk.Label(row, image=ph, bg=row_bg, bd=1, relief='flat').pack(
                    side=tk.LEFT, padx=3, pady=3)
            except Exception:
                pass

            # Name
            name_lbl = tk.Label(row, text=layer.name, bg=row_bg,
                                 fg=row_fg, font=('Segoe UI', 8), anchor='w')
            name_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

            # Klick = Ebene wählen, Doppelklick = umbenennen
            for w in [row, name_lbl]:
                w.bind('<Button-1>',        lambda e, i=real_idx: self._select_layer(i))
                w.bind('<Double-Button-1>', lambda e, i=real_idx: self._rename_layer(i))

            # Schloss-Icon wenn gesperrt
            if layer.locked:
                tk.Label(row, text='🔒', bg=row_bg, fg=TEXT_DIM,
                         font=('Segoe UI', 8)).pack(side=tk.RIGHT, padx=4)

    # ══════════════════════════════════════════════════════════════════════════
    #  SEO
    # ══════════════════════════════════════════════════════════════════════════

    def _focus_seo(self):
        self._right_nb.select(self._seo_tab)

    def _load_seo(self, img_path: Path):
        sc = img_path.with_suffix('.seo.json')
        if sc.exists():
            try:
                with open(sc, 'r', encoding='utf-8') as f:
                    self.seo.update(json.load(f))
                self._refresh_seo_ui()
            except Exception:
                pass

    def _save_seo(self, img_path: Path):
        # Sidecar nur schreiben, wenn der Nutzer es aktiviert hat UND Daten da sind.
        if not self._seo_sidecar.get() or not any(self.seo.values()):
            return
        try:
            with open(img_path.with_suffix('.seo.json'), 'w', encoding='utf-8') as f:
                json.dump(self.seo, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _refresh_seo_ui(self):
        for key, widget in self._seo_w.items():
            val = self.seo.get(key, '')
            if isinstance(widget, tk.StringVar):
                widget.set(val)
            elif isinstance(widget, tk.Text):
                widget.delete('1.0', tk.END); widget.insert('1.0', val)

    def cmd_import_seo(self):
        path = filedialog.askopenfilename(title='SEO-JSON importieren',
                                           filetypes=[('JSON','*.json'),('Alle','*.*')])
        if path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    self.seo.update(json.load(f))
                self._refresh_seo_ui()
                self.set_status('SEO-Metadaten importiert')
            except Exception as e:
                messagebox.showerror('Fehler', str(e))

    def cmd_strip_metadata(self):
        """Alle Metadaten entfernen: SEO-Felder leeren, Sidecar abschalten und
        eingebettete Tags (EXIF/PNG-Info/ICC) aus allen Ebenen löschen."""
        # 1) SEO-Felder leeren + Begleitdatei abschalten
        for k in self.seo:
            self.seo[k] = ''
        self._seo_sidecar.set(False)
        try:
            self._refresh_seo_ui()
        except Exception:
            pass
        # 2) Eingebettete Metadaten aus den Bilddaten entfernen
        n = 0
        for layer in self.layers:
            img = layer.image
            if getattr(img, 'info', None):
                img.info.clear(); n += 1
            for attr in ('_exif', 'applist'):
                if hasattr(img, attr):
                    try: delattr(img, attr)
                    except Exception: pass
        self.set_status('Metadaten entfernt – Exporte enthalten keine EXIF/SEO-Tags mehr')

    def cmd_export_seo(self):
        default = (self.file_path.stem + '.seo') if self.file_path else 'metadata.seo'
        path = filedialog.asksaveasfilename(title='SEO-JSON exportieren',
                                             defaultextension='.json', initialfile=default,
                                             filetypes=[('JSON','*.json')])
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(self.seo, f, ensure_ascii=False, indent=2)
                self.set_status(f'SEO gespeichert: {Path(path).name}')
            except Exception as e:
                messagebox.showerror('Fehler', str(e))

    # ══════════════════════════════════════════════════════════════════════════
    #  HILFS-METHODEN
    # ══════════════════════════════════════════════════════════════════════════

    def _pick_fg(self):
        c = colorchooser.askcolor(color=self.fg_color, title='Vordergrundfarbe', parent=self)
        if c[1]: self._set_fg(c[1])

    def _pick_bg(self):
        c = colorchooser.askcolor(color=self.bg_color, title='Hintergrundfarbe', parent=self)
        if c[1]: self._set_bg(c[1])

    def _set_fg(self, h: str):
        h = self._norm_hex(h)
        if h:
            self.fg_color = h
            self._draw_swatches()
            self._fg_hex.set(h)

    def _set_bg(self, h: str):
        h = self._norm_hex(h)
        if h:
            self.bg_color = h
            self._draw_swatches()
            self._bg_hex.set(h)

    # Geometrie der beiden Farbfelder (x1, y1, x2, y2)
    _FG_RECT = (8, 4, 40, 36)
    _BG_RECT = (26, 22, 58, 54)

    def _draw_swatches(self):
        c = self._swatch
        c.delete('all')
        def rr(x1, y1, x2, y2, r, **kw):
            pts = [x1+r,y1, x2-r,y1, x2,y1, x2,y1+r, x2,y2-r, x2,y2,
                   x2-r,y2, x1+r,y2, x1,y2, x1,y2-r, x1,y1+r, x1,y1]
            c.create_polygon(pts, smooth=True, **kw)
        rr(*self._BG_RECT, 7, fill=self.bg_color, outline=TEXT_DIM, width=2)
        rr(*self._FG_RECT, 7, fill=self.fg_color, outline=TEXT, width=2)

    def _swatch_click(self, ev):
        fx1, fy1, fx2, fy2 = self._FG_RECT
        if fx1 <= ev.x <= fx2 and fy1 <= ev.y <= fy2:
            self._pick_fg(); return
        bx1, by1, bx2, by2 = self._BG_RECT
        if bx1 <= ev.x <= bx2 and by1 <= ev.y <= by2:
            self._pick_bg()

    def _apply_hex_fg(self): self._set_fg(self._fg_hex.get())
    def _apply_hex_bg(self): self._set_bg(self._bg_hex.get())

    @staticmethod
    def _norm_hex(val: str) -> str:
        val = val.strip().lstrip('#')
        if len(val) == 3: val = val[0]*2 + val[1]*2 + val[2]*2
        if len(val) != 6: return ''
        try: int(val, 16); return '#' + val.lower()
        except ValueError: return ''

    @staticmethod
    def _hex2rgb(h: str) -> tuple[int,int,int]:
        h = h.lstrip('#')
        return tuple(int(h[i:i+2], 16) for i in (0,2,4))

    _TOOL_NAMES = {'cursor': 'Auswahl-Rechteck', 'magic_wand': 'Zauberstab',
                   'brush': 'Pinsel', 'eraser': 'Radierer', 'fill': 'Füllen',
                   'eyedrop': 'Pipette', 'text': 'Text', 'crop': 'Zuschneiden',
                   'move': 'Verschieben'}

    def _select_tool(self, name: str):
        self.tool.set(name)
        for n, b in self._tool_btns.items():
            b.set_active(n == name)
        # Cursor je Werkzeug – pro Name absichern (manche X11-Cursor fehlen unter Windows)
        CURSORS = {'cursor': 'arrow', 'magic_wand': 'target', 'brush': 'crosshair',
                   'eraser': 'crosshair', 'fill': 'dotbox', 'eyedrop': 'crosshair',
                   'text': 'xterm', 'crop': 'sizing', 'move': 'fleur'}
        for cur in (CURSORS.get(name, 'crosshair'), 'crosshair', 'arrow'):
            try:
                self._canvas.configure(cursor=cur); break
            except Exception:
                continue
        self.set_status(f'Werkzeug: {self._TOOL_NAMES.get(name, name)}')
        # Ring sofort an der aktuellen Mausposition zeigen (statt nur zu löschen);
        # _draw_cursor_ring entfernt ihn automatisch bei Nicht-Pinsel-Werkzeugen.
        self._refresh_cursor_ring()

    def _update_title(self):
        name = self.file_path.name if self.file_path else 'Unbenannt'
        self.title(f'Image Editor Pro  –  {name}')

    def _update_info(self):
        if not self.layers: return
        v = self._info_v
        v['dim'].config(text=f'{self.canvas_w} × {self.canvas_h} px')
        v['mode'].config(text=self.layers[self.active_idx].image.mode)
        v['zoom'].config(text=f'{self.zoom*100:.0f}%')
        v['layers'].config(text=f'{len(self.layers)} Ebene(n)')
        if self.file_path:
            v['file'].config(text=self.file_path.name)
            v['fmt'].config(text=self.file_path.suffix.upper().lstrip('.'))
            try:
                sz = self.file_path.stat().st_size
                v['fsize'].config(
                    text=f'{sz/1e6:.2f} MB' if sz > 1e6 else f'{sz/1000:.1f} KB')
            except Exception:
                pass

    def set_status(self, msg: str):
        self._status.config(text=msg)

    @staticmethod
    def _tooltip(widget, text: str):
        tip = None
        def show(ev):
            nonlocal tip
            tip = tk.Toplevel(widget)
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f'+{ev.x_root+14}+{ev.y_root+10}')
            tk.Label(tip, text=text, bg='#ffffe0', fg='#000',
                     relief='solid', bd=1, font=('Segoe UI', 8), padx=4, pady=2).pack()
        def hide(ev):
            nonlocal tip
            if tip: tip.destroy(); tip = None
        # add='+', damit Hover-Effekte (RoundedButton) erhalten bleiben
        widget.bind('<Enter>', show, add='+'); widget.bind('<Leave>', hide, add='+')

    def cmd_install_deps(self):
        # Im gebauten EXE sind alle Pakete bereits fest eingebacken – pip waere
        # hier wirkungslos (sys.executable ist die EXE, nicht Python).
        if getattr(sys, 'frozen', False):
            messagebox.showinfo(
                'Pakete',
                'Alle optionalen Funktionen (SVG, PSD, Zauberstab, KI-Freisteller)\n'
                'sind in dieser Version bereits fest enthalten.\n'
                'Es muss nichts nachinstalliert werden.')
            return
        pkgs = ['rembg', 'pymupdf', 'psd-tools', 'numpy', 'scipy']
        if messagebox.askyesno('Pakete installieren',
                               'Optionale Funktionen aktivieren:\n\n'
                               '  • rembg       – Hintergrund entfernen (KI)\n'
                               '  • pymupdf     – SVG öffnen\n'
                               '  • psd-tools   – PSD mit Ebenen\n'
                               '  • numpy/scipy – Zauberstab\n\n'
                               'Jetzt installieren?'):
            def worker():
                for p in pkgs:
                    try: subprocess.check_call([sys.executable,'-m','pip','install',p],
                                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception: pass
                self.after(0, lambda: (
                    messagebox.showinfo('Fertig','Pakete installiert. Bitte neu starten.'),
                    self.set_status('Installation abgeschlossen')))
            threading.Thread(target=worker, daemon=True).start()

    def cmd_about(self):
        messagebox.showinfo('Image Editor Pro',
            'Image Editor Pro  v2.0\n\n'
            '✔ Ebenen-System mit 10 Blend-Modi\n'
            '✔ PNG, JPG, WebP, BMP, TIFF, ICO, GIF, PSD, SVG, EPS*\n'
            '✔ Hintergrund entfernen (rembg / KI)\n'
            '✔ Vignette, Wasserzeichen, Rahmen, Schlagschatten\n'
            '✔ Farb-Balance, Weißabgleich, Unscharf-Maske\n'
            '✔ Farb-Palette extrahieren\n'
            '✔ Bild aus Zwischenablage einfügen\n'
            '✔ Social-Media-Größen-Vorlagen\n'
            '✔ SEO-Metadaten (JSON-Sidecar)\n'
            '✔ Export mit Dateigrößen-Vorschau\n\n'
            '* Benötigt cairosvg / Ghostscript\n'
            'Menü → Hilfe → Pakete installieren')


# ══════════════════════════════════════════════════════════════════════════════
#  HILFSFUNKTIONEN (Modul-Level)
# ══════════════════════════════════════════════════════════════════════════════

def _apply_alpha_threshold(img: Image.Image,
                            thresh: int = 10,
                            post_blur: int = 0) -> Image.Image:
    """
    Alpha-Kanal eines RGBA-Bildes nachbearbeiten:
    - thresh (0–255): Pixel mit alpha <= thresh werden vollständig transparent.
      Kleine Werte (0–10) = mehr behalten / sanft.
      Große Werte (100–200) = aggressiver, entfernt halbdurchsichtige Kantenpixel.
    - post_blur (0–5): Leichtes Weichzeichnen der Kante danach (Antialiasing).
    """
    rgba = img.convert('RGBA')
    r, g, b, a = rgba.split()
    # Schwellenwert: unter thresh → 0, darüber → 255
    if thresh > 0:
        a = a.point(lambda x: 0 if x <= thresh else 255)
    # Optionales Kantenglätten
    if post_blur > 0:
        a = a.filter(ImageFilter.GaussianBlur(radius=post_blur))
        a = a.point(lambda x: 0 if x < 128 else 255)
    return Image.merge('RGBA', (r, g, b, a))


class _BgRemoveOptionsDialog(tk.Toplevel):
    """Dialog vor dem BG-Entfernen: Toleranz + Kantenglätten."""
    def __init__(self, parent):
        super().__init__(parent)
        self.result = None
        self.title('Hintergrund entfernen')
        self.configure(bg=PANEL)
        self.resizable(False, False)
        self.transient(parent)
        self._thresh = tk.IntVar(value=0)
        self._blur   = tk.IntVar(value=0)
        self._model  = tk.StringVar(value=DEFAULT_BG_MODEL)
        self._matte  = tk.BooleanVar(value=True)
        self._build()
        self.grab_set()
        self.wait_window()

    def _build(self):
        f = tk.Frame(self, bg=PANEL, padx=20, pady=16); f.pack()
        tk.Label(f, text='KI-Freisteller (rembg)', bg=PANEL, fg=TEXT,
                 font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=(0, 10))

        # ── Modellauswahl ──────────────────────────────────────────────────
        tk.Label(f, text='Modell', bg=PANEL, fg=TEXT,
                 font=('Segoe UI', 9, 'bold')).pack(anchor='w', pady=(0, 0))
        tk.Label(f, text='isnet-general-use = beste Allzweck-Qualität (empfohlen)\n'
                         'u2net = schneller, aber mehr Rest-Halos\n'
                         'isnet-anime / silueta = Comics bzw. einfache Motive',
                 bg=PANEL, fg=TEXT_DIM, font=('Segoe UI', 7),
                 justify='left').pack(anchor='w')
        ttk.Combobox(f, textvariable=self._model, state='readonly', width=24,
                     values=['isnet-general-use', 'u2net', 'u2netp',
                             'isnet-anime', 'silueta']).pack(anchor='w', pady=(2, 6))

        # ── Alpha-Matting ──────────────────────────────────────────────────
        tk.Checkbutton(f, text='Alpha-Matting (entfernt dunkle Halo-Reste)',
                       variable=self._matte, bg=PANEL, fg=TEXT,
                       selectcolor=PANEL, activebackground=PANEL,
                       activeforeground=TEXT, font=('Segoe UI', 8),
                       anchor='w').pack(anchor='w', pady=(0, 4))

        for label, var, mn, mx, tip in [
            ('Alpha-Schwelle', self._thresh, 0, 200,
             '0 = alles behalten (wenig Rand)\n'
             '10 = Standard\n'
             '80–150 = Halbdurchsichtige Ränder entfernen'),
            ('Kanten-Glätten (Blur)', self._blur, 0, 5,
             '0 = scharf  |  1–3 = leichtes Antialiasing'),
        ]:
            tk.Label(f, text=label, bg=PANEL, fg=TEXT,
                     font=('Segoe UI', 9, 'bold')).pack(anchor='w', pady=(8, 0))
            tk.Label(f, text=tip, bg=PANEL, fg=TEXT_DIM,
                     font=('Segoe UI', 7), justify='left').pack(anchor='w')
            row = tk.Frame(f, bg=PANEL); row.pack(fill=tk.X, pady=2)
            lbl = tk.Label(row, text=str(var.get()), bg=PANEL, fg=ACCENT,
                           font=('Segoe UI', 9), width=4); lbl.pack(side=tk.RIGHT)
            ttk.Scale(row, from_=mn, to=mx, variable=var,
                      orient=tk.HORIZONTAL, length=260).pack(side=tk.LEFT, fill=tk.X, expand=True)
            var.trace_add('write', lambda *a, l=lbl, v=var: _safe_lbl(l, v, '{}'))

        tk.Frame(f, bg=BORDER, height=1).pack(fill=tk.X, pady=10)
        bf = tk.Frame(f, bg=PANEL); bf.pack(fill=tk.X)
        tk.Button(bf, text='Abbrechen', command=self.destroy,
                  bg=BTN, fg=TEXT, bd=0, padx=10, pady=4, relief=tk.FLAT).pack(side=tk.RIGHT, padx=4)
        tk.Button(bf, text='✔  Entfernen', command=self._ok,
                  bg=ACCENT, fg='#000', bd=0, padx=14, pady=4,
                  relief=tk.FLAT, font=('Segoe UI', 9, 'bold')).pack(side=tk.RIGHT, padx=4)

    def _ok(self):
        self.result = (self._thresh.get(), self._blur.get(),
                       self._model.get(), self._matte.get())
        self.destroy()


class _AlphaRefineDialog(tk.Toplevel):
    """Alpha-Kante nachträglich verfeinern – kein rembg-Aufruf."""
    def __init__(self, parent):
        super().__init__(parent)
        self.result = None
        self.title('Alpha-Kante verfeinern')
        self.configure(bg=PANEL)
        self.resizable(False, False)
        self.transient(parent)
        self._thresh = tk.IntVar(value=10)
        self._blur   = tk.IntVar(value=0)
        self._build()
        self.grab_set()
        self.wait_window()

    def _build(self):
        # Überschreibt _BgRemoveOptionsDialog._build, setzt anderen Titel
        f = tk.Frame(self, bg=PANEL, padx=20, pady=16); f.pack()
        tk.Label(f, text='Alpha-Kante verfeinern', bg=PANEL, fg=TEXT,
                 font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=(0, 10))
        tk.Label(f, text='Wirkt auf den Alpha-Kanal der aktiven Ebene.',
                 bg=PANEL, fg=TEXT_DIM, font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 8))

        for label, var, mn, mx, tip in [
            ('Alpha-Schwelle', self._thresh, 0, 200,
             '0 = keine Änderung  |  50–150 = Halbpixel entfernen'),
            ('Kanten-Glätten (Blur)', self._blur, 0, 5,
             '0 = scharf  |  1–3 = weiche Kante'),
        ]:
            tk.Label(f, text=label, bg=PANEL, fg=TEXT,
                     font=('Segoe UI', 9, 'bold')).pack(anchor='w', pady=(8, 0))
            tk.Label(f, text=tip, bg=PANEL, fg=TEXT_DIM,
                     font=('Segoe UI', 7), justify='left').pack(anchor='w')
            row = tk.Frame(f, bg=PANEL); row.pack(fill=tk.X, pady=2)
            lbl = tk.Label(row, text=str(var.get()), bg=PANEL, fg=ACCENT,
                           font=('Segoe UI', 9), width=4); lbl.pack(side=tk.RIGHT)
            ttk.Scale(row, from_=mn, to=mx, variable=var,
                      orient=tk.HORIZONTAL, length=260).pack(side=tk.LEFT, fill=tk.X, expand=True)
            var.trace_add('write', lambda *a, l=lbl, v=var: _safe_lbl(l, v, '{}'))

        tk.Frame(f, bg=BORDER, height=1).pack(fill=tk.X, pady=10)
        bf = tk.Frame(f, bg=PANEL); bf.pack(fill=tk.X)
        tk.Button(bf, text='Abbrechen', command=self.destroy,
                  bg=BTN, fg=TEXT, bd=0, padx=10, pady=4, relief=tk.FLAT).pack(side=tk.RIGHT, padx=4)
        tk.Button(bf, text='✔  Anwenden', command=self._ok,
                  bg=ACCENT, fg='#000', bd=0, padx=14, pady=4,
                  relief=tk.FLAT, font=('Segoe UI', 9, 'bold')).pack(side=tk.RIGHT, padx=4)

    def _ok(self):
        self.result = (self._thresh.get(), self._blur.get())
        self.destroy()


class _SmoothEdgesDialog(tk.Toplevel):
    """Kanten glätten – weiches Antialiasing der Freisteller-Kante."""
    def __init__(self, parent):
        super().__init__(parent)
        self.result = None
        self.title('Kanten glätten')
        self.configure(bg=PANEL)
        self.resizable(False, False)
        self.transient(parent)
        self._strength = tk.IntVar(value=3)
        self._tighten  = tk.IntVar(value=0)
        self._build()
        self.grab_set()
        self.wait_window()

    def _build(self):
        f = tk.Frame(self, bg=PANEL, padx=20, pady=16); f.pack()
        tk.Label(f, text='Kanten glätten', bg=PANEL, fg=TEXT,
                 font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=(0, 4))
        tk.Label(f, text='Glättet ausgefranste Freisteller-Kanten (Zauberstab /\n'
                         'BG-Entfernen) mit echtem Antialiasing – die Kante bleibt\n'
                         'weich statt wieder hart gerechnet zu werden.',
                 bg=PANEL, fg=TEXT_DIM, font=('Segoe UI', 8),
                 justify='left').pack(anchor='w', pady=(0, 8))

        for label, var, mn, mx, tip in [
            ('Stärke', self._strength, 1, 10,
             '1–3 = leicht (Treppen weg)  |  5–10 = sehr weiche Kante'),
            ('Kante zusammenziehen', self._tighten, -10, 10,
             '0 = neutral  |  + entfernt Rest-Halos  |  − lässt Kante wachsen'),
        ]:
            tk.Label(f, text=label, bg=PANEL, fg=TEXT,
                     font=('Segoe UI', 9, 'bold')).pack(anchor='w', pady=(8, 0))
            tk.Label(f, text=tip, bg=PANEL, fg=TEXT_DIM,
                     font=('Segoe UI', 7), justify='left').pack(anchor='w')
            row = tk.Frame(f, bg=PANEL); row.pack(fill=tk.X, pady=2)
            lbl = tk.Label(row, text=str(var.get()), bg=PANEL, fg=ACCENT,
                           font=('Segoe UI', 9), width=4); lbl.pack(side=tk.RIGHT)
            ttk.Scale(row, from_=mn, to=mx, variable=var,
                      orient=tk.HORIZONTAL, length=260).pack(side=tk.LEFT, fill=tk.X, expand=True)
            var.trace_add('write', lambda *a, l=lbl, v=var: _safe_lbl(l, v, '{}'))

        tk.Frame(f, bg=BORDER, height=1).pack(fill=tk.X, pady=10)
        bf = tk.Frame(f, bg=PANEL); bf.pack(fill=tk.X)
        tk.Button(bf, text='Abbrechen', command=self.destroy,
                  bg=BTN, fg=TEXT, bd=0, padx=10, pady=4, relief=tk.FLAT).pack(side=tk.RIGHT, padx=4)
        tk.Button(bf, text='✔  Anwenden', command=self._ok,
                  bg=ACCENT, fg='#000', bd=0, padx=14, pady=4,
                  relief=tk.FLAT, font=('Segoe UI', 9, 'bold')).pack(side=tk.RIGHT, padx=4)

    def _ok(self):
        self.result = (self._strength.get(), self._tighten.get())
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
#  START
# ══════════════════════════════════════════════════════════════════════════════

def main():
    try:
        from PIL import Image  # noqa
    except ImportError:
        import tkinter as tk
        root = tk.Tk(); root.withdraw()
        tk.messagebox.showerror('Pillow fehlt', 'pip install Pillow')
        root.destroy(); sys.exit(1)

    app = ImageEditorApp()
    app.mainloop()


if __name__ == '__main__':
    main()
