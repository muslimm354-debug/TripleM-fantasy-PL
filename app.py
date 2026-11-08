"""FPL Command Centre - personal Fantasy Premier League dashboard (Streamlit)."""
import math
from datetime import datetime, timezone

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

API = "https://fantasy.premierleague.com/api"
HDR = {"User-Agent": "Mozilla/5.0 (personal FPL dashboard)"}
POS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
STATUS = {"a": "متاح", "d": "شك", "i": "مصاب", "s": "موقوف", "u": "غير متاح", "n": "غير متاح"}

st.set_page_config(page_title="FPL Command Centre", page_icon="⚽", layout="wide")
st.markdown(
    """<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=Barlow:wght@400;500&display=swap');
html, body, [class*="css"] {font-family:'Barlow',sans-serif;}
h1,h2,h3 {font-family:'Barlow Condensed',sans-serif;}
.hero {background:linear-gradient(120deg,#2d0b4e 0%,#1a0b2e 65%);border:1px solid #3d1f63;
 border-radius:14px;padding:16px 24px;margin-bottom:14px;display:flex;justify-content:space-between;align-items:center}
.hero h1 {margin:0;font-size:2.1rem}
.hero small {color:#b9a6d6}
.cd {font-family:'Barlow Condensed',sans-serif;font-size:2.1rem;color:#04f5ff;text-align:right;line-height:1}
.pitch {background:repeating-linear-gradient(#0f5132 0 56px,#11593a 56px 112px);border-radius:12px;padding:10px}
.prow {display:flex;justify-content:center;gap:10px;margin:14px 0;flex-wrap:wrap}
.chip {background:#1a0b2ee6;border:1px solid #04f5ff66;border-radius:8px;padding:6px 10px;min-width:96px;
 text-align:center;font-size:.8rem;color:#f2ecff}
.chip b {display:block;font-size:.9rem}
.chip.cap {border-color:#e90052;box-shadow:0 0 0 1px #e90052}
.bench {margin-top:8px;color:#b9a6d6}
</style>""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------- data layer
@st.cache_data(ttl=600, show_spinner=False)
def get(path):
    r = requests.get(f"{API}/{path}", headers=HDR, timeout=20)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=45, show_spinner=False)
def get_live(path):
    r = requests.get(f"{API}/{path}", headers=HDR, timeout=20)
    r.raise_for_status()
    return r.json()


def safe_get(path, live=False):
    try:
        return (get_live if live else get)(path)
    except requests.RequestException:
        return None


@st.cache_data(ttl=600, show_spinner="جاري تحميل بيانات FPL...")
def load_core():
    b = get("bootstrap-static/")
    fx = pd.DataFrame(get("fixtures/"))
    teams = pd.DataFrame(b["teams"]).set_index("id")
    p = pd.DataFrame(b["elements"])
    num = ["form", "ep_next", "selected_by_percent", "expected_goals", "expected_assists",
           "expected_goal_involvements", "expected_goals_conceded", "expected_goals_per_90",
           "expected_assists_per_90", "expected_goal_involvements_per_90", "threat", "creativity", "ict_index"]
    for c in num:
        p[c] = pd.to_numeric(p[c], errors="coerce").fillna(0)
    p["price"] = p.now_cost / 10
    p["pos"] = p.element_type.map(POS)
    p["team_name"] = p.team.map(teams.short_name)
    return p, teams, fx, pd.DataFrame(b["events"])


def scale(s, invert=False):
    s = (s - s.min()) / (s.max() - s.min())
    return 1 + 4 * ((1 - s) if invert else s)


def fixture_rows(fx, teams, p):
    """One row per team per fixture, with a blended difficulty (official + strength + xG performance)."""
    tp = pd.DataFrame({"xg": p.groupby("team").expected_goals.sum(),
                       "xgc": p.groupby("team").expected_goals_conceded.max()})
    perf = (scale(tp.xg) + scale(tp.xgc, invert=True)) / 2  # higher = tougher opponent
    rows = []
    for r in fx[fx.event.notna()].itertuples():
        for home in (True, False):
            t, o = (r.team_h, r.team_a) if home else (r.team_a, r.team_h)
            rows.append(dict(team=t, event=int(r.event), opp=o, home=home,
                             off=r.team_h_difficulty if home else r.team_a_difficulty,
                             strength=teams.loc[o, "strength_overall_away" if home else "strength_overall_home"],
                             perf=perf.loc[o]))
    d = pd.DataFrame(rows)
    d["strength_n"] = scale(d.strength)
    d["fdr"] = 0.4 * d.off + 0.3 * d.strength_n + 0.3 * d.perf
    return d


def add_scores(p, fr, gw, horizon):
    q = p.copy()
    nxt = fr[(fr.event >= gw) & (fr.event < gw + horizon)]
    q["fix_fdr"] = q.team.map(nxt.groupby("team").fdr.mean()).fillna(3.5)
    q["n_fix"] = q.team.map(fr[fr.event == gw].groupby("team").size()).fillna(0)
    q["avail"] = q.chance_of_playing_next_round.fillna(100) / 100
    q["rel"] = (q.minutes / (max(gw - 1, 1) * 90)).clip(0, 1)
    goal_pts = q.pos.map({"GKP": 6, "DEF": 6, "MID": 5, "FWD": 4})
    xp90 = q.expected_goals_per_90 * goal_pts + q.expected_assists_per_90 * 3 + 2
    q["base"] = 0.4 * q.ep_next + 0.3 * q.form + 0.3 * xp90 * q.rel
    q["mult"] = 1 + (3 - q.fix_fdr) * 0.08
    q["score"] = q.base * q.mult * q.avail * (q.n_fix > 0)
    q["xgi90"] = q.expected_goal_involvements_per_90
    q["lam"] = q.xgi90 * q.rel * q.avail * q.mult * q.n_fix
    return q


# ---------------------------------------------------------------- lineup logic
def pick_xi(pool):
    best = None
    for d in range(3, 6):
        for m in range(2, 6):
            f = 10 - d - m
            if not 1 <= f <= 3:
                continue
            need = (("GKP", 1), ("DEF", d), ("MID", m), ("FWD", f))
            parts = [pool[pool.pos == k].nlargest(n, "score") for k, n in need]
            if any(len(x) < n for x, (_, n) in zip(parts, need)):
                continue
            xi = pd.concat(parts)
            if best is None or xi.score.sum() > best[0]:
                best = (xi.score.sum(), xi, f"{d}-{m}-{f}")
    if best is None:
        return None
    xi = best[1]
    rest = pool.drop(xi.index)
    bench = pd.concat([rest[rest.pos == "GKP"].nlargest(1, "score"),
                       rest[rest.pos != "GKP"].nlargest(3, "score")])
    top = xi.nlargest(2, "score")
    return xi, bench, int(top.id.iloc[0]), int(top.id.iloc[1]), best[2]


def capped_pool(q, n=80):
    keep, cnt = [], {}
    for i, r in q.sort_values("score", ascending=False).iterrows():
        if cnt.get(r.team, 0) < 3:
            keep.append(i)
            cnt[r.team] = cnt.get(r.team, 0) + 1
        if len(keep) >= n:
            break
    return q.loc[keep]


def render_pitch(xi, bench, cap, vice):
    html = "<div class='pitch'>"
    for pos in ["GKP", "DEF", "MID", "FWD"]:
        html += "<div class='prow'>"
        for r in xi[xi.pos == pos].itertuples():
            tag = " (C)" if r.id == cap else " (V)" if r.id == vice else ""
            html += (f"<div class='chip {'cap' if tag == ' (C)' else ''}'><b>{r.web_name}{tag}</b>"
                     f"{r.team_name} · {r.score:.1f}</div>")
        html += "</div>"
    html += "</div><div class='bench'><b>الدكة:</b> " + " | ".join(
        f"{r.web_name} ({r.pos})" for r in bench.itertuples()) + "</div>"
    st.markdown(html, unsafe_allow_html=True)


def fdr_heatmap(fr, teams, start, n=6):
    gws = list(range(start, start + n))
    g = fr[fr.event.isin(gws)].copy()
    g["lab"] = g.opp.map(teams.short_name) + g.home.map({True: " (H)", False: " (A)"})
    z = g.pivot_table(index="team", columns="event", values="fdr", aggfunc="mean").reindex(columns=gws)
    t = g.groupby(["team", "event"]).lab.apply(" + ".join).unstack().reindex(columns=gws)
    z = z.loc[z.mean(axis=1).sort_values().index]
    t = t.loc[z.index]
    fig = go.Figure(go.Heatmap(
        z=z.values, x=[f"GW{c}" for c in gws], y=[teams.short_name[i] for i in z.index],
        text=t.fillna("—").values, texttemplate="%{text}", showscale=False, zmin=1, zmax=5,
        colorscale=[[0, "#00c26e"], [0.5, "#f4d03f"], [1, "#e90052"]]))
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(height=680, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)")
    return fig


# ---------------------------------------------------------------- load + sidebar
p, teams, fx, ev = load_core()
fr = fixture_rows(fx, teams, p)
cur = int(ev[ev.is_current].id.max()) if ev.is_current.any() else None
nx = ev[ev.is_next]
gw_plan = int(nx.id.iloc[0]) if len(nx) else (cur or 1)

with st.sidebar:
    st.header("حسابي")
    tid = st.text_input("FPL Team ID", help="الرقم الظاهر في رابط فريقك: fantasy.premierleague.com/entry/<ID>/")
    horizon = st.slider("أفق التحليل (جولات)", 1, 6, 3)
    auto = st.toggle("تحديث تلقائي كل 60 ثانية", False)
    if auto and st_autorefresh:
        st_autorefresh(interval=60_000, key="live_refresh")
    if st.button("تحديث البيانات الآن"):
        st.cache_data.clear()
        st.rerun()

q = add_scores(p, fr, gw_plan, horizon)

sq = picks = entry = hist = None
pick_gw = cur or gw_plan
if tid.strip().isdigit():
    entry = safe_get(f"entry/{tid}/")
    hist = safe_get(f"entry/{tid}/history/")
    for g in (pick_gw, pick_gw - 1):
        picks = safe_get(f"entry/{tid}/event/{g}/picks/") if g >= 1 else None
        if picks:
            pick_gw = g
            break
    if picks:
        sq = pd.DataFrame(picks["picks"]).merge(q, left_on="element", right_on="id")
    else:
        st.sidebar.error("تعذّر جلب الفريق. تأكد من الرقم.")

# ---------------------------------------------------------------- hero
left = "—"
if len(nx):
    dl = datetime.fromisoformat(nx.deadline_time.iloc[0].replace("Z", "+00:00")) - datetime.now(timezone.utc)
    if dl.total_seconds() > 0:
        left = f"{dl.days}ي {dl.seconds // 3600}س {dl.seconds % 3600 // 60}د"
    else:
        left = "أُغلق"
who = f"{entry['player_first_name']} · {entry['name']}" if entry else "أدخل Team ID من الشريط الجانبي"
st.markdown(
    f"<div class='hero'><div><h1>FPL Command Centre</h1><small>{who}</small></div>"
    f"<div><div class='cd'>{left}</div><small>حتى موعد GW{gw_plan}</small></div></div>",
    unsafe_allow_html=True)

tabs = st.tabs(["المباشر والتحليل", "xG و FDR", "أفضل تشكيلة", "الكبتنة", "الأخبار", "التبديلات والرقائق"])
need_team = "أدخل Team ID في الشريط الجانبي لتفعيل هذا القسم."

# ---------------------------------------------------------------- 1. live + analysis
with tabs[0]:
    if sq is None:
        st.info(need_team)
    else:
        eh = picks["entry_history"]
        lv = safe_get(f"event/{pick_gw}/live/", live=True)
        if lv:
            pts = {e["id"]: e["stats"]["total_points"] for e in lv["elements"]}
            mn = {e["id"]: e["stats"]["minutes"] for e in lv["elements"]}
            sq["live"] = sq.element.map(pts).fillna(0).astype(int)
            sq["min_gw"] = sq.element.map(mn).fillna(0).astype(int)
        else:
            sq["live"], sq["min_gw"] = 0, 0
        total = int((sq.live * sq.multiplier).sum()) - eh["event_transfers_cost"]
        c = st.columns(4)
        c[0].metric(f"نقاط GW{pick_gw} (مباشر)", total, help="بدون احتساب التبديلات التلقائية")
        c[1].metric("الترتيب العام", f"{entry['summary_overall_rank']:,}")
        c[2].metric("البنك", f"£{eh['bank'] / 10:.1f}m")
        c[3].metric("قيمة الفريق", f"£{eh['value'] / 10:.1f}m")
        view = sq.assign(role=sq.multiplier.map({0: "دكة", 1: "أساسي", 2: "كابتن", 3: "TC"}))
        st.dataframe(
            view[["web_name", "pos", "team_name", "role", "min_gw", "live", "selected_by_percent"]].rename(columns={
                "web_name": "اللاعب", "pos": "المركز", "team_name": "الفريق", "role": "الدور",
                "min_gw": "الدقائق", "live": "النقاط", "selected_by_percent": "EO تقريبي %"}),
            hide_index=True, use_container_width=True)
        st.caption("EO التقريبي = نسبة الملكية العامة. الـ EO الحقيقي (أفضل 10k) غير متاح في الـ API الرسمي.")

        st.subheader("نقاط القوة والضعف")
        starters = sq[sq.multiplier > 0]
        elite = q[q.minutes > 0].nlargest(int(len(q[q.minutes > 0]) * 0.15), "form").form.mean()
        flagged = sq[sq.avail < 1]
        clubs = sq.team_name.value_counts()
        easy = sq.groupby("team_name").fix_fdr.first().sort_values()
        (st.success if starters.form.mean() >= elite * 0.8 else st.warning)(
            f"متوسط فورمة الأساسيين {starters.form.mean():.1f} مقابل {elite:.1f} لأفضل 15% في اللعبة.")
        if len(flagged):
            st.warning("لاعبون بشكوك: " + "، ".join(f"{r.web_name} ({int(r.avail * 100)}%)" for r in flagged.itertuples()))
        else:
            st.success("لا توجد شكوك إصابة في التشكيلة.")
        if clubs.iloc[0] >= 3:
            st.warning(f"تركيز مرتفع على {clubs.index[0]} ({clubs.iloc[0]} لاعبين): خطر تذبذب نقاط الفريق.")
        st.info(f"أسهل جدول للفريق خلال {horizon} جولات: {easy.index[0]}. "
                f"أصعب جدول: {easy.index[-1]} (FDR {easy.iloc[-1]:.1f}).")
        st.caption(f"نقاط الدكة المهدرة في هذه الجولة: {eh['points_on_bench']}")

# ---------------------------------------------------------------- 2. xG hub + FDR
with tabs[1]:
    st.subheader("مركز xG / xA")
    c = st.columns(3)
    pos_f = c[0].multiselect("المركز", list(POS.values()), default=["MID", "FWD"])
    min_f = c[1].slider("الحد الأدنى للدقائق", 0, 3000, 450, 90)
    max_p = c[2].slider("أقصى سعر", 4.0, 15.0, 15.0, 0.1)
    x = q[q.pos.isin(pos_f) & (q.minutes >= min_f) & (q.price <= max_p)].copy()
    x["ga"] = x.goals_scored + x.assists
    x["delta"] = x.ga - x.expected_goal_involvements
    cols = {"web_name": "اللاعب", "team_name": "الفريق", "pos": "المركز", "price": "السعر", "minutes": "الدقائق",
            "expected_goals": "xG", "expected_assists": "xA", "expected_goal_involvements": "xGI",
            "xgi90": "xGI/90", "ga": "G+A", "delta": "الفارق", "threat": "Threat", "ict_index": "ICT"}
    st.dataframe(x.sort_values("expected_goal_involvements", ascending=False)[list(cols)].rename(columns=cols),
                 hide_index=True, use_container_width=True, height=380)
    fig = px.scatter(x, x="expected_goal_involvements", y="ga", color="pos", size="price", hover_name="web_name",
                     labels={"expected_goal_involvements": "xGI", "ga": "G+A"})
    top = max(x.expected_goal_involvements.max(), x.ga.max(), 1) if len(x) else 1
    fig.add_shape(type="line", x0=0, y0=0, x1=top, y1=top, line=dict(dash="dot", color="#b9a6d6"))
    fig.update_layout(height=420, paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)
    st.caption("فوق الخط: يسجّل أكثر من المتوقع (احتمال تراجع). تحته: حظ سيئ وفرصة صعود.")
    st.caption("الـ API الرسمي لا يوفر «الفرص الخطيرة» مباشرة؛ مؤشر Threat هو الأقرب.")

    st.subheader("جدول الصعوبة المحسّن (FDR)")
    st.caption("الصعوبة = 40% تقييم FPL + 30% قوة الخصم + 30% أداء الخصم (xG له وعليه). الصفوف مرتبة من الأسهل.")
    st.plotly_chart(fdr_heatmap(fr, teams, gw_plan), use_container_width=True)

# ---------------------------------------------------------------- 3. best XI
with tabs[2]:
    st.subheader(f"أفضل تشكيلة لـ GW{gw_plan}")
    st.caption("التقييم = 40% EP + 30% الفورمة + 30% xG/xA لكل 90، ثم تعديل بالجدول والجاهزية. الدقة ليست مضمونة.")
    mode = st.radio("المصدر", ["من لاعبي فريقي", "أفضل لاعبي اللعبة (بدون ميزانية)"], horizontal=True)
    if mode.startswith("من"):
        res = pick_xi(sq) if sq is not None else None
        if sq is None:
            st.info(need_team)
    else:
        res = pick_xi(capped_pool(q))
    if res:
        xi, bench, cap, vice, form = res
        st.markdown(f"**الخطة: {form}** · مجموع التقييم {xi.score.sum():.1f}")
        render_pitch(xi, bench, cap, vice)

# ---------------------------------------------------------------- 4. captaincy
with tabs[3]:
    st.subheader("محلل الكبتنة")
    only_mine = st.checkbox("من لاعبي فريقي فقط", value=sq is not None, disabled=sq is None)
    pool = (sq if only_mine and sq is not None else q)
    cands = pool[pool.pos != "GKP"].nlargest(4, "score").copy()
    if len(cands):
        cands["ret"] = (1 - cands.lam.map(lambda l: math.exp(-l))) * 100
        cands["haul"] = (1 - cands.lam.map(lambda l: math.exp(-l) * (1 + l))) * 100
        cands["exp_c"] = cands.score * 2
        cands["risk"] = cands.selected_by_percent.map(
            lambda s: "آمن (Safe)" if s >= 30 else "مفاجأة (Differential)" if s <= 10 else "متوازن")
        st.dataframe(cands[["web_name", "team_name", "exp_c", "ret", "haul", "selected_by_percent", "fix_fdr", "risk"]]
                     .rename(columns={"web_name": "اللاعب", "team_name": "الفريق", "exp_c": "نقاط متوقعة (×2)",
                                      "ret": "احتمال مساهمة %", "haul": "احتمال 2+ مساهمة %",
                                      "selected_by_percent": "الملكية %", "fix_fdr": "FDR", "risk": "التصنيف"})
                     .round(1), hide_index=True, use_container_width=True)
        st.plotly_chart(px.bar(cands, x="web_name", y="exp_c", color="risk",
                               labels={"web_name": "", "exp_c": "نقاط الكابتن المتوقعة"}).update_layout(
            height=320, paper_bgcolor="rgba(0,0,0,0)"), use_container_width=True)
        safe = cands.nlargest(1, "selected_by_percent").iloc[0]
        diff = cands[cands.score >= cands.score.max() * 0.85].nsmallest(1, "selected_by_percent").iloc[0]
        st.success(f"الأكثر أماناً: {safe.web_name} · الأفضل كـ Differential ضمن 85% من القمة: {diff.web_name}")
        st.caption("احتمال المساهمة نموذج بواسون من xGI لكل 90 والدقائق والجدول، وهو تقدير وليس توقعاً مؤكداً.")

# ---------------------------------------------------------------- 5. news
with tabs[4]:
    st.subheader("الإصابات والأخبار الرسمية")
    st.caption("الـ API يوفر حالة اللاعبين وملاحظات FPL فقط. نصوص المؤتمرات الصحفية تقرأها من المصادر وتدوّنها أدناه.")
    c = st.columns(3)
    t_f = c[0].multiselect("الفريق", sorted(teams.short_name))
    mine = c[1].checkbox("لاعبو فريقي فقط", disabled=sq is None)
    own_min = c[2].slider("الملكية الدنيا %", 0.0, 30.0, 1.0)
    n = q[(q.news != "") & (q.selected_by_percent >= own_min)]
    if t_f:
        n = n[n.team_name.isin(t_f)]
    if mine and sq is not None:
        n = n[n.id.isin(sq.id)]
    n = n.assign(status_ar=n.status.map(STATUS))
    st.dataframe(n.sort_values("selected_by_percent", ascending=False)[
        ["web_name", "team_name", "status_ar", "chance_of_playing_next_round", "news", "news_added", "selected_by_percent"]]
        .rename(columns={"web_name": "اللاعب", "team_name": "الفريق", "status_ar": "الحالة",
                         "chance_of_playing_next_round": "فرصة اللعب %", "news": "الخبر",
                         "news_added": "وقت الإضافة", "selected_by_percent": "الملكية %"}),
        hide_index=True, use_container_width=True)
    st.text_area("ملاحظات المؤتمرات الصحفية (تبقى طوال الجلسة)", key="pc_notes", height=140)

# ---------------------------------------------------------------- 6. transfers + chips
with tabs[5]:
    if sq is None:
        st.info(need_team)
    else:
        st.subheader("محاكي التبديلات")
        bank = picks["entry_history"]["bank"] / 10
        ft = st.number_input("التبديلات المجانية المتاحة", 0, 5, 1, help="غير متوفرة في الـ API، أدخلها يدوياً")
        labels = (sq.web_name + " · " + sq.pos + " · £" + sq.price.astype(str)).tolist()
        outs = st.multiselect("بيع", labels)
        ins, spend, gain = [], 0.0, 0.0
        for i, lab in enumerate(outs):
            o = sq.iloc[labels.index(lab)]
            cand = q[(q.pos == o.pos) & ~q.id.isin(sq.id)].nlargest(40, "score")
            opts = (cand.web_name + " · " + cand.team_name + " · £" + cand.price.astype(str)
                    + " · " + cand.score.round(1).astype(str)).tolist()
            pick = st.selectbox(f"بديل {o.web_name}", opts, key=f"in{i}")
            r = cand.iloc[opts.index(pick)]
            ins.append(r)
            spend += r.price - o.price
            gain += r.score - o.score
        if outs:
            hits = 4 * max(0, len(outs) - ft)
            left_bank = bank - spend
            teams_after = sq[~sq.web_name.isin([l.split(" · ")[0] for l in outs])].team.tolist() + [r.team for r in ins]
            c = st.columns(4)
            c[0].metric("البنك بعد التبديل", f"£{left_bank:.1f}m")
            c[1].metric("الخصم", f"-{hits}")
            c[2].metric("مكسب التقييم", f"{gain:+.1f}")
            c[3].metric("الصافي بعد الخصم", f"{gain - hits:+.1f}")
            if left_bank < 0:
                st.error("الميزانية غير كافية.")
            if max(pd.Series(teams_after).value_counts()) > 3:
                st.error("أكثر من 3 لاعبين من نفس النادي.")
            st.caption("سعر البيع يُحتسب بالسعر الحالي؛ قد يختلف سعر البيع الفعلي قليلاً بسبب الأرباح.")

        st.subheader("مخطط الرقائق")
        used = {c_["name"]: c_["event"] for c_ in (hist or {}).get("chips", [])}
        if used:
            st.write("رقائق مستخدمة: " + "، ".join(f"{k} (GW{v})" for k, v in used.items()))
        fb = fr.groupby(["team", "event"]).agg(n=("fdr", "size"), f=("fdr", "mean"))
        rows = []
        for g in range(gw_plan, min(gw_plan + 8, 39)):
            xp, play, dgw = [], 0, 0
            for r in sq.itertuples():
                n_, f_ = fb.loc[(r.team, g)] if (r.team, g) in fb.index else (0, 3)
                xp.append(r.base * (1 + (3 - f_) * 0.08) * n_)
                play += n_ > 0
                dgw += n_ > 1
            rows.append({"GW": g, "لاعبون بمباراة (من 15)": int(play), "DGW": int(dgw),
                         "Bench Boost (مكسب الدكة)": round(sum(sorted(xp)[:4]), 1),
                         "Triple Captain (المكسب)": round(max(xp), 1), "xP للفريق": round(sum(xp), 1)})
        plan = pd.DataFrame(rows)
        st.dataframe(plan, hide_index=True, use_container_width=True)
        bb, tc, wc = (plan.loc[plan["Bench Boost (مكسب الدكة)"].idxmax()], plan.loc[plan["Triple Captain (المكسب)"].idxmax()],
                      plan.loc[plan["لاعبون بمباراة (من 15)"].idxmin()])
        st.success(f"أفضل Bench Boost: GW{int(bb.GW)} · أفضل Triple Captain: GW{int(tc.GW)} · "
                   f"Free Hit / Wildcard: GW{int(wc.GW)} (أقل عدد لاعبين بمباراة)")
        ready = int(plan.iloc[0]["لاعبون بمباراة (من 15)"])
        fit = int(((sq.avail >= 0.75) & (sq.n_fix > 0)).sum())
        st.metric(f"جاهزية Bench Boost في GW{gw_plan}", f"{fit}/15",
                  help=f"{ready} لاعباً لديهم مباراة، منهم {fit} بلا شكوك كبيرة")
        st.caption("المخطط تقديري ويعتمد على جدول المباريات المعلن؛ راجعه عند تغيّر المواعيد أو الإصابات.")
