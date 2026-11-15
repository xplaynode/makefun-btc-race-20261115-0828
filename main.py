# Burst-rider for the cbBTC/USDC minute-bar race (agent-fun/bars-replay/v1).
#
# Design, from grading every kit baseline and a parameter search on the dev
# window with a replay built on the harness's own fill formulas:
#   - The dev tape is a grinding slide (about -4% over 24h). Buy-and-hold,
#     momentum, EMA-cross, ADX and RSI/Bollinger baselines all finish under
#     water there: in a slide, dip-buying catches falling knives and slow
#     trend systems whipsaw. What pays is the opposite posture: stay in cash
#     and buy only a genuine burst of strength, then let a trailing stop
#     harvest it.
#   - Entry: the close at least +1.0% above its close 30 bars earlier. That
#     bar is rare (a handful per day), large next to the ~26 bps a full-size
#     round trip costs, and it marks capitulation bounces and real breakouts
#     alike, in either regime. Sized at 95% of equity: one position, no adds.
#   - Exits: a 0.8% hard stop under cost (valued at the close), a 0.55%
#     trailing stop under the best close since entry, and a 180-bar time
#     stop. No fixed take-profit: the trail is what lets one strong leg pay
#     for several small stopped bursts.
#   - A 30-bar cooldown after every exit keeps chop from re-triggering the
#     bot into the same failed burst.
#   - Guardrail probe: the ranking asks for at least one trade. If nothing
#     has qualified by bar 1200, one 25%-of-equity probe is taken on mild
#     evidence (close above its EMA(20) with a positive 30-bar return, or
#     any non-falling close after bar 1380), stop-bounded like any trade.
#     On the dev window the burst rule fires long before, so the probe
#     never trades there.
# All indicator math is float64 on + - * / over the closes, correctly
# rounded (IEEE 754), so the same bars give the same orders in both graded
# executions. No clock, no randomness, no environment: the bars are the
# only input. hello, batch, orders and bar handling goes through the
# vendored SDK shim (vendor/makefun_bars.py, byte-identical to the kit's).

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"
#: Entry: trailing return over WIN bars must reach THR.
WIN = 30
THR = 0.010
#: Share of equity one entry deploys.
SIZE = 0.95
#: Trailing stop under the best close since entry.
TRAIL = 0.0055
#: Hard stop: position value under cost by this share.
STOP = 0.008
#: A position held this many bars is closed whatever it shows.
MAX_HOLD = 180
#: Bars to sit out after an exit.
COOLDOWN = 30
#: Runaway guard: never more than this many entries in one window. The
#: burst rule fires a handful of times a day, so this never binds in
#: practice; it only caps the damage if a future tape turns pathological.
MAX_ENTRIES = 24
#: Slippage cap on every order, in bps past the decision close.
SLIP_BPS = 300
#: Probe: first bar it may fire, the bar from which it needs no evidence,
#: and its size as a share of equity.
PROBE_AFTER = 1200
PROBE_HARD = 1380
PROBE_SIZE = 0.25
#: EMA span for the probe's mild-evidence test.
EMA_SPAN = 20

closes = []
ema = None
ema_warm = []
bar_idx = -1
entries = 0
entry_bar = None
best_close = None
cooldown = 0


def _push_indicators(close):
    global ema
    closes.append(close)
    if ema is None:
        ema_warm.append(close)
        if len(ema_warm) == EMA_SPAN:
            ema = sum(ema_warm) / EMA_SPAN
    else:
        ema = ema + (2.0 / (EMA_SPAN + 1)) * (close - ema)


def on_batch(state, batch):
    global bar_idx, entries, entry_bar, best_close, cooldown
    bar = None
    for b in batch["bars"]:
        if b["symbol"] == SYMBOL:
            bar = b
            break
    if bar is None:
        return []
    bar_idx += 1
    close = int(bar["c"])
    _push_indicators(close)
    if state.warming_up:
        return []
    if cooldown > 0:
        cooldown -= 1
    held = state.positions.get(SYMBOL)
    if held is not None:
        if best_close is None or close > best_close:
            best_close = close
        value = state.value(SYMBOL, held.qty)
        ret = value / held.cost - 1 if held.cost else 0.0
        exit_now = False
        if ret <= -STOP:
            exit_now = True
        if best_close is not None and close <= best_close * (1 - TRAIL):
            exit_now = True
        if entry_bar is not None and bar_idx - entry_bar >= MAX_HOLD:
            exit_now = True
        if exit_now:
            entry_bar = None
            best_close = None
            cooldown = COOLDOWN
            return [{"side": "sell", "symbol": SYMBOL, "qty": held.qty,
                     "max_slippage_bps": SLIP_BPS}]
        return []
    # Flat. Guardrail probe first: only while nothing has ever qualified.
    if entries == 0 and bar_idx >= PROBE_AFTER:
        mild = False
        if bar_idx >= WIN and ema is not None:
            mild = close > ema and (close / closes[-1 - WIN] - 1) > 0
        hard = bar_idx >= PROBE_HARD and close >= closes[-2]
        if mild or hard:
            notional = int(state.equity * PROBE_SIZE)
            if notional < 1_000_000:
                return []
            entries += 1
            entry_bar = bar_idx
            best_close = close
            return [{"side": "buy", "symbol": SYMBOL,
                     "notional_quote_units": notional,
                     "max_slippage_bps": SLIP_BPS}]
    if cooldown > 0 or bar_idx < WIN + 2 or entries >= MAX_ENTRIES:
        return []
    momentum = close / closes[-1 - WIN] - 1
    if momentum < THR:
        return []
    notional = int(state.equity * SIZE)
    if notional < 1_000_000:
        return []
    entries += 1
    entry_bar = bar_idx
    best_close = close
    return [{"side": "buy", "symbol": SYMBOL,
             "notional_quote_units": notional,
             "max_slippage_bps": SLIP_BPS}]


if __name__ == "__main__":
    makefun_bars.run(on_batch)
