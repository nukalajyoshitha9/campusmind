"""Run once, in the same folder as index.html:  py patch_index.py
It saves a backup (index_backup.html) and updates index.html so the 3D map
fits the new Student / Admin pages."""
import shutil

src = open("index.html", encoding="utf-8", newline="").read().replace("\r\n", "\n")
shutil.copy("index.html", "index_backup.html")

EDITS = [
    # 1. nav tabs instead of the old Student/Admin mode buttons
    ('''<button id="bs" class="on" onclick="setMode('student')">Student</button>
<button id="ba" onclick="setMode('admin')">Admin</button>
''',
     '''<div class="nav"><a href="/student">Student</a><a href="/admin">Admin</a><a class="on" href="/map">3D Map</a></div>
'''),
    # 2. CSS for the tabs and the emergency banner
    ('</style></head><body>',
     '''.nav{display:flex;gap:6px;margin-bottom:8px}
.nav a{color:#cbd5ff;text-decoration:none;padding:6px 11px;border-radius:8px;background:#1e2d57;font-size:13px}
.nav a.on{background:#2e9e3f;color:#fff}
#em .e{background:#c0392b;border-radius:8px;padding:6px 8px;margin:6px 0;font-size:13px;font-weight:600}
summary{cursor:pointer;color:#9db4ff;font-size:13px;margin:10px 0 4px}
</style></head><body>'''),
    # 3. emergency banner slot
    ('<div id="err"></div>', '<div id="err"></div><div id="em"></div>'),
    # 4. remove "Report an issue" (now in the Student page) and fold admin tools into "Map setup tools"
    ('''<h3>Report an issue</h3>
<select id="sel"></select>
<button onclick="pin('water leak')">Water leak</button>
<button onclick="pin('lights on')">Lights on</button>
<div id="admin" style="display:none">
<h3>Admin: simulate</h3>''',
     '''<select id="sel" style="display:none"></select>
<details><summary>Map setup tools</summary>
<div id="admin">
<div style="display:none">
<h3>Admin: simulate</h3>'''),
    ('<h3>Admin: place building</h3>', '</div>\n<h3>Setup: place building</h3>'),
    ('<h3>Admin: trace real shape</h3>', '<h3>Setup: trace real shape</h3>'),
    ('</div>\n<h3>Go to location</h3>', '</div></details>\n<h3>Go to location</h3>'),
    # 5. show open student emergencies on the map
    ('if(!lled){const o=Object.entries(ROOMS)',
     '''try{const fb=await (await fetch(API+"/feedbacks")).json();
$("em").innerHTML=fb.filter(x=>x.urgent&&x.status==="open").map(x=>'<div class="e">EMERGENCY: '+x.category+' at '+(ROOMS[x.room]?ROOMS[x.room].name:x.room)+'</div>').join("")}catch(e){}
if(!lled){const o=Object.entries(ROOMS)'''),
]

done = 0
for i, (old, new) in enumerate(EDITS, 1):
    if src.count(old) == 1:
        src = src.replace(old, new)
        done += 1
        print(f"edit {i}: done")
    else:
        print(f"edit {i}: SKIPPED (found {src.count(old)} times). Send me this edit number.")

open("index.html", "w", encoding="utf-8", newline="\n").write(src)
print(f"\n{done} of {len(EDITS)} edits applied. Backup saved as index_backup.html")