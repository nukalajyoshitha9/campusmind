import random 
import math
import os
import time
from typing import Optional


import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel

app = FastAPI(title="CampusMind - DSU Digital Twin")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

# ---------------------------------------------------------------
# SETTINGS
# ---------------------------------------------------------------
RUPEES_PER_KWH = 8        # simulated assumption, say this to the judges
LEAK_HOURS_SAVED = 1.5    # simulated: hours of waste avoided per switch-off
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")   # optional
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# Room ids must stay the same as the map uses them (block-b, admin ...)
BASE = {
    "block-a": {"name": "Block A", "kw": 12.0, "people": 140},
    "block-b": {"name": "CD Simer", "kw": 15.0, "people": 120},
    "library": {"name": "Library", "kw": 9.0, "people": 85},
    "admin": {"name": "School of Health Sciences & Pharmacy", "kw": 10.0, "people": 60},
    "lab": {"name": "CS Lab", "kw": 18.0, "people": 45},
}
LEAK_KW = {"block-a": 21.0, "block-b": 26.0, "library": 15.0, "admin": 17.0, "lab": 30.0}
EVENT_KW = {"block-a": 16.0, "block-b": 24.0, "library": 12.0, "admin": 14.0, "lab": 24.0}

ROOMS = {}
STATS = {"alerts": 0, "kwh_saved": 0.0, "rupees_saved": 0}
LOG = []          # action log the copilot can read
FEEDBACK = []     # student pins


def reset_state():
    ROOMS.clear()
    for rid, b in BASE.items():
        ROOMS[rid] = {
            "id": rid,
            "name": b["name"],
            "kw": b["kw"],
            "people": b["people"],
            "lights": True,
            "status": "ok",
        }
    STATS.update({"alerts": 0, "kwh_saved": 0.0, "rupees_saved": 0})
    LOG.clear()
    FEEDBACK.clear()


reset_state()

# Code Clash 2.0 is running now, 10 AM to 4 PM
EVENTS = [
    {"title": "Code Clash 2.0", "room": "block-b", "start": "10:00 AM", "end": "4:00 PM", "live": True},
    {"title": "Guest lecture: Green Energy", "room": "library", "start": "4:30 PM", "end": "5:30 PM", "live": False},
    {"title": "Pharmacy seminar", "room": "admin", "start": "5:00 PM", "end": "6:00 PM", "live": False},
]


def now_str():
    return time.strftime("%I:%M %p")


def log(msg):
    LOG.append(f"{now_str()} - {msg}")
    del LOG[:-30]


# ---------------------------------------------------------------
# PAGES + DATA
# ---------------------------------------------------------------
@app.get("/")
def home():
    return RedirectResponse("/student")


@app.get("/student")
def student_page():
    return FileResponse("student.html")


@app.get("/admin")
def admin_page():
    return FileResponse("admin.html")


@app.get("/map")
def map_page():
    return FileResponse("index.html")   # the 3D map you already have


@app.get("/rooms")
def rooms():
    return ROOMS


@app.get("/stats")
def stats():
    return STATS


@app.get("/events")
def events():
    return EVENTS


# ---------------------------------------------------------------
# SIMULATION + ACTIONS
# ---------------------------------------------------------------
@app.post("/simulate/empty-room/{room_id}")
def simulate_empty(room_id: str):
    r = ROOMS.get(room_id)
    if not r:
        return {"ok": False, "msg": "Unknown room"}
    if r["status"] != "leak":
        STATS["alerts"] += 1
    r.update(people=0, lights=True, kw=LEAK_KW[room_id], status="leak")
    log(f"CCTV: {r['name']} is empty but lights are ON (energy leak)")
    return {"ok": True, "msg": f"Energy leak detected in {r['name']}"}


@app.post("/simulate/event/{room_id}")
def simulate_event(room_id: str):
    r = ROOMS.get(room_id)
    if not r:
        return {"ok": False, "msg": "Unknown room"}
    r.update(people=180, lights=True, kw=EVENT_KW[room_id], status="event")
    log(f"Event started in {r['name']}, high power use is expected")
    return {"ok": True, "msg": f"Event started in {r['name']}"}


@app.post("/action/switch-off/{room_id}")
def switch_off(room_id: str):
    r = ROOMS.get(room_id)
    if not r:
        return {"ok": False, "msg": "Unknown room"}
    if r["status"] == "leak":
        saved = round((r["kw"] - BASE[room_id]["kw"] * 0.2) * LEAK_HOURS_SAVED, 1)
        STATS["kwh_saved"] += saved
        STATS["rupees_saved"] = round(STATS["kwh_saved"] * RUPEES_PER_KWH)
        log(f"Auto switch-off in {r['name']}, saved about {saved} kWh (simulated)")
    r.update(people=0, lights=False, kw=round(BASE[room_id]["kw"] * 0.2, 1), status="ok")
    return {"ok": True, "msg": f"Lights switched off in {r['name']}"}


@app.post("/reset")
def reset():
    reset_state()
    return {"ok": True, "msg": "Demo reset"}


class Feedback(BaseModel):
    room: str = ""
    issue: str = ""            # old map button sends this
    kind: str = "problem"      # "problem" or "class"
    category: str = ""
    rating: Optional[int] = None
    text: str = ""
    class_id: str = ""


URGENT = ("water leak", "damage", "fire", "short circuit")


@app.post("/feedback")
def feedback(f: Feedback):
    cat = f.category or f.issue
    name = ROOMS.get(f.room, {}).get("name", f.room)
    FEEDBACK.append({
        "id": len(FEEDBACK) + 1, "kind": f.kind, "room": f.room, "category": cat,
        "rating": f.rating, "text": f.text, "class_id": f.class_id,
        "time": now_str(), "status": "open", "urgent": cat.lower() in URGENT,
    })
    log(f"Student {f.kind} report at {name}: {cat or 'class feedback'}")
    return {"ok": True, "msg": "Sent to admin"}


@app.get("/feedbacks")
def feedbacks():
    return FEEDBACK[::-1]


@app.post("/feedback/{fid}/resolve")
def resolve(fid: int):
    for x in FEEDBACK:
        if x["id"] == fid:
            x["status"] = "resolved"
    return {"ok": True}


# ---------------------------------------------------------------
# CLASSES (student portal)
# ---------------------------------------------------------------
CLASSES = [
    {"id": "c1", "subject": "Data Structures", "room": "block-a", "faculty": "Prof. Rao", "start": "10:00", "end": "11:00", "enrolled": 60},
    {"id": "c2", "subject": "Pharmacology", "room": "admin", "faculty": "Dr. Nair", "start": "09:00", "end": "10:00", "enrolled": 55},
    {"id": "c3", "subject": "DBMS Lab", "room": "lab", "faculty": "Prof. Iyer", "start": "10:00", "end": "13:00", "enrolled": 45},
    {"id": "c4", "subject": "Engineering Mathematics", "room": "block-a", "faculty": "Dr. Kumar", "start": "14:00", "end": "15:00", "enrolled": 70},
]
OVERRIDE = {}   # demo: force a class to "live" or "done"


def class_status(c):
    if c["id"] in OVERRIDE:
        return OVERRIDE[c["id"]]
    t = time.strftime("%H:%M")
    if c["start"] <= t < c["end"]:
        return "live"
    return "done" if t >= c["end"] else "upcoming"


@app.get("/classes")
def classes():
    out = []
    for c in CLASSES:
        st = class_status(c)
        out.append({**c, "status": st, "strength": ROOMS[c["room"]]["people"] if st == "live" else 0})
    return out


@app.post("/demo/class/{cid}/{state}")
def demo_class(cid: str, state: str):
    OVERRIDE[cid] = "live" if state == "live" else "done"
    return {"ok": True}


@app.post("/demo/classes-reset")
def demo_classes_reset():
    OVERRIDE.clear()
    return {"ok": True}


# ---------------------------------------------------------------
# DIRECTIONS (metres east / south of the fountain, same as the map)
# ---------------------------------------------------------------
PLACES = {
    "gate": ("Main Gate", -168, -10), "fountain": ("Fountain", 0, 0),
    "library": ("Library", 52, -3), "block-a": ("Block A", -63, 28),
    "block-b": ("CD Simer", -42, 105), "admin": ("School of Health Sciences & Pharmacy", 96, -66),
    "lab": ("CS Lab", 150, 62),
}


@app.get("/route")
def route(src: str, dst: str):
    a, b = PLACES.get(src), PLACES.get(dst)
    if not a or not b:
        return {"ok": False, "msg": "Unknown place"}
    if src == dst:
        return {"ok": False, "msg": "You are already there."}
    na = ROOMS[src]["name"] if src in ROOMS else a[0]
    nb = ROOMS[dst]["name"] if dst in ROOMS else b[0]
    dx, dy = b[1] - a[1], b[2] - a[2]
    d = round(math.hypot(dx, dy))
    ang = (math.degrees(math.atan2(dx, -dy)) + 360) % 360
    way = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"][int((ang + 22.5) // 45) % 8]
    mins = max(1, round(d / 75))
    return {"ok": True, "distance_m": d, "steps": [
        f"Start at {na}.",
        f"Walk {way} for about {d} metres.",
        f"You reach {nb}. About {mins} min on foot.",
    ]}


# ---------------------------------------------------------------
# AI COPILOT (Gemini if a key is set, otherwise a built-in answer)
# ---------------------------------------------------------------
class Ask(BaseModel):
    question: str


def context_text():
    lines = ["LIVE ROOMS:"]
    for r in ROOMS.values():
        lines.append(
            f"- {r['name']}: {r['kw']} kW, {r['people']} people, "
            f"lights {'ON' if r['lights'] else 'OFF'}, status {r['status']}"
        )
    lines.append("EVENTS:")
    for e in EVENTS:
        room = ROOMS[e["room"]]["name"]
        lines.append(f"- {e['title']} in {room}, {e['start']} to {e['end']}, live={e['live']}")
    lines.append(f"STATS: {STATS['alerts']} alerts, {STATS['kwh_saved']:.1f} kWh saved, Rs {STATS['rupees_saved']} saved")
    lines.append("RECENT ACTIONS:")
    lines.extend(f"- {x}" for x in LOG[-8:])
    lines.append("Savings are simulated using Rs 8 per kWh.")
    return "\n".join(lines)


def fallback_answer(q: str) -> str:
    s = q.lower()
    leaks = [r for r in ROOMS.values() if r["status"] == "leak"]
    events = [r for r in ROOMS.values() if r["status"] == "event"]
    live = [e for e in EVENTS if e["live"]]

    if "spike" in s or "why" in s:
        target = next((r for r in ROOMS.values() if r["name"].lower() in s), None)
        if target is None and leaks:
            target = leaks[0]
        if target is None:
            target = ROOMS["block-b"]
        if target["status"] == "leak":
            return (f"{target['name']} is using {target['kw']} kW with 0 people inside. "
                    "CCTV shows the room empty while the lights are ON, so this is an energy leak, "
                    "not real demand. Recommended action: auto switch-off now.")
        ev = next((e for e in live if e["room"] == next(k for k, v in ROOMS.items() if v is target)), None)
        if ev:
            return (f"{target['name']} is using {target['kw']} kW because {ev['title']} is live "
                    f"({ev['start']} to {ev['end']}) with {target['people']} people. "
                    "This is expected demand, not a leak.")
        return f"{target['name']} is at {target['kw']} kW with {target['people']} people. Nothing unusual right now."

    if "wast" in s or "which room" in s:
        if not leaks:
            return "No room is wasting energy right now. Every occupied room has people inside."
        return "Wasting energy now: " + ", ".join(
            f"{r['name']} ({r['kw']} kW, empty, lights ON)" for r in leaks
        ) + ". Auto switch-off will fix it."

    if "policy" in s:
        return ("Draft policy for the dean: (1) Lights and AC auto switch off after 10 minutes with no one "
                "detected by CCTV. (2) Daily alert report to the facilities head. (3) Events must book rooms "
                "so power is planned. (4) Review savings monthly. Savings figures are simulated at Rs 8 per kWh.")

    if "report" in s or "weekly" in s:
        top = sorted(ROOMS.values(), key=lambda r: r["kw"], reverse=True)[:3]
        names = ", ".join(f"{r['name']} ({r['kw']} kW)" for r in top)
        return (f"Sustainability report: {STATS['alerts']} energy leaks caught, "
                f"{STATS['kwh_saved']:.1f} kWh saved, Rs {STATS['rupees_saved']} saved (simulated, Rs 8 per kWh). "
                f"Top 3 power users: {names}.")

    if "event" in s or "code clash" in s:
        if live:
            e = live[0]
            return f"{e['title']} is live in {ROOMS[e['room']]['name']} from {e['start']} to {e['end']}."
        return "No event is live right now."

    return (f"Campus status: {len(leaks)} leak(s), {len(events)} room(s) hosting events, "
            f"{STATS['kwh_saved']:.1f} kWh saved so far. Ask me why a block spiked, "
            "which rooms waste energy, or for a report for the dean.")


def ask_gemini(q: str):
    if not GEMINI_KEY:
        return None
    prompt = (
        "You are CampusMind Copilot for Dayananda Sagar University. Answer in 3 to 5 short sentences "
        "using ONLY the data below. Name the room, the kW and the people count. If a room is an energy leak "
        "(empty, lights ON), say so and recommend auto switch-off. If a live event explains high power, say that "
        "it is expected. Always call savings simulated.\n\n"
        f"{context_text()}\n\nQUESTION: {q}"
    )
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}"
           f":generateContent?key={GEMINI_KEY}")
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=12)
        res.raise_for_status()
        return res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print("Gemini failed, using fallback:", e)
        return None


@app.post("/copilot")
def copilot(a: Ask):
    text = ask_gemini(a.question)
    if text:
        return {"answer": text, "source": "Gemini"}
    return {"answer": fallback_answer(a.question), "source": "built-in analyst (saved fallback)"}
    