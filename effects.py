"""Bild-Effekte für Image Editor Pro"""

import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageFont, ImageChops


# ── Vignette ──────────────────────────────────────────────────────────────────

def apply_vignette(img: Image.Image, strength: float = 0.6) -> Image.Image:
    """Dunkelt die Bildränder ab (Vignetten-Effekt)."""
    rgba = img.convert('RGBA')
    w, h = rgba.size

    # Elliptische Maske: Mitte weiß, Rand schwarz
    mask = Image.new('L', (w, h), 0)
    draw = ImageDraw.Draw(mask)
    mx = int(w * 0.08)
    my = int(h * 0.08)
    draw.ellipse([mx, my, w - mx, h - my], fill=255)
    blur_r = int(min(w, h) * 0.22)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=blur_r))

    # Invertiert → Rand hell, Mitte dunkel → wird als schwarzes Overlay genutzt
    mask_inv = ImageOps.invert(mask)
    alpha_val = int(strength * 255)
    overlay = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    overlay.putalpha(mask_inv.point(lambda x: x * alpha_val // 255))
    # Eigentlich: overlay = schwarzes Bild mit alpha = mask_inv * strength
    overlay = Image.new('RGBA', (w, h), (0, 0, 0, 255))
    overlay.putalpha(mask_inv.point(lambda x: x * alpha_val // 255))

    return Image.alpha_composite(rgba, overlay)


# ── Wasserzeichen ─────────────────────────────────────────────────────────────

POSITIONS = ['Oben links', 'Oben rechts', 'Mitte', 'Unten links', 'Unten rechts']

def apply_watermark(img: Image.Image, text: str, position: str = 'Unten rechts',
                    opacity: int = 60, font_size: int = 36,
                    color: str = '#ffffff') -> Image.Image:
    """Text-Wasserzeichen auf das Bild legen."""
    rgba = img.convert('RGBA')
    w, h = rgba.size

    overlay = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Font
    font = _load_font(font_size)

    # Text-Größe ermitteln
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    pad = 16

    pos_map = {
        'Oben links':    (pad, pad),
        'Oben rechts':   (w - tw - pad, pad),
        'Mitte':         ((w - tw) // 2, (h - th) // 2),
        'Unten links':   (pad, h - th - pad),
        'Unten rechts':  (w - tw - pad, h - th - pad),
    }
    x, y = pos_map.get(position, pos_map['Unten rechts'])

    r, g, b = _hex_to_rgb(color)
    a = int(opacity / 100 * 255)

    # Schatten
    draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, a // 2))
    draw.text((x, y), text, font=font, fill=(r, g, b, a))

    return Image.alpha_composite(rgba, overlay)


# ── Rahmen / Border ───────────────────────────────────────────────────────────

def apply_border(img: Image.Image, size: int = 20,
                 color: str = '#ffffff', inner: bool = False) -> Image.Image:
    """Einfarbigen Rahmen hinzufügen."""
    rgba = img.convert('RGBA')
    r, g, b = _hex_to_rgb(color)
    fill = (r, g, b, 255)

    if inner:
        draw = ImageDraw.Draw(rgba)
        w, h = rgba.size
        for i in range(size):
            draw.rectangle([i, i, w - 1 - i, h - 1 - i], outline=fill)
        return rgba
    else:
        w, h = rgba.size
        new = Image.new('RGBA', (w + size * 2, h + size * 2), fill)
        new.paste(rgba, (size, size))
        return new


# ── Drop Shadow ───────────────────────────────────────────────────────────────

def apply_drop_shadow(img: Image.Image, offset_x: int = 6, offset_y: int = 6,
                      blur: int = 12, color: str = '#000000',
                      shadow_opacity: int = 80) -> Image.Image:
    """Schatten unterhalb des Bildmotivs hinzufügen."""
    rgba = img.convert('RGBA')
    r, g, b = _hex_to_rgb(color)
    a_val = int(shadow_opacity / 100 * 255)

    # Canvas vergrößern damit Schatten Platz hat
    pad = blur * 2 + max(abs(offset_x), abs(offset_y))
    new_w = rgba.width  + pad * 2
    new_h = rgba.height + pad * 2

    # Schatten-Ebene: Umriss des Originals einfärben + blur
    shadow = Image.new('RGBA', (new_w, new_h), (0, 0, 0, 0))
    orig_alpha = rgba.split()[3]
    colored = Image.new('RGBA', rgba.size, (r, g, b, a_val))
    colored.putalpha(orig_alpha.point(lambda x: x * a_val // 255))
    sx = pad + offset_x
    sy = pad + offset_y
    shadow.paste(colored, (sx, sy))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=blur))

    # Original drüber
    result = shadow.copy()
    result.paste(rgba, (pad, pad), mask=rgba.split()[3])
    return result


# ── Farb-Palette extrahieren ──────────────────────────────────────────────────

def extract_palette(img: Image.Image, count: int = 8) -> list[str]:
    """Dominante Farben als Liste von Hex-Strings."""
    small = img.convert('RGB').resize((150, 150), Image.LANCZOS)
    quantized = small.quantize(colors=count, method=Image.Quantize.MEDIANCUT)
    palette_data = quantized.getpalette()[:count * 3]
    colors = []
    for i in range(0, len(palette_data), 3):
        r, g, b = palette_data[i], palette_data[i+1], palette_data[i+2]
        colors.append(f'#{r:02x}{g:02x}{b:02x}')
    # Duplikate entfernen, dabei Reihenfolge beibehalten
    seen = set()
    unique = []
    for c in colors:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique[:count]


# ── Unscharf-Maske (Unsharp Mask) ─────────────────────────────────────────────

def apply_unsharp_mask(img: Image.Image, radius: float = 2.0,
                        percent: int = 150, threshold: int = 3) -> Image.Image:
    """Schärft das Bild mit der Unscharf-Masken-Methode."""
    return img.filter(ImageFilter.UnsharpMask(
        radius=radius, percent=percent, threshold=threshold))


# ── Farb-Balance ──────────────────────────────────────────────────────────────

def apply_color_balance(img: Image.Image,
                         r_shift: int = 0, g_shift: int = 0, b_shift: int = 0,
                         shadows: float = 0.0, highlights: float = 0.0) -> Image.Image:
    """
    Verschiebt RGB-Kanäle (-100…+100) und hebt Lichter/Schatten an.
    shadows / highlights: -1.0 … +1.0
    """
    mode = img.mode
    rgba = img.convert('RGBA')
    r, g, b, a = rgba.split()

    def shift(channel, amount):
        if amount == 0:
            return channel
        return channel.point(lambda x: max(0, min(255, x + amount)))

    r = shift(r, r_shift)
    g = shift(g, g_shift)
    b = shift(b, b_shift)

    # Lichter/Schatten (einfache Kurven-Annäherung)
    if highlights != 0.0:
        v = int(highlights * 60)
        r = r.point(lambda x: max(0, min(255, x + v if x > 128 else x)))
        g = g.point(lambda x: max(0, min(255, x + v if x > 128 else x)))
        b = b.point(lambda x: max(0, min(255, x + v if x > 128 else x)))

    if shadows != 0.0:
        v = int(shadows * 60)
        r = r.point(lambda x: max(0, min(255, x + v if x < 128 else x)))
        g = g.point(lambda x: max(0, min(255, x + v if x < 128 else x)))
        b = b.point(lambda x: max(0, min(255, x + v if x < 128 else x)))

    result = Image.merge('RGBA', (r, g, b, a))
    return result.convert(mode) if mode != 'RGBA' else result


# ── Rauschreduzierung ─────────────────────────────────────────────────────────

def apply_denoise(img: Image.Image, strength: int = 1) -> Image.Image:
    """Einfache Rauschreduzierung über Medianfilter."""
    mode = img.mode
    result = img.convert('RGB')
    for _ in range(strength):
        result = result.filter(ImageFilter.MedianFilter(size=3))
    if mode == 'RGBA':
        result = result.convert('RGBA')
        result.putalpha(img.convert('RGBA').split()[3])
    return result


# ── Weißabgleich ──────────────────────────────────────────────────────────────

def apply_white_balance(img: Image.Image, temperature: int = 0) -> Image.Image:
    """
    Farbtemperatur: negativ = kälter (blauer), positiv = wärmer (oranger).
    Bereich: -100 … +100
    """
    mode = img.mode
    rgba = img.convert('RGBA')
    r, g, b, a = rgba.split()
    t = temperature
    r = r.point(lambda x: max(0, min(255, x + t)))
    b = b.point(lambda x: max(0, min(255, x - t)))
    result = Image.merge('RGBA', (r, g, b, a))
    return result.convert(mode) if mode != 'RGBA' else result


# ── Sepia ───────────────────────────────────────────────────────────────────

def apply_sepia(img: Image.Image) -> Image.Image:
    """Warmer Vintage-Sepia-Ton (Alpha bleibt erhalten)."""
    rgba = img.convert('RGBA')
    a    = rgba.split()[3]
    gray = ImageOps.grayscale(rgba)
    sep  = ImageOps.colorize(gray, black=(34, 21, 9),
                             white=(255, 235, 200), mid=(150, 110, 60))
    out = sep.convert('RGBA'); out.putalpha(a)
    return out


# ── Posterisieren ─────────────────────────────────────────────────────────────

def apply_posterize(img: Image.Image, bits: int = 3) -> Image.Image:
    """Reduziert die Farbabstufungen pro Kanal (1–8 Bit)."""
    rgba = img.convert('RGBA')
    a    = rgba.split()[3]
    rgb  = ImageOps.posterize(rgba.convert('RGB'), max(1, min(8, bits)))
    out  = rgb.convert('RGBA'); out.putalpha(a)
    return out


# ── Schwellenwert ─────────────────────────────────────────────────────────────

def apply_threshold(img: Image.Image, level: int = 128) -> Image.Image:
    """Reines Schwarz/Weiß ab Helligkeits-Schwelle (Alpha bleibt erhalten)."""
    rgba = img.convert('RGBA')
    a    = rgba.split()[3]
    gray = ImageOps.grayscale(rgba)
    bw   = gray.point(lambda x: 255 if x >= level else 0).convert('RGB')
    out  = bw.convert('RGBA'); out.putalpha(a)
    return out


# ── Verpixeln / Mosaik ──────────────────────────────────────────────────────

def apply_pixelate(img: Image.Image, block: int = 12) -> Image.Image:
    """Mosaik-Effekt – runter- und wieder hochskalieren (für Zensur o. Ä.)."""
    rgba = img.convert('RGBA')
    w, h = rgba.size
    block = max(2, int(block))
    small = rgba.resize((max(1, w // block), max(1, h // block)), Image.NEAREST)
    return small.resize((w, h), Image.NEAREST)


# ── Stilisieren: Emboss / Kanten / Skizze / Ölgemälde ───────────────────────

def apply_emboss(img: Image.Image) -> Image.Image:
    """Relief-Effekt."""
    rgba = img.convert('RGBA')
    a    = rgba.split()[3]
    emb  = rgba.convert('RGB').filter(ImageFilter.EMBOSS)
    out  = emb.convert('RGBA'); out.putalpha(a)
    return out


def apply_find_edges(img: Image.Image) -> Image.Image:
    """Konturen hervorheben (Kantenerkennung)."""
    rgba = img.convert('RGBA')
    a    = rgba.split()[3]
    edg  = rgba.convert('RGB').filter(ImageFilter.FIND_EDGES)
    out  = edg.convert('RGBA'); out.putalpha(a)
    return out


def apply_sketch(img: Image.Image, blur: int = 12) -> Image.Image:
    """Bleistift-Skizze über Color-Dodge (Grau ÷ unscharf invertiertes Grau)."""
    import numpy as np
    rgba = img.convert('RGBA')
    a    = rgba.split()[3]
    gray = ImageOps.grayscale(rgba)
    inv  = ImageOps.invert(gray).filter(ImageFilter.GaussianBlur(blur))
    g    = np.asarray(gray, dtype=np.float32)
    b    = np.asarray(inv,  dtype=np.float32)
    res  = np.clip(g * 255.0 / (256.0 - b), 0, 255).astype('uint8')
    sk   = Image.fromarray(res, 'L').convert('RGBA'); sk.putalpha(a)
    return sk


def apply_oil_paint(img: Image.Image, size: int = 5) -> Image.Image:
    """Ölgemälde-Annäherung über den Modus-Filter."""
    rgba = img.convert('RGBA')
    a    = rgba.split()[3]
    rgb  = rgba.convert('RGB').filter(ImageFilter.ModeFilter(size=max(3, int(size))))
    out  = rgb.convert('RGBA'); out.putalpha(a)
    return out


# ── Farbton verschieben (Hue) ───────────────────────────────────────────────

def apply_hue_shift(img: Image.Image, degrees: int = 0) -> Image.Image:
    """Dreht den Farbton (0–360°), Sättigung/Helligkeit bleiben."""
    rgba  = img.convert('RGBA')
    a     = rgba.split()[3]
    h, s, v = rgba.convert('RGB').convert('HSV').split()
    shift = int(degrees / 360.0 * 255) % 256
    h     = h.point(lambda x: (x + shift) % 256)
    rgb   = Image.merge('HSV', (h, s, v)).convert('RGB')
    out   = rgb.convert('RGBA'); out.putalpha(a)
    return out


# ── Bewegungsunschärfe (Motion Blur) ─────────────────────────────────────────

def apply_motion_blur(img: Image.Image, distance: int = 15,
                      angle: int = 0) -> Image.Image:
    """Richtungs-Unschärfe: mittelt versetzte Kopien entlang eines Winkels."""
    import numpy as np
    rgba = img.convert('RGBA')
    arr  = np.asarray(rgba, dtype=np.float32)
    n    = max(1, int(distance))
    dx   = math.cos(math.radians(angle))
    dy   = math.sin(math.radians(angle))
    acc  = np.zeros_like(arr)
    cnt  = 0
    for i in range(-n, n + 1):
        ox = int(round(dx * i)); oy = int(round(dy * i))
        acc += np.roll(arr, (oy, ox), axis=(0, 1))
        cnt += 1
    out = (acc / cnt).astype('uint8')
    return Image.fromarray(out, 'RGBA')


# ── Helfer ────────────────────────────────────────────────────────────────────

def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _load_font(size: int) -> ImageFont.ImageFont:
    for name in ['arialbd.ttf', 'arial.ttf', 'DejaVuSans-Bold.ttf', 'DejaVuSans.ttf']:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()
