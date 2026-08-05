"""
Customer base and the order calendar.

The design decision that matters: lifetime order count is drawn from a
channel-specific geometric distribution, and the inter-purchase gap is also
channel-specific. That single mechanism produces realistic cohort retention
curves *and* Finding 4 (Google Search customers are worth multiples of TikTok
customers) without either being hard-coded as an output.

Acquisition channel is frozen at first order and never reassigned. Everything
downstream in the cohort analysis depends on that.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from . import config as C

_FIRST = ["James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael",
          "Linda", "David", "Elizabeth", "William", "Barbara", "Richard",
          "Susan", "Joseph", "Jessica", "Thomas", "Sarah", "Chris", "Karen",
          "Daniel", "Nancy", "Matthew", "Lisa", "Anthony", "Betty", "Mark",
          "Sandra", "Donald", "Ashley", "Steven", "Kimberly", "Andrew", "Emily",
          "Joshua", "Donna", "Kevin", "Michelle", "Brian", "Carol", "Miguel",
          "Aisha", "Wei", "Priya", "Diego", "Fatima", "Jamal", "Sofia"]
_LAST = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
         "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
         "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
         "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
         "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King",
         "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Patel",
         "Okafor", "Chen", "Kowalski", "Rossi", "Dubois"]
_DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "icloud.com", "hotmail.com",
            "proton.me", "aol.com"]


def _daily_acquisition_weights(year: int) -> tuple[list[dt.date], np.ndarray]:
    """Seasonality-weighted probability of acquiring a customer on each day."""
    days, weights = [], []
    d = dt.date(year, 1, 1)
    bf_start, bf_end = C.BFCM_DATES[year]
    while d.year == year:
        w = C.MONTH_SEASONALITY[d.month] * C.DOW_SEASONALITY[d.weekday()]
        if bf_start <= d <= bf_end:
            w *= C.BFCM_SPIKE
        days.append(d)
        weights.append(w)
        d += dt.timedelta(days=1)
    arr = np.asarray(weights, dtype=float)
    return days, arr / arr.sum()


def build_customers(rng: np.random.Generator, geo: pd.DataFrame) -> pd.DataFrame:
    frames = []
    seq = 0

    channels = list(C.ACQUISITION_CHANNELS)
    channel_shares = np.array([C.ACQUISITION_CHANNELS[c][0] for c in channels])
    channel_shares = channel_shares / channel_shares.sum()

    for year, n in C.NEW_CUSTOMERS_PER_YEAR.items():
        days, probs = _daily_acquisition_weights(year)
        first_dates = rng.choice(len(days), size=n, p=probs)

        frames.append(pd.DataFrame({
            "customer_key": [f"C{seq + i:07d}" for i in range(n)],
            "first_order_date": [days[i] for i in first_dates],
            "acquisition_channel": rng.choice(channels, size=n, p=channel_shares),
        }))
        seq += n

    cust = pd.concat(frames, ignore_index=True)
    cust = cust.sort_values("first_order_date").reset_index(drop=True)

    # ---- Identity -------------------------------------------------------
    cust["first_name"] = rng.choice(_FIRST, size=len(cust))
    cust["last_name"] = rng.choice(_LAST, size=len(cust))
    cust["email"] = [
        f"{f.lower()}.{l.lower()}{rng.integers(1, 9999)}@{d}"
        for f, l, d in zip(cust["first_name"], cust["last_name"],
                           rng.choice(_DOMAINS, size=len(cust)))
    ]

    # ---- Home state -----------------------------------------------------
    cust["state_code"] = rng.choice(
        geo["state_code"].to_numpy(), size=len(cust),
        p=geo["demand_weight"].to_numpy()
    )

    # ---- Channel behavioral parameters ---------------------------------
    prop = cust["acquisition_channel"].map(
        {c: v[2] for c, v in C.ACQUISITION_CHANNELS.items()})
    cust["repeat_propensity"] = prop.astype(float)
    cust["discount_affinity"] = cust["acquisition_channel"].map(
        {c: v[3] for c, v in C.ACQUISITION_CHANNELS.items()}).astype(float)
    cust["return_uplift"] = cust["acquisition_channel"].map(
        {c: v[4] for c, v in C.ACQUISITION_CHANNELS.items()}).astype(float)

    # Individual heterogeneity around the channel mean, clipped to (0, 0.85)
    noise = rng.normal(0, 0.07, len(cust))
    cust["repeat_propensity"] = np.clip(cust["repeat_propensity"] + noise, 0.01, 0.85)

    cust["cohort_month"] = pd.to_datetime(cust["first_order_date"]).dt.to_period("M").astype(str)
    return cust


def build_order_calendar(rng: np.random.Generator, cust: pd.DataFrame) -> pd.DataFrame:
    """One row per (customer, order sequence). Dates only -- no basket yet."""
    p_repeat = cust["repeat_propensity"].to_numpy()

    # Lifetime orders = 1 + Geometric(1 - p). Mean extra orders = p / (1 - p).
    extra = rng.geometric(1.0 - p_repeat, size=len(cust)) - 1
    extra = np.minimum(extra, 24)  # guard against the tail
    n_orders = 1 + extra

    cust_idx = np.repeat(np.arange(len(cust)), n_orders)
    order_seq = np.concatenate([np.arange(k) for k in n_orders])

    # Inter-purchase gap: gamma, mean shrinks as propensity rises.
    mean_gap = 210.0 - 180.0 * p_repeat[cust_idx]
    shape = 1.8
    gaps = rng.gamma(shape, mean_gap / shape)
    gaps = np.where(order_seq == 0, 0.0, np.maximum(gaps, 3.0))

    first = pd.to_datetime(cust["first_order_date"]).to_numpy()[cust_idx]
    offsets = pd.Series(gaps).groupby(cust_idx).cumsum().to_numpy()
    order_date = first + pd.to_timedelta(np.round(offsets), unit="D").to_numpy()

    cal = pd.DataFrame({
        "customer_key": cust["customer_key"].to_numpy()[cust_idx],
        "order_seq": order_seq,
        "order_date": order_date,
    })

    # Drop orders that fall outside the observation window.
    cal = cal[cal["order_date"] <= pd.Timestamp(C.END_DATE)].copy()

    # Seasonal thinning of *repeat* orders: high season pulls demand forward.
    # First orders already carry seasonality from the acquisition curve.
    month = pd.DatetimeIndex(cal["order_date"]).month
    season = pd.Series(month).map(C.MONTH_SEASONALITY).to_numpy()
    keep_p = np.where(cal["order_seq"].to_numpy() == 0, 1.0,
                      np.clip(season / max(C.MONTH_SEASONALITY.values()) + 0.45, 0, 1))
    cal = cal[rng.random(len(cal)) < keep_p].copy()

    # A customer's first surviving order defines is_first_order.
    cal = cal.sort_values(["customer_key", "order_date"]).reset_index(drop=True)
    cal["is_first_order"] = ~cal.duplicated("customer_key")
    return cal
