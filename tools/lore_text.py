"""Превращает текст страниц книги (pdftotext) в HTML для журналов компендиума.

Используется сборщиком: python3 tools/build.py --lore <папка со страницами NNN.txt>
Результат сохраняется в tools/data/lore.json, чтобы обычная сборка не зависела от книги.
"""

import html
import re

END_PUNCT = tuple(".!?:;…»)\"")


def clean_lines(text):
    lines = []
    for raw in text.replace("­", "").replace("‑", "-").split("\n"):
        line = raw.strip()
        if not line:
            continue
        if "____" in line or re.fullmatch(r"\d{1,3}", line):
            continue
        lines.append(line)
    # Колонтитул вверху страницы набран строчными буквами.
    if lines and lines[0] == lines[0].lower() and not lines[0][:1].isdigit():
        lines = lines[1:]
    return lines


def to_blocks(lines):
    """Склеивает строки в абзацы; короткие строки без знака препинания перед строкой с заглавной — заголовки."""
    blocks = []
    para = []

    def flush():
        if para:
            blocks.append(("p", " ".join(para)))
            para.clear()

    for i, line in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        is_heading = (len(line) < 45 and not line.endswith(END_PUNCT) and not line.endswith(",")
                      and line[:1].isupper() and nxt[:1].isupper() and not para
                      and ". " not in line and not line.endswith(("—", "-")))
        if is_heading:
            flush()
            blocks.append(("h", line))
            continue
        if para and para[-1].endswith("-") and not para[-1].endswith(" -"):
            para[-1] = para[-1][:-1] + line if line[:1].islower() else para[-1] + line
        else:
            para.append(line)
        if line.endswith((":", ";")):
            if nxt[:1].isupper() or nxt[:1] in "•–—-":
                flush()
        elif line.endswith(END_PUNCT) and (len(line) < 55 or nxt[:1].isupper() or nxt[:1] in "•–—"):
            flush()
        elif len(line) < 40 and len(para) <= 3 and nxt[:1].isupper() and not line.endswith(","):
            # Пункты списков в книге часто без точки в конце.
            flush()
    flush()
    return blocks


def pages_to_html(texts, title=None):
    pages = [clean_lines(text) for text in texts]
    # Колонтитулы: строка, открывающая несколько страниц подряд, или заголовок раздела книги.
    firsts = [pg[0].casefold() for pg in pages if pg]
    running = {f for f in firsts if firsts.count(f) > 1} | {"введение"}
    lines = []
    for n, pg in enumerate(pages):
        while pg and (pg[0].casefold() in running) and (n > 0 or pg[0].casefold() == "введение"):
            pg = pg[1:]
        lines.extend(pg)
    out = []
    for kind, text in to_blocks(lines):
        if kind == "h" and text.casefold() == "введение":
            continue
        text = html.escape(text)
        out.append(f"<h3>{text}</h3>" if kind == "h" else f"<p>{text}</p>")
    return "".join(out)


# Ручные правки там, где вёрстка книги (схемы, врезки) не переводится в текст автоматически.
FIXES = {
    "А что сейчас?": [
        (r"<p>Система Родимая — планета Аврора.*?<p>&gt;250 лет до П\.Г\.</p><p>145 П\.Г\.</p>",
         "<ul><li>Система Родимая — планета Аврора — столица Обитель</li>"
         "<li>Стольная система Славная — планета Дива — столица Красноград</li>"
         "<li>Система Хранимая — планета Гладь — столица Зеленеласк</li>"
         "<li>Система Тихая — планета Темнодуй — столица Туманск</li>"
         "<li>Система Буйная — планета Сушь — столица Урожайск</li></ul>"),
    ],
}


def build_lore(chapters, pages_dir):
    """Главы лора → [{journal, pages: [{name, html}]}] с ручными правками."""
    import re
    from pathlib import Path
    out = []
    for journal, pages in chapters:
        entry = {"journal": journal, "pages": []}
        for name, nums in pages:
            texts = [(Path(pages_dir) / f"{n:03d}.txt").read_text(encoding="utf-8") for n in nums]
            content = pages_to_html(texts)
            # Название страницы журнала и так выводится заголовком.
            for tag in ("h3", "p"):
                if content.startswith(f"<{tag}>{html.escape(name)}</{tag}>"):
                    content = content[len(f"<{tag}>{html.escape(name)}</{tag}>"):]
            for pattern, repl in FIXES.get(name, []):
                content = re.sub(pattern, lambda m: repl, content, flags=re.S)
            entry["pages"].append({"name": name, "html": content})
        out.append(entry)
    return out
