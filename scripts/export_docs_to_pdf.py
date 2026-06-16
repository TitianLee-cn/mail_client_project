"""Export project Markdown documents to simple PDF files.

This avoids requiring pandoc or LibreOffice in the grading environment.
"""

from pathlib import Path
import re
import textwrap

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.font_manager import FontProperties


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS = [
    ("docs/design.md", "docs/design.pdf"),
    ("docs/test_plan.md", "docs/test_plan.pdf"),
    ("docs/user_manual.md", "docs/user_manual.pdf"),
]
FONT_CANDIDATES = [
    "/mnt/c/Windows/Fonts/msyh.ttc",
    "/mnt/c/Windows/Fonts/simhei.ttf",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def font_properties():
    for candidate in FONT_CANDIDATES:
        path = Path(candidate)
        if path.exists():
            return FontProperties(fname=str(path))
    return FontProperties()


def strip_inline_markdown(text):
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text


def add_text_page(pdf, lines, font, page_no):
    fig = plt.figure(figsize=(8.27, 11.69), dpi=150)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    y = 0.965
    line_height = 0.024
    for text, size, weight in lines:
        ax.text(
            0.07,
            y,
            text,
            fontproperties=font,
            fontsize=size,
            fontweight=weight,
            va="top",
            color="#111827",
        )
        y -= line_height * (size / 10.5)
    ax.text(
        0.5,
        0.025,
        str(page_no),
        ha="center",
        va="bottom",
        fontproperties=font,
        fontsize=9,
        color="#6b7280",
    )
    pdf.savefig(fig)
    plt.close(fig)


def add_image_page(pdf, image_path, caption, font, page_no):
    fig = plt.figure(figsize=(8.27, 11.69), dpi=150)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.text(
        0.07,
        0.95,
        caption,
        fontproperties=font,
        fontsize=14,
        fontweight="bold",
        va="top",
    )
    image = plt.imread(str(image_path))
    img_ax = fig.add_axes([0.12, 0.18, 0.76, 0.68])
    img_ax.imshow(image)
    img_ax.axis("off")
    ax.text(
        0.5,
        0.025,
        str(page_no),
        ha="center",
        va="bottom",
        fontproperties=font,
        fontsize=9,
        color="#6b7280",
    )
    pdf.savefig(fig)
    plt.close(fig)


def render_markdown_to_pdf(markdown_path, pdf_path):
    font = font_properties()
    source = Path(markdown_path)
    output = Path(pdf_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    page_lines = []
    page_no = 1
    in_code = False

    def flush(pdf):
        nonlocal page_lines, page_no
        if page_lines:
            add_text_page(pdf, page_lines, font, page_no)
            page_no += 1
            page_lines = []

    with PdfPages(output) as pdf:
        for raw_line in source.read_text(encoding="utf-8").splitlines():
            line = raw_line.rstrip()
            image_match = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", line.strip())
            if image_match:
                flush(pdf)
                caption = image_match.group(1) or "Figure"
                image_path = (source.parent / image_match.group(2)).resolve()
                add_image_page(pdf, image_path, caption, font, page_no)
                page_no += 1
                continue

            if line.startswith("```"):
                in_code = not in_code
                continue

            if in_code:
                wrapped = textwrap.wrap(line, width=82) or [""]
                for item in wrapped:
                    page_lines.append((item, 8.5, "normal"))
                continue

            if not line:
                page_lines.append(("", 10.5, "normal"))
                continue

            size = 10.5
            weight = "normal"
            prefix = ""
            text = line
            if line.startswith("# "):
                size, weight, text = 18, "bold", line[2:]
            elif line.startswith("## "):
                size, weight, text = 14, "bold", line[3:]
            elif line.startswith("### "):
                size, weight, text = 12, "bold", line[4:]
            elif line.startswith("- "):
                prefix, text = "• ", line[2:]
            elif re.match(r"\d+\. ", line):
                text = line

            text = prefix + strip_inline_markdown(text)
            width = 48 if size >= 14 else 62
            for item in textwrap.wrap(text, width=width) or [""]:
                page_lines.append((item, size, weight))

            if len(page_lines) >= 38:
                flush(pdf)
        flush(pdf)


def main():
    for source, output in DOCS:
        render_markdown_to_pdf(PROJECT_ROOT / source, PROJECT_ROOT / output)
        print(f"exported {output}")


if __name__ == "__main__":
    main()
