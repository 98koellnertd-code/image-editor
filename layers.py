"""Layer-System für Image Editor Pro"""

from PIL import Image, ImageChops

BLEND_MODES = [
    'Normal', 'Multiplizieren', 'Bildschirm', 'Überlagern',
    'Abdunkeln', 'Aufhellen', 'Differenz', 'Weich-Licht',
    'Addition', 'Subtrahieren',
]


class Layer:
    _counter = 0

    def __init__(self, image: Image.Image, name: str | None = None,
                 visible: bool = True, opacity: int = 100,
                 blend_mode: str = 'Normal', locked: bool = False):
        Layer._counter += 1
        self.image      = image.convert('RGBA')
        self.name       = name or f'Ebene {Layer._counter}'
        self.visible    = visible
        self.opacity    = opacity      # 0–100
        self.blend_mode = blend_mode
        self.locked     = locked

    def copy(self) -> 'Layer':
        obj = Layer.__new__(Layer)
        obj.image      = self.image.copy()
        obj.name       = self.name
        obj.visible    = self.visible
        obj.opacity    = self.opacity
        obj.blend_mode = self.blend_mode
        obj.locked     = self.locked
        return obj

    def __repr__(self):
        return (f'<Layer "{self.name}" vis={self.visible} '
                f'op={self.opacity} mode={self.blend_mode}>')


def composite(layers: list[Layer], canvas_w: int, canvas_h: int) -> Image.Image:
    """Alle sichtbaren Ebenen zu einem RGBA-Bild zusammenführen."""
    result = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
    for layer in layers:
        if not layer.visible:
            continue
        top = layer.image.copy()
        # Deckkraft anwenden
        if layer.opacity < 100:
            r, g, b, a = top.split()
            a = a.point(lambda x: x * layer.opacity // 100)
            top = Image.merge('RGBA', (r, g, b, a))
        result = blend_layers(result, top, layer.blend_mode)
    return result


def blend_layers(base: Image.Image, top: Image.Image, mode: str) -> Image.Image:
    """Composite 'top' auf 'base' mit dem gewählten Modus (beide RGBA)."""
    if mode == 'Normal':
        return Image.alpha_composite(base, top)

    base_rgb  = base.convert('RGB')
    top_rgb   = top.convert('RGB')
    top_alpha = top.split()[3]

    if mode == 'Multiplizieren':
        blended = ImageChops.multiply(base_rgb, top_rgb)

    elif mode == 'Bildschirm':
        inv_b   = ImageChops.invert(base_rgb)
        inv_t   = ImageChops.invert(top_rgb)
        blended = ImageChops.invert(ImageChops.multiply(inv_b, inv_t))

    elif mode == 'Abdunkeln':
        blended = ImageChops.darker(base_rgb, top_rgb)

    elif mode == 'Aufhellen':
        blended = ImageChops.lighter(base_rgb, top_rgb)

    elif mode == 'Differenz':
        blended = ImageChops.difference(base_rgb, top_rgb)

    elif mode == 'Addition':
        blended = ImageChops.add(base_rgb, top_rgb)

    elif mode == 'Subtrahieren':
        blended = ImageChops.subtract(base_rgb, top_rgb)

    elif mode in ('Überlagern', 'Weich-Licht'):
        try:
            import numpy as np
            b = np.array(base_rgb, dtype=np.float32) / 255.0
            t = np.array(top_rgb,  dtype=np.float32) / 255.0
            if mode == 'Überlagern':
                r = np.where(b < 0.5, 2*b*t, 1 - 2*(1-b)*(1-t))
            else:  # Weich-Licht
                sqrt_b = np.sqrt(np.clip(b, 0, 1))
                r = np.where(t < 0.5,
                             b - (1 - 2*t) * b * (1 - b),
                             b + (2*t - 1) * (sqrt_b - b))
            blended = Image.fromarray(
                (np.clip(r, 0, 1) * 255).astype('uint8'), 'RGB')
        except ImportError:
            blended = ImageChops.multiply(base_rgb, top_rgb)

    else:
        return Image.alpha_composite(base, top)

    # Ergebnis: blended RGB + top alpha über base compositen
    r2, g2, b2 = blended.split()
    blended_rgba = Image.merge('RGBA', (r2, g2, b2, top_alpha))
    result = base.copy()
    result = Image.alpha_composite(result, blended_rgba)
    return result
