import os, json, re, datetime, urllib.request, urllib.error

API_KEY  = os.environ["ANTHROPIC_API_KEY"]
MODE     = os.environ.get("MODE", "shoutout").strip()
TARGET   = os.environ.get("TARGET", "").strip()
PLATFORM = os.environ.get("PLATFORM", "Both").strip()
MODEL    = "claude-sonnet-4-6"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "data", "stockists.json"), encoding="utf-8") as f:
    DATA = json.load(f)
with open(os.path.join(ROOT, "brand", "brand-voice.md"), encoding="utf-8") as f:
    VOICE = f.read()
STOCKISTS = DATA.get("stockists", [])

def find_stockist(t):
    tl = t.lower()
    for s in STOCKISTS:
        if s["name"].lower() == tl or s["town"].lower() == tl:
            return s
    for s in STOCKISTS:
        if tl and (tl in s["name"].lower() or tl in s["town"].lower()):
            return s
    return None

def de_hyphen(text):
    if not text: return text
    text = re.sub(r"\s[\u2013\u2014-]\s", ", ", text)
    text = re.sub(r"([A-Za-z])[\u2013\u2014-]([A-Za-z])", r"\1 \2", text)
    text = text.replace("\u2013", " ").replace("\u2014", " ")
    return re.sub(r"\s{2,}", " ", text).strip()

if MODE == "shoutout":
    s = find_stockist(TARGET)
    if s:
        active = s["status"] == "active"
        label  = "STOCKIST" if active else "COMING SOON"
        name, town, typ = s["name"], s["town"], s.get("type", "")
    else:
        active, label = True, "STOCKIST"
        name, town, typ = (TARGET or "a local stockist"), TARGET, ""
    task = (
        f"Write a STOCKIST SHOUTOUT post for {PLATFORM}.\n"
        f"Stockist: {name} in {town}. Type: {typ}.\n"
        f"This belongs to a recurring flag post series, one per stockist town, with a hero photo of the rubs and books on the real {name} shelf and a map stamp overlay carrying a pin, the town name and a {label} label in a fixed corner.\n"
        + ("This is an active stockist.\n" if active else "Not yet stocking, so frame it as coming soon.\n")
        + 'Return ONLY a JSON object with keys: caption, hashtags (array of 6 to 9), mapStamp (object with pin, townName, label, position), visualBrief, altText.'
    )
else:
    task = (
        f"Write a NEW CLIENT advertising post for {PLATFORM}.\n"
        f"Goal and region: {TARGET or 'reach home cooks across regional NSW'}.\n"
        "If the goal is recruiting a stockist, aim it at independent butchers, grocers and venues and make joining feel like momentum, not a cold pitch, noting the consignment model means low risk. If the goal is home cooks, make them want the rub on their next cook and point to the books and the stockist network without listing them.\n"
        'Return ONLY a JSON object with keys: caption, hashtags (array of 6 to 9), callToAction, visualBrief, altText.'
    )

prompt = f"{VOICE}\n\nTASK: {task}\nAustralian spelling. Never use a hyphen or dash anywhere."

body = json.dumps({
    "model": MODEL,
    "max_tokens": 1200,
    "messages": [{"role": "user", "content": prompt}],
}).encode("utf-8")

req = urllib.request.Request(
    "https://api.anthropic.com/v1/messages",
    data=body,
    headers={"x-api-key": API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
)
try:
    with urllib.request.urlopen(req) as resp:
        result = json.load(resp)
except urllib.error.HTTPError as e:
    print("API error:", e.read().decode("utf-8", "replace"))
    raise

text  = "".join(b.get("text", "") for b in result.get("content", []) if b.get("type") == "text")
clean = text.replace("```json", "").replace("```", "").strip()
try:
    pack = json.loads(clean)
except Exception:
    pack = {"caption": clean, "hashtags": [], "visualBrief": "", "altText": ""}

pack["caption"] = de_hyphen(pack.get("caption", ""))
if pack.get("callToAction"): pack["callToAction"] = de_hyphen(pack["callToAction"])
if pack.get("visualBrief"):  pack["visualBrief"]  = de_hyphen(pack["visualBrief"])

now  = datetime.datetime.now()
slug = (re.sub(r"[^a-z0-9]+", "-", (TARGET or MODE).lower()).strip("-")[:40]) or MODE
fname = f"{now:%Y-%m-%d-%H%M}-{MODE}-{slug}.md"
outdir = os.path.join(ROOT, "content", "drafts")
os.makedirs(outdir, exist_ok=True)

L = []
L += [f"# {MODE.title()} pack", "",
      f"- Target: {TARGET}", f"- Platform: {PLATFORM}",
      f"- Generated: {now:%Y-%m-%d %H:%M}", "- Status: draft, awaiting your approval", "",
      "## Caption", "", pack.get("caption", ""), "",
      "## Hashtags", ""]
tags = pack.get("hashtags", []) or []
L += [" ".join(h if h.startswith("#") else "#" + h for h in tags)]
if pack.get("callToAction"):
    L += ["", "## Call to action", "", pack["callToAction"]]
if pack.get("mapStamp"):
    m = pack["mapStamp"]
    L += ["", "## Map stamp", "", f"Pin {m.get('pin','')} | {m.get('label','')} | {m.get('position','')}"]
L += ["", "## Visual brief", "", pack.get("visualBrief", ""),
      "", "## Alt text", "", pack.get("altText", ""), ""]

with open(os.path.join(outdir, fname), "w", encoding="utf-8") as f:
    f.write("\n".join(L))

print("Wrote", os.path.join("content", "drafts", fname))
print("----")
print(pack.get("caption", ""))
