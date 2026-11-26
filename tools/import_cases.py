"""Import the case study text from saved pages of the old lunedata.io site.
Usage: python3 tools/import_cases.py <dir with saved html>   -> case_src/<slug>.json"""
import sys, re, json, html, pathlib
sys.argv_backup = sys.argv[:]
ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "tools"))
from html.parser import HTMLParser
import importlib.util
spec = importlib.util.spec_from_file_location("ib", ROOT / "tools" / "import_blog.py")

KEEP = {"p", "h2", "h3", "h4", "ul", "ol", "li", "a", "strong", "b", "em", "i", "blockquote", "br"}


class Region(HTMLParser):
    """Keeps headings and rich text between the case study section and the contact block."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.on, self.rich, self.head, self.out, self.h1s = False, 0, None, [], []
        self.stack = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs); cls = a.get("class") or ""
        if tag == "section" and "case-study-templete" in cls:
            self.on = True
        if not self.on:
            return
        if tag == "h1":
            if "big-h2-80" in cls:
                self.on = False; return
            self.head = "h1"; self.buf = []; return
        if tag in ("div", "section"):
            if self.rich:
                self.rich += 1
            elif "w-richtext" in cls:
                self.rich = 1
            return
        if tag in ("h2", "h3") and not self.rich:
            self.head = tag; self.buf = []; return
        if self.rich and tag in KEEP:
            if tag == "a":
                href = (a.get("href") or "").strip()
                if href.startswith("/"):
                    href = "https://www.lunedata.io" + href
                self.out.append(f'<a href="{html.escape(href, quote=True)}">')
            elif tag == "br":
                self.out.append("<br>")
            else:
                self.out.append(f"<{tag}>")

    def handle_endtag(self, tag):
        if not self.on:
            return
        if self.head and tag == self.head:
            text = " ".join("".join(self.buf).split())
            if self.head == "h1":
                self.h1s.append(text)
            elif text:
                self.out.append(f"<h2>{html.escape(text, quote=False)}</h2>")
            self.head = None; return
        if tag in ("div", "section") and self.rich:
            self.rich -= 1; return
        if self.rich and tag in KEEP and tag != "br":
            self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.on:
            return
        if self.head:
            self.buf.append(data)
        elif self.rich:
            self.out.append(html.escape(data, quote=False))


for f in sorted(SRC.glob("case-studies__*.html")):
    slug = f.stem.split("__", 1)[1]
    t = f.read_text(encoding="utf-8", errors="replace")
    p = Region(); p.feed(t)
    body = "".join(p.out).replace("‍", "")
    for _ in range(3):
        body = re.sub(r"<(p|h\d|li|strong|em|b|i|ul|ol|blockquote)>(?:\s|<br>|&nbsp;)*</\1>", "", body)
    # the old page repeats its intro paragraph: keep the first copy of each paragraph
    seen, parts = set(), []
    for part in re.split(r"(?=<(?:p|h2|h3|h4|ul|ol|blockquote)>)", body):
        key = re.sub(r"\W+", "", re.sub(r"<[^>]+>", "", part)).lower()[:160]
        if key and key in seen and part.startswith("<p>"):
            continue
        seen.add(key); parts.append(part)
    body = "".join(parts)
    d = re.search(r'<meta content="([^"]*)" name="description"', t)
    rec = {"slug": slug, "h1": p.h1s, "desc": html.unescape(d.group(1)) if d else "", "body": body,
           "source": f"https://www.lunedata.io/case-studies/{slug}"}
    (ROOT / "case_src" / f"{slug}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(slug, len(re.sub(r"<[^>]+>", " ", body).split()), "words", p.h1s, body.count("<h2>"), "h2")
