BLUE_CHIP_UNIVERSE = {
    # Mega-cap technology / internet
    "AAPL": ("Apple", "Technology", 10),
    "MSFT": ("Microsoft", "Technology", 10),
    "NVDA": ("NVIDIA", "Semiconductors", 10),
    "GOOGL": ("Alphabet Class A", "Communication Services", 10),
    "GOOG": ("Alphabet Class C", "Communication Services", 10),
    "AMZN": ("Amazon", "Consumer Discretionary", 10),
    "META": ("Meta Platforms", "Communication Services", 10),

    # Semiconductors / infrastructure
    "AVGO": ("Broadcom", "Semiconductors", 10),
    "AMD": ("Advanced Micro Devices", "Semiconductors", 9),
    "MU": ("Micron Technology", "Semiconductors", 9),
    "LRCX": ("Lam Research", "Semiconductor Equipment", 9),
    "AMAT": ("Applied Materials", "Semiconductor Equipment", 9),
    "QCOM": ("Qualcomm", "Semiconductors", 8),
    "TXN": ("Texas Instruments", "Semiconductors", 8),
    "INTC": ("Intel", "Semiconductors", 8),
    "TSM": ("Taiwan Semiconductor", "Semiconductors", 10),

    # Software / cloud / security
    "ORCL": ("Oracle", "Software / Cloud", 9),
    "CRM": ("Salesforce", "Software / Cloud", 8),
    "ADBE": ("Adobe", "Software", 8),
    "NOW": ("ServiceNow", "Software", 8),
    "PANW": ("Palo Alto Networks", "Cybersecurity", 8),
    "CRWD": ("CrowdStrike", "Cybersecurity", 8),
    "IBM": ("IBM", "Technology", 7),

    # Financials
    "JPM": ("JPMorgan Chase", "Financials", 9),
    "BAC": ("Bank of America", "Financials", 8),
    "WFC": ("Wells Fargo", "Financials", 8),
    "GS": ("Goldman Sachs", "Financials", 8),
    "MS": ("Morgan Stanley", "Financials", 8),
    "V": ("Visa", "Financials", 8),
    "MA": ("Mastercard", "Financials", 8),
    "BRK.B": ("Berkshire Hathaway", "Financials", 9),

    # Consumer
    "WMT": ("Walmart", "Consumer Staples", 9),
    "COST": ("Costco", "Consumer Staples", 8),
    "HD": ("Home Depot", "Consumer Discretionary", 8),
    "MCD": ("McDonald's", "Consumer Discretionary", 7),
    "NKE": ("Nike", "Consumer Discretionary", 7),
    "PG": ("Procter & Gamble", "Consumer Staples", 7),
    "KO": ("Coca-Cola", "Consumer Staples", 7),
    "PEP": ("PepsiCo", "Consumer Staples", 7),

    # Healthcare
    "LLY": ("Eli Lilly", "Health Care", 9),
    "UNH": ("UnitedHealth Group", "Health Care", 9),
    "JNJ": ("Johnson & Johnson", "Health Care", 8),
    "ABBV": ("AbbVie", "Health Care", 8),
    "MRK": ("Merck", "Health Care", 8),

    # Industrials
    "CAT": ("Caterpillar", "Industrials", 8),
    "GE": ("GE Aerospace", "Industrials", 8),
    "HON": ("Honeywell", "Industrials", 7),
    "RTX": ("RTX", "Industrials", 8),
    "BA": ("Boeing", "Industrials", 8),

    # Energy
    "XOM": ("Exxon Mobil", "Energy", 9),
    "CVX": ("Chevron", "Energy", 8),

    # Communication
    "NFLX": ("Netflix", "Communication Services", 8),
    "DIS": ("Walt Disney", "Communication Services", 8),
}


# Yahoo uses BRK-B rather than BRK.B.
YAHOO_SYMBOL_OVERRIDES = {
    "BRK.B": "BRK-B",
}


def yahoo_symbol(ticker: str) -> str:
    return YAHOO_SYMBOL_OVERRIDES.get(ticker.upper(), ticker.upper())


def canonical_symbol(ticker: str) -> str:
    ticker = ticker.upper().strip()
    if ticker == "BRK-B":
        return "BRK.B"
    return ticker


def universe_rows() -> list[dict]:
    rows = []

    for ticker, (company_name, sector, impact_score) in BLUE_CHIP_UNIVERSE.items():
        rows.append(
            {
                "ticker": ticker,
                "company_name": company_name,
                "sector": sector,
                "impact_score": impact_score,
            }
        )

    rows.sort(key=lambda row: (-row["impact_score"], row["ticker"]))
    return rows
