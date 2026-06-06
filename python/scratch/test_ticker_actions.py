import yfinance as yf
import time

symbol = "GMRAIRPORT.NS"
print(f"Fetching Ticker actions for {symbol}...")
start = time.time()
ticker = yf.Ticker(symbol)
actions = ticker.actions
print(f"Fetched in {time.time() - start:.2f} seconds.")
print("\nActions DataFrame:")
print(actions)

# Format the actions as a list of dicts to see what we get
actions_list = []
for idx, row in actions.iterrows():
    actions_list.append({
        "action_date": idx.date(),
        "action_type": "DIVIDEND" if row["Dividends"] > 0 else "SPLIT",
        "value": row["Dividends"] if row["Dividends"] > 0 else row["Stock Splits"]
    })
print("\nParsed actions:")
print(actions_list)
