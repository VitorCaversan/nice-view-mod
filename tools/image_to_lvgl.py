"""
Convert any image to an LVGL INDEXED_1BIT C array, suitable for nice-view.

Usage:
    pip install pillow
    python image_to_lvgl.py <image_path> <symbol_name> [options]

Options:
    --width       Output width in pixels  (default: 140)
    --height      Output height in pixels (default: 68)
    --invert      Swap black and white
    --no-crop     Stretch to fit instead of cropping to preserve aspect ratio
    --threshold   Brightness cutoff for B&W (0-255, default: 128)

Examples:
    python image_to_lvgl.py logo.png motociclosos_left
    python image_to_lvgl.py logo.png motociclosos_left --width 68 --height 140
    python image_to_lvgl.py logo.png motociclosos_right --invert --threshold 100

The script outputs C code ready to paste into art.c.
"""

import sys
import argparse
import math

try:
    from PIL import Image, ImageOps
except ImportError:
    print("ERROR: Pillow is not installed. Run: pip install pillow")
    sys.exit(1)


def image_to_lvgl(
    image_path: str,
    symbol_name: str,
    width: int = 140,
    height: int = 68,
    invert: bool = False,
    crop: bool = True,
    threshold: int = 128,
) -> str:
    img = Image.open(image_path)

    # Convert to RGBA first to handle transparent PNGs correctly
    img = img.convert("RGBA")

    # Composite onto a white background (handles transparency)
    background = Image.new("RGBA", img.size, (255, 255, 255, 255))
    background.paste(img, mask=img.split()[3])  # alpha channel as mask
    img = background.convert("L")  # grayscale

    # Resize to target dimensions
    if crop:
        # Scale so the image fills the target, then center-crop (preserves aspect ratio)
        img = ImageOps.fit(img, (width, height), Image.LANCZOS)
    else:
        # Stretch to fit exactly (may distort)
        img = img.resize((width, height), Image.LANCZOS)

    # Threshold to pure 1-bit (0 = black, 255 = white)
    img = img.point(lambda p: 255 if p >= threshold else 0, "L")

    if invert:
        img = ImageOps.invert(img)

    # Pack pixel data: 1 = white (index 1), 0 = black (index 0)
    # Each row is ceil(width / 8) bytes, last bits padded with 0
    bytes_per_row = math.ceil(width / 8)
    pixel_rows = []

    for y in range(height):
        row_bytes = []
        for bx in range(bytes_per_row):
            byte_val = 0
            for bit in range(8):
                x = bx * 8 + bit
                if x < width:
                    pixel = img.getpixel((x, y))
                    # White pixel → bit 1 (index 1 = white in LVGL palette below)
                    if pixel >= 128:
                        byte_val |= 1 << (7 - bit)
            row_bytes.append(byte_val)
        pixel_rows.append(row_bytes)

    data_size = height * bytes_per_row + 8  # +8 for 2-color palette

    # Build C output
    lines = []
    attr = symbol_name.upper()
    lines.append(f"#ifndef LV_ATTRIBUTE_IMG_{attr}")
    lines.append(f"#define LV_ATTRIBUTE_IMG_{attr}")
    lines.append(f"#endif")
    lines.append(f"")
    lines.append(
        f"const LV_ATTRIBUTE_MEM_ALIGN LV_ATTRIBUTE_LARGE_CONST LV_ATTRIBUTE_IMG_{attr} uint8_t"
    )
    lines.append(f"    {symbol_name}_map[] = {{")
    lines.append(f"#if CONFIG_NICE_VIEW_WIDGET_INVERTED")
    lines.append(f"        0xff, 0xff, 0xff, 0xff, /*Color of index 0*/")
    lines.append(f"        0x00, 0x00, 0x00, 0xff, /*Color of index 1*/")
    lines.append(f"#else")
    lines.append(f"        0x00, 0x00, 0x00, 0xff, /*Color of index 0*/")
    lines.append(f"        0xff, 0xff, 0xff, 0xff, /*Color of index 1*/")
    lines.append(f"#endif")
    lines.append(f"")

    for row in pixel_rows:
        hex_bytes = ", ".join(f"0x{b:02x}" for b in row)
        lines.append(f"        {hex_bytes},")

    lines.append(f"}};")
    lines.append(f"")
    lines.append(f"const lv_img_dsc_t {symbol_name} = {{")
    lines.append(f"    .header.cf = LV_IMG_CF_INDEXED_1BIT,")
    lines.append(f"    .header.always_zero = 0,")
    lines.append(f"    .header.reserved = 0,")
    lines.append(f"    .header.w = {width},")
    lines.append(f"    .header.h = {height},")
    lines.append(f"    .data_size = {data_size},")
    lines.append(f"    .data = {symbol_name}_map,")
    lines.append(f"}};")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Convert image to LVGL INDEXED_1BIT C array")
    parser.add_argument("image", help="Path to input image (PNG, JPG, BMP, etc.)")
    parser.add_argument("symbol", help="C symbol name (e.g. motociclosos_left)")
    parser.add_argument("--width", type=int, default=140, help="Output width in pixels (default: 140)")
    parser.add_argument("--height", type=int, default=68, help="Output height in pixels (default: 68)")
    parser.add_argument("--invert", action="store_true", help="Invert black/white")
    parser.add_argument(
        "--no-crop",
        action="store_true",
        help="Stretch to fit instead of center-crop (may distort aspect ratio)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=128,
        help="Brightness threshold for B&W conversion (0-255, default 128). "
             "Lower = more white pixels kept as white.",
    )
    args = parser.parse_args()

    result = image_to_lvgl(
        args.image,
        args.symbol,
        width=args.width,
        height=args.height,
        invert=args.invert,
        crop=not args.no_crop,
        threshold=args.threshold,
    )
    print(result)


if __name__ == "__main__":
    main()
