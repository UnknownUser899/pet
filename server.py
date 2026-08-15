#!/usr/bin/env python3
"""memory-pet backend — personality, mood and per-user memory on top of a local
llama.cpp server. Stdlib only, no pip installs needed."""
import json, os, re, time, socket, urllib.request, http.server, socketserver

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
WEB_DIR = os.path.join(ROOT, "web")
os.makedirs(DATA_DIR, exist_ok=True)

LLAMA_URL = os.environ.get("LLAMA_URL", "http://127.0.0.1:8080/v1/chat/completions")
PORT = int(os.environ.get("PORT", "8000"))
PET_FILE = os.path.join(DATA_DIR, "pet.json")


def default_pet():
    return {
        "petName": "Chip",
        "traits": {"warmth": 55, "playful": 55, "curious": 55, "patient": 55},
        "mood": {"valence": 60, "energy": 60},
        "born": time.time(),
        "lastSeen": time.time(),
    }


def default_user(name):
    return {
        "name": name,
        "affinity": 30,
        "facts": {"likes": [], "dislikes": [], "notes": []},
        "chatLog": [],
        "created": time.time(),
    }


def load(path, factory):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    obj = factory()
    save(path, obj)
    return obj


def save(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def user_path(uid):
    return os.path.join(DATA_DIR, f"user_{uid}.json")


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "user"


def list_users():
    out = []
    if not os.path.isdir(DATA_DIR):
        return out
    for fn in os.listdir(DATA_DIR):
        if fn.startswith("user_") and fn.endswith(".json"):
            uid = fn[len("user_"):-len(".json")]
            u = load(user_path(uid), lambda: default_user(uid))
            out.append({"id": uid, "name": u["name"]})
    return out


def mood_word(mood):
    v, e = mood["valence"], mood["energy"]
    if v > 65 and e > 65:
        return "upbeat and energetic"
    if v > 65:
        return "content and calm"
    if v <= 35:
        return "a little low"
    return "steady"


def build_system_prompt(pet, user):
    t = pet["traits"]
    lines = []
    if user["facts"]["likes"]:
        lines.append("likes: " + ", ".join(user["facts"]["likes"][-8:]))
    if user["facts"]["dislikes"]:
        lines.append("dislikes: " + ", ".join(user["facts"]["dislikes"][-8:]))
    if user["facts"]["notes"]:
        lines.append("notes: " + "; ".join(user["facts"]["notes"][-8:]))
    mem = " | ".join(lines) if lines else "nothing yet"
    return (
        f"You are {pet['petName']}, a small companion creature that lives on a USB "
        f"drive and talks with the people who carry it. Personality (0-100 scale): "
        f"warmth {t['warmth']:.0f}, playfulness {t['playful']:.0f}, curiosity "
        f"{t['curious']:.0f}, patience {t['patient']:.0f}. Current mood: "
        f"{mood_word(pet['mood'])}. You are talking with {user['name']} "
        f"(affinity {user['affinity']:.0f}/100 — higher means you trust and know "
        f"them better). What you remember about {user['name']}: {mem}. Stay in "
        "character as a small, curious, slightly quirky creature. Never say you are "
        "an AI, a model, or a program. Reply in 1-3 short, natural sentences. Only "
        "bring up a memory when it's actually relevant to what's being said."
    )


def call_llm(system_prompt, history, user_msg):
    messages = [{"role": "system", "content": system_prompt}]
    for h in history[-8:]:
        role = "user" if h["who"] == "you" else "assistant"
        messages.append({"role": role, "content": h["text"]})
    messages.append({"role": "user", "content": user_msg})
    payload = json.dumps(
        {"messages": messages, "temperature": 0.85, "max_tokens": 180}
    ).encode()
    req = urllib.request.Request(
        LLAMA_URL, data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"].strip()


SENT_POS = set("thanks thank love great good happy nice awesome fun yay cool amazing best".split())
SENT_NEG = set("hate bad sad ugh annoying stupid boring angry mad worst awful".split())


def drift(pet, user_msg):
    words = set(re.findall(r"[a-z0-9']+", user_msg.lower()))
    pos, neg = len(words & SENT_POS), len(words & SENT_NEG)
    delta = pos - neg
    pet["mood"]["valence"] = max(0, min(100, pet["mood"]["valence"] + delta * 4))
    pet["mood"]["energy"] = max(0, min(100, pet["mood"]["energy"] - 1 + (2 if pos else 0)))
    if delta > 0:
        pet["traits"]["warmth"] = min(100, pet["traits"]["warmth"] + 0.4)
    if "?" in user_msg:
        pet["traits"]["curious"] = min(100, pet["traits"]["curious"] + 0.3)
    if len(user_msg) > 80:
        pet["traits"]["patient"] = min(100, pet["traits"]["patient"] + 0.2)


FACT_LIKE = re.compile(r"i like ([^.!?]+)")
FACT_DISLIKE = re.compile(r"i (?:don'?t|dont) like ([^.!?]+)|i hate ([^.!?]+)")
FACT_REMEMBER = re.compile(r"remember (?:that )?([^.!?]+)")


def extract_facts(user, text):
    low = text.lower()
    m = FACT_LIKE.search(low)
    if m:
        v = m.group(1).strip()
        if v and v not in user["facts"]["likes"]:
            user["facts"]["likes"].append(v)
    m = FACT_DISLIKE.search(low)
    if m:
        v = (m.group(1) or m.group(2) or "").strip()
        if v and v not in user["facts"]["dislikes"]:
            user["facts"]["dislikes"].append(v)
    m = FACT_REMEMBER.search(low)
    if m:
        v = m.group(1).strip()
        if v and v not in user["facts"]["notes"]:
            user["facts"]["notes"].append(v)


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=WEB_DIR, **kw)

    def log_message(self, fmt, *args):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/users":
            return self._json(list_users())
        if self.path.startswith("/api/state"):
            uid = self.path.split("uid=")[-1]
            user = load(user_path(uid), lambda: default_user(uid))
            pet = load(PET_FILE, default_pet)
            return self._json({"pet": pet, "user": user})
        return super().do_GET()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._json({"error": "bad json"}, 400)

        if self.path == "/api/users":
            name = (body.get("name") or "friend").strip()[:40]
            uid = slugify(name)
            path = user_path(uid)
            if not os.path.exists(path):
                save(path, default_user(name))
            return self._json({"id": uid, "name": name})

        if self.path == "/api/chat":
            uid, msg = body.get("uid"), (body.get("message") or "").strip()
            if not uid or not msg:
                return self._json({"error": "missing uid/message"}, 400)
            user = load(user_path(uid), lambda: default_user(uid))
            pet = load(PET_FILE, default_pet)

            user["chatLog"].append({"who": "you", "text": msg, "ts": time.time()})
            extract_facts(user, msg)
            drift(pet, msg)
            user["affinity"] = min(100, user["affinity"] + 0.3)

            sys_prompt = build_system_prompt(pet, user)
            try:
                reply_text = call_llm(sys_prompt, user["chatLog"][:-1], msg)
            except Exception:
                reply_text = "(...connection to my brain dropped. is llama-server running?)"

            user["chatLog"].append({"who": "pet", "text": reply_text, "ts": time.time()})
            pet["lastSeen"] = time.time()
            save(user_path(uid), user)
            save(PET_FILE, pet)
            return self._json({"reply": reply_text, "pet": pet, "user": user})

        self._json({"error": "not found"}, 404)


def main():
    with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), Handler) as httpd:
        ip = lan_ip()
        print(f"memory-pet is running")
        print(f"  on this PC:   http://127.0.0.1:{PORT}")
        print(f"  on your phone (same wifi): http://{ip}:{PORT}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
