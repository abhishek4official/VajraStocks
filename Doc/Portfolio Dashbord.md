# **System Requirements Specification (SRS)**

## **Production Blueprint: Pure Equity Dual-Timeframe Risk Engine**

This document defines the comprehensive functional specifications, mathematical models, and architectural routing logic for an automated risk-management and capital-allocation system. The engine processes a pure **Equity (Cash/Spot)** universe across two distinct runtime profiles: **Daily (Moderate Risk)** and **Weekly (Low Risk / Conservative)**.  
The core risk parameters and execution pipelines detailed below are systematically adapted from the foundational architecture outlined in *Portfolio Risk & Allocation Modules.pdf*.

## **1\. System Scope & Core Constraints**

To ensure capital preservation and eliminate operational hazards, the engine must operate strictly under the following system constraints:

* **Asset Class Restriction:** 100% long-only cash equity. No derivatives (Futures & Options), margin trading, leverage, or short-selling are permitted.  
* **Corporate Action Adjustments:** All incoming price feeds must be fully adjusted for historical splits, reverse splits, bonuses, and dividends to prevent data anomalies or false technical indicators.  
* **Liquidity Safeguard:** Assets are subjected to an automated **Liquidity Gate** prior to technical scanning. Any stock with a 20-day Average Daily Trading Volume (ADTV) below ₹5 Crores is automatically blacklisted to minimize slippage and impact costs.

## **2\. Master System Configuration Matrix**

The execution core manages two distinct, parallel operational tracks with the following structural parameters:

| Engine Component | Daily Track (Moderate Risk) | Weekly Track (Low Risk / Conservative) |
| :---- | :---- | :---- |
| **Execution Cadence** | Daily post-market close. | Weekly (Friday evening closing bar processing). |
| **Market Benchmark** | NIFTY 50 Index (^NSEI). | NIFTY 50 Index (^NSEI). |
| **Regime Filter** | NIFTY 200-day EMA. | NIFTY 40-week EMA. |
| **Whipsaw Protection** | 1-bar closing confirmation. | 2-bar consecutive closing confirmation (with rising EMA slope). |
| **Bear Market Rule** | Reduce new position sizes by 50%. | **Halt all new buying entirely**; manage trailing exits. |
| **Volatility Anchor** | Daily $ATR(14)$. | Weekly $ATR(14)$. |
| **Correlation Lookback** | 60 Trading Days. | 12 Weeks (Rolling). |
| **Clustering Threshold** | Pearson $r \\ge 0.80$. | Pearson $r \\ge 0.70$ *(Heightened risk detection)*. |
| **Max Cluster Weight** | 25% of Portfolio Equity. | 15% of Portfolio Equity. |
| **Max Bull Heat Limit** | 8% Maximum. | 4% to 5% Maximum. |
| **Max Bear Heat Limit** | 4% Maximum. | 0% *(Strict Capital Lockdown)*. |
| **Primary Trigger** | Daily Close \> 20-day High. | Weekly Close \> 10-week High. |
| **Macro Confirmation** | Weekly Trend Confirmation \= TRUE. | Monthly Trend Confirmation \= TRUE. |
| **Min Breadth Trigger** | \> 35% of stocks above Daily 200 EMA. | \> 45% to 50% of stocks above Weekly 40 EMA. |

## **3\. Core Engine Modules & Mathematical Models**

### **Module F: Market Regime Filter**

**Purpose:** Determine macro environment viability for capital deployment.

* **Daily Regime Evaluation:**  
  * *Bull Market Condition:* A bull market exists when the NIFTY Close \> NIFTY 200-day EMA. Actions allow full position sizing, new breakout entries, and maximum portfolio heat limits.  
  * *Bear Market Condition:* A bear market exists when the NIFTY Close \< NIFTY 200-day EMA. Actions mandate a 50% reduction in new position sizes, increased cash allocation, reduced maximum portfolio heat, and tightened risk controls.  
* **Weekly Regime Evaluation (Hysteresis-Protected):**  
  * *Bull Market Condition:* NIFTY Weekly Close satisfies NIFTY \> NIFTY 40-week EMA for 2 consecutive weekly bars, with the EMA slope $\> 0$.  
  * *Bear Market Condition:* NIFTY Weekly Close satisfies NIFTY \< NIFTY 40-week EMA for 2 consecutive weekly bars.

### **Module G: ATR Volatility Scaling Engine**

**Purpose:** Equalize risk across positions by normalizing sizes based on individual stock volatility. Stocks with higher volatility receive smaller allocations, while stocks with lower volatility receive larger allocations.

$$ATR\_{pct} \= \\frac{ATR(14)}{\\text{Current Close}} \\times 100$$

$$\\text{Adjusted Risk Budget} \= \\text{Base Risk Budget} \\times \\text{Volatility Risk Multiplier}$$

* **Daily Volatility Classification & Multipliers:**  
  * Low Volatility ($ATR\_{pct} \< 2\\%$): Classification \= Low, Multiplier \= 1.20.  
  * Medium Volatility ($2\\% \\le ATR\_{pct} \\le 5\\%$): Classification \= Medium, Multiplier \= 1.00.  
  * High Volatility ($ATR\_{pct} \> 5\\%$): Classification \= High, Multiplier \= 0.75.  
* **Weekly Volatility Classification & Multipliers (Conservative):**  
  * Low Volatility ($ATR\_{pct} \< 3\\%$): Classification \= Low, Multiplier \= 1.00 *(Leverage capped for safety)*.  
  * Medium Volatility ($3\\% \\le ATR\_{pct} \\le 6\\%$): Classification \= Medium, Multiplier \= 0.75.  
  * High Volatility ($ATR\_{pct} \> 6\\%$): Classification \= High, Multiplier \= 0.50 *(Or automatically discarded)*.

### **Module H: Correlation Risk Engine**

**Purpose:** Prevent hidden sector/cluster concentration risk where assets move together.

1. Calculate a rolling Pearson correlation coefficient ($r$) matrix using price log-returns over the designated lookback period (60 Trading Days for Daily  / 12 Weeks for Weekly).  
2. If $r \\ge \\text{Threshold}$ (0.80 Daily / 0.70 Weekly), bind the assets into an isolated **Risk Cluster**.  
3. Validate total exposure:

$$\\sum (\\text{Weights of Assets in Cluster } X) \\le \\text{Max Cluster Weight Limit}$$

* **System Action:** If a prospective allocation causes a cluster to exceed its limit (25% for Daily / 15% for Weekly), the system must **Reject Additional Allocation**.

### **Module I: Portfolio Heat Engine**

**Purpose:** Enforce a global circuit breaker on total potential portfolio risk by measuring total potential loss if all active stops are triggered.

$$\\text{Position Risk} \= \\text{Shares} \\times (\\text{Entry Price} \- \\text{Stop Price})$$

$$\\text{Portfolio Heat \\%} \= \\frac{\\sum (\\text{Position Risk})}{\\text{Portfolio Equity}} \\times 100$$

* **System Constraint:** When portfolio heat breaches the designated regime limit, the engine must not open new positions while existing positions remain unchanged. Allocation resumes only when heat falls back below limits.

| Market Regime | Maximum Heat (Daily Track) | Maximum Heat (Weekly Track) |
| :---- | :---- | :---- |
| **Bull Market** | 8% Maximum. | 4% to 5% Maximum. |
| **Neutral Market** | 6% Maximum. | 2% to 3% Maximum. |
| **Bear Market** | 4% Maximum. | 0% *(Strict Capital Lockdown)*. |

### **Module J: Multi-Timeframe Confirmation Engine**

**Purpose:** Eliminate false breakout signals and improve signal quality. A lower timeframe breakout must be confirmed by the higher timeframe structural trend.

* **Daily Execution Prerequisites:**  
  1. Daily Close \> 20-day High.  
  2. Daily Volume \> $1.5 \\times \\text{20-day Volume SMA}$ *(Quantified volume expansion threshold)*.  
  3. Daily Close \> 200 EMA.  
  4. *Macro Confirmation:* Weekly Close \> Weekly 20 EMA **AND** Weekly Rate of Change $\\text{ROC}(10) \> 0$.  
* **Weekly Execution Prerequisites:**  
  1. Weekly Close \> 10-week High.  
  2. Weekly Volume \> $1.5 \\times \\text{10-week Volume SMA}$.  
  3. Weekly Close \> 40 EMA.  
  4. *Macro Confirmation:* Monthly Close \> Monthly 10 EMA **AND** Monthly Rate of Change $\\text{ROC}(10) \> 0$.

### **Module K: Market Breadth Engine**

**Purpose:** Quantify the internal structural health of the broad market before exposing capital.

* **System Metrics:** Track the percentage of stocks above their 50 EMA, percentage of stocks above their 200 EMA, Advance/Decline Ratio, and New Highs vs. New Lows.  
* **System Constraint:** If the percentage of stocks trading above their long-term moving average (200-day EMA for Daily / 40-week EMA for Weekly) drops below the minimum threshold (35% Daily / 45% Weekly), the system must disable aggressive buying, reduce new position sizes, and increase cash allocation.

### **Module L: Dynamic Stock Replacement & Rotation Engine**

**Purpose:** Programmatically recycle capital out of stopped or underperforming assets into high-momentum candidates without breaking global risk boundaries.

* **Replacement Triggers:**  
  * *Hard Exit:* Position hits its trailing stop-loss monitored by Module A. Capital is released completely.  
  * *Soft Exit:* Asset remains active but its Relative Strength (RS) ranking decays below a specified cut-off. Position is systematically wound down.  
* **Replacement Selection:** The engine queries the high-ranking breakout pool confirmed by Module J. The top available candidate on the Relative Strength Matrix (Module C) is selected, provided it clears all Module H (Correlation) and Module G (Volatility) scaling filters.  
* **Operational Execution Profiles:**  
  * *Daily Track:* Calculated daily post-market close. Replacements execute on the next trading session open. Positions are rotated out if they fall out of the Top 25% of the RS universe.  
  * *Weekly Track:* Calculated during weekend batching. Replacements execute solely on Monday morning opens. Rotations trigger if an asset falls out of the Top 15% of the RS universe. Turnovers are capped at a maximum of 2 replacements per week to prevent over-trading.

## **4\. Ingestion & Sequential Execution Flow**

The system must parse data chronologically down a strict waterfall, ensuring risk filters are parsed before capital is allocated:

\[Step 01\] Ingest Raw Pricing Data & Corporate-Action Adjusted Feeds.  
    │  
\[Step 02\] Execute Liquidity Gate Filter (Filter ADTV \< ₹5 Crores)  
    │  
\[Step 03\] Calculate Indicators (EMA, ATR, Volume SMA, Correlation Matrix)\[cite: 143\].  
    │  
\[Step 04\] Run Module F: Market Regime Filter\[cite: 144\].  
    │  
\[Step 05\] Run Module A: Position Risk Manager & Process Open Sell/Stop Orders\[cite: 145, 146\].  
    │  
\[Step 06\] Compute Residual Free Equity & Identified Cash from Exits\[cite: 147\].  
    │  
\[Step 07\] Run Module L: Evaluate Relative Strength (RS) Decay & Hard/Soft Exits  
    │  
\[Step 08\] Run Module B: Breakout Scanner & Module J: Multi-Timeframe Confirmation\[cite: 148, 149\].  
    │  
\[Step 09\] Run Module C: Relative Strength Ranking Matrix\[cite: 150\].  
    │  
\[Step 10\] Apply Module H: Correlation Risk Engine (Isolate & Filter Risk Clusters)\[cite: 151\].  
    │  
\[Step 11\] Apply Module G: Volatility Scaling Engine & Module D: Capital Allocation\[cite: 152, 153\].  
    │  
\[Step 12\] Validate via Module I: Portfolio Heat Engine & Module K: Market Breadth\[cite: 154, 155\].  
    │  
\[Step 13\] Generate Final Balanced Execution Arrays \[BUY, SELL, HOLD, ADD, REDUCE\]\[cite: 156\].  
    │  
\[Step 14\] Publish Portfolio Dashboard & System Execution Reports\[cite: 157\].

## **5\. Tactical Cash Management Requirements**

* **Idle Capital Protocol:** When the Market Regime Filter (Module F) or Market Breadth Engine (Module K) restricts trading or mandates an increased cash position, unallocated capital must not remain uninvested.  
* **Defensive Routing:** The engine routes idle trading cash balances into zero-duration, highly liquid **Liquid ETFs** or **Overnight Mutual Funds**. This preserves capital and optimizes baseline yield while ensuring instant liquidation access when a favorable market regime shifts capital allocation back to active equity scanning.