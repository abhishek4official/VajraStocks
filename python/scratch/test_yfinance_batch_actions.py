import yfinance as yf
import datetime
import pandas as pd

tickers = ["TRENT.NS", "ASHOKLEY.NS", "RALLIS.NS"]
start_date = datetime.date.today() - datetime.timedelta(days=365)
end_date = datetime.date.today()

print(f"Downloading batch {tickers} from {start_date} to {end_date}...")
df = yf.download(
    tickers=tickers,
    start=start_date.strftime("%Y-%m-%d"),
    end=end_date.strftime("%Y-%m-%d"),
    group_by="ticker",
    auto_adjust=False,
    actions=True,
    threads=True
)

print("\nDataFrame columns structure:")
print(df.columns)

is_multi = isinstance(df.columns, pd.MultiIndex)
print(f"\nIs MultiIndex: {is_multi}")

for ticker in tickers:
    print(f"\n--- Ticker: {ticker} ---")
    if is_multi:
        if ticker not in df.columns.levels[0]:
            print(f"Ticker {ticker} not found in columns levels[0]!")
            continue
        ticker_df = df[ticker].dropna(subset=["Close", "Volume"])
    else:
        ticker_df = df.dropna(subset=["Close", "Volume"])
        
    print(f"Columns for {ticker}: {list(ticker_df.columns)}")
    
    # Check if Dividends or Stock Splits are present and have non-zero values
    if "Dividends" in ticker_df.columns:
        divs = ticker_df[ticker_df["Dividends"] > 0]
        print(f"Dividends found: {len(divs)}")
        if len(divs) > 0:
            print(divs["Dividends"].head())
    else:
        print("Dividends column not found!")
        
    if "Stock Splits" in ticker_df.columns:
        splits = ticker_df[ticker_df["Stock Splits"] > 0]
        print(f"Stock Splits found: {len(splits)}")
        if len(splits) > 0:
            print(splits["Stock Splits"].head())
    else:
        print("Stock Splits column not found!")
