"""International Cost of Capital App: cost of equity, cost of debt and WACC in USD and a foreign currency."""
import io
import re
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="International Cost of Capital", layout="wide")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
URLS = {
    "beta": "https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls",
    "spread": "https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html",
    "tax": "https://www.oecd.org/en/publications/corporate-tax-statistics-2024_9c27d6e8-en/full-report/statutory-corporate-income-tax-rates_440f9286.html",
    "bond": "https://tradingeconomics.com/bonds",
}
DEFAULT_INDUSTRY = "Software (System & Application)"
ALIAS = {"Korea": "South Korea", "Türkiye": "Turkey", "Slovak Republic": "Slovakia", "Czech Republic": "Czechia"}

# Placeholders used ONLY if a live fetch fails (clearly flagged in the app).
FB_TAX = {"United States": 0.258, "Germany": 0.299, "United Kingdom": 0.25, "Japan": 0.297,
          "Canada": 0.262, "Australia": 0.30, "France": 0.258}
FB_YLD = {"United States": 0.041, "Germany": 0.027, "United Kingdom": 0.044, "Japan": 0.017,
          "Canada": 0.032, "Australia": 0.042, "France": 0.035}
FB_BETA = pd.DataFrame({"Industry Name": [DEFAULT_INDUSTRY, "Retail (General)", "Utility (General)"],
                        "Number of firms": [0, 0, 0], "Unlevered beta": [1.20, 0.90, 0.35]})


# ----------------------------------------------------------------------------- data fetching
def _get(url):
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    return r


def _month_year(text):
    m = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}", text)
    return m.group(0) if m else "date not stated on source"


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_betas():
    raw = pd.read_excel(io.BytesIO(_get(URLS["beta"]).content), sheet_name="Industry Averages", header=None)
    hdr = raw.index[raw[0].astype(str).str.strip() == "Industry Name"][0]
    df = raw.iloc[hdr + 1:].copy()
    df.columns = [str(c).strip() for c in raw.iloc[hdr]]
    df = df[["Industry Name", "Number of firms", "Unlevered beta"]].dropna(subset=["Industry Name"])
    df["Industry Name"] = df["Industry Name"].astype(str).str.strip()
    df["Unlevered beta"] = pd.to_numeric(df["Unlevered beta"], errors="coerce")
    df = df.dropna(subset=["Unlevered beta"])
    df = df[~df["Industry Name"].str.contains("Total Market", case=False)].reset_index(drop=True)
    head = " ".join(raw.iloc[:hdr].astype(str).values.ravel())
    return df, _month_year(head)


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_spread():
    html = _get(URLS["spread"]).text
    for t in pd.read_html(io.StringIO(html)):
        for _, row in t.iterrows():
            cells = [str(c) for c in row]
            if any("Baa2/BBB" in c for c in cells):
                pct = [c for c in cells if "%" in c]
                if pct:
                    return float(re.sub(r"[^0-9.]", "", pct[-1])) / 100, _month_year(html)
    raise ValueError("Baa2/BBB row not found")


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_tax():
    html = _get(URLS["tax"]).text
    best = None
    for t in pd.read_html(io.StringIO(html)):
        t.columns = [" ".join(map(str, c)) if isinstance(c, tuple) else str(c) for c in t.columns]
        if len(t) > 30 and t.iloc[:, 0].astype(str).str.contains("United States").any():
            best = t
            break
    if best is None:
        raise ValueError("OECD tax table not found")
    year_cols = [c for c in best.columns if re.fullmatch(r"\d{4}", c.strip())]
    col = max(year_cols, key=int) if year_cols else best.columns[-1]
    out = {}
    for name, v in zip(best.iloc[:, 0].astype(str).str.strip(), pd.to_numeric(best[col], errors="coerce")):
        if pd.notna(v):
            out[ALIAS.get(name, name)] = float(v) / 100
    return out, f"OECD table, {col} rates"


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_yields():
    html = _get(URLS["bond"]).text
    out = {}
    for t in pd.read_html(io.StringIO(html)):
        if t.shape[1] < 2:
            continue
        for name, y in zip(t.iloc[:, 0].astype(str).str.strip(), pd.to_numeric(t.iloc[:, 1], errors="coerce")):
            if pd.notna(y) and name not in out:
                out[name] = float(y) / 100
    if "United States" not in out:
        raise ValueError("US yield not found")
    return out, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC (time of fetch)")


def safe(fn, fallback, label):
    try:
        return fn(), True
    except Exception as e:  # noqa: BLE001
        st.sidebar.warning(f"{label}: live fetch failed ({type(e).__name__}); using placeholder. Use manual overrides.")
        return fallback, False


# ----------------------------------------------------------------------------- finance
def cost_of_capital(beta_u, tax, debt_w, erp, rf, spread):
    """Relever beta (Hamada), CAPM equity cost, debt cost, after-tax WACC. All rates as decimals."""
    de = debt_w / (1 - debt_w)
    beta_l = beta_u * (1 + (1 - tax) * de)
    ke = rf + beta_l * erp
    kd = rf + spread
    kd_at = kd * (1 - tax)
    wacc = (1 - debt_w) * ke + debt_w * kd_at
    return dict(rf=rf, beta_u=beta_u, beta_l=beta_l, ke=ke, spread=spread, kd=kd, kd_at=kd_at, wacc=wacc)


def foreign_auto_spread(usd_spread):
    """Auto foreign BBB spread = USD BBB spread (same credit risk premium over the local government yield)."""
    return usd_spread


# ----------------------------------------------------------------------------- load data
st.title("International Cost of Capital: USD vs. Foreign Currency")
st.sidebar.header("Data")
if st.sidebar.button("🔄 Refresh data"):
    st.cache_data.clear()
    st.rerun()

(betas, beta_date), ok_b = safe(fetch_betas, (FB_BETA, "placeholder"), "Betas")
(spr_auto, spr_date), ok_s = safe(fetch_spread, (0.016, "placeholder"), "BBB spread")
(tax_map, tax_date), ok_t = safe(fetch_tax, (FB_TAX, "placeholder"), "Tax rates")
(yld_map, yld_date), ok_y = safe(fetch_yields, (FB_YLD, "placeholder"), "Bond yields")

countries = sorted(set(tax_map) & set(yld_map)) or sorted(FB_TAX)
if "United States" not in countries:
    countries.insert(0, "United States")

# ----------------------------------------------------------------------------- inputs
st.sidebar.header("Assumptions")
industries = betas["Industry Name"].tolist()
industry = st.sidebar.selectbox("Industry", industries,
                                index=industries.index(DEFAULT_INDUSTRY) if DEFAULT_INDUSTRY in industries else 0)
country = st.sidebar.selectbox("Target country", countries, index=countries.index("United States"))
erp = st.sidebar.number_input("Equity risk premium (%)", 0.0, 20.0, 6.5, 0.1) / 100
debt_w = st.sidebar.slider("Target debt share (D/V, %)", 0, 95, 30) / 100
tax_choice = st.sidebar.radio("Project tax rate", ["United States", "Selected country"], horizontal=True)

st.sidebar.header("Manual overrides")


def pick(label, auto, key, decimals=2, pct=True):
    """Returns auto value, or manual input if the override switch is on."""
    on = st.sidebar.checkbox(f"Override {label}", key=f"on_{key}")
    scale = 100 if pct else 1
    if on:
        return st.sidebar.number_input(label, value=float(auto or 0) * scale, step=0.05, format=f"%.{decimals}f",
                                       key=f"v_{key}") / scale
    st.sidebar.caption(f"{label}: {auto * scale:.{decimals}f}{'%' if pct else ''} (fetched)")
    return auto


beta_auto = float(betas.loc[betas["Industry Name"] == industry, "Unlevered beta"].iloc[0])
beta_u = pick("Unlevered beta", beta_auto, "beta", 3, pct=False)
spread_usd = pick("USD BBB spread (%)", spr_auto, "spr")
rf_us = pick("US 10Y yield (%)", yld_map.get("United States", FB_YLD["United States"]), "rfus")
rf_f = pick(f"{country} 10Y yield (%)", yld_map.get(country, rf_us), "rff")
tax_us = pick("US tax rate (%)", tax_map.get("United States", FB_TAX["United States"]), "taxus")
tax_f = pick(f"{country} tax rate (%)", tax_map.get(country, tax_us), "taxf")
spr_f_auto = foreign_auto_spread(spread_usd)
spr_f_on = st.sidebar.checkbox("Override foreign-currency BBB spread", key="on_sprf")
if spr_f_on:
    spread_f = st.sidebar.number_input("Foreign BBB spread (%)", value=spr_f_auto * 100, step=0.05, key="v_sprf") / 100
else:
    spread_f = spr_f_auto
    st.sidebar.caption(f"Foreign BBB spread (auto): {spread_f * 100:.2f}%")

tax = tax_us if tax_choice == "United States" else tax_f

# ----------------------------------------------------------------------------- results
usd = cost_of_capital(beta_u, tax, debt_w, erp, rf_us, spread_usd)
loc = cost_of_capital(beta_u, tax, debt_w, erp, rf_f, spread_f)

st.subheader(f"{industry} | {country} | project tax rate {tax:.2%} ({tax_choice})")
c1, c2 = st.columns(2)
for col, title, r in [(c1, "USD", usd), (c2, f"Local currency ({country})", loc)]:
    with col:
        st.markdown(f"### {title}")
        m1, m2, m3 = st.columns(3)
        m1.metric("Cost of equity", f"{r['ke']:.2%}")
        m2.metric("Cost of debt (pre-tax)", f"{r['kd']:.2%}")
        m3.metric("WACC", f"{r['wacc']:.2%}")

rows = [("Risk-free rate (10Y gov. yield)", "rf"), ("Unlevered beta", "beta_u"), ("Relevered beta", "beta_l"),
        ("Cost of equity", "ke"), ("BBB spread", "spread"), ("Pre-tax cost of debt", "kd"),
        ("After-tax cost of debt", "kd_at"), ("WACC", "wacc")]
tbl = pd.DataFrame({"Item": [r[0] for r in rows],
                    "USD": [usd[r[1]] for r in rows], f"Local ({country})": [loc[r[1]] for r in rows]})
fmt = tbl.copy()
for i, (_, k) in enumerate(rows):
    f = (lambda v: f"{v:.3f}") if "beta" in k else (lambda v: f"{v:.2%}")
    fmt.loc[i, "USD"], fmt.loc[i, f"Local ({country})"] = f(usd[k]), f(loc[k])
st.dataframe(fmt, hide_index=True, use_container_width=True)

# ----------------------------------------------------------------------------- assumptions & sources
with st.expander("Main assumptions and formulas", expanded=True):
    st.markdown(f"""
- **Relevered beta** = βU × [1 + (1 − t) × D/E], where D/E = D/V ÷ (1 − D/V).
- **Cost of equity** = risk-free rate + relevered beta × ERP (same beta and ERP in both currencies; only the risk-free rate differs).
- **Cost of debt** = risk-free rate + BBB spread. The foreign spread defaults to the USD BBB spread unless overridden.
- **WACC** = E/V × Ke + D/V × Kd × (1 − t).
- The **same project tax rate** ({tax_choice}), debt share ({debt_w:.0%}) and ERP ({erp:.2%}) are used in both currencies.
- Foreign-currency rates differ from USD only through the government-yield difference (and the foreign spread override).
""")

with st.expander("Data sources and dates"):
    flag = lambda ok: "live" if ok else "PLACEHOLDER (fetch failed)"  # noqa: E731
    st.table(pd.DataFrame([
        ["Unlevered beta (industry)", "Damodaran betas.xls", URLS["beta"], beta_date, flag(ok_b)],
        ["BBB spread (Baa2/BBB)", "Damodaran ratings", URLS["spread"], spr_date, flag(ok_s)],
        ["Corporate tax rates", "OECD", URLS["tax"], tax_date, flag(ok_t)],
        ["10Y government yields", "Trading Economics", URLS["bond"], yld_date, flag(ok_y)],
    ], columns=["Item", "Source", "URL", "As of", "Status"]))

# ----------------------------------------------------------------------------- all industries
st.subheader("All-industry comparison")
allrows = []
for _, r in betas.iterrows():
    u = cost_of_capital(r["Unlevered beta"], tax, debt_w, erp, rf_us, spread_usd)
    f = cost_of_capital(r["Unlevered beta"], tax, debt_w, erp, rf_f, spread_f)
    allrows.append({"Industry": r["Industry Name"], "Unlevered beta": r["Unlevered beta"],
                    "Relevered beta": u["beta_l"], "Ke USD": u["ke"], "WACC USD": u["wacc"],
                    f"Ke {country}": f["ke"], f"WACC {country}": f["wacc"]})
all_df = pd.DataFrame(allrows)
pcts = [c for c in all_df.columns if c.startswith(("Ke", "WACC"))]
st.dataframe(all_df.style.format({**{c: "{:.2%}" for c in pcts}, "Unlevered beta": "{:.3f}",
                                  "Relevered beta": "{:.3f}"}), hide_index=True, use_container_width=True)

d1, d2 = st.columns(2)
d1.download_button("⬇ Download selected-industry results (CSV)", tbl.to_csv(index=False), "results.csv", "text/csv")
d2.download_button("⬇ Download all-industry results (CSV)", all_df.to_csv(index=False), "all_industries.csv", "text/csv")

# ----------------------------------------------------------------------------- self-checks
with st.expander("Built-in verification checks"):
    a = cost_of_capital(beta_u, tax, debt_w, erp, rf_us, spread_usd)
    b = cost_of_capital(beta_u, tax, debt_w, erp, rf_us, foreign_auto_spread(spread_usd))
    z = cost_of_capital(beta_u, tax, 0.0, erp, rf_us, spread_usd)
    o = cost_of_capital(beta_u, tax, debt_w, erp, rf_us, spread_usd)  # USD unaffected by foreign spread
    checks = {
        "Equal yields (foreign spread override off) -> equal Ke, Kd, WACC":
            all(abs(a[k] - b[k]) < 1e-12 for k in ("ke", "kd", "wacc")),
        "Zero debt -> WACC equals cost of equity": abs(z["wacc"] - z["ke"]) < 1e-12,
        "Foreign spread override leaves USD results unchanged": all(abs(usd[k] - o[k]) < 1e-12 for k in usd),
    }
    for k, v in checks.items():
        st.write(("✅ " if v else "❌ ") + k)
