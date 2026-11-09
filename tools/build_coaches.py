"""Build coaches/index.html (the coaches' edition) from index.html.

The coaches' edition is the athletes' page plus a Check-in section that reads and ticks the
Attendance tab through the Google Apps Script web app whose URL is in coaches/config.js.
Run after any change to index.html:  python3 -I tools/build_coaches.py
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CSS = """
.checkin{margin-top:20px;background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:16px;display:grid;gap:12px}
.ci-top{display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:space-between}
.ci-top h2{margin:0}
.ci-count{font:700 28px/1 var(--display);color:var(--accent)}
.ci-count small{font:600 13px var(--body);color:var(--muted);margin-left:4px}
.ci-controls{display:grid;grid-template-columns:1fr;gap:8px}
@media (min-width:560px){.ci-controls{grid-template-columns:1fr 1fr}}
.ci-controls select,.ci-controls input{font:500 16px var(--body);width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--ink)}
.ci-list{list-style:none;margin:0;padding:0;display:grid;gap:6px}
.ci-list li{margin:0}
.ci-btn{width:100%;display:flex;align-items:center;gap:12px;text-align:left;font:600 17px var(--body);color:var(--ink);background:var(--bg);border:1px solid var(--line);border-radius:12px;padding:12px 14px;cursor:pointer;min-height:52px}
.ci-btn .box{flex:none;width:26px;height:26px;border-radius:7px;border:2px solid var(--muted);display:grid;place-items:center;font-size:16px;line-height:1;color:transparent}
.ci-btn[aria-pressed="true"]{background:var(--accent-soft);border-color:var(--accent)}
.ci-btn[aria-pressed="true"] .box{background:var(--accent);border-color:var(--accent);color:var(--bg)}
.ci-btn.saving{opacity:.6}
.ci-btn:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.ci-msg{font-size:14px;color:var(--muted);margin:0}
.ci-msg.err{color:var(--accent);font-weight:600}
.panel .checkin{margin:0;border:0;padding:0;background:none}
.ci-open{font:700 15px var(--body);border:0;background:var(--accent);color:var(--bg);border-radius:999px;padding:10px 16px;cursor:pointer;display:inline-flex;align-items:center;gap:6px}
.ci-open:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
"""

HTML = """
<div class="sheet" id="ci-sheet" hidden><div class="panel" role="dialog" aria-modal="true" aria-labelledby="ci-title">
<section class="checkin" id="checkin" aria-labelledby="ci-title">
  <div class="ci-top"><h2 id="ci-title">Check-in</h2><div class="ci-count" id="ci-count" aria-live="polite"></div><button class="close" id="ci-close" type="button">Close</button></div>
  <div class="ci-controls">
    <label class="sr" for="ci-session">Session</label>
    <select id="ci-session" aria-label="Session"></select>
    <input id="ci-search" type="search" placeholder="Find a name" aria-label="Find a name" autocomplete="off">
  </div>
  <p class="ci-msg" id="ci-msg">Loading the attendance list…</p>
  <ul class="ci-list" id="ci-list"></ul>
  <p class="ci-msg">Tap a name to check them in; tap again to undo. Each tap saves to the Attendance tab. New athletes are added in the Sheet.</p>
</section>
</div></div>
"""

JS = r"""
// coaches' check-in (Attendance tab via Google Apps Script)
(function(){
  const URL_=(window.ATTENDANCE_URL||"").trim();
  const $=id=>document.getElementById(id);
  const sel=$("ci-session"), list=$("ci-list"), msg=$("ci-msg"), count=$("ci-count"), search=$("ci-search");
  let sessions=[], col=null, roster=[], pending=new Set(), timer=null, started=false;
  const sheetEl=$("ci-sheet"); let lastFocus=null;
  const isOpen=()=>!sheetEl.hidden;
  function openCI(){
    if(isOpen()) return;
    lastFocus=document.activeElement; sheetEl.hidden=false; document.body.style.overflow="hidden";
    if(location.hash!=="#checkin") history.replaceState(null,"","#checkin");
    if(!started){started=true;start()} else if(!pending.size) loadRoster(true);
    $("ci-close").focus();
  }
  function closeCI(){
    if(!isOpen()) return;
    sheetEl.hidden=true; document.body.style.overflow="";
    if(location.hash==="#checkin") history.replaceState(null,"","#"+track);
    if(lastFocus&&lastFocus.focus) lastFocus.focus();
  }
  $("ci-close").addEventListener("click",closeCI);
  sheetEl.addEventListener("click",e=>{if(e.target===sheetEl)closeCI()});
  document.addEventListener("keydown",e=>{if(e.key==="Escape")closeCI()});
  document.addEventListener("click",e=>{const a=e.target.closest('#ci-open,a[href="#checkin"]');if(!a)return;e.preventDefault();openCI()});
  window.addEventListener("hashchange",()=>{if(location.hash==="#checkin")openCI()});
  const yr=m=>m>=8?2026:2027;
  const label=s=>{const d=new Date(yr(s.month),s.month-1,s.day);return `${DAYS[d.getDay()]} ${MN[s.month-1]} ${s.day}${s.ampm?" · "+s.ampm:""}${s.cancelled?" (cancelled)":""}`};
  const say=(t,err)=>{msg.textContent=t;msg.classList.toggle("err",!!err);msg.hidden=!t};
  async function api(params){
    const q=new URLSearchParams(params).toString();
    const r=await fetch(`${URL_}?${q}`,{redirect:"follow"});
    if(!r.ok) throw new Error(`The Sheet didn't answer (error ${r.status}).`);
    const j=await r.json(); if(j.error) throw new Error(j.error); return j;
  }
  function pickDefault(){
    const now=new Date(), t=new Date(now.getFullYear(),now.getMonth(),now.getDate()).getTime(), pm=now.getHours()>=12;
    const ts=s=>new Date(yr(s.month),s.month-1,s.day).getTime();
    const today=sessions.filter(s=>ts(s)===t);
    if(today.length) return (today.find(s=>s.ampm===(pm?"PM":"AM"))||today[today.length-1]).col;
    const past=sessions.filter(s=>ts(s)<t); const next=sessions.find(s=>ts(s)>t);
    return (next||past[past.length-1]||sessions[0]).col;
  }
  function draw(){
    const q=search.value.trim().toLowerCase();
    const shown=roster.filter(p=>!q||`${p.first} ${p.last}`.toLowerCase().includes(q));
    const n=roster.filter(p=>p.present).length;
    count.innerHTML=`${n}<small>checked in</small>`;
    list.innerHTML=shown.map(p=>`<li><button type="button" class="ci-btn${pending.has(p.row)?" saving":""}" data-row="${p.row}" aria-pressed="${p.present}"><span class="box" aria-hidden="true">✓</span><span>${esc(p.first)} ${esc(p.last)}</span></button></li>`).join("")
      || (roster.length?`<li class="ci-msg">No names match "${esc(search.value)}".</li>`:"");
  }
  async function loadRoster(quiet){
    if(!col) return;
    try{
      const j=await api({col});
      if(+j.col!==+col) return;
      const keep=new Map(roster.filter(p=>pending.has(p.row)).map(p=>[p.row,p.present]));
      roster=(j.roster||[]).map(p=>keep.has(p.row)?{...p,present:keep.get(p.row)}:p);
      say(roster.length?"":"No names in the Attendance tab yet."); draw();
    }catch(e){ if(!quiet) say(`Couldn't load the list. ${e.message} Check your signal and pull down to reload.`,true) }
  }
  async function start(){
    if(!URL_){say("Check-in isn't connected to the Sheet yet. Add the Google script's web app address to coaches/config.js.",true);return}
    try{
      const j=await api({});
      sessions=(j.sessions||[]);
      if(!sessions.length){say("No session dates found in row 3 of the Attendance tab.",true);return}
      let saved=null; try{saved=+sessionStorage.getItem("arc-ci-col")}catch(e){}
      col=sessions.some(s=>s.col===saved)?saved:pickDefault();
      sel.innerHTML=sessions.map(s=>`<option value="${s.col}"${s.col===col?" selected":""}>${esc(label(s))}</option>`).join("");
      say("Loading names…"); await loadRoster();
      timer=setInterval(()=>{if(isOpen()&&!document.hidden&&!pending.size)loadRoster(true)},30000);
    }catch(e){say(`Couldn't reach the Sheet. ${e.message}`,true)}
  }
  sel.addEventListener("change",()=>{col=+sel.value;try{sessionStorage.setItem("arc-ci-col",col)}catch(e){};roster=[];pending.clear();draw();say("Loading names…");loadRoster()});
  search.addEventListener("input",draw);
  list.addEventListener("click",async e=>{
    const b=e.target.closest("[data-row]"); if(!b) return;
    const row=+b.dataset.row, p=roster.find(x=>x.row===row); if(!p||pending.has(row)) return;
    const want=!p.present; p.present=want; pending.add(row); draw();
    try{ const j=await api({action:"set",col,row,present:want?1:0}); p.present=!!j.present; say("") }
    catch(err){ p.present=!want; say(`${p.first} ${p.last} wasn't saved. ${err.message} Tap again to retry.`,true) }
    finally{ pending.delete(row); draw() }
  });
  document.addEventListener("visibilitychange",()=>{if(isOpen()&&started&&!document.hidden&&!pending.size)loadRoster(true)});
  if(location.hash==="#checkin") openCI();
})();
"""


def build():
    src = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    s = src

    def rep(old, new, count=1):
        nonlocal s
        assert s.count(old) >= 1, f"missing: {old[:60]}"
        s = s.replace(old, new) if count == 0 else s.replace(old, new, count)

    s = re.sub(r"<title>.*?</title>", "<title>ARC Winter Erg Plan · Coaches</title>", s, count=1)
    rep("<title>", '<meta name="robots" content="noindex">\n<title>')
    for f in ("icon-192.png", "apple-touch-icon.png", "manifest.webmanifest"):
        rep(f'href="{f}"', f'href="../{f}"')
    rep('content="ARC Erg"', 'content="ARC Coach"')
    for f in ("plan.json", "details.json"):
        rep(f'getJSON("{f}")', f'getJSON("../{f}")')
    rep('<div class="eyebrow">Annapolis Rowing Club · Masters</div>', '<div class="eyebrow">Annapolis Rowing Club · Coaches\' edition</div>')
    rep('<nav class="jump">', '<button type="button" class="ci-open" id="ci-open"><span aria-hidden="true">✓</span> Check-in</button>\n  <nav class="jump">')
    rep('<div class="now" id="now">', HTML.strip() + '\n\n<div class="now" id="now">')
    rep("</style>", CSS.strip() + "\n.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}\n</style>")
    # version the settings file by its contents so phones never keep an old copy
    import hashlib
    cfgp = os.path.join(ROOT, "coaches", "config.js")
    ver = hashlib.sha1(open(cfgp, "rb").read()).hexdigest()[:8] if os.path.exists(cfgp) else "0"
    rep("<script>", f'<script src="config.js?v={ver}"></script>\n<script>')
    idx = s.rindex("</script>")
    s = s[:idx] + JS.strip() + "\n" + s[idx:]
    os.makedirs(os.path.join(ROOT, "coaches"), exist_ok=True)
    open(os.path.join(ROOT, "coaches", "index.html"), "w", encoding="utf-8").write(s)
    cfg = os.path.join(ROOT, "coaches", "config.js")
    if not os.path.exists(cfg):
        open(cfg, "w").write('// Web app address of the Attendance Google script (ends in /exec)\nwindow.ATTENDANCE_URL = "";\n')
    print("built coaches/index.html")


if __name__ == "__main__":
    build()
