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


def tokenize_atoms(code):
    """Lex the source into a flat list of (text, space_before, forced_break_before)
    atoms. Each atom is one indivisible lexer token (identifier, keyword,
    number, string, punctuation, ...) - real comments are dropped and pure
    whitespace is collapsed into the space_before / forced_break_before flags,
    so downstream wrapping can pack atoms onto lines but never cut through
    the middle of one (no more "Microsoft" splitting into "M" + "icrosoft").

    space_before mirrors the same rule as the character-wise minifier: a
    single space is required wherever dropping it would fuse two tokens into
    a different one (identifier/keyword/number runs, or adjacent operator
    characters that would form a new compound operator).

    forced_break_before is set after a preprocessor directive (#if, #region,
    ...), since its extent is the rest of the line - it must never be
    followed by more text on the same visual line.
    """
    atoms = []
    prev_last_char = ""
    prev_was_preproc = False

    for ttype, value in CSharpLexer().get_tokens(code):
        if ttype in Comment and ttype not in Comment.Preproc:
            continue
        if not value.strip():
            continue

        forced_break = False
        space_before = False
        if atoms:
            if prev_was_preproc:
                forced_break = True
            else:
                first_char = value[0]
                space_before = (
                    WORD_RE.match(prev_last_char) and WORD_RE.match(first_char)
                ) or (prev_last_char in OPERATOR_CHARS and first_char in OPERATOR_CHARS)

        atoms.append((value, space_before, forced_break))
        prev_last_char = value[-1]
        prev_was_preproc = ttype in Comment.Preproc

    return atoms


def wrap_atoms(atoms, max_chars_per_line):
    """Greedily pack atoms onto lines up to max_chars_per_line, breaking only
    between atoms - never inside one - so no identifier, keyword, number,
    string, or operator run is ever split across a line boundary. An atom
    longer than max_chars_per_line on its own is placed on its own line and
    allowed to overflow the width budget rather than being cut.
    """
    lines = []
    current = ""
    overflow_atoms = []

    for text, space_before, forced_break in atoms:
        if forced_break and current:
            lines.append(current)
            current = ""

        if not current:
            current = text
            if len(text) > max_chars_per_line:
                overflow_atoms.append(text)
            continue

        piece = (" " + text) if space_before else text
        if len(current) + len(piece) <= max_chars_per_line:
            current += piece
        else:
            lines.append(current)
            current = text
            if len(text) > max_chars_per_line:
                overflow_atoms.append(text)

    if current:
        lines.append(current)

    return lines, overflow_atoms


def paginate(lines, max_lines_per_page):
    return [
        lines[i : i + max_lines_per_page]
        for i in range(0, len(lines), max_lines_per_page)
    ]


def compress_and_render_cs(input_path, output_path, font_size=FONT_SIZE):
    with open(input_path, "r", encoding="utf-8") as f:
        code = f.read()

    print("Tokenizing with semantic-aware lexing (token-safe wrap)...")
    atoms = tokenize_atoms(code)

    # Exact pixel metrics pygments' ImageFormatter will use, so our packing
    # matches the renderer precisely instead of guessing.
    char_width, _ = FontManager(FONT_NAME, font_size).get_char_size()
    line_height = font_size  # line_pad=0

    max_chars_per_line = MAX_DIM // char_width
    max_lines_per_page = MAX_DIM // line_height

    lines, overflow_atoms = wrap_atoms(atoms, max_chars_per_line)
    if overflow_atoms:
        print(
            f"  note: {len(overflow_atoms)} token(s) exceed {max_chars_per_line} "
            f"chars and were kept whole on their own (over-width) line rather than split:"
        )
        for a in overflow_atoms[:5]:
            print(f"    - {a[:80]}{'...' if len(a) > 80 else ''}")

    pages = paginate(lines, max_lines_per_page)

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
            font_size=font_size,
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
            f"({len(page_lines)} lines, max {max(len(l) for l in page_lines)} chars wide)"
        )

    print(f"Done: {len(written)} PNG(s) generated from {len(atoms)} tokens.")
    return written


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python test2.py <input.cs> <output.png> [font_size]")
        sys.exit(1)

    fsize = int(sys.argv[3]) if len(sys.argv) > 3 else FONT_SIZE
    compress_and_render_cs(sys.argv[1], sys.argv[2], font_size=fsize)
