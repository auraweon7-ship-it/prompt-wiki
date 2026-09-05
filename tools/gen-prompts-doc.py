# -*- coding: utf-8 -*-
"""index.html의 PROMPTS를 읽어 전체 프롬프트 문서(prompts.html)를 만든다.

  python tools/gen-prompts-doc.py

index.html을 고친 뒤 다시 돌리면 prompts.html이 최신 내용으로 갱신된다.
"""
import io, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "index.html")
OUT = os.path.join(ROOT, "prompts.html")

# --- 템플릿 리터럴 안의 이스케이프를 원문으로 되돌린다 ---
_ESC = {"n": "\n", "t": "\t", "r": "\r", "`": "`", "$": "$",
        "\\": "\\", "'": "'", '"': '"'}


def unbt(s):
    out, i = [], 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            out.append(_ESC.get(s[i + 1], "\\" + s[i + 1]))
            i += 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def unq(s):
    return s.replace("\\'", "'").replace("\\\\", "\\")


def parse_prompts(block):
    """{ cat, title, desc, prompt:`...`, ex:{...} } 항목을 순서대로 뽑는다."""
    head = re.compile(r"\{\s*cat:'((?:[^'\\]|\\.)*)',\s*title:'((?:[^'\\]|\\.)*)',\s*"
                      r"desc:'((?:[^'\\]|\\.)*)',\s*\n?\s*prompt:`", re.S)
    entries, pos = [], 0
    while True:
        m = head.search(block, pos)
        if not m:
            break
        i = m.end()
        buf = []
        while block[i] != "`":
            if block[i] == "\\":
                buf.append(block[i]); buf.append(block[i + 1]); i += 2
            else:
                buf.append(block[i]); i += 1
        prompt = unbt("".join(buf))
        i += 1
        ex = {}
        if block[i:i + 12].lstrip().startswith(","):        # 선택 항목 , ex:{...}
            j = block.index("ex:", i) + 3
            depth, k = 0, j
            while True:
                if block[k] == "{":
                    depth += 1
                elif block[k] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                elif block[k] == '"':                        # 문자열은 건너뛴다
                    k += 1
                    while block[k] != '"':
                        k += 2 if block[k] == "\\" else 1
                k += 1
            ex = json.loads(block[j:k + 1])
            i = k + 1
        entries.append({"cat": unq(m.group(1)), "title": unq(m.group(2)),
                        "desc": unq(m.group(3)), "prompt": prompt, "ex": ex})
        pos = i
    return entries


raw = io.open(SRC, encoding="utf-8", newline="").read()

cat_re = re.compile(r"\{\s*id:'([^']+)',\s*name:'([^']+)',\s*icon:'([^']*)',"
                    r"\s*color:'([^']+)',\s*group:'([^']+)'\s*\}")
CATS = [dict(zip(("id", "name", "icon", "color", "group"), m.groups()))
        for m in cat_re.finditer(raw)]
assert CATS, "CATEGORIES를 찾지 못했다"

gstart = raw.index("const GROUPS")
GROUPS = [dict(zip(("id", "name"), m.groups()))
          for m in re.finditer(r"\{\s*id:'([^']+)',\s*name:'([^']+)'",
                               raw[gstart:raw.index("]", gstart)])]

VERSION = re.search(r"const VERSION = '([^']+)'", raw).group(1)
UPDATED = re.search(r"const LAST_UPDATED = '([^']+)'", raw).group(1)

pstart = raw.index("const PROMPTS = [")
PROMPTS = parse_prompts(raw[pstart:raw.index("\n];", pstart)])
assert PROMPTS, "PROMPTS를 찾지 못했다"

by_cat = {}
for p in PROMPTS:
    by_cat.setdefault(p["cat"], []).append(p)

# 카테고리 순서는 index.html의 GROUPS·CATEGORIES 순서를 그대로 따른다
ordered = [(g, c) for g in GROUPS for c in CATS
           if c["group"] == g["id"] and c["id"] in by_cat]
seen = set(c["id"] for _, c in ordered)
ordered += [({"id": "etc", "name": "기타"}, c) for c in CATS
            if c["id"] in by_cat and c["id"] not in seen]

PH = re.compile(r"\[([^\[\]]+)\]")


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def body(text, ex):
    """본문을 이스케이프하고 자리표시자를 감싼다. 예제 값이 있으면 tooltip에 넣는다."""
    out, last = [], 0
    for m in PH.finditer(text):
        out.append(esc(text[last:m.start()]))
        key = m.group(1)
        val = (ex or {}).get(key)
        if val:
            out.append('<span class="ph filled" title="%s">[%s]</span>'
                       % (esc(val).replace('"', "&quot;"), esc(key)))
        else:
            out.append('<span class="ph">[%s]</span>' % esc(key))
        last = m.end()
    out.append(esc(text[last:]))
    return "".join(out)


parts = []
A = parts.append
total = format(len(PROMPTS), ",")

A("<h1>AI 프롬프트 위키 — 전체 프롬프트</h1>")
A('<p class="lede">%s개 프롬프트 전문을 카테고리 순서대로 모은 문서입니다. '
  '주황색 <span class="ph">[대괄호]</span>는 본인 상황으로 바꿔 쓰는 자리고, '
  '초록색은 예제 값이 있는 항목입니다 — 마우스를 올리면 값이 보입니다.</p>' % total)
A('<p class="meta">v%s · %s 기준 · '
  '<a href="https://prompt-wiki.up.railway.app/">prompt-wiki.up.railway.app</a></p>'
  % (esc(VERSION), esc(UPDATED)))

A('<nav class="toc"><h2>목차</h2>')
cur = None
for g, c in ordered:
    if g["id"] != cur:
        if cur is not None:
            A("</ul>")
        cur = g["id"]
        A('<p class="toc-group">%s</p><ul class="toc-list">' % esc(g["name"]))
    A('<li><a href="#cat-%s">%s %s</a><span class="n">%d</span></li>'
      % (c["id"], c["icon"], esc(c["name"]), len(by_cat[c["id"]])))
A("</ul></nav>")

cur, n = None, 0
for g, c in ordered:
    if g["id"] != cur:
        cur = g["id"]
        A('<h2 class="group-head">%s</h2>' % esc(g["name"]))
    A('<section class="cat" id="cat-%s">' % c["id"])
    A('<h3 class="cat-head"><span class="ico">%s</span>%s'
      '<span class="cnt">%d개</span></h3>'
      % (c["icon"], esc(c["name"]), len(by_cat[c["id"]])))
    for p in by_cat[c["id"]]:
        n += 1
        A('<article class="p">')
        A('<h4><span class="no">%03d</span>%s</h4>' % (n, esc(p["title"])))
        A('<p class="desc">%s</p>' % esc(p["desc"]))
        A('<pre class="prompt">%s</pre>' % body(p["prompt"], p.get("ex")))
        if p.get("ex"):
            rows = "".join('<tr><th scope="row">%s</th><td>%s</td></tr>'
                           % (esc(k), esc(v)) for k, v in p["ex"].items())
            A('<details class="ex"><summary>예제 값 %d개</summary>'
              "<table>%s</table></details>" % (len(p["ex"]), rows))
        A("</article>")
    A("</section>")

CSS = """
:root{
  --bg:#0d0e12; --panel:#15161c; --panel-2:#1b1d25; --border:#282a35;
  --text:#e9eaf0; --text-2:#a8abbb; --text-3:#71748a;
  --accent:#7c5cff; --orange:#f0883e; --green:#3fb950;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
  font-family:Pretendard,'Malgun Gothic',system-ui,sans-serif;
  font-size:15px;line-height:1.7;-webkit-font-smoothing:antialiased}
.wrap{max-width:920px;margin:0 auto;padding:48px 24px 80px}
a{color:var(--accent)}
h1{font-size:30px;font-weight:800;letter-spacing:-.5px;margin:0 0 12px}
.lede{color:var(--text-2);font-size:14px;margin:0 0 8px}
.meta{color:var(--text-3);font-size:12.5px;margin:0 0 36px}
.toc{background:var(--panel);border:1px solid var(--border);border-radius:14px;
  padding:20px 22px;margin-bottom:44px}
.toc h2{font-size:13px;font-weight:800;color:var(--text-3);letter-spacing:.05em;margin:0 0 14px}
.toc-group{font-size:12px;font-weight:800;color:var(--accent);margin:16px 0 8px}
.toc-group:first-of-type{margin-top:0}
.toc-list{list-style:none;margin:0;padding:0;
  display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:2px 16px}
.toc-list li{display:flex;gap:8px;align-items:baseline;font-size:13px}
.toc-list a{text-decoration:none;color:var(--text-2)}
.toc-list a:hover{color:var(--text)}
.toc-list .n{margin-left:auto;color:var(--text-3);font-size:11.5px}
.group-head{font-size:12px;font-weight:800;color:var(--text-3);letter-spacing:.06em;
  margin:56px 0 0;padding-bottom:10px;border-bottom:1px solid var(--border)}
.cat{margin-top:32px}
.cat-head{display:flex;align-items:center;gap:10px;font-size:20px;font-weight:800;
  letter-spacing:-.3px;margin:0 0 18px;scroll-margin-top:20px}
.cat-head .ico{font-size:18px}
.cat-head .cnt{margin-left:auto;font-size:12px;font-weight:600;color:var(--text-3)}
.p{background:var(--panel);border:1px solid var(--border);border-radius:14px;
  padding:20px 22px;margin-bottom:16px;break-inside:avoid;
  /* 1,000개가 넘는 문서라 화면 밖 카드는 렌더를 건너뛴다 */
  content-visibility:auto;contain-intrinsic-size:auto 1100px}
.p h4{display:flex;align-items:baseline;gap:10px;font-size:16px;font-weight:800;
  letter-spacing:-.2px;margin:0 0 6px}
.p h4 .no{font-family:ui-monospace,'JetBrains Mono',monospace;font-size:11.5px;
  font-weight:700;color:var(--text-3);flex:none}
.desc{color:var(--text-2);font-size:13.5px;margin:0 0 14px}
.prompt{background:var(--bg);border:1px solid var(--border);border-radius:10px;
  padding:16px 18px;margin:0;white-space:pre-wrap;word-break:break-word;
  font-family:ui-monospace,'JetBrains Mono',monospace;font-size:12.5px;line-height:1.75;
  color:var(--text-2);overflow-x:auto}
.ph{color:var(--orange);font-weight:600}
.ph.filled{color:var(--green);border-bottom:1px dotted currentColor;cursor:help}
.ex{margin-top:12px}
.ex summary{cursor:pointer;font-size:12.5px;color:var(--text-3);
  padding:7px 12px;background:var(--panel-2);border:1px solid var(--border);border-radius:8px;
  display:inline-block;list-style:none}
.ex summary::-webkit-details-marker{display:none}
.ex summary::before{content:'\\25B8 ';color:var(--accent)}
.ex[open] summary::before{content:'\\25BE '}
.ex table{width:100%;border-collapse:collapse;margin-top:10px;font-size:12.5px}
.ex th,.ex td{border:1px solid var(--border);padding:7px 11px;text-align:left;
  vertical-align:top;line-height:1.55}
.ex th{width:34%;color:var(--orange);font-weight:600;background:var(--panel-2)}
.ex td{color:var(--text-2)}
@media(max-width:640px){
  .wrap{padding:28px 14px 60px}
  h1{font-size:23px}
  .p{padding:15px 14px;border-radius:11px}
  .prompt{font-size:12px;padding:13px 12px}
  .ex th{width:40%}
}
@media print{
  .p{content-visibility:visible;contain-intrinsic-size:none}
  :root{--bg:#fff;--panel:#fff;--panel-2:#f6f6f8;--border:#d5d7de;
    --text:#111;--text-2:#333;--text-3:#666;--orange:#b45309;--green:#166534}
  body{font-size:10.5pt}
  .wrap{max-width:none;padding:0}
  .toc{break-after:page}
  .cat-head{break-after:avoid}
  .ex[open] summary{display:none}
  .ex table{margin-top:0}
  .prompt{overflow:visible}
  a{color:inherit;text-decoration:none}
}
"""

html = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 프롬프트 위키 — 전체 프롬프트 %s개</title>
<meta name="description" content="한국어 AI 프롬프트 %s개 전문을 카테고리별로 모은 문서">
<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
<link href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard-dynamic-subset.min.css" rel="stylesheet">
<style>%s</style>
</head>
<body>
<div class="wrap">
%s
</div>
</body>
</html>
""" % (total, total, CSS, "\n".join(parts))

io.open(OUT, "w", encoding="utf-8", newline="\r\n").write(html)
print("prompts.html 생성 — 프롬프트 %d개, 카테고리 %d개, %.2f MB"
      % (len(PROMPTS), len(by_cat), len(html.encode("utf-8")) / 1048576.0))
