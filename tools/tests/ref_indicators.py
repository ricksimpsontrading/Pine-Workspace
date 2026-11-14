# SPDX-License-Identifier: Apache-2.0
"""Independent reference implementation for PineTS calibration.

INDEPENDENCE CONTRACT (spec section 24.4.5): expected values are computed
here from the dataset file alone — PineTS is never used as an oracle. This
module also mirrors the 32-bit LCG dataset generator so cross-language
determinism of datasets can be asserted.

Claim type: local mathematical contract (not TradingView correspondence).
EMA seeding conventions differ across implementations; both variants are
computed so a divergence can be characterized precisely.
"""
import json
from pathlib import Path

MASK = 0xFFFFFFFF


def lcg_stream(seed):
    x = seed & MASK
    while True:
        x = (1664525 * x + 1013904223) & MASK
        yield x


def generate_bars(seed, bars, base_cents, vol_cents, t0_ms, tf_ms):
    """Exact mirror of datasets.mjs generateBars (32-bit integer arithmetic)."""
    stream = lcg_stream(seed)
    out = []
    prev_close = base_cents
    for i in range(bars):
        delta = (next(stream) % (2 * vol_cents + 1)) - vol_cents
        o = prev_close
        c = o + delta
        h = max(o, c) + (next(stream) % vol_cents)
        low = min(o, c) - (next(stream) % vol_cents)
        v = 1000 + (next(stream) % 9000)
        out.append({"t": t0_ms + i * tf_ms, "o": o, "h": h, "l": low, "c": c, "v": v})
        prev_close = c
    return out


def round12(v):
    """Mirror of normalize.mjs roundValue: 12 significant digits, -0 -> 0."""
    if v is None:
        return None
    r = float("%.12g" % v)
    return 0.0 if r == 0 else r


def load_dataset(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    scale = data["descriptor"].get("price_scale", 100)
    closes = [b["c"] / scale for b in data["bars"]]
    highs = [b["h"] / scale for b in data["bars"]]
    lows = [b["l"] / scale for b in data["bars"]]
    times = [b["t"] for b in data["bars"]]
    return data, closes, highs, lows, times


def ref_sma(values, length):
    out = []
    for i in range(len(values)):
        if i < length - 1:
            out.append(None)
        else:
            out.append(sum(values[i - length + 1:i + 1]) / length)
    return out


def ref_ema_first_value_seed(values, length):
    """Recurrence e = a*v + (1-a)*e[1], seeded with the first value."""
    alpha = 2.0 / (length + 1)
    out = []
    e = None
    for v in values:
        e = v if e is None else alpha * v + (1 - alpha) * e
        out.append(e)
    return out


def ref_ema_sma_seed(values, length):
    """Same recurrence, na until bar length-1 where it is seeded with SMA."""
    alpha = 2.0 / (length + 1)
    out = []
    e = None
    for i, v in enumerate(values):
        if i < length - 1:
            out.append(None)
            continue
        if e is None:
            e = sum(values[i - length + 1:i + 1]) / length
        else:
            e = alpha * v + (1 - alpha) * e
        out.append(e)
    return out


def ref_prev(values):
    return [None] + list(values[:-1])


def ref_mid(highs, lows):
    return [(h + low) / 2 for h, low in zip(highs, lows)]


def expected_payload_for_core_case(dataset_path):
    """Expected normalized plots for calibration/cases/calib-core.pine."""
    _, closes, highs, lows, times = load_dataset(dataset_path)
    def series(values):
        return [{"t": t, "v": round12(v)} for t, v in zip(times, values)]
    return {
        "SMA5": series(ref_sma(closes, 5)),
        "EMA5_first_value_seed": series(ref_ema_first_value_seed(closes, 5)),
        "EMA5_sma_seed": series(ref_ema_sma_seed(closes, 5)),
        "PREV": series(ref_prev(closes)),
        "MID": series(ref_mid(highs, lows)),
    }


if __name__ == "__main__":
    import sys
    payload = expected_payload_for_core_case(sys.argv[1])
    json.dump(payload, sys.stdout, ensure_ascii=False, sort_keys=True, indent=1)
    sys.stdout.write("\n")
