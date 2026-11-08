"""Generate the demo fixtures: one year of a fictional account, once with an
SGD base currency (tests/fixtures/test_data.xml) and once with USD
(tests/fixtures/test_usd.xml). Same trades and market path; only the
currency the books are kept in differs.

Run: uv run python scripts/make_demo_xml.py

A seeded simulation keeps the books day by day and writes them in the shape
of a Flex query with Breakout by Day (one <FlexStatement> per business day),
so every number ties:

- NAV = cash in every currency × that day's rate + holdings at market
- each day's Change in NAV: ending = starting + deposits + dividends +
  withholding + commissions + realized + change in unrealized + FX translation
- daily TWR = (ending − deposits) ÷ starting − 1 (deposits counted at day end)
- unrealized = price part + FX part; realized = proceeds − cost, per lot
- the Cash Report's base total = each currency's cash × rate

One simplification against IB: commissions are reported on their own line
and kept out of cost basis and realized P&L, so nothing is counted twice.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from xml.sax.saxutils import quoteattr

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
OUT = {"SGD": FIXTURES / "test_data.xml", "USD": FIXTURES / "test_usd.xml"}  # base currency → file
ACCOUNT = "DEMO0001"
FIRST, LAST = date(2025, 10, 1), date(2026, 9, 30)  # FIRST only anchors the opening NAV
OPENING_CASH = 60_000.0
SEED = 7  # picked for a typical year: +13% with an 11% drawdown


@dataclass(frozen=True)
class Sec:
    symbol: str
    conid: str
    isin: str
    currency: str
    sub: str  # ETF / COMMON
    exchange: str
    country: str
    description: str
    price: float  # opening price
    drift: float  # annual
    vol: float  # annual
    market: float  # correlation of daily moves with the shared market factor


SECS = [
    Sec("CSPX", "900101", "IE00B5BMR087", "USD", "ETF", "LSEETF", "IE", "ISHARES CORE S&P 500", 620.0, 0.10, 0.16, 0.9),
    Sec("VWRA", "900102", "IE00BK5BQT80", "USD", "ETF", "LSEETF", "IE", "VANGUARD FTSE ALL-WORLD", 140.0, 0.09, 0.14, 0.97),
    Sec("IMAE", "900103", "IE00B4K48X80", "EUR", "ETF", "AEB", "IE", "ISHARES CORE MSCI EUROPE ACC", 88.0, 0.07, 0.15, 0.75),
    Sec("ES3", "900104", "SG1Q52922370", "SGD", "ETF", "SGX", "SG", "SPDR STRAITS TIMES INDEX ETF", 4.10, 0.06, 0.12, 0.5),
    Sec("MSFT", "900105", "US5949181045", "USD", "COMMON", "NASDAQ", "US", "MICROSOFT CORP", 510.0, 0.12, 0.24, 0.7),
    Sec("NVDA", "900106", "US67066G1040", "USD", "COMMON", "NASDAQ", "US", "NVIDIA CORP", 180.0, 0.25, 0.45, 0.6),
    Sec("7203", "900107", "JP3633400001", "JPY", "COMMON", "TSEJ", "JP", "TOYOTA MOTOR CORP", 2900.0, 0.06, 0.25, 0.45),
]
BY_SYMBOL = {s.symbol: s for s in SECS}
# SGD per unit and annual vol; rates against any other base are crosses of these
FX0 = {"USD": (1.29, 0.04), "EUR": (1.50, 0.06), "JPY": (0.0087, 0.09)}
COMMISSION = {"USD": 1.0, "EUR": 3.0, "JPY": 100.0, "SGD": 2.5}


# Business-day index → what happens that day (index 1 is the first statement)
BUYS = {
    1: [("CSPX", 20), ("VWRA", 60), ("IMAE", 40), ("ES3", 500), ("MSFT", 12), ("NVDA", 30), ("7203", 200)],
    45: [("CSPX", 10)],
    100: [("VWRA", 50), ("NVDA", 15)],
}
SELLS = {160: [("NVDA", 40)], 230: [("MSFT", 5)]}  # NVDA closes two lots, MSFT part of one
FLOWS = {45: 10_000.0, 100: 15_000.0, 200: -8_000.0}  # base-currency deposits (+) and withdrawals (−)
DIVIDENDS = {  # symbol, gross per share (local), withholding rate
    30: [("MSFT", 0.91, 0.30)],
    55: [("7203", 45.0, 0.15)],
    80: [("ES3", 0.065, 0.0)],
    95: [("MSFT", 0.91, 0.30)],
    170: [("MSFT", 0.91, 0.30)],
    180: [("7203", 45.0, 0.15)],
    205: [("ES3", 0.065, 0.0)],
    240: [("MSFT", 0.91, 0.30)],
}


@dataclass
class Lot:
    qty: float
    price: float  # local, per share
    fx: float  # rate at purchase
    opened: str  # Flex dateTime
    txn: str


@dataclass
class Book:
    cash: dict[str, float]
    lots: dict[str, list[Lot]] = field(default_factory=lambda: {s.symbol: [] for s in SECS})


def business_days(start: date, end: date) -> list[date]:
    days, d = [], start
    while d <= end:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def n(x: float, dp: int = 6) -> str:
    """Flex-style number: plain decimal, no exponent, trailing zeros trimmed."""
    s = f"{x:.{dp}f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def el(tag: str, **attrs: object) -> str:
    return f"<{tag} " + " ".join(f"{k}={quoteattr(str(v))}" for k, v in attrs.items()) + " />"


def simulate(base: str = "SGD") -> str:
    rng = random.Random(SEED)
    days = business_days(FIRST, LAST)
    price = {s.symbol: s.price for s in SECS}
    sgd_per = {c: r for c, (r, _) in FX0.items()} | {"SGD": 1.0}
    rate = {c: v / sgd_per[base] for c, v in sgd_per.items()}
    book = Book(cash={base: OPENING_CASH} | {c: 0.0 for c in rate if c != base})
    ids = iter(range(5_000_001, 9_999_999))

    def mv_base() -> dict[str, float]:
        return {s.symbol: sum(l.qty for l in book.lots[s.symbol]) * price[s.symbol] * rate[s.currency] for s in SECS}

    def cost_base(sym: str) -> float:
        return sum(l.qty * l.price * l.fx for l in book.lots[sym])

    def unrealized() -> float:
        return sum(mv_base()[s.symbol] - cost_base(s.symbol) for s in SECS)

    def cash_base() -> float:
        return sum(v * rate[c] for c, v in book.cash.items())

    def nav() -> float:
        return cash_base() + sum(mv_base().values())

    statements: list[str] = []
    prev_nav, prev_day, prev_unreal = nav(), days[0], 0.0

    for i, day in enumerate(days[1:], start=1):
        # --- the day's market: prices and FX rates move, then trading at the close
        prev_rate = dict(rate)
        market = rng.gauss(0, 1)  # one shared shock, so holdings move together like real ones
        for s in SECS:
            mu, sig = s.drift, s.vol
            z = s.market * market + math.sqrt(1 - s.market**2) * rng.gauss(0, 1)
            price[s.symbol] *= math.exp((mu - sig * sig / 2) / 252 + sig / math.sqrt(252) * z)
        for c, (_, vol) in FX0.items():
            sgd_per[c] *= math.exp(vol / math.sqrt(252) * rng.gauss(0, 1))
        rate = {c: v / sgd_per[base] for c, v in sgd_per.items()}
        translation = sum(v * (rate[c] - prev_rate[c]) for c, v in book.cash.items())

        stamp = day.isoformat()
        trades: list[str] = []
        cash_txns: list[str] = []
        flows = dividends = withholding = commissions = realized = 0.0

        def fx_trade(ccy: str, amount: float, t: str) -> None:
            """Convert base ↔ ccy at today's rate (amount > 0 buys ccy)."""
            book.cash[ccy] += amount
            book.cash[base] -= amount * rate[ccy]
            trades.append(el(
                "Trade", accountId=ACCOUNT, currency=base, fxRateToBase="1", assetCategory="CASH",
                subCategory="", symbol=f"{ccy}.{base}", description=f"{ccy}.{base}", conid=f"9909{len(ccy)}{ccy}",
                isin="", listingExchange="", tradeID=str(next(ids)), multiplier="1", reportDate=stamp,
                dateTime=f"{stamp};{t}", tradeDate=stamp, settleDateTarget=stamp, transactionType="ExchTrade",
                exchange="IDEALFX", quantity=n(amount), tradePrice=n(rate[ccy], 8),
                tradeMoney=n(amount * rate[ccy]), proceeds=n(-amount * rate[ccy]), taxes="0", ibCommission="0",
                ibCommissionCurrency=base, netCash=n(-amount * rate[ccy]), closePrice="0", openCloseIndicator="",
                notes="", cost="0", fifoPnlRealized="0", mtmPnl="0", buySell="BUY" if amount > 0 else "SELL",
                transactionID=str(next(ids)), orderTime=f"{stamp};{t}", openDateTime="",
                levelOfDetail="EXECUTION", orderType="", isAPIOrder="N",
            ))

        def stock_trade(sym: str, qty: float, t: str) -> None:
            nonlocal commissions, realized
            s = BY_SYMBOL[sym]
            p, x, comm = price[sym], rate[s.currency], COMMISSION[s.currency]
            common = dict(
                accountId=ACCOUNT, currency=s.currency, fxRateToBase=n(x, 8), assetCategory="STK",
                subCategory=s.sub, symbol=s.symbol, description=s.description, conid=s.conid, isin=s.isin,
                listingExchange=s.exchange, multiplier="1", reportDate=stamp, tradeDate=stamp,
                settleDateTarget=stamp, transactionType="ExchTrade", exchange=s.exchange,
            )
            when = f"{stamp};{t}"
            trade_id, txn = str(next(ids)), str(next(ids))
            lot_rows: list[str] = []
            if qty > 0:
                if s.currency != base:
                    fx_trade(s.currency, qty * p + comm, t)
                book.lots[sym].append(Lot(qty, p, x, when, txn))
                cost, pnl = qty * p, 0.0
            else:
                left, cost, pnl = -qty, 0.0, 0.0
                while left > 1e-9:  # FIFO
                    lot = book.lots[sym][0]
                    q = min(left, lot.qty)
                    lot_cost = q * lot.price * lot.fx
                    lot_pnl = q * p * x - lot_cost
                    lot_rows.append(el(
                        "Lot", **common, tradeID="", dateTime=when, quantity=n(q), tradePrice=n(lot.price * lot.fx, 9),
                        tradeMoney="", proceeds="", taxes="", ibCommission="", ibCommissionCurrency="", netCash="",
                        closePrice="", openCloseIndicator="C", notes="ST" if (day - date.fromisoformat(lot.opened[:10])).days < 365 else "LT",
                        cost=n(lot_cost), fifoPnlRealized=n(lot_pnl), capitalGainsPnl=n(q * (p - lot.price) * x),
                        fxPnl=n(q * lot.price * (x - lot.fx)), mtmPnl="", buySell="SELL", transactionID=lot.txn,
                        orderTime="", openDateTime=lot.opened, levelOfDetail="CLOSED_LOT", orderType="", isAPIOrder="",
                    ))
                    cost, pnl, lot.qty, left = cost + lot_cost, pnl + lot_pnl, lot.qty - q, left - q
                    if lot.qty <= 1e-9:
                        book.lots[sym].pop(0)
                realized += pnl
            book.cash[s.currency] += -qty * p - comm
            commissions -= comm * x
            trades.append(el(
                "Trade", **common, tradeID=trade_id, dateTime=when, quantity=n(qty), tradePrice=n(p, 4),
                tradeMoney=n(qty * p), proceeds=n(-qty * p), taxes="0", ibCommission=n(-comm),
                ibCommissionCurrency=s.currency, netCash=n(-qty * p - comm), closePrice=n(p, 4),
                openCloseIndicator="O" if qty > 0 else "C", notes="", cost=n(cost if qty > 0 else -cost),
                fifoPnlRealized=n(pnl), mtmPnl="0", buySell="BUY" if qty > 0 else "SELL", transactionID=txn,
                orderTime=when, openDateTime="", levelOfDetail="EXECUTION", orderType="LMT", isAPIOrder="N",
            ))
            trades.extend(lot_rows)  # IB lists a sale's closed lots right after it
            if qty < 0 and s.currency != base:
                fx_trade(s.currency, -book.cash[s.currency], t)  # bring proceeds home

        for sym, qty in BUYS.get(i, []):
            stock_trade(sym, qty, "10:15:00")
        for sym, qty in SELLS.get(i, []):
            stock_trade(sym, -qty, "11:30:00")

        if i in FLOWS:
            amount = FLOWS[i]
            book.cash[base] += amount
            flows += amount
            cash_txns.append(el(
                "CashTransaction", dateTime=f"{stamp};20:20:00", accountId=ACCOUNT, currency=base, fxRateToBase="1",
                symbol="", isin="", listingExchange="", amount=n(amount), type="Deposits/Withdrawals",
                transactionID=str(next(ids)),
            ))
        for sym, per_share, wht_rate in DIVIDENDS.get(i, []):
            s = BY_SYMBOL[sym]
            shares = sum(l.qty for l in book.lots[sym])
            gross, x = shares * per_share, rate[s.currency]
            book.cash[s.currency] += gross * (1 - wht_rate)  # foreign dividends stay in their currency
            dividends += gross * x
            withholding -= gross * wht_rate * x
            common = dict(accountId=ACCOUNT, currency=s.currency, fxRateToBase=n(x, 8), symbol=s.symbol,
                          isin=s.isin, listingExchange=s.exchange)
            cash_txns.append(el("CashTransaction", dateTime=f"{stamp};20:20:00", **common, amount=n(gross),
                                type="Dividends", transactionID=str(next(ids))))
            if wht_rate:
                cash_txns.append(el("CashTransaction", dateTime=f"{stamp};20:20:00", **common,
                                    amount=n(-gross * wht_rate), type="Withholding Tax", transactionID=str(next(ids))))

        assert all(v > -1e-6 for v in book.cash.values()), (day, book.cash)

        # --- the day's books
        today_nav, today_unreal = nav(), unrealized()
        change_unreal = today_unreal - prev_unreal
        parts = flows + dividends + withholding + commissions + realized + change_unreal + translation
        assert abs(prev_nav + parts - today_nav) < 1e-6, (day, prev_nav + parts, today_nav)
        twr = ((today_nav - flows) / prev_nav - 1) * 100

        mv = mv_base()
        invested = sum(mv.values())
        stock_value = invested  # IB reports these ETFs and stocks under "stock"
        positions = []
        for s in SECS:
            qty = sum(l.qty for l in book.lots[s.symbol])
            if qty <= 1e-9:
                continue
            x, p = rate[s.currency], price[s.symbol]
            cost_local = sum(l.qty * l.price for l in book.lots[s.symbol])
            cb = cost_base(s.symbol)
            positions.append(el(
                "OpenPosition", accountId=ACCOUNT, currency=s.currency, fxRateToBase=n(x, 8), assetCategory="STK",
                subCategory=s.sub, symbol=s.symbol, description=s.description, conid=s.conid, isin=s.isin,
                listingExchange=s.exchange, issuerCountryCode=s.country, multiplier="1", reportDate=stamp,
                position=n(qty), markPrice=n(p, 4), positionValue=n(qty * p), positionValueInBase=n(mv[s.symbol]),
                costBasisPrice=n(cb / qty, 9), costBasisMoney=n(cb), percentOfNAV=n(mv[s.symbol] / invested * 100, 2),
                fifoPnlUnrealized=n(mv[s.symbol] - cb), unrealizedCapitalGainsPnl=n((qty * p - cost_local) * x),
                unrealizedlFxPnl=n(cost_local * x - cb), side="Long", levelOfDetail="SUMMARY",
                openPrice=n(cb / qty, 9),
            ))

        cash_rows = [el("CashReportCurrency", currency="BASE_SUMMARY", fromDate=stamp, toDate=stamp,
                        depositWithdrawals=n(flows), endingCash=n(cash_base()), endingSettledCash=n(cash_base()))]
        cash_rows += [el("CashReportCurrency", currency=c, fromDate=stamp, toDate=stamp,
                         depositWithdrawals=n(flows if c == base else 0), endingCash=n(v), endingSettledCash=n(v))
                      for c, v in sorted(book.cash.items())]

        def equity(d: date, cash: float, stock: float) -> str:
            return el("EquitySummaryByReportDateInBase", accountId=ACCOUNT, currency=base, reportDate=d.isoformat(),
                      cash=n(cash), stock=n(stock), options="0", bonds="0", funds="0", dividendAccruals="0",
                      interestAccruals="0", crypto="0", total=n(cash + stock))

        statements.append("\n".join([
            f'<FlexStatement accountId="{ACCOUNT}" fromDate="{stamp}" toDate="{stamp}" period="" '
            f'whenGenerated="{(day + timedelta(days=1)).isoformat()};06:00:00">',
            f'<AccountInformation acctAlias="" currency="{base}" />',
            "<EquitySummaryInBase>",
            equity(prev_day, *prev_equity) if i > 1 else equity(prev_day, OPENING_CASH, 0.0),
            equity(day, cash_base(), stock_value),
            "</EquitySummaryInBase>",
            el("ChangeInNAV", accountId=ACCOUNT, currency=base, fromDate=stamp, toDate=stamp,
               startingValue=n(prev_nav), realized=n(realized), changeInUnrealized=n(change_unreal),
               depositsWithdrawals=n(flows), dividends=n(dividends), withholdingTax=n(withholding), interest="0",
               otherFees="0", commissions=n(commissions), netFxTrading="0", fxTranslation=n(translation),
               endingValue=n(today_nav), twr=n(twr, 10)),
            "<CashReport>", *cash_rows, "</CashReport>",
            "<OpenPositions>", *positions, "</OpenPositions>",
            "<Trades>", *trades, "</Trades>",
            "<CashTransactions>", *cash_txns, "</CashTransactions>",
            "<SecuritiesInfo>",
            *[el("SecurityInfo", currency=s.currency, assetCategory="STK", subCategory=s.sub, symbol=s.symbol,
                 description=s.description, conid=s.conid, isin=s.isin, listingExchange=s.exchange, issuer="",
                 issuerCountryCode=s.country, multiplier="1", underlyingCategory="", code="") for s in SECS],
            "</SecuritiesInfo>",
            "<ConversionRates>",
            *[el("ConversionRate", reportDate=stamp, fromCurrency=c, toCurrency=base, rate=n(rate[c], 8))
              for c in sorted(rate) if c != base],
            "</ConversionRates>",
            "</FlexStatement>",
        ]))
        prev_nav, prev_day, prev_unreal = today_nav, day, today_unreal
        prev_equity = (cash_base(), stock_value)

    return "\n".join([
        '<FlexQueryResponse queryName="demo_portfolio" type="AF">',
        f'<FlexStatements count="{len(statements)}">',
        *statements,
        "</FlexStatements>",
        "</FlexQueryResponse>",
        "",
    ])


if __name__ == "__main__":
    for base, out in OUT.items():
        out.write_text(simulate(base))
        print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")
