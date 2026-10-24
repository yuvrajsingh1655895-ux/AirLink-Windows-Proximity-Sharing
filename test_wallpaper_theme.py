import tempfile
import unittest
from pathlib import Path

from PIL import Image

from wallpaper_theme import DEFAULT_PALETTE, palette_for_wallpaper


class WallpaperThemeTests(unittest.TestCase):
    def _palette_for_rgb(self, rgb):
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()
        path = Path(tmp.name)
        try:
            Image.new("RGB", (24, 24), rgb).save(path)
            return palette_for_wallpaper(str(path))
        finally:
            path.unlink(missing_ok=True)

    def test_missing_wallpaper_uses_default_palette(self):
        self.assertEqual(palette_for_wallpaper(None), DEFAULT_PALETTE)

    def test_different_wallpaper_hues_change_accent(self):
        blue = self._palette_for_rgb((35, 100, 230))
        green = self._palette_for_rgb((35, 190, 90))
        purple = self._palette_for_rgb((150, 50, 220))
        self.assertNotEqual(blue["BLUE"], green["BLUE"])
        self.assertNotEqual(blue["BLUE"], purple["BLUE"])
        self.assertNotEqual(green["BLUE"], purple["BLUE"])

    def test_palette_has_all_expected_roles_and_hex_values(self):
        palette = self._palette_for_rgb((220, 75, 50))
        self.assertEqual(set(palette), set(DEFAULT_PALETTE))
        for value in palette.values():
            self.assertRegex(value, r"^#[0-9a-fA-F]{6}$")


if __name__ == "__main__":
    unittest.main()
