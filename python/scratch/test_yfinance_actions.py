import yfinance as yf
import datetime
import pandas as pd

ticker = "TRENT.NS"
start_date = datetime.date.today() - datetime.timedelta(days=365)
end_date = datetime.date.today()

print(f"Downloading {ticker} from {start_date} to {end_date}...")
df = yf.download(
    tickers=[ticker],
    start=start_date.strftime("%Y-%m-%d"),
    end=end_date.strftime("%Y-%m-%d"),
    group_by="ticker",
    auto_adjust=False,
    actions=True,
    threads=False
)

is_multi = isinstance(df.columns, pd.MultiIndex)

ticker_df = df[ticker] if is_multi else df

print("\nticker_df columns:")
print(ticker_df.columns)

# Look for non-zero Dividends or Stock Splits
if "Dividends" in ticker_df.columns:
    divs = ticker_df[ticker_df["Dividends"] > 0]
    print(f"\nNon-zero dividends found: {len(divs)}")
    if len(divs) > 0:
        print(divs[["Close", "Dividends"]])

if "Stock Splits" in ticker_df.columns:
    splits = ticker_df[ticker_df["Stock Splits"] > 0]
    print(f"\nNon-zero stock splits found: {len(splits)}")
    if len(splits) > 0:
        print(splits[["Close", "Stock Splits"]])
