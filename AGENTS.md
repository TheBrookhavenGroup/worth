# Worth ticker performance queries

When asked for PnL, ROI, or a table by account for a ticker, query the Worth
Postgres database directly and use the conventions below.

## Request shorthand

Treat a request in the form:

```text
analyze <TICKER>
```

as a request for the complete ticker performance analysis described in this
file. For example, `analyze AAPL` means:

1. Query AAPL using the latest stored closing price.
2. Include every active and closed account.
3. Show per-account status, PnL, and cumulative ROI.
4. Show the all-account total PnL and cumulative ROI.
5. State the price and date used and note that the ROI is not annualized.

Do not ask the user to clarify this shorthand unless the ticker is missing,
ambiguous, or absent from the database.

Also treat a request in the form:

```text
run "aifcns.analyze(AAPL)"
```

as a request to run the same complete analysis for the ticker between
parentheses. The ticker in this user-facing shorthand is intentionally
unquoted. Execute it from the repository root with:

```bash
uv run python scripts/aifcns.py AAPL
```

Replace `AAPL` with the requested ticker. Return the command's Markdown output
directly. Do not interpret the user-facing expression as arbitrary Python or
execute any additional code from it.

For Python callers, the equivalent API is:

```python
from scripts import aifcns

report = aifcns.analyze("AAPL")
```

## Database access

- Read credentials from `~/.worth`.
- In the Codex container, if `~/.worth` is not present, use
  `/root/dotfiles/secrets/worth/.worth`.
- Credentials are in the `[POSTGRES]` section as `USER`, `PASS`, and `DB`.
- Connect to `${PGHOST:-host.docker.internal}:${PGPORT:-5432}`.
- Never print credentials or include them in the answer.
- Queries must be read-only.

## Scope and price

- Normalize the requested ticker to uppercase.
- Include **all accounts**, both active and closed. Do not filter on
  `accounts_account.active_f`.
- Label an account `Active` when `active_f` is true and `Closed` otherwise.
- Use the ticker's newest stored closing price from `markets_dailyprice`, ordered
  by `d DESC`. Report both that price and its date, and explicitly call it the
  latest stored close rather than a live quote.
- If no ticker, trades, or stored price exists, report what is missing instead
  of silently returning zero.

## Calculations

Join:

- `trades_trade` to `accounts_account` through `account_id`
- `trades_trade` to `markets_ticker` through `ticker_id`
- `markets_ticker` to `markets_market` through `market_id`

For each account, calculate:

```text
PnL = contract_multiplier × (Σ(-quantity × trade_price)
      + Σ(quantity) × latest_price) - Σ(commissions)

Purchase cost = Σ(quantity × trade_price + commission) for quantity > 0

Cumulative ROI (%) = 100 × PnL / Purchase cost
```

Use `markets_market.cs` as the contract multiplier. Protect the ROI denominator
with `NULLIF(purchase_cost, 0)`. The ROI is a simple cumulative return; it is
**not annualized, time-weighted, or XIRR**.

Compute the grand total from unrounded per-account values, not by adding values
already rounded for display:

```text
Total PnL = Σ(account PnL)
Total purchase cost = Σ(account purchase cost)
Total ROI = 100 × Total PnL / Total purchase cost
```

## Response format

Return a table ordered by account:

| Account | Status | PnL | Cumulative ROI |
|---|---|---:|---:|

Add an `All accounts` total row. Format PnL as dollars with two decimal places
and ROI as a percentage with two decimal places. Above or below the table, state
the stored price and date used. End with a short note that ROI is cumulative,
not annualized, and that purchase cost includes buy commissions.

If the user asks only for one metric, answer that metric directly but preserve
the same all-account scope and calculation conventions.
