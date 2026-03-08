#!/usr/bin/env python3
"""
Athens Metro Line C — Optimal Timetable Generator

Optimises train frequency per hour using a multi-objective cost function:
    Total Cost = Passenger Wait Cost + Operating Cost + Peak Crowding Penalty

Airport branch (ΔΟΥΚΙΣΣΗΣ ΠΛΑΚΕΝΤΙΑΣ → ΑΕΡΟΔΡΟΜΙΟ) runs as a fixed 36-minute
overlay independent of main line frequency. Main line departures that coincide
with an airport slot are tagged (A). Standalone airport workings are tagged (A)*.

Calibration notes:
    train_op_cost_weight : 8500  (derived from ~€1,350/train-hour operating cost
                                  converted to passenger-wait-minute equivalents
                                  at €12/hr passenger time value)
    congestion_target    : 0.85  (SLA ceiling — trains added before this is breached)
    peak_congestion_cap  : 0.70  (quality floor during peak — nonlinear crowding
                                  penalty kicks in above this, replicating OASA's
                                  practice of running well below crush capacity
                                  during 06:30–10:00 and 14:00–18:00)
    crowding_penalty_weight: 50000 (scales the quadratic crowding penalty term;
                                    raise to add more trains at peak, lower to reduce)
"""

import math
from typing import List

from predict import Predictor

# ---------------------------------------------------------------------------
# Service parameters
# ---------------------------------------------------------------------------

# Hours with scheduled service. Hour 0 = last overnight service slot.
SERVICE_HOURS = frozenset([0] + list(range(5, 24)))

# Peak windows where crowding quality penalty applies (hour indices).
PEAK_HOURS = frozenset(list(range(7, 10)) + list(range(14, 18)))

# Airport branch fixed headway (minutes) — STASY policy, all days.
AIRPORT_HEADWAY_MINUTES = 36

# A main line departure covers an airport slot if within this tolerance (minutes).
AIRPORT_COINCIDENCE_WINDOW_MINUTES = 2

# Index of branch split station in SUBWAY_STATIONS (ΔΟΥΚΙΣΣΗΣ ΠΛΑΚΕΝΤΙΑΣ, 0-based).
# Stations 23–26 are airport-branch-only beyond this point.
BRANCH_SPLIT_STATION_INDEX = 22


# ---------------------------------------------------------------------------
# Airport branch helpers
# ---------------------------------------------------------------------------

def _airport_departures_for_hour(hour: int) -> list[int]:
    """
    Return sorted departure minutes within `hour` for the airport branch.
    The 36-minute cycle runs continuously from 00:00 across the full day,
    ensuring phase consistency across hour boundaries.
    """
    departures = []
    minute = 0
    while minute < 60 * 24:
        if minute // 60 == hour:
            departures.append(minute % 60)
        elif minute // 60 > hour:
            break
        minute += AIRPORT_HEADWAY_MINUTES
    return sorted(departures)


def _covers_airport_slot(departure_minute: int, airport_minutes: list[int]) -> bool:
    """True if departure_minute falls within the coincidence window of any airport slot."""
    return any(
        abs(departure_minute - a) <= AIRPORT_COINCIDENCE_WINDOW_MINUTES
        for a in airport_minutes
    )


# ---------------------------------------------------------------------------
# Schedule generator
# ---------------------------------------------------------------------------

def generate_optimal_schedule(
    tap_in_data: List[List[int]],
    tap_out_data: List[List[int]],
    train_capacity: int = 1200,
    congestion_target: float = 0.85,
    peak_congestion_cap: float = 0.70,
    crowding_penalty_weight: int = 50_000,
    min_trains_per_hour: int = 4,
    max_trains_per_hour: int = 24,
    train_op_cost_weight: int = 8_500,
    debug: bool = False,
) -> str:
    """
    Generate an optimised hourly timetable for Athens Metro Line C.

    Parameters
    ----------
    tap_in_data              : 27 stations × 24 hours of boarding counts
    tap_out_data             : 27 stations × 24 hours of alighting counts
    train_capacity           : maximum passengers per train
    congestion_target        : hard SLA ceiling (trains added before breach)
    peak_congestion_cap      : quality target during PEAK_HOURS; crowding penalty
                               activates above this fraction of capacity
    crowding_penalty_weight  : scale of the quadratic crowding penalty term;
                               raise to increase peak frequency, lower to reduce
    min_trains_per_hour      : absolute frequency floor
    max_trains_per_hour      : absolute frequency ceiling
    train_op_cost_weight     : operating cost in passenger-wait-minute equivalents
    debug                    : emit per-hour load, congestion, and airport detail

    Returns
    -------
    Formatted timetable string ready for display or logging.
    """
    try:
        NUM_STATIONS = len(tap_in_data)
        NUM_HOURS    = len(tap_in_data[0])
        if (NUM_STATIONS != 27 or NUM_HOURS != 24 or
                len(tap_out_data) != 27 or len(tap_out_data[0]) != 24):
            return "Error: Input data must be 27 stations x 24 hours."
    except (TypeError, IndexError):
        return "Error: Invalid data format. Expected List[List[int]]."

    EFFECTIVE_CAPACITY = train_capacity * congestion_target
    if EFFECTIVE_CAPACITY <= 0:
        return "Error: Effective capacity must be positive."

    lines = [
        "Optimal Metro Schedule (v7: Calibrated Multi-Objective + Airport Overlay)",
        "=" * 74,
        (f"Params: Cap={train_capacity}, SLA={congestion_target*100:.0f}%, "
         f"PeakCap={peak_congestion_cap*100:.0f}%, "
         f"CrowdW={crowding_penalty_weight:,}, "
         f"Min/Max={min_trains_per_hour}/{max_trains_per_hour}, "
         f"OpCost={train_op_cost_weight:,}"),
        f"Airport branch: every {AIRPORT_HEADWAY_MINUTES} min (fixed policy, all service hours)",
        "(A)  = main line train continues to ΑΕΡΟΔΡΟΜΙΟ via airport branch",
        "(A)* = airport branch departure only (no coinciding main line train)",
        "-" * 74,
    ]

    hourly_trains    = [0] * NUM_HOURS
    hourly_peak_load = [0.0] * NUM_HOURS
    total_trains     = 0

    for h in SERVICE_HOURS:

        # ------------------------------------------------------------------
        # Gravity model: precompute prefix/suffix sums for O(n) passes
        # ------------------------------------------------------------------
        suffix_out = [0.0] * (NUM_STATIONS + 1)
        for s in range(NUM_STATIONS - 1, -1, -1):
            suffix_out[s] = suffix_out[s + 1] + tap_out_data[s][h]

        prefix_out = [0.0] * (NUM_STATIONS + 1)
        for s in range(NUM_STATIONS):
            prefix_out[s + 1] = prefix_out[s] + tap_out_data[s][h]

        prefix_in = [0.0] * (NUM_STATIONS + 1)
        for s in range(NUM_STATIONS):
            prefix_in[s + 1] = prefix_in[s] + tap_in_data[s][h]

        total_in = prefix_in[NUM_STATIONS]

        # Direction A: station 0 → 26
        peak_A = 0.0
        load_A = 0.0
        for s in range(NUM_STATIONS - 1):
            w_fwd     = suffix_out[s + 1]
            w_bwd     = prefix_out[s]
            denom     = w_fwd + w_bwd
            r_in      = w_fwd / denom if denom else 0.5
            w_arr_fwd = prefix_in[s]
            w_arr_bwd = total_in - prefix_in[s + 1]
            denom_arr = w_arr_fwd + w_arr_bwd
            r_out     = w_arr_fwd / denom_arr if denom_arr else 0.5
            load_A    = max(0.0, load_A + tap_in_data[s][h] * r_in
                           - tap_out_data[s][h] * r_out)
            if load_A > peak_A:
                peak_A = load_A

        # Direction B: station 26 → 0
        peak_B = 0.0
        load_B = 0.0
        for s in range(NUM_STATIONS - 1, 0, -1):
            w_fwd     = suffix_out[s + 1]
            w_bwd     = prefix_out[s]
            denom     = w_fwd + w_bwd
            r_in      = w_bwd / denom if denom else 0.5
            w_arr_fwd = prefix_in[s]
            w_arr_bwd = total_in - prefix_in[s + 1]
            denom_arr = w_arr_fwd + w_arr_bwd
            r_out     = (total_in - prefix_in[s + 1]) / denom_arr if denom_arr else 0.5
            load_B    = max(0.0, load_B + tap_in_data[s][h] * r_in
                           - tap_out_data[s][h] * r_out)
            if load_B > peak_B:
                peak_B = load_B

        peak_load              = max(peak_A, peak_B)
        hourly_peak_load[h]    = peak_load
        total_hourly_pax       = sum(tap_in_data[s][h] for s in range(NUM_STATIONS))
        is_peak                = h in PEAK_HOURS

        # ------------------------------------------------------------------
        # Minimum trains required to satisfy the congestion SLA
        # ------------------------------------------------------------------
        min_by_sla = (
            math.ceil(peak_load / EFFECTIVE_CAPACITY) if peak_load > 0
            else min_trains_per_hour
        )
        min_k = max(min_trains_per_hour, min_by_sla)

        # ------------------------------------------------------------------
        # Multi-objective cost sweep
        #
        # Total Cost = Passenger Wait Cost
        #            + Operating Cost
        #            + Peak Crowding Penalty (peak hours only)
        #
        # Crowding penalty is quadratic above peak_congestion_cap, which
        # causes the optimiser to aggressively add trains once the quality
        # threshold is breached during peak — replicating OASA's practice
        # of running well below crush capacity during high-demand windows.
        # ------------------------------------------------------------------
        best_k   = min_k
        min_cost = float("inf")

        for k in range(min_k, max_trains_per_hour + 1):
            wait_cost      = total_hourly_pax * 30.0 / k
            operating_cost = k * train_op_cost_weight

            crowding_penalty = 0.0
            if is_peak and k > 0:
                congestion = peak_load / (k * EFFECTIVE_CAPACITY)
                if congestion > peak_congestion_cap:
                    crowding_penalty = (
                        (congestion - peak_congestion_cap) ** 2
                        * crowding_penalty_weight
                    )

            total_cost = wait_cost + operating_cost + crowding_penalty
            if total_cost < min_cost:
                min_cost = total_cost
                best_k   = k

        hourly_trains[h]  = best_k
        total_trains      += best_k

    # --------------------------------------------------------------------------
    # Debug table
    # --------------------------------------------------------------------------
    if debug:
        lines += [
            "",
            "--- DEBUG ---",
            f"Total Main Line Trains Scheduled: {total_trains}",
            "-" * 74,
            (f"{'Hour':<6} | {'Peak Load':<10} | {'Trains':<7} | "
             f"{'Congestion':<11} | {'Peak?':<6} | Airport deps"),
            "-" * 74,
        ]
        for h in sorted(SERVICE_HOURS):
            cap      = hourly_trains[h] * EFFECTIVE_CAPACITY
            cong     = hourly_peak_load[h] / cap if cap > 0 else 0.0
            apt_deps = _airport_departures_for_hour(h)
            apt_str  = ", ".join(f"{h:02d}:{m:02d}" for m in apt_deps) if apt_deps else "-"
            peak_tag = "YES" if h in PEAK_HOURS else "-"
            lines.append(
                f"{h:02d}:00 | {hourly_peak_load[h]:<10.0f} | {hourly_trains[h]:<7} | "
                f"{cong:<11.2f} | {peak_tag:<6} | {apt_str}"
            )
        lines.append("-" * 74)

    # --------------------------------------------------------------------------
    # Timetable output
    # --------------------------------------------------------------------------
    lines.append(
        f"{'Timeframe':<14} | {'Trains':<8} | {'Headway':<10} | "
        f"Departure Times (approx.)"
    )
    lines.append("-" * 74)

    for h in range(NUM_HOURS):
        start_str = f"{h:02d}:00"
        end_str   = "00:00" if h == 23 else f"{h+1:02d}:00"
        timeframe = f"{start_str}-{end_str}"

        if h not in SERVICE_HOURS:
            lines.append(
                f"{timeframe:<14} | {'-':<8} | {'-':<10} | --- No Service ---"
            )
            continue

        k = hourly_trains[h]
        if k == 0:
            lines.append(
                f"{timeframe:<14} | {'0':<8} | {'-':<10} | --- NO TRAINS ALLOCATED ---"
            )
            continue

        headway       = 60.0 / k
        airport_slots = _airport_departures_for_hour(h)
        main_minutes  = [int(i * headway) for i in range(k)]

        # Tag main line departures that absorb an airport slot
        covered_airport = set()
        tagged_main     = []
        for minute in main_minutes:
            is_apt = False
            for apt_min in airport_slots:
                if abs(minute - apt_min) <= AIRPORT_COINCIDENCE_WINDOW_MINUTES:
                    is_apt = True
                    covered_airport.add(apt_min)
                    break
            label = f"{h:02d}:{minute:02d}(A)" if is_apt else f"{h:02d}:{minute:02d}"
            tagged_main.append((minute, label))

        # Standalone airport workings not covered by any main line train
        airport_only = [m for m in airport_slots if m not in covered_airport]

        all_events = list(tagged_main) + [(m, f"{h:02d}:{m:02d}(A)*") for m in airport_only]
        all_events.sort(key=lambda x: x[0])

        times_str    = ", ".join(lbl for _, lbl in all_events)
        apt_extra    = len(airport_only)
        train_display = f"{k}+{apt_extra}(A)" if apt_extra > 0 else str(k)

        lines.append(
            f"{timeframe:<14} | {train_display:<8} | {headway:<4.1f} min  | {times_str}"
        )

    lines += [
        "-" * 74,
        "Legend:",
        "  (A)  = main line train continues to ΑΕΡΟΔΡΟΜΙΟ via branch",
        "  (A)* = airport branch departure only (no coinciding main line train)",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pred = Predictor()
    print("Initializing predictor...")
    pred.init()

    weather = {
        "temperature":  15.0,
        "precipitation": 0.0,
        "cloud_cover":  20.0,
        "wind_speed":   10.0,
    }

    tap_in = [
        [pred.predict(s, "2025-10-17", f"{h:02d}:00", "b", **weather)[0]
         for h in range(24)]
        for s in range(27)
    ]
    tap_out = [
        [pred.predict(s, "2025-10-17", f"{h:02d}:00", "d", **weather)[0]
         for h in range(24)]
        for s in range(27)
    ]

    print(generate_optimal_schedule(
        tap_in,
        tap_out,
        train_capacity=1235,
        congestion_target=0.80,
        peak_congestion_cap=0.70,
        crowding_penalty_weight=50_000,
        min_trains_per_hour=4,
        max_trains_per_hour=24,
        train_op_cost_weight=8_500,
        debug=True,
    ))