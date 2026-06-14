<div align="center">

# 🎨 Image Editor Pro

**Ein schlanker, schneller Bildeditor mit Ebenen-System, KI-Hintergrundentfernung und integriertem SEO-Panel — komplett in Python & Tkinter.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Pillow](https://img.shields.io/badge/Pillow-10.0%2B-0a7c96)](https://python-pillow.org/)
[![Platform](https://img.shields.io/badge/Plattform-Windows-0078D6?logo=windows&logoColor=white)](#)
[![GUI](https://img.shields.io/badge/GUI-Tkinter-ff4466)](#)
[![License](https://img.shields.io/badge/Lizenz-MIT-00d4ff)](#-lizenz)

<sub>Modernes UI mit abgerundeten Buttons · Ebenen mit Blend-Modi · Zauberstab mit Live-Vorschau · Hintergrund entfernen (rembg) · PSD & SVG · SEO-Metadaten · One-File-Build</sub>

</div>

---

## 📑 Inhaltsverzeichnis

- [Überblick](#-überblick)
- [Features](#-features)
- [Performance & Bedienkomfort](#-performance--bedienkomfort)
- [Screenshots](#-screenshots)
- [Installation](#-installation)
- [Schnellstart](#-schnellstart)
- [Bedienung](#-bedienung)
- [Tastaturkürzel](#-tastaturkürzel)
- [Projektstruktur](#-projektstruktur)
- [Build (.exe erstellen)](#-build-exe-erstellen)
- [Abhängigkeiten](#-abhängigkeiten)
- [Lizenz](#-lizenz)

---

## 🔍 Überblick

**Image Editor Pro** ist eine eigenständige Desktop-Anwendung zur Bildbearbeitung mit modernem, dunklem Interface — mit abgerundeten Buttons, klar hervorgehobenem aktivem Werkzeug und einem mitwachsenden Pinsel-Cursor. Der Editor kombiniert klassische Pixel-Werkzeuge (Pinsel, Radierer, Auswahl, Zauberstab) mit einem vollwertigen **Ebenen-System**, professionellen **Effekten** und einem eingebauten **SEO-Workflow** für Web- und Social-Media-Bilder.

Das Fenster öffnet sich automatisch maximiert, und auch bei starkem Zoom bleibt die Darstellung flüssig, da nur der sichtbare Bildausschnitt gerendert wird.

Die Anwendung ist modular aufgebaut, läuft direkt über Python oder lässt sich mit **PyInstaller** zu einer einzelnen `.exe` kompilieren — ganz ohne Installation.

---

## ✨ Features

### 🖌 Werkzeuge
| Werkzeug | Beschreibung |
|----------|--------------|
| **Auswahl** | Rechteckige Auswahl mit Verschieben & Zuschneiden |
| **Zauberstab** ⚡ | Farbbasierte Auswahl mit einstellbarer Toleranz und Live-Vorschau (zusammenhängend / global) |
| **Pinsel** 🖌 | Freihandmalen mit variabler Größe & Opazität |
| **Radierer** ◻ | Transparentes Löschen |
| **Füllen** 🪣 | Flächen- & Flood-Fill |
| **Pipette** 🔬 | Farbe aus dem Bild aufnehmen |
| **Text** T | Text direkt auf das Bild setzen |
| **Zuschneiden** ⊹ | Crop-Werkzeug |

### 🗂 Ebenen-System
- Mehrere Ebenen mit **Sichtbarkeit, Deckkraft & Sperren**
- **10 Blend-Modi**: Normal, Multiplizieren, Bildschirm, Überlagern, Abdunkeln, Aufhellen, Differenz, Weich-Licht, Addition, Subtrahieren
- Ebenen duplizieren, verschieben, umbenennen, zusammenführen (merge down) und reduzieren (flatten)

### 🎚 Korrekturen
- Helligkeit / Kontrast · Sättigung / Schärfe
- Farb-Balance · Weißabgleich (Farbtemperatur)
- Weichzeichner · Unscharf-Maske · Rauschreduzierung
- Auto-Kontrast · Farben angleichen (Equalize)

### 🌈 Effekte
- **Vignette** mit einstellbarer Stärke
- **Wasserzeichen** (Text, Position, Opazität, Schatten)
- **Rahmen** (innen/außen, Farbe, Breite)
- **Schlagschatten** (Offset, Blur, Farbe, Deckkraft)
- **Farb-Palette** aus dem Bild extrahieren

### 🪄 Bild-Operationen
- Größe ändern & Arbeitsfläche anpassen
- Drehen (90°/180°/frei) & Spiegeln
- Graustufen · Invertieren · Ecken abrunden
- **Hintergrund entfernen (KI)** über [rembg](https://github.com/danielgatis/rembg) — Standardmodell `isnet-general-use` mit Alpha-Matting
- **Alpha-Kante verfeinern** für saubere Freisteller

### 🔎 SEO-Panel
Pflege von Bild-Metadaten direkt im Editor:
`Alt-Text`, `Meta-Titel`, `Meta-Beschreibung`, `Keywords`, `Tags`, `Autor`, `Copyright`, `Kategorie`.
- **`.seo.json`-Begleitdatei ist opt-in** — sie wird nur erzeugt, wenn das Häkchen im SEO-Tab gesetzt **und** SEO-Daten vorhanden sind (standardmäßig aus, kein ungewolltes Mit-Exportieren).
- Import/Export der Metadaten als JSON.
- **🧹 Meta entfernen** (Toolbar-Button): löscht in einem Schritt alle SEO-Felder, schaltet die Begleitdatei ab und entfernt eingebettete Tags (EXIF / PNG-Info / ICC) aus allen Ebenen → garantiert metadatenfreie Exporte.

### 📐 Social-Media-Presets
Fertige Größen für Instagram, Facebook, Twitter/X, LinkedIn, YouTube, TikTok, Pinterest, OG-Images, Favicon sowie HD/QHD/4K und A4 @150dpi.

### 📁 Dateiformate
- **Öffnen:** PNG, JPG/JPEG, BMP, TIFF, WebP, ICO, GIF, EPS, PPM
  - **SVG** wird über **PyMuPDF** in 2× Auflösung gerendert — bewusst ohne native Cairo-DLL, damit das Laden unter Windows ohne Zusatz-Installation funktioniert.
  - **PSD mit Ebenen** über **psd-tools** — jede PSD-Ebene wird als eigene Ebene übernommen (inkl. Position & Sichtbarkeit), mit automatischem Fallback auf das zusammengefasste Bild.
- **Speichern/Export:** PNG, JPEG, WebP, BMP, TIFF, ICO, GIF, PPM — inkl. Qualität & WebP-Lossless
- Einfügen direkt aus der **Zwischenablage**

---

## ⚡ Performance & Bedienkomfort

Der Editor ist auf flüssiges Arbeiten auch bei großen Bildern und hohem Zoom ausgelegt:

| Bereich | Detail |
|---------|--------|
| **Viewport-Rendering** | Nur der sichtbare Ausschnitt wird gerendert — der Aufwand bleibt konstant, egal wie weit du hineinzoomst (keine Freezes mehr). |
| **Composite-Cache** | Die Ebenen werden beim Zoomen/Verschieben nicht bei jedem Frame neu zusammengerechnet. |
| **Schnell → scharf** | `NEAREST` während Zoom/Pan für sofortige Reaktion, danach automatischer scharfer `LANCZOS`-Nachzieh-Render. |
| **Zoom zum Cursor** | Mausrad-Zoom zentriert auf den Mauszeiger statt auf die Ecke. |
| **Maximierter Start** | Das Fenster öffnet automatisch im maximierten Zustand. |
| **Mitwachsender Cursor** | Pinsel-/Radierer-Ring zeigt Größe **und** Position live am Cursor (Pinsel cyan, Radierer rot, mit Fadenkreuz) und aktualisiert sich sofort beim Verstellen des Größe-Reglers. |
| **Sichtbares Werkzeug** | Aktives Werkzeug mit Akzent-Balken, fetter Cyan-Schrift und Hover-Effekt; aktuelle Auswahl zusätzlich in der Statusleiste. |
| **Besserer Zauberstab** | Intuitivere Toleranz-Metrik (Max-Kanal-Differenz) mit **Live-Update** der Auswahl beim Schieben des Reglers oder Umschalten von „Zusammenhängend". |

---

## 🖼 Screenshots

<div align="center">

> Dunkles UI mit abgerundeter Werkzeugleiste links (aktives Werkzeug hervorgehoben), Canvas mit Transparenz-Schachbrett und mitwachsendem Cursor-Ring in der Mitte sowie Info-/Ebenen-/Korrekturen-/SEO-Tabs rechts. Toolbar oben mit `Vignette`, `Schatten`, `Wasserzeichen` und `Meta entfernen`.

</div>

---

## 📦 Installation

### Voraussetzungen
- **Python 3.10+** (Windows empfohlen)
- `tkinter` (bei Standard-Python-Installationen bereits enthalten)

### Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

Die optionalen KI-Pakete (`rembg`) und SVG-Unterstützung (`pymupdf`) lassen sich auch direkt aus dem Programm heraus über **Hilfe → Pakete installieren** nachinstallieren.

---

## 🚀 Schnellstart

**Per Doppelklick (Windows):**

```bat
START_IMAGE_EDITOR.bat
```

Das Skript prüft, ob Pillow vorhanden ist, installiert es ggf. und startet die App.

**Oder direkt über Python:**

```bash
python image_editor.py
```

---

## 🎮 Bedienung

1. **Bild öffnen** über `Datei → Öffnen…` oder aus der Zwischenablage einfügen (`Strg+V`).
2. **Werkzeug wählen** in der linken Leiste — Farben über Vordergrund/Hintergrund-Swatches oder Hex-Eingabe setzen.
3. **Ebenen** im rechten Tab verwalten (Sichtbarkeit, Deckkraft, Blend-Modus).
4. **Korrekturen & Effekte** über die gleichnamigen Menüs anwenden.
5. **Hintergrund entfernen** über `Bild → Hintergrund entfernen…` (lädt das KI-Modell beim ersten Aufruf).
6. **SEO-Daten** im SEO-Tab pflegen — die `.seo.json`-Begleitdatei wird nur erzeugt, wenn du das Häkchen aktiv setzt. Mit **🧹 Meta entfernen** löschst du alle Metadaten in einem Schritt.
7. **Exportieren** über `Datei → Exportieren als…` (`Strg+E`) mit Format- und Qualitätsauswahl.

---

## ⌨️ Tastaturkürzel

| Kürzel | Aktion | | Kürzel | Aktion |
|--------|--------|---|--------|--------|
| `Strg+N` | Neu | | `Strg+Z` | Rückgängig |
| `Strg+O` | Öffnen | | `Strg+Y` | Wiederholen |
| `Strg+S` | Speichern | | `Strg+A` | Alles auswählen |
| `Strg+Shift+S` | Speichern unter | | `Esc` | Auswahl aufheben |
| `Strg+E` | Exportieren | | `Entf` | Auswahl löschen |
| `Strg+V` | Aus Zwischenablage einfügen | | `Strg+I` | Auswahl umkehren |
| `Strg+Shift+N` | Neue Ebene | | `Strg++` / `Strg+-` | Zoom rein/raus |
| `Strg+0` | An Fenster anpassen | | `Strg+1` | 100 % |

---

## 🗂 Projektstruktur

```
Image-Editor/
├── image_editor.py        # Hauptanwendung (UI, Canvas, Menüs, Werkzeuge)
├── constants.py           # Theme-Farben, Blend-Modi, Datei- & Social-Presets
├── layers.py              # Ebenen-Klasse & Compositing / Blend-Modi
├── effects.py             # Vignette, Wasserzeichen, Rahmen, Schatten, Palette …
├── dialogs.py             # Alle modalen Dialoge (Resize, Watermark, Adjust …)
├── requirements.txt       # Python-Abhängigkeiten
├── START_IMAGE_EDITOR.bat # Schnellstart unter Windows
├── BUILD.bat              # One-File-Build mit PyInstaller
└── ImageEditorPro.spec    # PyInstaller-Spezifikation
```

---

## 🔨 Build (.exe erstellen)

Erstellt eine eigenständige Windows-Executable mit **PyInstaller**:

```bat
BUILD.bat
```

Das Skript prüft & installiert benötigte Build-Abhängigkeiten, beendet laufende Instanzen, räumt alte Builds auf und kompiliert:

```
dist\ImageEditorPro.exe
```

Alternativ direkt über die Spec-Datei:

```bash
python -m PyInstaller ImageEditorPro.spec
```

---

## 📚 Abhängigkeiten

| Paket | Zweck | Status |
|-------|-------|--------|
| **Pillow** ≥ 10.0 | Bildverarbeitung (Kern) | Pflicht |
| **numpy** ≥ 1.24 | Zauberstab & Blend-Modi | Empfohlen |
| **scipy** ≥ 1.10 | Zusammenhängende Auswahl | Empfohlen |
| **pymupdf** ≥ 1.24 | SVG öffnen (ohne native Cairo-DLL) | Optional |
| **psd-tools** ≥ 1.9 | PSD mit Ebenen öffnen | Optional |
| **rembg** ≥ 2.0 | KI-Hintergrundentfernung | Optional |

> Ohne die optionalen Pakete bleibt der Editor voll funktionsfähig — nur die jeweiligen Spezialfunktionen sind dann deaktiviert.

---

## 📄 Lizenz

Veröffentlicht unter der **MIT-Lizenz**. Frei nutzbar, anpassbar und verteilbar.

---

<div align="center">

**Image Editor Pro** · Erstellt mit 🐍 Python & Tkinter

<sub>Wenn dir das Projekt gefällt, gib ihm ein ⭐ auf GitHub!</sub>

</div>
