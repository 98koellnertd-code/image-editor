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
