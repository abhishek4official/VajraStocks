# Installer Assets

Place application icons here before building installers:

| File | Used by | Notes |
|------|---------|-------|
| `icon.ico` | Windows (Inno Setup, PyInstaller EXE) | 256×256 multi-res ICO |
| `icon.png` | Linux .deb / .rpm / AppImage | 256×256 PNG |
| `icon.icns` | macOS DMG | Multi-res ICNS bundle |

If icons are absent the build scripts will still complete; the installer will use
the default system/PyInstaller icon.

## Quick conversion (ImageMagick)

```bash
# PNG → ICO (Windows)
convert icon.png -resize 256x256 icon.ico

# PNG → ICNS (macOS)
mkdir icon.iconset
sips -z 16 16     icon.png --out icon.iconset/icon_16x16.png
sips -z 32 32     icon.png --out icon.iconset/icon_32x32.png
sips -z 128 128   icon.png --out icon.iconset/icon_128x128.png
sips -z 256 256   icon.png --out icon.iconset/icon_256x256.png
iconutil -c icns icon.iconset -o icon.icns
```
