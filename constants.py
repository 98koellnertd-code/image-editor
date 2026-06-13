"""Farben, Presets, Dateitypen für Image Editor Pro"""

# ── Theme ──────────────────────────────────────────────────────────────────
BG        = '#0f1117'
PANEL     = '#161b27'
PANEL2    = '#1c2333'
ACCENT    = '#00d4ff'
ACCENT2   = '#ff4466'
TEXT      = '#e8edf8'
TEXT_DIM  = '#5a6e96'
BORDER    = '#232e44'
BTN       = '#1e2b44'
BTN_ACT   = '#2a3f66'
CANVAS_BG = '#1a1a28'
TOOLBAR   = '#12182a'

# ── Ebenenmodi ────────────────────────────────────────────────────────────
BLEND_MODES = [
    'Normal', 'Multiplizieren', 'Bildschirm', 'Überlagern',
    'Abdunkeln', 'Aufhellen', 'Differenz', 'Weich-Licht',
    'Addition', 'Subtrahieren',
]

# ── Dateitypen ─────────────────────────────────────────────────────────────
OPEN_TYPES = [
    ('Alle Bilder', '*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.webp *.ico *.gif *.svg *.eps *.ppm'),
    ('PNG',  '*.png'), ('JPEG', '*.jpg *.jpeg'), ('WebP', '*.webp'),
    ('BMP',  '*.bmp'), ('TIFF', '*.tiff *.tif'), ('ICO',  '*.ico'),
    ('GIF',  '*.gif'), ('SVG',  '*.svg'),        ('EPS',  '*.eps'),
    ('Alle Dateien', '*.*'),
]
SAVE_TYPES = [
    ('PNG',  '*.png'), ('JPEG', '*.jpg'), ('WebP', '*.webp'),
    ('BMP',  '*.bmp'), ('TIFF', '*.tiff'), ('ICO', '*.ico'),
    ('GIF',  '*.gif'), ('PPM',  '*.ppm'), ('Alle Dateien', '*.*'),
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
