import json
import sys

import pandas as pd
from yahooquery import Ticker


def main():
    sym = sys.argv[1].upper() if len(sys.argv) > 1 else "ABNB"
    t = Ticker(sym)

    modules = t.get_modules(
        [
            "financialData",
            "recommendationTrend",
            "defaultKeyStatistics",
            "summaryDetail",
            "price",
            "assetProfile",
            "earningsTrend",
        ]
    )
    mods = modules.get(sym) or modules.get(sym.lower()) or modules

    print(f"Modules for {sym}: {list(mods.keys())}\n")
    for k, v in mods.items():
        print(f"{k}:\n{json.dumps(v, indent=2, default=str)}\n")

    print("valuation_measures:\n", t.valuation_measures)

# Fund holdings example (QQQ) via yahooquery
tq = Ticker("QQQ")
fund = tq.fund_holding_info.get("QQQ", {}) or {}
holdings = fund.get("holdings", [])
df = pd.DataFrame.from_records(holdings)
print(df.head())
print(len(df), "rows")


if __name__ == "__main__":
    main()
