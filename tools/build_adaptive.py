"""Build adaptive/index.html (the Adaptive team's edition) from index.html.

The Adaptive team trains only in the Monday PM and Wednesday PM Fitness & Community sessions,
so this edition shows just Fitness & Community workouts #1 (Monday PM) and #2 (Wednesday PM)
each week, with the PM coach only. It reads the same plan.json and details.json as the main
page, so the daily spreadsheet update keeps it current with no extra step.
Run after any change to index.html:  python3 -I tools/build_adaptive.py
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Runs on load: keep only Fitness & Community sessions 1 (Mon PM) and 2 (Wed PM)
ADAPT_JS = r"""
// Adaptive edition: Fitness & Community #1 = Monday PM, #2 = Wednesday PM
const ADAPT_SLOTS={1:{day:"Monday PM",off:0},2:{day:"Wednesday PM",off:2}};
function adapt(p){
  const weeks=(p&&p.fitness)||[];
  return {competitive:[],fitness:weeks.map(w=>{
    if(!w.wk) return w;
    const s=weekStart(w.dates);
    const type=String(w.type||"").replace(/\s*\+\s*test\b/i,"").replace(/^test$/i,"");
    const workouts=w.workouts.filter(x=>ADAPT_SLOTS[x.n]).map(x=>{
      const sl=ADAPT_SLOTS[x.n], d=s?new Date(s.getTime()+sl.off*864e5):null;
      return {...x,label:sl.day+(d?` · ${MN[d.getMonth()]} ${d.getDate()}`:""),coachAm:"",coachPm:x.coachPm||""};
    });
    return {...w,type,workouts};
  })};
}
// detail tabs list several coaches (e.g. "11.16 pm …", "11.17 am …"); keep the PM ones
function pmCoaches(list){const pm=(list||[]).filter(c=>/\bpm\b/i.test(c));return pm.length?pm:(list||[])}
"""


def build():
    s = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()

    def rep(old, new):
        nonlocal s
        assert s.count(old) == 1, f"expected exactly one: {old[:70]}"
        s = s.replace(old, new)

    s = re.sub(r"<title>.*?</title>", "<title>ARC Adaptive Erg Plan</title>", s, count=1)
    rep('content="Annapolis Rowing Club masters winter erg training plan, 2026–27."',
        'content="Annapolis Rowing Club Adaptive team: Monday and Wednesday PM erg sessions, winter 2026–27."')
    rep('content="ARC Erg"', 'content="ARC Adaptive"')
    # versioned icon addresses so phones never reuse a stale or missing icon
    rep('<link rel="icon" href="icon-192.png" type="image/png">',
        '<link rel="icon" href="icon-192.png?v=2" type="image/png" sizes="192x192">')
    rep('<link rel="apple-touch-icon" href="apple-touch-icon.png">',
        '<link rel="apple-touch-icon" href="apple-touch-icon.png?v=2" sizes="180x180">')
    rep('<link rel="manifest" href="manifest.webmanifest">',
        '<link rel="manifest" href="manifest.webmanifest?v=2">')
    for f in ("plan.json", "details.json"):
        rep(f'getJSON("{f}")', f'getJSON("../{f}")')

    # header
    rep('<div class="eyebrow">Annapolis Rowing Club · Masters</div>',
        '<div class="eyebrow">Annapolis Rowing Club · Adaptive</div>')
    rep('<h1>Winter Erg Plan 2026–27</h1>', '<h1>Adaptive Erg Plan 2026–27</h1>')
    rep('<p class="sub">Mon Nov 2, 2026 – Wed Mar 31, 2027</p>',
        '<p class="sub">Monday &amp; Wednesday PM Community &amp; Fitness sessions · Nov 2, 2026 – Mar 31, 2027</p>')

    # no track switch: this edition is Fitness & Community only
    s, n = re.subn(r'\s*<div class="seg" role="group" aria-label="Choose your track">.*?</div>', "", s, count=1, flags=re.S)
    assert n == 1, "track switch not found"

    # data: filter to Mon PM / Wed PM and always show the Fitness track
    rep('let PLAN={competitive:[],fitness:[]}, DETAILS={}, track="competitive";',
        'let PLAN={competitive:[],fitness:[]}, DETAILS={}, track="fitness";' + ADAPT_JS)
    rep("if(p)PLAN=p;", "if(p)PLAN=adapt(p);")
    rep("function render(){", 'function render(){track="fitness";')
    rep("const d=DETAILS[k]; if(!d) return;",
        'const d=DETAILS[k]; if(!d||!/^fit-\\d+-[12]$/.test(k)) return;')
    rep("d.coach.map(c=>esc(fmtCoach(c)))", "pmCoaches(d.coach).map(c=>esc(fmtCoach(c)))")
    rep('${tr==="competitive"?"Competitive":"Fitness &amp; Community"} · Week',
        'Adaptive · Week')
    rep("<h2 id=\"ptitle\">Workout ${esc(title)}</h2>", "<h2 id=\"ptitle\">${esc(title)}</h2>")
    rep('wo.label.replace(/\\s*\\(.*\\)$/,"")', 'wo.label.replace(" · ",", ")')

    os.makedirs(os.path.join(ROOT, "adaptive"), exist_ok=True)
    open(os.path.join(ROOT, "adaptive", "index.html"), "w", encoding="utf-8").write(s)
    print("built adaptive/index.html")


if __name__ == "__main__":
    build()
