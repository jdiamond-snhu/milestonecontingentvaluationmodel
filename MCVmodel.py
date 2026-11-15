import streamlit as st
import yfinance as yf

# Page configuration
st.set_page_config(
    page_title="Pre-Revenue Milestone Valuation Calculator",
    layout="wide"
)

st.title("Pre-Revenue Milestone Valuation Model")
st.markdown("Real-options and narrative-adjusted fair value calculator for non-operational companies.")

# --- SIDEBAR INPUTS ---
st.sidebar.header("Model Inputs")

# 1. Stock Ticker Symbol (Blank by default)
ticker_symbol = st.sidebar.text_input(
    "Stock Ticker Symbol",
    value="",
    placeholder="e.g., SPCE, RKLB, CRSP",
    help="Enter any publicly traded stock symbol to auto-fetch its latest price and balance sheet data."
).upper().strip()

# Initialize defaults before a ticker is entered
fetched_price = 0.00
fetched_nav = 0.00
fetched_shares = 100.00  # in millions

if ticker_symbol:
    try:
        stock = yf.Ticker(ticker_symbol)
        hist = stock.history(period="5d")
        if not hist.empty:
            fetched_price = round(float(hist["Close"].iloc[-1]), 2)
        
        # Attempt to pull book value & shares for NAV_0 default
        info = stock.info
        book_val = info.get("bookValue")
        shares_out = info.get("sharesOutstanding")
        if book_val and book_val > 0:
            fetched_nav = round(float(book_val), 2)
        if shares_out and shares_out > 0:
            fetched_shares = round(float(shares_out) / 1e6, 2)
    except Exception:
        st.sidebar.caption("⚠️ Could not fetch live data for that ticker; enter values manually below.")

# 2. Last Price of the Stock (Auto-populated once ticker is entered)
last_price = st.sidebar.number_input(
    "Last Stock Price ($)",
    min_value=0.00,
    value=fetched_price,
    step=0.01,
    format="%.2f",
    help="Auto-populates with the stock's most recent closing price. You can manually override this to test 'what-if' entry prices."
)

# 3. % Value for Chance of Milestone Being Achieved
p_success_pct = st.sidebar.slider(
    "Chance of Milestone Achieved (%)",
    min_value=0,
    max_value=100,
    value=50,
    step=1,
    help="Your estimated probability (0% to 100%) that the company successfully completes its next key milestone on schedule."
)
p_success = p_success_pct / 100.0

# 4. Assumed Price Target if Milestone is Achieved (Narrative Option Value)
narrative_target = st.sidebar.number_input(
    "Assumed Price Target if Achieved ($)",
    min_value=0.00,
    value=0.00,
    step=0.50,
    format="%.2f",
    help="The share price you expect the market to reward the stock with immediately upon hitting the milestone (captures the hype/narrative re-rating)."
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
        step=10.0,
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
        min_value=0.0,
        value=18.0,
        step=1.0,
        format="%.1f",
        help="""Your required annual return (%) to compensate for taking on speculative risk while waiting for the milestone. Typical % values are as follows:
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
