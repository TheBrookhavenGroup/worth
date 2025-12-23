from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
import pandas as pd
import time

class IBApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.data = []

    def historicalData(self, reqId, bar):
        self.data.append({
            "date": bar.date,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume
        })

    def historicalDataEnd(self, reqId, start, end):
        print("Historical data download complete")
        self.disconnect()

def main():
    app = IBApp()
    # Connect TWS or IB Gateway
    app.connect("127.0.0.1", 7496, clientId=1)

    # Define the Futures Contract
    contract = Contract()
    contract.symbol = "ES"
    contract.secType = "FUT"
    contract.exchange = "GLOBEX"
    contract.currency = "USD"
    contract.lastTradeDateOrContractMonth = "202403"  # Mar 2024
    contract.tradingClass = "ES"
    contract.multiplier = 50

    # Request Historical Daily Bars
    app.reqHistoricalData(
        reqId=1,
        contract=contract,
        endDateTime="20250101 23:59:59",  # Must be >= your desired end date
        durationStr="1 M",                # 1 month of data
        barSizeSetting="1 day",
        whatToShow="TRADES",
        useRTH=1,
        formatDate=1,
        keepUpToDate=False,
        chartOptions=[]
    )

    app.run()

    df = pd.DataFrame(app.data)
    df["date"] = pd.to_datetime(df["date"])
    df = df[(df["date"] >= "2024-01-01") & (df["date"] <= "2024-01-31")]
    df.to_csv("ESH2024_Jan2024_IBKR.csv", index=False)
    print(df)

if __name__ == "__main__":
    main()
