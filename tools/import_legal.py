"""Import the legal pages from saved pages of the old lunedata.io site, text unchanged.
Usage: python3 tools/import_legal.py <dir with saved html>   -> legal_src/<slug>.json
The tool compares the words of each result with the words of the old page and reports a difference."""
import sys, re, json, html, pathlib
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = pathlib.Path(sys.argv[1])
KEEP = {"p", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "a", "strong", "b", "em", "i", "u", "blockquote", "br",
        "table", "thead", "tbody", "tr", "td", "th", "sup", "sub"}
SKIP = {"script", "style"}


class Legal(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth, self.on, self.done, self.skip, self.out, self.words = 0, False, False, 0, [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if not self.on:
            if tag == "div" and "w-richtext" in (a.get("class") or "") and not self.done:
                self.on, self.depth = True, 1
            return
        if tag in SKIP:
            self.skip += 1; return
        if tag == "div":
            self.depth += 1; return
        if tag == "h1":
            tag = "h2"
        if tag not in KEEP:
            return
        if tag == "a":
            href = (a.get("href") or "").strip()
            if href.startswith("/"):
                href = href.lstrip("/") + ".html" if href.strip("/") in ("terms", "lune-privacy", "cookie", "msa", "msa-secan", "contact") else "https://www.lunedata.io" + href
            self.out.append(f'<a href="{html.escape(href, quote=True)}">')
        elif tag == "ol":
            extra = "".join(f' {k}="{html.escape(a[k], quote=True)}"' for k in ("start", "type") if a.get(k))
            self.out.append(f"<ol{extra}>")
        elif tag in ("td", "th"):
            extra = "".join(f' {k}="{html.escape(a[k], quote=True)}"' for k in ("colspan", "rowspan") if a.get(k))
            self.out.append(f"<{tag}{extra}>")
        else:
            self.out.append(f"<{tag}>")

    def handle_endtag(self, tag):
        if not self.on:
            return
        if tag in SKIP:
            self.skip = max(0, self.skip - 1); return
        if tag == "div":
            self.depth -= 1
            if self.depth == 0:
                self.on, self.done = False, True
            return
        if tag == "h1":
            tag = "h2"
        if tag in KEEP and tag != "br":
            self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if self.on and not self.skip:
            self.out.append(html.escape(data, quote=False))
            self.words += data.replace("‍", "").split()


def words_of(fragment):
    return html.unescape(re.sub(r"<[^>]+>", " ", fragment)).replace("‍", "").split()


for slug in ("terms", "lune-privacy", "cookie", "msa", "msa-secan"):
    t = (SRC / f"legal__{slug}.html").read_text(encoding="utf-8", errors="replace")
    p = Legal(); p.feed(t)
    body = "".join(p.out).replace("‍", "")
    for _ in range(3):
        body = re.sub(r"<(p|h\d|li|strong|em|b|i|u)>(?:\s|<br>|&nbsp;)*</\1>", "", body)
    h1 = html.unescape(re.sub(r"<[^>]+>", "", re.search(r"<h1[^>]*>(.*?)</h1>", t, re.S).group(1))).strip()
    title = html.unescape(re.search(r"<title>(.*?)</title>", t, re.S).group(1)).strip()
    d = re.search(r'<meta content="([^"]*)" name="description"', t)
    same = words_of(body) == p.words
    # lines between the page heading and the legal text, for example the revision date
    k = t.index("</h1>"); r = t.index("w-richtext", k)
    intro = [x for x in (" ".join(html.unescape(re.sub(r"<[^>]+>", "", seg)).split()) for seg in re.split(r"</(?:div|p)>", t[k:t.rindex("<", 0, r)])) if x]
    rec = {"slug": slug, "h1": h1, "intro": intro, "title": title, "desc": html.unescape(d.group(1)) if d else "", "body": body,
           "source": f"https://www.lunedata.io/{slug}"}
    (ROOT / "legal_src" / f"{slug}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{slug:14s} {len(p.words):6d} words  same as old page: {same}  tables: {body.count('<table>')}  intro: {intro}")
