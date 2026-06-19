"""Farben, Presets, Dateitypen für Image Editor Pro"""

# ── Theme  (hell, modern – helles Grau statt Dunkelblau) ────────────────────
BG        = '#e9ebef'   # App-Hintergrund (helles Grau)
PANEL     = '#f6f7f9'   # Panels, fast weiß
PANEL2    = '#eceef2'   # eingelassene Felder / Eingaben
ACCENT    = '#4f46e5'   # Indigo – dezenter moderner Akzent
ACCENT2   = '#ef4444'   # Rot (Radierer, Warnungen)
TEXT      = '#222630'   # nahezu Schwarz
TEXT_DIM  = '#6b7280'   # sekundäres Grau
BORDER    = '#d6d9df'   # feine Trennlinien
BTN       = '#e9ebf0'   # Button-Fläche
BTN_ACT   = '#d5dae6'   # aktiver/gedrückter Button
BTN_HOVER = '#dde1e9'   # Hover-Zustand
CANVAS_BG = '#cfd2d8'   # mittleres Grau hinter dem Bild
TOOLBAR   = '#f0f1f4'   # Toolbar / Statusleiste
ACCENT_DIM = '#a5b4fc'  # heller Indigo (Rahmen/Glow)
CURSOR_RING = '#4f46e5' # Pinsel-Ring auf dem Canvas

# ── Ebenenmodi ────────────────────────────────────────────────────────────
BLEND_MODES = [
    'Normal', 'Multiplizieren', 'Bildschirm', 'Überlagern',
    'Abdunkeln', 'Aufhellen', 'Differenz', 'Weich-Licht',
    'Addition', 'Subtrahieren',
]

# ── Dateitypen ─────────────────────────────────────────────────────────────
OPEN_TYPES = [
    ('Alle Bilder', '*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.webp *.ico *.gif *.svg *.eps *.ppm *.psd'),
    ('PNG',  '*.png'), ('JPEG', '*.jpg *.jpeg'), ('WebP', '*.webp'),
    ('BMP',  '*.bmp'), ('TIFF', '*.tiff *.tif'), ('ICO',  '*.ico'),
    ('GIF',  '*.gif'), ('SVG',  '*.svg'),        ('EPS',  '*.eps'),
    ('Photoshop', '*.psd'),
    ('Alle Dateien', '*.*'),
]
SAVE_TYPES = [
    ('PNG',  '*.png'), ('JPEG', '*.jpg'), ('WebP', '*.webp'),
    ('BMP',  '*.bmp'), ('TIFF', '*.tiff'), ('ICO', '*.ico'),
    ('GIF',  '*.gif'), ('SVG',  '*.svg'), ('PPM',  '*.ppm'),
    ('Alle Dateien', '*.*'),
]

# ── Social-Media & Web-Presets ─────────────────────────────────────────────
SOCIAL_PRESETS = [
    ('Instagram Post',     1080,  1080),
    ('Instagram Story',    1080,  1920),
    ('Instagram Landscape',1080,   566),
    ('Facebook Cover',      820,   312),
    ('Facebook Post',      1200,   630),
    ('OG-Image (Website)', 1200,   630),
    ('Twitter/X Post',     1200,   675),
    ('Twitter/X Header',   1500,   500),
    ('LinkedIn Post',      1200,   627),
    ('LinkedIn Cover',     1584,   396),
    ('YouTube Thumbnail',  1280,   720),
    ('YouTube Banner',     2560,  1440),
    ('TikTok Video',       1080,  1920),
    ('Pinterest Pin',      1000,  1500),
    ('Favicon',             512,   512),
    ('HD  1920×1080',      1920,  1080),
    ('QHD 2560×1440',      2560,  1440),
    ('4K  3840×2160',      3840,  2160),
    ('A4  @150dpi',        1240,  1754),
]
