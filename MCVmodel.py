import streamlit as st
import requests

# Pull Tiingo API token securely from Streamlit Secrets
API_KEY = st.secrets["TIINGO_API_KEY"]

@st.cache_data(ttl=300)
def fetch_tiingo_quote(symbol: str):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Token {API_KEY}"
    }
    clean_sym = symbol.lower().strip()
    base = "https://" + "api." + "tiingo.com"

    # 1. Live / Intraday IEX Endpoint
    iex_url = f"{base}/iex/{clean_sym}"
    iex_resp = requests.get(iex_url, headers=headers, timeout=10)
    if iex_resp.status_code == 200:
        iex_data = iex_resp.json()
        if isinstance(iex_data, list) and len(iex_data) > 0:
            quote = next(iter(iex_data))
            price = (
                quote.get("tngoLast")
                or quote.get("last")
                or quote.get("prevClose")
                or quote.get("open")
            )
            if price is not None and float(price) > 0:
                return float(price)

    # 2. Fallback to End-of-Day endpoint (also works for any ticker)
    eod_url = f"https://api.tiingo.com/iex/{symbol.lower()}/prices"
    eod_resp = requests.get(eod_url, headers=headers, timeout=10)
    if eod_resp.status_code == 200:
        eod_data = eod_resp.json()
        if isinstance(eod_data, list) and len(eod_data) > 0:
            return float(eod_data[-1]["close"])

    return None

# 1. Stock Ticker Symbol (Blank by default)
ticker_symbol = st.sidebar.text_input(
    "Stock Ticker Symbol",
    value="",
    placeholder="e.g., F, RKLB, CRSP",
).upper().strip()

# Initialize defaults before a ticker is entered
fetched_price = 0.00
fetched_nav = 0.00
fetched_shares = 100.00  # in millions

if ticker_symbol:
    try:
        # Tiingo uses hyphens for share classes (e.g., BRK-B instead of BRK.B)
        clean_symbol = ticker_symbol.replace(".", "-")
        live_price = fetch_tiingo_quote(clean_symbol)
        
        if live_price and live_price > 0:
            fetched_price = round(live_price, 2)
        else:
            st.sidebar.caption("⚠️ Could not fetch live price for that ticker; enter values manually below.")
    except Exception as e:
        st.sidebar.caption(f"⚠️ Error fetching data: {e}")

# 2. Last Price of the Stock (Auto-populated once ticker is entered)
last_price = st.sidebar.number_input(
    "Last Price of the Stock ($)",
    min_value=0.00,
    value=fetched_price,
    step=0.01,
    format="%.2f",
    key=f"price_{ticker_symbol}"
)

# 3. % Value for Chance of Milestone Being Achieved
p_success_pct = st.sidebar.slider(
    "% Chance Milestone is Achieved",
    min_value=0,
    max_value=100,
    value=50,
    step=1,
    help="Your estimate (0% to 100%) that the company will achieve its next key milestone on schedule."
)
p_success = p_success_pct / 100.0

# 4. Your Assumed Price Target if the Milestone is Achieved (Narrative Option Value)
assumed_target = st.sidebar.number_input(
    "Assumed Price Target ($)",
    min_value=0.00,
    value=None,
    step=0.01,
    format="%.2f",
    placeholder="Enter target price...",
    key=f"target_{ticker_symbol}"
)

# Supporting Model Parameters with '?' hover tooltips
with st.sidebar.expander("Baseline & Dilution Parameters", expanded=False):
    nav_0 = st.number_input(
        "Tangible NAV₀ per Share ($)",
        min_value=0.00,
        value=fetched_nav,
        step=0.05,
        format="%.2f",
        help="""Net Asset Value per share right now (book value minus intangible goodwill).

- Serves as the liquidation floor if the business stalls
- Auto-fills from reported book value per share when available"""
    )
    existing_shares = st.number_input(
        "Existing Shares (Millions)",
        min_value=0.1,
        value=fetched_shares,
        step=1.0,
        format="%.2f",
        help="Total current share count in millions before any new stock is issued."
    )
    atm_raise = st.number_input(
        "Planned Capital Raise / Burn ($M)",
        min_value=0.0,
        value=0.0,
        step=1.0,
        format="%.1f",
        help="""Total cash (in millions) the company needs to raise via new shares to fund its cash burn if the milestone is delayed.

- Set to **0.0** if the company already has enough cash to reach the milestone without issuing stock"""
    )
    atm_avg_price = st.number_input(
        "Assumed Raise Share Price ($)",
        min_value=0.01,
        value=max(0.01, last_price),
        step=0.05,
        format="%.2f",
        help="""The average stock price at which management sells new shares to raise cash.

- **Lower price:** More shares printed and heavier dilution
- **Higher price:** Fewer shares printed if sold into a rally"""
    )
    hurdle_rate_pct = st.number_input(
        "Cost of Equity Hurdle Rate r (%)",
        min_value=5.0,
        value=5.0,
        step=1.0,
        format="%.1f",
        help="""Your required annual return (%) to compensate for taking on speculative risk while waiting for the milestone. The default rate is 5% because it should at least cover average inflation. Typical % values are as follows:
- **10% – 12%:** Established, stable businesses that have a new milestone or new product they are working on.
- **15% – 20%:** Speculative pre-revenue companies such as emerging tech, aviation/aerospace, biotechs, etc.)
- **25%+:** Ultra-high-risk startups always near cash exhaustion."""
    )
    years_t = st.number_input(
        "Time to Milestone (Years, t)",
        min_value=0.25,
        value=1.0,
        step=0.25,
        format="%.2f",
        help="""How many years from today until the milestone is expected to be completed.

- **0.50** = 6 months
- **1.00** = 1 year
- **2.00** = 2 years"""
    )

# --- MAIN DISPLAY AREA ---
st.subheader("1. Abstract Formula")
st.latex(
    r"\text{Fair Value}_0 = \text{NAV}_0 + \frac{\left(P_{\text{success}, t} \times \text{Narrative Option Value}_t\right) - \left((1 - P_{\text{success}, t}) \times \text{Dilution Cost}_t\right)}{(1 + r)^t}"
)

st.divider()

if not ticker_symbol and last_price == 0.0:
    st.info("👈 Enter a **Stock Ticker Symbol** in the sidebar to load live market data and calculate the live formula.")
else:
    # --- CORE CALCULATIONS ---
    hurdle_rate = hurdle_rate_pct / 100.0

    # Dilution Cost_t calculation
    if atm_raise > 0 and atm_avg_price > 0:
        new_shares = atm_raise / atm_avg_price
        ownership_lost = new_shares / (existing_shares + new_shares)
        dilution_cost = last_price * ownership_lost
    else:
        new_shares = 0.0
        ownership_lost = 0.0
        dilution_cost = 0.0

    # Fair Value_0 calculation
    expected_upside = p_success * narrative_target
    expected_dilution = (1.0 - p_success) * dilution_cost
    net_milestone_val = expected_upside - expected_dilution
    discounted_val = net_milestone_val / ((1.0 + hurdle_rate) ** years_t)
    fair_value = max(0.0, nav_0 + discounted_val)

    display_label = ticker_symbol if ticker_symbol else "Custom Stock"
    st.subheader(f"2. Live Formula Calculation for {display_label}")
    st.latex(
        rf"\text{{Fair Value}}_0 = \${nav_0:.2f} + \frac{{\left({p_success:.2f} \times \${narrative_target:.2f}\right) - \left((1 - {p_success:.2f}) \times \${dilution_cost:.2f}\right)}}{{(1 + {hurdle_rate:.2f})^{{{years_t:g}}}}} = \mathbf{{\${fair_value:.2f}}}"
    )

    st.divider()

    # Summary Metrics Row
    col1, col2, col3, col4 = st.columns(4)
    upside_diff = ((fair_value - last_price) / last_price) * 100 if last_price > 0 else 0

    col1.metric("Calculated Fair Value", f"${fair_value:.2f}", f"{upside_diff:+.1f}% vs. Last Price")
    col2.metric("Tangible Floor (NAV₀)", f"${nav_0:.2f}")
    col3.metric("Expected Upside", f"${expected_upside:.2f}", f"{p_success_pct}% × ${narrative_target:.2f}")
    col4.metric("Dilution Cost (If Stalled)", f"-${dilution_cost:.2f}", f"{ownership_lost*100:.1f}% ownership cut")
