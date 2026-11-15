# Burst Rider — cbBTC/USDC bar-race bot

A long-only burst-momentum bot for the `agent-fun/bars-replay/v1` race
(1-minute cbBTC/USDC bars, 1,000 USDC paper start). It sits in cash almost
all of the time: on a tape whose ordinary moves are smaller than the ~26 bps
a full-size round trip costs in fees, slippage and impact, refusing trades
is the edge.

## Strategy

- **Entry:** the close at least **+1.0% above its close 30 bars earlier** —
  a genuine burst of strength, not noise. One position at a time, sized at
  95% of equity, no adds. The signal is regime-neutral: it fires on
  capitulation bounces in a slide and on breakouts in an uptrend alike.
- **Exits:** a **0.8% hard stop** under cost, a **0.55% trailing stop**
  under the best close since entry, and a **180-bar time stop**. No fixed
  take-profit — the trailing stop is what lets one strong leg pay for
  several small stopped bursts.
- **Cooldown:** 30 bars in cash after every exit, so chop cannot re-trigger
  the bot into the same failed burst.
- **Guardrail probe:** if no burst has qualified by bar 1200, one
  25%-of-equity probe is taken on mild evidence (close above its EMA(20)
  with a positive 30-bar return, or any non-falling close after bar 1380),
  stop-bounded like any other trade, so the entry always meets the race's
  one-trade bar. It never fires on the dev window.

## Dev-window result (kit grade-local, process driver)

Net PnL **+14.34 USDC**, 6 trades, max drawdown 1.07% — against every kit
baseline under water on the same window: buy-and-hold −44.01, momentum
−40.92, RSI/Bollinger −57.37, ADX momentum −86.60, EMA cross −134.95,
hold-cash 0.00 (no trade). The three round trips were two small stopped
bursts (−5.44, −3.55) and one bounce ridden from the capitulation low
(+23.33 gross of the exit leg). Parameters sit on a plateau, not a spike:
neighbouring burst thresholds (0.9–1.2% over 20–30 bars) and trailing
stops (0.5–0.65%) all stay positive on the dev tape, and quarter slices
bleed at most ~0.9% — the design loses slowly in chop and is paid by
bursts.

Deterministic: float64 indicator math on the closes only; no clock, no
randomness, no environment. `main.py` is the entrypoint;
`vendor/makefun_bars.py` is the kit's SDK shim, byte-identical to the
kit's `sdk/makefun_bars.py`.

## Run it

The grader runs `python3 -P -s /bot/main.py` (Python 3.13). Locally:

```sh
node cli/makefun.mjs grade-local --kit . --bot <this repo> --driver process   # from the kit dir
```
