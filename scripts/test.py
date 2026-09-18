import os
import re
import sys

from pygments import highlight
from pygments.formatters.img import FontManager, ImageFormatter
from pygments.lexers import CSharpLexer
from pygments.token import Comment

FONT_NAME = "DejaVu Sans Mono"
FONT_SIZE = 12
STYLE = "monokai"
MAX_DIM = 1000  # hard pixel budget per generated PNG

WORD_RE = re.compile(r"\w")
OPERATOR_CHARS = set("+-*/%=&|^<>!~?:.")


def semantic_minify(code):
    """Strip real comments and collapse whitespace, but only where doing so
    can't change the token stream: a space is re-inserted anywhere its
    removal would fuse two tokens into a different one (identifier/keyword/
    number runs, or adjacent operator characters that would form a new
    compound operator). Preprocessor directives (#if, #region, ...) are
    terminated with a forced line break since their extent is line-based.
    """
    parts = []
    prev_last_char = ""
    prev_was_preproc = False

    for ttype, value in CSharpLexer().get_tokens(code):
        # Drop real comments, but keep preprocessor directives (Comment.Preproc)
        if ttype in Comment and ttype not in Comment.Preproc:
            continue
        if not value.strip():
            continue  # pure whitespace/newline token - re-derived below if needed

        if parts:
            if prev_was_preproc:
                # A preprocessor directive's extent ends at the line - never
                # let the next token silently become part of it.
                parts.append("\n")
            else:
                first_char = value[0]
                needs_space = (
                    WORD_RE.match(prev_last_char) and WORD_RE.match(first_char)
                ) or (prev_last_char in OPERATOR_CHARS and first_char in OPERATOR_CHARS)
                if needs_space:
                    parts.append(" ")

        parts.append(value)
        prev_last_char = value[-1]
        prev_was_preproc = ttype in Comment.Preproc

    return "".join(parts)


def paginate(minified_code, max_chars_per_line, max_lines_per_page):
    """Hard-pack characters into lines up to max_chars_per_line (breaking
    anywhere, since this is a rendered image, not compiled source), then
    group lines into pages of max_lines_per_page so every page fits the
    pixel budget. Forced newlines (from preprocessor directives) are
    respected as real line breaks rather than being packed through.
    """
    lines = []
    for segment in minified_code.split("\n"):
        if not segment:
            continue
        for i in range(0, len(segment), max_chars_per_line):
            lines.append(segment[i : i + max_chars_per_line])

    pages = [
        lines[i : i + max_lines_per_page]
        for i in range(0, len(lines), max_lines_per_page)
    ]
    return pages


def compress_and_render_cs(input_path, output_path):
    with open(input_path, "r", encoding="utf-8") as f:
        code = f.read()

    print("Minifying with semantic-aware tokenization...")
    minified = semantic_minify(code)

    # Exact pixel metrics pygments' ImageFormatter will use, so our packing
    # matches the renderer precisely instead of guessing.
    char_width, _ = FontManager(FONT_NAME, FONT_SIZE).get_char_size()
    line_height = FONT_SIZE  # line_pad=0

    max_chars_per_line = MAX_DIM // char_width
    max_lines_per_page = MAX_DIM // line_height

    pages = paginate(minified, max_chars_per_line, max_lines_per_page)

    root, ext = os.path.splitext(output_path)
    ext = ext or ".png"

    def make_formatter():
        # ImageFormatter accumulates every drawn glyph into self.drawables
        # and never clears it between .format() calls, so reusing one
        # instance across pages ghosts earlier pages' text into later ones.
        # A fresh instance per page avoids that entirely.
        return ImageFormatter(
            style=STYLE,
            font_name=FONT_NAME,
            font_size=FONT_SIZE,
            line_pad=0,
            line_numbers=False,
            image_pad=0,
            image_format="PNG",
        )

    written = []
    for i, page_lines in enumerate(pages, start=1):
        page_code = "\n".join(page_lines)
        page_path = f"{root}_p{i:02d}{ext}" if len(pages) > 1 else output_path
        image_bytes = highlight(page_code, CSharpLexer(), make_formatter())
        with open(page_path, "wb") as f:
            f.write(image_bytes)
        written.append(page_path)
        print(
            f"  page {i}/{len(pages)} -> {page_path} "
            f"({len(page_lines)} lines x up to {max_chars_per_line} chars)"
        )

    print(f"Done: {len(written)} PNG(s) generated from {len(minified)} minified chars.")
    return written


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python script.py <input.cs> <output.png>")
        sys.exit(1)

    compress_and_render_cs(sys.argv[1], sys.argv[2])
