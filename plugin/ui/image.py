from __future__ import annotations

import base64
import io
import re
from collections.abc import Sequence
from functools import lru_cache
from itertools import chain

import sublime
from more_itertools import grouper

from ..libs import png
from ..settings import get_setting
from ..shared import global_get
from ..utils import simple_decorator


def get_image_color(img_name: str, region: sublime.Region) -> str:
    """
    @brief Get the image color from plugin settings in the form of #RRGGBBAA.

    @param img_name The image name
    @param region   The region

    @return The color code in the form of #RRGGBBAA
    """
    return color_code_to_rgba(get_setting("image_colors")[img_name], region)


@lru_cache
def get_colored_image_base64_by_color(img_name: str, rgba_code: str) -> str:
    """
    @brief Get the colored image in base64 string by RGBA color code.

    @param img_name  The image name
    @param rgba_code The color code in #RRGGBBAA

    @return The image base64 string
    """
    if not rgba_code:
        return global_get(f"images.{img_name}.base64")

    img_bytes: bytes = global_get(f"images.{img_name}.bytes")
    img_bytes = change_png_bytes_color(img_bytes, rgba_code)

    return base64.b64encode(img_bytes).decode()


def get_colored_image_base64_by_region(img_name: str, region: sublime.Region) -> str:
    """
    @brief Get the colored image in base64 string by region.

    @param img_name The image name
    @param region   The region

    @return The image base64 string
    """
    return get_colored_image_base64_by_color(img_name, get_image_color(img_name, region))


@lru_cache
def change_png_bytes_color(img_bytes: bytes, rgba_code: str) -> bytes:
    """
    @brief Change all colors in the PNG bytes to the new color.

    @param img_bytes The PNG image bytes
    @param rgba_code The color code in the form of #RRGGBBAA

    @return Color-changed PNG image bytes.
    """
    if not rgba_code:
        return img_bytes

    if not re.match(r"#[0-9a-fA-F]{8}$", rgba_code):
        raise ValueError("Invalid RGBA color code: " + rgba_code)

    def render_pixel(
        rgba_src: Sequence[int],  # length=4
        rgba_dst: Sequence[int],  # length=4
        invert_gray: bool = False,
    ) -> tuple[int, int, int, int]:
        gray = calculate_gray(rgba_src)
        if invert_gray:
            gray = 0xFF - gray

        # ">> 8" is an approximation for "/ 0xFF" in following calculations
        return (
            int(rgba_dst[0] * gray) >> 8,
            int(rgba_dst[1] * gray) >> 8,
            int(rgba_dst[2] * gray) >> 8,
            int(rgba_dst[3] * rgba_src[3]) >> 8,
        )

    invert_gray = not is_img_light(img_bytes)  # invert for dark image to get a solid looking
    rgba_dst = [int(rgba_code[i : i + 2], 16) for i in range(1, 9, 2)]

    rows_dst: list[list[int]] = []
    for row_src in png.Reader(bytes=img_bytes).asRGBA()[2]:
        row_dst = list(chain(*(render_pixel(rgba_src, rgba_dst, invert_gray) for rgba_src in grouper(row_src, 4))))
        rows_dst.append(row_dst)

    buf = io.BytesIO()
    png.from_array(rows_dst, "RGBA").write(buf)

    return buf.getvalue()


def calculate_gray(rgb: Sequence[int]) -> int:
    """
    @brief Calculate the gray scale of a color.
    @see   https://atlaboratary.blogspot.com/2013/08/rgb-g-rey-l-gray-r0.html

    @param rgb The rgb color in list form

    @return The gray scale.
    """
    return (rgb[0] * 38 + rgb[1] * 75 + rgb[2] * 15) >> 7


def is_img_light(img_bytes: bytes) -> bool:
    """
    @brief Determine if image is light colored.

    @param img_bytes The image bytes

    @return True if image is light, False otherwise.
    """
    w, h, rows, _ = png.Reader(bytes=img_bytes).asRGBA()
    gray_sum = sum(calculate_gray(rgba) for row in rows for rgba in grouper(row, 4))
    return (gray_sum >> 7) > w * h


def add_alpha_to_rgb(color_code: str) -> str:
    """
    @brief Add the alpha part to a valid RGB color code (#RGB, #RRGGBB, #RRGGBBAA)

    @param color_code The color code

    @return The color code in the form of #RRGGBBAA in lowercase
    """
    if not (rgb := color_code.lstrip("#")[:8]):
        return ""

    if len(rgb) == 8:
        return f"#{rgb}".lower()

    # RGB to RRGGBB
    if len(rgb) == 3:
        rgb = rgb[0] * 2 + rgb[1] * 2 + rgb[2] * 2

    if len(rgb) == 6:
        return f"#{rgb[:6]}ff".lower()

    raise ValueError(f"Invalid RGB/RGBA color code: {color_code}")


@simple_decorator(add_alpha_to_rgb)
def color_code_to_rgba(color_code: str, region: sublime.Region) -> str:
    """
    @brief Convert user settings color code into #RRGGBBAA form

    @param color_code The color code string from user settings
    @param region     The scope-related region

    @return The color code in the form of #RRGGBBAA
    """
    if not color_code:
        return ""

    # "color_code" is a scope?
    if not color_code.startswith("#"):
        if view := sublime.active_window().active_view():
            # "color" is guaranteed to be #RRGGBB or #RRGGBBAA
            color = view.style_for_scope(view.scope_name(region.end() - 1)).get("foreground", "")

            if color_code == "@scope":
                return color

            if color_code == "@scope_inverted":
                # strip "#" and make color into RRGGBBAA int
                rgba_int = int(f"{color}ff"[1:9], 16)
                # invert RRGGBB and remain AA, prepend 0s to hex until 8 chars RRGGBBAA
                return f"#{(~rgba_int & 0xFFFFFF00) | (rgba_int & 0xFF):08x}"
        return ""

    # now color code must starts with "#"
    rgb = color_code[1:9]  # strip "#" and possible extra chars

    # RGB, RRGGBB, RRGGBBAA are legal
    if len(rgb) in {3, 6, 8} and re.match(r"[0-9a-fA-F]+$", rgb):
        return f"#{rgb}"

    return ""
