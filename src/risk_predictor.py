#!/usr/bin/env python3
"""
risk_predictor.py — Altman Z-Score trend extrapolation and risk trajectory forecasting.

Fits a linear trend to historical Altman Z observations per supplier and projects
3/6/12-month future values. Flags suppliers approaching distress (<1.81) or grey (<2.99)
zone crossings. Also scores a composite risk trajectory index.

Usage:
  python3 src/risk_predictor.py                   # table output
  python3 src/risk_predictor.py --json            # JSON for dashboard integration
  python3 src/risk_predictor.py --supplier TSMC   # single-supplier detail
  python3 src/risk_predictor.py --crossing        # only suppliers crossing a threshold
"""

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from typing import Optional


# ── historical observations (quarterly snapshots) ─────────────────────────────
# Format: supplier → [(quarter_offset_months, altman_z), ...]
# quarter_offset 0 = current, -3 = 3 months ago, etc.

HISTORICAL_Z = {
    "ZF Friedrichshafen": [
        (-15, 3.4), (-12, 3.2), (-9, 3.0), (-6, 2.8), (-3, 2.4), (0, 1.95),
    ],
    "Leoni AG": [
        (-15, 2.1), (-12, 1.8), (-9, 1.6), (-6, 1.4), (-3, 1.2), (0, 1.1),
    ],
    "Luminar Technologies": [
        (-12, 1.4), (-9, 1.1), (-6, 0.9), (-3, 0.8), (0, 0.6),
    ],
    "Norilsk Nickel": [
        (-15, 2.4), (-12, 2.1), (-9, 1.9), (-6, 1.6), (-3, 1.4), (0, 1.3),
    ],
    "CATL": [
        (-12, 3.4), (-9, 3.3), (-6, 3.2), (-3, 3.1), (0, 3.1),
    ],
    "TSMC": [
        (-12, 4.5), (-9, 4.4), (-6, 4.3), (-3, 4.2), (0, 4.2),
    ],
    "Bosch": [
        (-12, 4.1), (-9, 4.0), (-6, 3.9), (-3, 3.8), (0, 3.7),
    ],
    "SSAB": [
        (-12, 2.4), (-9, 2.3), (-6, 2.2), (-3, 2.1), (0, 2.1),
    ],
    "Infineon Technologies": [
        (-12, 3.5), (-9, 3.5), (-6, 3.4), (-3, 3.4), (0, 3.4),
    ],
    "Michelin": [
        (-9, 3.4), (-6, 3.4), (-3, 3.3), (0, 3.3),
    ],
    "SQM": [
        (-12, 3.2), (-9, 3.1), (-6, 3.0), (-3, 2.9), (0, 2.9),
    ],
    "JSR Corporation": [
        (-9, 3.3), (-6, 3.2), (-3, 3.2), (0, 3.1),
    ],
    "Mobileye Global": [
        (-6, 3.0), (-3, 2.8), (0, 2.7),
    ],
    "Dana Incorporated": [
        (-9, 2.8), (-6, 2.7), (-3, 2.6), (0, 2.5),
    ],
    "Aptiv": [
        (-9, 3.6), (-6, 3.5), (-3, 3.5), (0, 3.4),
    ],
    "Continental AG": [
        (-12, 2.9), (-9, 2.8), (-6, 2.7), (-3, 2.6), (0, 2.5),
    ],
    "Samsung SDI": [
        (-9, 3.2), (-6, 3.1), (-3, 3.0), (0, 2.9),
    ],
    "Cryoin Engineering": [
        (-6, 1.4), (-3, 1.1), (0, 0.9),
    ],
    "ASML Holding": [
        (-9, 5.1), (-6, 5.0), (-3, 4.9), (0, 4.8),
    ],
}

# Revenue at risk per supplier (€M)
REVENUE_AT_RISK = {
    "ZF Friedrichshafen": 124.5, "Leoni AG": 34.7, "Luminar Technologies": 12.3,
    "Norilsk Nickel": 178.4, "CATL": 820.0, "TSMC": 340.0, "Bosch": 89.2,
    "SSAB": 67.3, "Infineon Technologies": 45.1, "Michelin": 44.0, "SQM": 95.6,
    "JSR Corporation": 220.0, "Mobileye Global": 28.0, "Dana Incorporated": 78.0,
    "Aptiv": 0.0, "Continental AG": 180.0, "Samsung SDI": 55.0,
    "Cryoin Engineering": 85.0, "ASML Holding": 180.0,
}

DISTRESS_THRESHOLD = 1.81
GREY_THRESHOLD = 2.99


@dataclass
class ZTrend:
    slope: float         # Z-units per month
    intercept: float     # current predicted Z (at t=0)
    r_squared: float     # fit quality
    n_points: int


@dataclass
class Forecast:
    supplier: str
    current_z: float
    trend: ZTrend
    z_3m: float
    z_6m: float
    z_12m: float
    revenue_at_risk: float
    trajectory: str          # IMPROVING | STABLE | DECLINING | ACCELERATING_DOWN
    crossings: list = field(default_factory=list)
    months_to_distress: Optional[float] = None
    months_to_grey: Optional[float] = None
    composite_risk: int = 0  # 0-100


def _linreg(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """Simple OLS linear regression. Returns (slope, intercept, r²)."""
    n = len(xs)
    if n < 2:
        return 0.0, ys[-1] if ys else 0.0, 0.0
    x_bar = sum(xs) / n
    y_bar = sum(ys) / n
    ss_xy = sum((x - x_bar) * (y - y_bar) for x, y in zip(xs, ys))
    ss_xx = sum((x - x_bar) ** 2 for x in xs)
    if ss_xx == 0:
        return 0.0, y_bar, 0.0
    slope = ss_xy / ss_xx
    intercept = y_bar - slope * x_bar
    y_pred = [slope * x + intercept for x in xs]
    ss_res = sum((y - yp) ** 2 for y, yp in zip(ys, y_pred))
    ss_tot = sum((y - y_bar) ** 2 for y in ys)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 1.0
    return slope, intercept, max(0.0, r2)


def _months_to_cross(current_z: float, slope: float, threshold: float) -> Optional[float]:
    """Months until Z reaches threshold at current slope. None if moving away."""
    if slope == 0:
        return None
    months = (threshold - current_z) / slope
    return months if months > 0 else None


def _trajectory(slope: float) -> str:
    if slope > 0.05:
        return "IMPROVING"
    if slope < -0.10:
        return "ACCELERATING_DOWN"
    if slope < -0.02:
        return "DECLINING"
    return "STABLE"


def _composite_risk(f: Forecast) -> int:
    """Score 0-100: higher = more at risk. Weighted blend of Z level, trend, proximity to thresholds."""
    z = f.current_z
    # Z-score component (40%): lower Z = higher score
    z_score = max(0, min(100, (4.0 - z) / 4.0 * 100)) * 0.40
    # Trend component (30%): steeper decline = higher score
    trend_score = max(0, min(100, -f.trend.slope * 50 + 50)) * 0.30
    # Crossing proximity (20%): close to crossing = higher score
    prox_score = 0.0
    if f.months_to_distress is not None and f.months_to_distress <= 24:
        prox_score = max(0, (24 - f.months_to_distress) / 24 * 100)
    elif f.months_to_grey is not None and f.months_to_grey <= 18:
        prox_score = max(0, (18 - f.months_to_grey) / 18 * 60)
    prox_score *= 0.20
    # Revenue weight (10%): larger contracts = more risk exposure
    rar = REVENUE_AT_RISK.get(f.supplier, 0)
    rev_score = min(100, rar / 1000 * 100) * 0.10
    return round(z_score + trend_score + prox_score + rev_score)


def forecast_supplier(name: str, observations: list[tuple[int, float]]) -> Forecast:
    xs = [float(o[0]) for o in observations]
    ys = [float(o[1]) for o in observations]
    slope, intercept, r2 = _linreg(xs, ys)

    current_z = ys[-1]
    trend = ZTrend(slope=slope, intercept=intercept, r_squared=r2, n_points=len(xs))

    z_3m  = current_z + slope * 3
    z_6m  = current_z + slope * 6
    z_12m = current_z + slope * 12

    crossings = []
    mtd = _months_to_cross(current_z, slope, DISTRESS_THRESHOLD) if current_z > DISTRESS_THRESHOLD else None
    mtg = _months_to_cross(current_z, slope, GREY_THRESHOLD) if current_z > GREY_THRESHOLD else None

    if mtd is not None and mtd <= 18:
        crossings.append(f"Enters distress (<1.81) in ~{mtd:.0f} months")
    if mtg is not None and mtg <= 12:
        crossings.append(f"Enters grey zone (<2.99) in ~{mtg:.0f} months")

    f = Forecast(
        supplier=name,
        current_z=current_z,
        trend=trend,
        z_3m=max(0, z_3m),
        z_6m=max(0, z_6m),
        z_12m=max(0, z_12m),
        revenue_at_risk=REVENUE_AT_RISK.get(name, 0.0),
        trajectory=_trajectory(slope),
        crossings=crossings,
        months_to_distress=mtd,
        months_to_grey=mtg,
    )
    f.composite_risk = _composite_risk(f)
    return f


def run_all_forecasts() -> list[Forecast]:
    forecasts = []
    for name, obs in HISTORICAL_Z.items():
        forecasts.append(forecast_supplier(name, obs))
    forecasts.sort(key=lambda f: f.composite_risk, reverse=True)
    return forecasts


def print_table(forecasts: list[Forecast], crossing_only: bool = False):
    R = "\033[91m"; Y = "\033[93m"; G = "\033[92m"; C = "\033[96m"
    B = "\033[1m";  X = "\033[0m"

    def z_col(z):
        return R if z < DISTRESS_THRESHOLD else Y if z < GREY_THRESHOLD else G

    print(f"\n{B}Risk Trajectory Forecast — {date.today()}{X}")
    print(f"{'Supplier':<28} {'Z now':>6} {'3M':>6} {'6M':>6} {'12M':>6} "
          f"{'Trend':>7} {'Trajectory':<18} {'R²':>5} {'Risk':>5} {'RAR €M':>7}")
    print("─" * 100)

    shown = 0
    for f in forecasts:
        if crossing_only and not f.crossings:
            continue
        z = f.current_z
        slope_str = f"{f.trend.slope:+.3f}/mo"
        col = z_col(z)
        traj_col = R if "ACCEL" in f.trajectory else Y if f.trajectory == "DECLINING" else G if f.trajectory == "IMPROVING" else C
        print(f"{f.supplier:<28} {col}{z:>6.2f}{X} "
              f"{z_col(f.z_3m)}{f.z_3m:>6.2f}{X} "
              f"{z_col(f.z_6m)}{f.z_6m:>6.2f}{X} "
              f"{z_col(f.z_12m)}{f.z_12m:>6.2f}{X} "
              f"{slope_str:>7} "
              f"{traj_col}{f.trajectory:<18}{X} "
              f"{f.trend.r_squared:>5.2f} {f.composite_risk:>5} {f.revenue_at_risk:>7.0f}")

        for c in f.crossings:
            print(f"  {'':28} {R}⚠ {c}{X}")
        shown += 1

    print()
    print(f"Distress zone: Z < {DISTRESS_THRESHOLD} (red)  |  Grey zone: Z < {GREY_THRESHOLD} (yellow)  |  Safe: Z ≥ {GREY_THRESHOLD} (green)")
    if crossing_only:
        print(f"\nShowing {shown} suppliers with threshold crossings forecast within 18 months.")


def print_supplier_detail(f: Forecast):
    R = "\033[91m"; Y = "\033[93m"; G = "\033[92m"; B = "\033[1m"; X = "\033[0m"

    def zc(z): return R if z < DISTRESS_THRESHOLD else Y if z < GREY_THRESHOLD else G

    print(f"\n{B}{f.supplier} — Risk Trajectory{X}")
    print(f"  Current Z-Score : {zc(f.current_z)}{f.current_z:.2f}{X}")
    print(f"  Trend           : {f.trend.slope:+.4f}/month (R²={f.trend.r_squared:.2f}, n={f.trend.n_points})")
    print(f"  Trajectory      : {f.trajectory}")
    print(f"  Composite risk  : {f.composite_risk}/100")
    print(f"  Revenue at risk : €{f.revenue_at_risk:.0f}M")
    print()
    print(f"  Forecast:")
    print(f"    3  months  : {zc(f.z_3m)}{f.z_3m:.2f}{X}")
    print(f"    6  months  : {zc(f.z_6m)}{f.z_6m:.2f}{X}")
    print(f"    12 months  : {zc(f.z_12m)}{f.z_12m:.2f}{X}")

    if f.months_to_distress:
        est = date.today() + timedelta(days=f.months_to_distress * 30)
        print(f"\n  {R}⚠ Enters distress zone in ~{f.months_to_distress:.0f} months (est. {est.strftime('%Y-%m')}){X}")
    if f.months_to_grey:
        est = date.today() + timedelta(days=f.months_to_grey * 30)
        print(f"\n  {Y}⚠ Enters grey zone in ~{f.months_to_grey:.0f} months (est. {est.strftime('%Y-%m')}){X}")

    print(f"\n  Historical observations:")
    for offset, z in HISTORICAL_Z.get(f.supplier, []):
        obs_date = date.today() + timedelta(days=offset * 30)
        marker = " ← current" if offset == 0 else ""
        col = R if z < DISTRESS_THRESHOLD else Y if z < GREY_THRESHOLD else G
        print(f"    {obs_date.strftime('%Y-%m')}  {col}{z:.2f}{X}{marker}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Supply chain risk trajectory forecaster")
    parser.add_argument("--json", action="store_true", dest="json_out", help="JSON output")
    parser.add_argument("--crossing", action="store_true", help="Only show threshold crossings")
    parser.add_argument("--supplier", type=str, help="Detail for one supplier")
    parser.add_argument("--top", type=int, default=0, help="Limit output to top N by composite risk")
    args = parser.parse_args()

    forecasts = run_all_forecasts()

    if args.top:
        forecasts = forecasts[:args.top]

    if args.supplier:
        match = next((f for f in forecasts if args.supplier.lower() in f.supplier.lower()), None)
        if not match:
            print(f"Supplier not found: {args.supplier}", file=sys.stderr)
            sys.exit(1)
        if args.json_out:
            print(json.dumps(asdict(match), indent=2, default=str))
        else:
            print_supplier_detail(match)
        return

    if args.json_out:
        print(json.dumps([{
            "supplier": f.supplier,
            "current_z": f.current_z,
            "z_3m": f.z_3m, "z_6m": f.z_6m, "z_12m": f.z_12m,
            "slope_per_month": f.trend.slope,
            "r_squared": f.trend.r_squared,
            "trajectory": f.trajectory,
            "crossings": f.crossings,
            "months_to_distress": f.months_to_distress,
            "months_to_grey": f.months_to_grey,
            "composite_risk": f.composite_risk,
            "revenue_at_risk_m": f.revenue_at_risk,
        } for f in forecasts], indent=2))
        return

    print_table(forecasts, crossing_only=args.crossing)
    sys.exit(2 if any(f.months_to_distress and f.months_to_distress <= 6 for f in forecasts) else 0)


if __name__ == "__main__":
    main()
