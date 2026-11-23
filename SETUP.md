# Setup

## 1. Install

You need [uv](https://docs.astral.sh/uv/getting-started/installation/) and
[Node.js](https://nodejs.org/) 20 or newer. From the project folder:

```bash
uv sync
npm --prefix web install
npm --prefix web run build
```

Check that everything works with the demo before connecting your account:

```bash
uv run portfolio ingest --demo
uv run portfolio serve --demo
```

Open http://localhost:8000, look around, then stop the server with Ctrl+C.

## 2. Create the Flex query in IBKR

A Flex query tells IBKR what to put in your statements. In Client Portal, go to
**Performance & Reports → Flex Queries → Custom Flex Queries → Create**.

Tick each item as you go. IBKR's field labels can differ slightly from these
names. Ticking extra fields is harmless; the ones listed are the minimum.

### Sections

**Account Information**
- [ ] Section ticked
- [ ] Field: **Currency**. This is your base currency; every amount in the app is shown in it.

**Net Asset Value (NAV) in Base**
- [ ] Section ticked
- [ ] Options: leave **Exclude prior report date** unticked, and tick **Exclude long/short breakout**
- [ ] Fields: Report Date, Cash, Stock, Options, Bonds, Funds, Crypto, Dividend Accruals, Interest Accruals, Total

**Change in NAV**
- [ ] Section ticked
- [ ] Fields: From Date, To Date, Starting Value, Realized, Change in Unrealized, Deposits & Withdrawals, Dividends, Withholding Tax, Interest, Commissions, Other Fees, FX Translation, Ending Value
- [ ] Field: **TWR**. Every return figure in the app comes from this field.

**Cash Report**
- [ ] Section ticked
- [ ] Fields: Currency, From Date, To Date, Ending Cash, Ending Settled Cash

**Open Positions**
- [ ] Section ticked
- [ ] Options: **Summary** (not Lot)
- [ ] Fields: Report Date, Conid, Currency, FX Rate To Base, Quantity, Mark Price, Position Value, Position Value In Base, Cost Basis Price, Cost Basis Money, FIFO Unrealized P&L, Unrealized Capital Gains P&L, Unrealized FX P&L, Percent of NAV, Side, Level of Detail

**Trades**
- [ ] Section ticked
- [ ] Options: **Execution** and **Closed Lots**
- [ ] Options: leave **Symbol Summary**, **Asset Class** and **Orders** unticked. They add summary rows the app can't use.
- [ ] Fields: Trade ID, Transaction ID, Conid, Currency, FX Rate To Base, Trade Date, Date/Time, Quantity, Trade Price, Proceeds, IB Commission, Cost, FIFO Realized P&L, Capital Gains P&L, FX P&L, Open/Close Indicator, Buy/Sell, Open Date Time, Level of Detail

**Cash Transactions**
- [ ] Section ticked
- [ ] Options: Dividends, Payment in Lieu of Dividends, Withholding Tax, Deposits & Withdrawals, Broker Interest Paid, Broker Interest Received, Other Fees
- [ ] Fields: Type, Amount, Currency, FX Rate To Base, Date/Time, Transaction ID, ISIN, Description

**Financial Instrument Information**
- [ ] Section ticked
- [ ] Fields: Conid, Symbol, Description, Asset Category, Sub Category, Currency, ISIN, Listing Exchange, Issuer Country Code

### Delivery and general settings

- [ ] Format: **XML**
- [ ] Period: **Last 365 Calendar Days** (pulls ask for their own dates; this is a fallback)
- [ ] Date format: **yyyy-MM-dd**
- [ ] Time format: **HH:mm:ss**
- [ ] Date/time separator: **; (semicolon)**
- [ ] Profit and Loss: **Base Currency**. Costs and P&L are then in your base currency.
- [ ] Include Currency Rates: **Yes**
- [ ] Breakout by Day: **Yes**. This is what gives the app one row per day.

Save the query, then note its **Query ID**: the number shown next to it in
the Flex Queries list (click the info icon if it's hidden).

## 3. Create a token

In Client Portal, go to **Settings → Account Report → Flex Web Service**:

- [ ] Click **Generate New Token**
- [ ] Choose the longest validity (one year) and leave the IP restriction empty
- [ ] Add a calendar reminder to renew it a week before it expires

## 4. Add your details

```bash
cp .env.example .env
```

Open `.env` and fill in `FLEX_TOKEN`, `FLEX_QUERY_ID` and, optionally,
`IBKR_ACCOUNT_ID` (the app then warns if a statement belongs to a different
account). `.env` stays on your machine; git ignores it.

Everything else has sensible defaults. To change the benchmark or database
file, copy `config/config.example.yaml` to `config/config.yaml` and
edit the lines you need.

## 5. Load your history

IBKR caps each statement at 365 days. A live pull therefore fetches at most the
last year:

```bash
uv run portfolio ingest
```

To go further back, download one statement per year from Client Portal:
**Performance & Reports → Flex Queries**, then the run button next to your query,
format **XML**, and a date range of up to a year. Put the files in `data/xml/`
(ignored by git) and load them all at once, in any order:

```bash
uv run portfolio ingest --xml data/xml/*.xml
```

Overlapping dates are fine: every row is stored once, keyed by date and
security, and later files update earlier ones.

If a downloaded file says "Realized P/L is not ready" near the top, IBKR hadn't
finished that day's P&L when you downloaded it. The app refuses such files
rather than store zeros. Download again later, or end the range a day earlier.

## 6. Open the dashboard

```bash
uv run portfolio serve
```

Open http://localhost:8000. On **Positions**, double-click the Sleeve column to
mark holdings Core, Satellite or Cash, and add themes or a thesis. These labels
are stored in `portfolio.db` and never overwritten by a pull.

## 7. Schedule daily pulls

```bash
./scripts/install_schedule.sh
```

This pulls Tuesday to Saturday at 20:00 your Mac's time, after IBKR has
finished the previous trading day's P&L. If your Mac is asleep at that time,
the pull runs when it wakes. Each pull re-fetches the last 14 days, so a missed
or failed one fills itself in next time. Output goes to `ingest.log`.

The script is macOS only. On Linux or Windows, run `uv run portfolio ingest`
from the project folder with cron or Task Scheduler, Tuesday to Saturday at
20:00.

```bash
./scripts/install_schedule.sh --remove   # stop scheduled pulls
launchctl kickstart gui/$UID/com.ibkr-portfolio.ingest   # run the scheduled pull now
tail -n 50 ingest.log                    # see recent pull output
```

Run the script again after moving the project folder.

You're set up. The rest of this guide covers running the app day to day,
fixing what goes wrong, and keeping your data safe.

## Day to day

```bash
uv run portfolio serve        # dashboard at http://localhost:8000
uv run portfolio ingest       # pull now, instead of waiting for the schedule
```

The **Ops** tab, and the status in the top bar, show when data was last loaded
and whether the last pull failed. You can leave the dashboard running during a
pull; refresh the page afterwards.

Each pull asks IBKR for everything from 14 days before the last loaded date up
to yesterday. A failed pull doesn't move that date, so the next one retries the
same days. Every pull's XML is saved in `data/xml/live_<from>_<to>.xml`, and
can be loaded again at any time, for example:

```bash
uv run portfolio ingest --xml data/xml/live_20261001_20261015.xml
```

## Renew the token (yearly)

A pull that fails straight away with error **1012** means the token has
expired.

1. Client Portal → **Settings → Account Report → Flex Web Service** → **Generate New Token**.
2. Replace `FLEX_TOKEN` in `.env`.
3. Run `uv run portfolio ingest` and check the Ops tab.

## When a pull fails

The Ops tab shows the error. Common ones:

| Error | What it means | What to do |
|---|---|---|
| `1012` | Token expired | Renew it (above) |
| `1013` | Token is limited to other IP addresses | Generate a token with no IP restriction |
| `1014`, `1015` | Query ID or token is wrong | Compare `.env` with Client Portal |
| `1003` | The statement isn't available yet | Pull later; never ask for today's date |
| `1019`, `FlexRetryExhaustedError` | IBKR was busy and the statement never became ready | Try again later |
| `StatementNotReadyError` | IBKR hadn't finished its P&L run | Pull later; scheduled pulls run in the evening for this reason |
| `IncompleteSectionError` | A Flex section is missing required fields | The message names the fields; tick them in the query (step 2) |
| `BaseCurrencyChangedError` | The statement's base currency differs from the one already in the database | One database holds one base currency. Load it into a new one (`--db`), or rebuild (below) with every statement in the new currency |
| `ConfigError` | `config/config.yaml` or `.env` has a problem | The message names the setting |

The Overview's return figures come from IBKR's own daily return (the **TWR**
field). If the log warns that some dates "have no IB daily TWR", tick that
field in the query's Change in NAV section and pull again.

## Back up and restore

Everything lives in `portfolio.db`: IBKR data, which can be pulled again, and
your labels and notes, which can't.

```bash
sqlite3 portfolio.db ".backup 'backup-$(date +%F).db'"   # safe while the app runs
cp backup-2026-10-17.db portfolio.db                     # restore, with the app stopped
```

`portfolio.db-wal` and `portfolio.db-shm` sit next to the database while it's
open. They're SQLite's working files; don't delete them while the app runs.

To rebuild from scratch, which loses your labels and notes unless you keep a
backup:

```bash
rm portfolio.db*
uv run portfolio ingest --xml data/xml/*.xml
```
