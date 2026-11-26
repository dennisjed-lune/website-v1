"""Import blog posts from saved pages of the old lunedata.io site.
Usage: python3 tools/import_blog.py <dir with saved html>
Writes blog_src/<slug>.json and downloads images to img/blog/."""
import sys, re, json, html, hashlib, subprocess, pathlib, datetime, urllib.parse
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = pathlib.Path(sys.argv[1])
KEEP = {"p", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "a", "strong", "b", "em", "i", "blockquote", "figure", "figcaption", "img", "br", "table", "thead", "tbody", "tr", "td", "th", "sup", "sub"}
VOID = {"img", "br"}


def fetch_img(url, slug):
    url = html.unescape(url)
    ext = pathlib.PurePosixPath(urllib.parse.urlparse(url).path).suffix.lower() or ".png"
    if ext not in (".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif", ".avif"):
        ext = ".png"
    name = f"{slug[:40]}-{hashlib.md5(url.encode()).hexdigest()[:6]}{ext}"
    out = ROOT / "img" / "blog" / name
    if not out.exists() or out.stat().st_size == 0:
        subprocess.run(["curl", "-sL", "-A", "Mozilla/5.0", url, "-o", str(out)], check=False)
    return f"img/blog/{name}" if out.exists() and out.stat().st_size > 0 else ""


class Rich(HTMLParser):
    def __init__(self, slug):
        super().__init__(convert_charrefs=True)
        self.slug, self.depth, self.on, self.out, self.done = slug, 0, False, [], False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if not self.on:
            if tag == "div" and "blog-body-rich" in (a.get("class") or "") and not self.done:
                self.on, self.depth = True, 1
            return
        if tag == "div":
            self.depth += 1
        if tag == "h1":
            tag = "h2"
        if tag not in KEEP:
            return
        if tag == "a":
            href = (a.get("href") or "").strip()
            if href.startswith("/"):
                href = "https://www.lunedata.io" + href
            ext = ' target="_blank" rel="noopener"' if href.startswith("http") and "lunedata.io" not in href else ""
            self.out.append(f'<a href="{html.escape(href, quote=True)}"{ext}>')
        elif tag == "img":
            src = fetch_img(a.get("src") or "", self.slug) if a.get("src") else ""
            if src:
                self.out.append(f'<img src="{src}" alt="{html.escape(a.get("alt") or "", quote=True)}" loading="lazy">')
        elif tag == "br":
            self.out.append("<br>")
        else:
            self.out.append(f"<{tag}>")

    def handle_endtag(self, tag):
        if not self.on:
            return
        if tag == "div":
            self.depth -= 1
            if self.depth == 0:
                self.on, self.done = False, True
            return
        if tag == "h1":
            tag = "h2"
        if tag in KEEP and tag not in VOID:
            self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if self.on:
            self.out.append(html.escape(data, quote=False))


def meta(t, key):
    m = re.search(r'<meta content="([^"]*)" (?:name|property)="' + re.escape(key) + '"', t)
    return html.unescape(m.group(1)) if m else ""


n = 0
for f in sorted(SRC.glob("blog__*.html")):
    slug = f.stem.split("__", 1)[1]
    t = f.read_text(encoding="utf-8", errors="replace")
    title = html.unescape(re.search(r"<title>(.*?)</title>", t, re.S).group(1)).strip()
    h1 = re.search(r'<h1[^>]*class="h1-100"[^>]*>(.*?)</h1>', t, re.S)
    if h1:
        title = html.unescape(re.sub(r"<[^>]+>", "", h1.group(1))).strip() or title
    d = re.search(r"<div>Published on</div><div>([^<]+)</div>", t)
    date = ""
    if d:
        try:
            date = datetime.datetime.strptime(d.group(1).strip(), "%B %d, %Y").date().isoformat()
        except ValueError:
            date = ""
    p = Rich(slug); p.feed(t)
    body = "".join(p.out)
    body = re.sub(r"<(p|h\d|li|strong|em|b|i|figcaption)>\s*(?:‍|&nbsp;|\s)*</\1>", "", body)
    body = re.sub(r"<figure>\s*</figure>", "", body)
    img = meta(t, "og:image")
    rec = {"slug": slug, "title": title, "desc": meta(t, "description") or meta(t, "og:description"), "date": date,
           "image": fetch_img(img, slug) if img else "", "body": body, "source": f"https://www.lunedata.io/blog/{slug}"}
    (ROOT / "blog_src" / f"{slug}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    words = len(re.sub(r"<[^>]+>", " ", body).split())
    print(f"{date or '????-??-??'} {words:5d}w img={'y' if rec['image'] else 'n'} {slug[:70]}")
    n += 1
print(n, "posts")
