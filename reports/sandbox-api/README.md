# Real sandbox API checks

This is an executed connection to a vendor's sandbox over HTTPS, separate from
the six offline demonstrations. It uses simulated funds, not a live brokerage account.

## Verified: tastytrade

[Executed result](tastytrade.json) · [Client source](../../lab/sandbox_api.py)

On 2026-10-27 UTC the check successfully:

1. Exchanged a personal OAuth refresh token for an access token.
2. Queried the sandbox account, balance and positions.
3. Validated a one-share AAPL limit order using the dry-run endpoint.
4. Submitted and retrieved the simulated order.
5. Canceled it and independently confirmed `Cancelled` with another GET.

Observed order states: `Received → Received → Cancelled`.
This run validates acceptance and cancellation, not a fill, P&L, market-data feed,
WebSocket stream, option order, or futures order. The sandbox resets trading state daily
and does not serve market data. Its synthetic fills are unsuitable for evaluating alpha.

## Verified: OANDA

[Executed result](oanda.json) uses the `api-fxpractice.oanda.com` practice host.
On 2026-10-27 UTC it queried account summary and positions, retrieved a EUR/USD
bid/ask snapshot and 20 one-minute candles (19 marked complete), submitted a minimum-size
limit order below the current bid, retrieved it, canceled it and confirmed `CANCELLED`.

Observed order states: `PENDING → CANCELLED`. No fill, streaming connection or strategy
performance was tested. Raw vendor prices, account identifiers and API tokens are not published.

For OANDA use `oanda` in the command below and a private JSON file containing
`environment: practice`, `api_token`, and `account_number`.

## Reproduce

Keep a JSON credential file outside this repository with owner-only permissions:

```json
{
  "environment": "sandbox",
  "client_id": "YOUR_SANDBOX_CLIENT_ID",
  "client_secret": "YOUR_SANDBOX_CLIENT_SECRET",
  "refresh_token": "YOUR_SANDBOX_REFRESH_TOKEN",
  "account_number": "YOUR_SANDBOX_ACCOUNT"
}
```

```sh
chmod 600 /private/path/tastytrade.json
python check_sandbox.py tastytrade --credentials /private/path/tastytrade.json
python check_sandbox.py tastytrade --credentials /private/path/tastytrade.json --exercise-orders
```

Default checks query account data only after authenticating. `--exercise-orders`
submits and cancels one simulated order. Outputs omit credentials and account/order IDs.
Clients use fixed sandbox hosts, refuse redirects and do not automatically retry failed
order submissions. After an ambiguous network failure, reconcile the sandbox order history
before running the order exercise again. This is a short smoke test, not a resilient daemon.

## Verified: Alpaca

[Executed result](alpaca.json) uses the `paper-api.alpaca.markets` trading host and
`data.alpaca.markets` for historical data. On 2026-10-27 America/New_York (UTC timestamp
in the JSON), a dedicated Paper account returned `ACTIVE`, and the client retrieved
five AAPL daily bars from the IEX feed using the requested UTC window
2025-01-02 00:00 to 2025-01-10 00:00.
The run submitted a one-share $1 buy limit order, retrieved it, canceled it, and confirmed
the final state with a separate GET. Fill handling was not tested.

Observed order states: `accepted → accepted → canceled`. The market was closed during
this run; this verifies acceptance/cancellation, not a fill or regular-session execution.
Streaming, reconnect behavior, order amendment and crypto orders have not been tested.

Use `alpaca` in the command above with a private JSON file containing
`environment: paper`, `api_key`, and `api_secret`. Raw vendor bars, account identifiers
and API credentials are not published.

## Official references

- [tastytrade sandbox](https://developer.tastytrade.com/docs/sandbox/)
- [tastytrade OAuth](https://developer.tastytrade.com/docs/authentication/oauth2/)
- [tastytrade order guide](https://developer.tastytrade.com/docs/guides/place-an-equity-order/)
- [Alpaca paper trading](https://docs.alpaca.markets/us/docs/paper-trading)
- [OANDA API environments](https://developer.oanda.com/rest-live-v20/development-guide/)
- [OANDA pricing and candles](https://developer.oanda.com/rest-live-v20/pricing-ep/)
- [OANDA order endpoints](https://developer.oanda.com/rest-live-v20/order-ep/)

Original integration work for this portfolio. No client work or private account details are included.
