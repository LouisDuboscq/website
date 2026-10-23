#!/usr/bin/env python3
"""Turns every apps/<app>/privacy-policy.txt into a readable apps/<app>/privacy-policy.html (same text).

The .txt stays the source (and the URL given in Play Console / App Store Connect); the .html is what the apps open
in their in-app browser: headings, lists, links, contents, dark mode, phone width.
Two source formats: plain text (« 1. SUMMARY » headings, « a) » sub-headings, « - » lists) and the older Markdown
(« ## », « **bold** », « --- »).

Run after editing a policy:  python3 scripts/policy_html.py
"""
import html
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ACRONYMS = {"gdpr", "ccpa", "ai", "id", "eu", "uk", "us", "usa", "faq", "ios", "bmi"}

STYLE = """
    :root { color-scheme: light dark; --text: #1c1c1e; --muted: #6e6e73; --bg: #fff; --card: #f2f2f7; --accent: #0a7f6f; --line: #d1d1d6; }
    @media (prefers-color-scheme: dark) { :root { --text: #f2f2f7; --muted: #98989d; --bg: #000; --card: #1c1c1e; --accent: #4fd1bd; --line: #38383a; } }
    * { box-sizing: border-box; }
    body { margin: 0; background: var(--bg); color: var(--text); font: 17px/1.55 -apple-system, system-ui, "Segoe UI", Roboto, sans-serif; -webkit-text-size-adjust: 100%; overflow-wrap: break-word; }
    main { max-width: 680px; margin: 0 auto; padding: 28px 16px 56px; }
    h1 { font-size: 1.6em; line-height: 1.25; margin: 0 0 4px; }
    .updated { color: var(--muted); margin: 0 0 20px; font-size: .95em; }
    nav { background: var(--card); border-radius: 14px; padding: 14px 18px; margin: 20px 0 8px; }
    nav strong { display: block; margin-bottom: 6px; }
    nav ol { margin: 0; padding-left: 1.3em; }
    nav li { margin: 3px 0; }
    h2 { font-size: 1.2em; margin: 2em 0 .5em; padding-top: .9em; border-top: 1px solid var(--line); scroll-margin-top: 12px; }
    h3 { font-size: 1.02em; margin: 1.4em 0 .3em; }
    p, ul { margin: .5em 0; }
    ul { padding-left: 1.25em; }
    li { margin: .3em 0; }
    a { color: var(--accent); overflow-wrap: anywhere; }
    .summary { background: var(--card); border-radius: 14px; padding: 4px 18px; }
"""

LINK = re.compile(r"(https?://[^\s<>()]+[^\s<>().,;:]|[\w.+-]+@[\w-]+(?:\.[\w-]+)+)")
HEADING = re.compile(r"^(\d+)\.\s+(.+)$")
SUB = re.compile(r"^[a-z]\)\s+")


def links(text: str) -> str:
    out, last = [], 0
    for m in LINK.finditer(text):
        out.append(html.escape(text[last:m.start()]))
        target = m.group(0)
        href = target if target.startswith("http") else f"mailto:{target}"
        out.append(f'<a href="{html.escape(href)}">{html.escape(target)}</a>')
        last = m.end()
    out.append(html.escape(text[last:]))
    return "".join(out)


def inline(text: str) -> str:
    """Escapes [text], links its URLs / e-mails and turns Markdown **bold** into <strong>."""
    parts = re.split(r"\*\*(.+?)\*\*", text)
    return "".join(f"<strong>{links(p)}</strong>" if i % 2 else links(p) for i, p in enumerate(parts))


def sentence_case(text: str) -> str:
    words = [w.upper() if w.strip("(),").lower() in ACRONYMS else w for w in text.lower().split(" ")]
    s = " ".join(words)
    return s[:1].upper() + s[1:]


def title_case(text: str) -> str:
    return " ".join(w.upper() if w.lower() in ACRONYMS else w.capitalize() for w in text.split(" "))


def page(title: str, updated: str, toc: list, body: list) -> str:
    nav = f'<nav><strong>Contents</strong><ol>{"".join(toc)}</ol></nav>' if len(toc) > 2 else ""
    updated_html = f'<p class="updated">{html.escape(updated)}</p>' if updated else ""
    content = "\n  ".join(body)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>{html.escape(title)}</title>
  <!-- Generated from privacy-policy.txt by scripts/policy_html.py: edit the .txt, then run the script. -->
  <style>{STYLE}  </style>
</head>
<body>
<main>
  <h1>{html.escape(title)}</h1>
  {updated_html}
  {nav}
  {content}
</main>
</body>
</html>
"""


class Blocks:
    """Paragraph and list accumulator shared by both formats."""

    def __init__(self, body: list):
        self.body, self.para, self.items = body, [], []

    def flush(self, line_breaks: bool):
        if self.para:
            joiner = "<br>" if line_breaks else " "
            self.body.append("<p>" + joiner.join(inline(l) for l in self.para) + "</p>")
            self.para = []
        if self.items:
            self.body.append("<ul>" + "".join(f"<li>{inline(i)}</li>" for i in self.items) + "</ul>")
            self.items = []


def convert_text(txt: str) -> str:
    """Plain-text policies: « TITLE — APP », « Last updated », « 1. SECTION », « a) Sub-section », « - » lists."""
    blocks = [b.strip("\n") for b in re.split(r"\n\s*\n", txt.strip()) if b.strip()]
    parts = [p.strip() for p in blocks.pop(0).strip().split("—")]
    title = " — ".join([sentence_case(parts[0])] + [title_case(p) for p in parts[1:]])
    updated = blocks.pop(0).strip() if blocks and blocks[0].lower().startswith("last updated") else ""

    body, toc, in_summary = [], [], False
    acc = Blocks(body)
    for block in blocks:
        lines = block.split("\n")
        first = lines[0].strip()
        m = HEADING.match(first)
        if m and first == first.upper():
            if in_summary:
                body.append("</div>")
                in_summary = False
            name = sentence_case(m.group(2))
            toc.append(f'<li><a href="#s{m.group(1)}">{html.escape(name)}</a></li>')
            body.append(f'<h2 id="s{m.group(1)}">{html.escape(f"{m.group(1)}. {name}")}</h2>')
            if m.group(1) == "1" and "summary" in name.lower():
                body.append('<div class="summary">')
                in_summary = True
            lines = lines[1:]
        if lines and SUB.match(lines[0].strip()):
            body.append(f"<h3>{inline(lines[0].strip())}</h3>")
            lines = lines[1:]
        for raw in lines:
            line = raw.strip()
            if line.startswith("- "):
                if acc.para:
                    acc.flush(line_breaks=True)
                acc.items.append(line[2:])
            elif acc.items and raw.startswith("  "):
                acc.items[-1] += " " + line
            else:
                if acc.items:
                    acc.flush(line_breaks=True)
                acc.para.append(line)
        # Lines of one block stay on their own lines (addresses, contact)
        acc.flush(line_breaks=True)
    if in_summary:
        body.append("</div>")
    return page(title, updated, toc, body)


def convert_markdown(txt: str, app_name: str) -> str:
    """Older policies, written in Markdown (« # », « ## », « ### », « **bold** », « --- », « - » lists)."""
    title, updated, body, toc = f"Privacy policy — {app_name}", "", [], []
    acc = Blocks(body)
    for raw in txt.splitlines():
        line = raw.strip()
        if not line or line == "---":
            acc.flush(line_breaks=False)
        elif line.startswith("# "):
            acc.flush(line_breaks=False)
            title = line[2:].strip().replace("**", "")
        elif line.startswith("## "):
            acc.flush(line_breaks=False)
            n = len(toc) + 1
            text = line[3:].strip()
            toc.append(f'<li><a href="#s{n}">{inline(text)}</a></li>')
            body.append(f'<h2 id="s{n}">{inline(text)}</h2>')
        elif line.startswith("### "):
            acc.flush(line_breaks=False)
            body.append(f"<h3>{inline(line[4:].strip())}</h3>")
        elif not updated and line.replace("*", "").lower().startswith("last updated"):
            acc.flush(line_breaks=False)
            updated = line.replace("**", "")
        elif line.startswith(("- ", "* ")):
            if acc.para:
                acc.flush(line_breaks=False)
            acc.items.append(line[2:])
        else:
            if acc.items:
                acc.flush(line_breaks=False)
            acc.para.append(line)
    acc.flush(line_breaks=False)
    return page(title, updated, toc, body)


def main() -> int:
    for txt in sorted(ROOT.glob("apps/*/privacy-policy.txt")):
        source = txt.read_text(encoding="utf-8")
        if any(l.startswith("## ") for l in source.splitlines()):
            result = convert_markdown(source, title_case(txt.parent.name.replace("-", " ")))
        else:
            result = convert_text(source)
        out = txt.with_suffix(".html")
        out.write_text(result, encoding="utf-8")
        print(out.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
