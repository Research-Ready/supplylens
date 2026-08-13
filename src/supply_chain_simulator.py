"""Supply Chain Monte Carlo Simulator — UC4

Runs N=10,000 trials per scenario to produce P10/P50/P90 disruption cost estimates,
correlation-adjusted portfolio risk, and time-to-recovery distributions.

Usage:
    python3 src/supply_chain_simulator.py [--scenarios all] [--trials 10000]
                                          [--json] [--product SCANIA-R-500]
"""
import argparse
import json
import math
import os
import random
import sys
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

SCANIA_ANNUAL_REVENUE_EUR = 19_500_000_000
PROD_DAYS = 250
DAILY_REV = SCANIA_ANNUAL_REVENUE_EUR / PROD_DAYS   # ~78M/day

# ── Scenario definitions ────────────────────────────────────────────────────────
# halt_days: (min, mode, max) triangular distribution
# prob_annual: probability of event occurring in any given year
# corr_group: correlated scenario groups — if A fires, B prob multiplied
# alt_cost_pct: alternative sourcing premium as % of contract_value_eur
# products: affected SKUs
# cbam_delta_eur: change in CBAM liability if scenario fires

SCENARIOS: Dict[str, dict] = {
    "CATL_DEFAULT": {
        "name": "CATL Payment/Delivery Default",
        "supplier": "CATL",
        "country": "CN",
        "type": "FINANCIAL",
        "prob_annual": 0.08,
        "halt_days": (5, 18, 60),
        "contract_value_eur": 820_000_000,
        "alt_cost_pct": 0.35,
        "legal_exposure_eur": 120_000_000,
        "cbam_delta_eur": 0,
        "corr_group": "CHINA_RISK",
        "products": ["SCANIA-L-340-BEV"],
        "alt_suppliers": ["Samsung SDI", "LG Energy Solution", "Northvolt"],
        "alt_capacity_pct": 45,
    },
    "XINJIANG_BAN": {
        "name": "UFLPA Xinjiang Ban — Battery Materials",
        "supplier": "Shanshan / Ganfeng",
        "country": "CN",
        "type": "REGULATORY",
        "prob_annual": 0.20,
        "halt_days": (30, 90, 180),
        "contract_value_eur": 180_000_000,
        "alt_cost_pct": 0.25,
        "legal_exposure_eur": 25_000_000,
        "cbam_delta_eur": 8_500_000,
        "corr_group": "CHINA_RISK",
        "products": ["SCANIA-L-340-BEV"],
        "alt_suppliers": ["Umicore BM", "BASF Battery Materials"],
        "alt_capacity_pct": 55,
    },
    "NORILSK_FULL_SANC": {
        "name": "Norilsk Nickel Full OFAC Sanction",
        "supplier": "Norilsk Nickel",
        "country": "RU",
        "type": "SANCTIONS",
        "prob_annual": 0.15,
        "halt_days": (60, 120, 365),
        "contract_value_eur": 280_000_000,
        "alt_cost_pct": 0.40,
        "legal_exposure_eur": 80_000_000,
        "cbam_delta_eur": 24_000_000,
        "corr_group": "RUSSIA_RISK",
        "products": ["SCANIA-L-340-BEV"],
        "alt_suppliers": ["Vale Nickel", "Norilsk-alt Glencore", "BHP"],
        "alt_capacity_pct": 70,
    },
    "RUSSIA_SUPPLY_HALT": {
        "name": "Russia-EU Supply Halt (energy + materials)",
        "supplier": "Multiple RU",
        "country": "RU",
        "type": "GEOPOLITICAL",
        "prob_annual": 0.12,
        "halt_days": (30, 90, 270),
        "contract_value_eur": 350_000_000,
        "alt_cost_pct": 0.30,
        "legal_exposure_eur": 45_000_000,
        "cbam_delta_eur": 35_000_000,
        "corr_group": "RUSSIA_RISK",
        "products": ["SCANIA-R-500", "SCANIA-L-340-BEV"],
        "alt_suppliers": ["Diversified non-RU sources"],
        "alt_capacity_pct": 60,
    },
    "UKRAINE_WIRING": {
        "name": "Ukraine Wiring Harness Disruption (Aptiv/Leoni)",
        "supplier": "Aptiv / Leoni AG",
        "country": "UA",
        "type": "CONFLICT",
        "prob_annual": 0.30,
        "halt_days": (7, 21, 60),
        "contract_value_eur": 190_000_000,
        "alt_cost_pct": 0.20,
        "legal_exposure_eur": 30_000_000,
        "cbam_delta_eur": 0,
        "corr_group": "RUSSIA_RISK",
        "products": ["SCANIA-R-500", "SCANIA-G-410"],
        "alt_suppliers": ["TE Connectivity", "Dräxlmaier", "Sumitomo Electric"],
        "alt_capacity_pct": 60,
    },
    "PALLADIUM_SHORTAGE": {
        "name": "Palladium Supply Crisis (Norilsk sanctions + Zimbabwe floods)",
        "supplier": "Norilsk / Sibanye",
        "country": "RU",
        "type": "SHORTAGE",
        "prob_annual": 0.10,
        "halt_days": (14, 45, 120),
        "contract_value_eur": 95_000_000,
        "alt_cost_pct": 0.55,   # precious metal premium
        "legal_exposure_eur": 10_000_000,
        "cbam_delta_eur": 0,
        "corr_group": "RUSSIA_RISK",
        "products": ["SCANIA-R-500", "SCANIA-G-410"],
        "alt_suppliers": ["Sibanye-Stillwater", "Anglo American Platinum"],
        "alt_capacity_pct": 40,
    },
    "CHINA_EXPORT_CTRL": {
        "name": "China Export Controls — Rare Earths + Polysilicon",
        "supplier": "China Rare Earth Group / Shanshan",
        "country": "CN",
        "type": "REGULATORY",
        "prob_annual": 0.18,
        "halt_days": (90, 180, 365),
        "contract_value_eur": 640_000_000,
        "alt_cost_pct": 0.45,
        "legal_exposure_eur": 90_000_000,
        "cbam_delta_eur": 15_000_000,
        "corr_group": "CHINA_RISK",
        "products": ["SCANIA-L-340-BEV", "SCANIA-R-500"],
        "alt_suppliers": ["MP Materials (US)", "Lynas (AU)", "REEtec (NO)"],
        "alt_capacity_pct": 30,
    },
    "SSAB_STRIKE": {
        "name": "SSAB / Steel Supply Strike (Nordic labour action)",
        "supplier": "SSAB",
        "country": "SE",
        "type": "LABOUR",
        "prob_annual": 0.06,
        "halt_days": (7, 28, 60),
        "contract_value_eur": 310_000_000,
        "alt_cost_pct": 0.18,
        "legal_exposure_eur": 20_000_000,
        "cbam_delta_eur": 5_000_000,
        "corr_group": None,
        "products": ["SCANIA-R-500", "SCANIA-T-500", "SCANIA-G-410"],
        "alt_suppliers": ["ArcelorMittal", "Tata Steel Europe", "Saarstahl AG"],
        "alt_capacity_pct": 75,
    },
    "ATACAMA_QUAKE": {
        "name": "Atacama Lithium Region Earthquake (SQM / Albemarle)",
        "supplier": "SQM / Albemarle",
        "country": "CL",
        "type": "NATURAL_DISASTER",
        "prob_annual": 0.05,
        "halt_days": (30, 75, 180),
        "contract_value_eur": 120_000_000,
        "alt_cost_pct": 0.30,
        "legal_exposure_eur": 15_000_000,
        "cbam_delta_eur": 6_000_000,
        "corr_group": None,
        "products": ["SCANIA-L-340-BEV"],
        "alt_suppliers": ["Ganfeng Lithium", "Livent", "Sigma Lithium"],
        "alt_capacity_pct": 50,
    },
    "CHIP_SHORTAGE_REPEAT": {
        "name": "Semiconductor Shortage Repeat (STMicro / Infineon)",
        "supplier": "STMicroelectronics / Infineon",
        "country": "CH",
        "type": "SHORTAGE",
        "prob_annual": 0.15,
        "halt_days": (30, 90, 270),
        "contract_value_eur": 240_000_000,
        "alt_cost_pct": 0.35,
        "legal_exposure_eur": 40_000_000,
        "cbam_delta_eur": 0,
        "corr_group": None,
        "products": ["SCANIA-R-500", "SCANIA-G-410", "SCANIA-ENG-DC09"],
        "alt_suppliers": ["NXP Semiconductors", "Renesas", "Texas Instruments"],
        "alt_capacity_pct": 55,
    },
    "SUEZ_CLOSURE": {
        "name": "Suez Canal Closure (Houthi escalation)",
        "supplier": "Maritime logistics",
        "country": "EG",
        "type": "LOGISTICS",
        "prob_annual": 0.20,
        "halt_days": (14, 35, 90),
        "contract_value_eur": 0,
        "alt_cost_pct": 0.0,
        "legal_exposure_eur": 0,
        "cbam_delta_eur": 0,
        "extra_logistics_eur": 85_000_000,  # Cape of Good Hope re-routing
        "corr_group": None,
        "products": ["SCANIA-R-500", "SCANIA-L-340-BEV"],
        "alt_suppliers": ["Cape of Good Hope routing", "Air freight (premium)"],
        "alt_capacity_pct": 90,
    },
}

# Correlation matrix for correlated scenario groups
# P(B fires | A fires) multiplier on B's probability
CORR_MULTIPLIERS = {
    ("RUSSIA_RISK", "RUSSIA_RISK"): 2.5,  # Russia scenarios cluster
    ("CHINA_RISK",  "CHINA_RISK"):  2.0,  # China scenarios cluster
}


def _triangular_sample(a: float, c: float, b: float) -> float:
    """Sample from triangular distribution [a, b] with mode c."""
    u = random.random()
    fc = (c - a) / (b - a)
    if u < fc:
        return a + math.sqrt(u * (b - a) * (c - a))
    else:
        return b - math.sqrt((1 - u) * (b - a) * (b - c))


def _compute_impact(sc: dict, halt_days: float) -> dict:
    """Compute financial impact for a single scenario fire."""
    revenue_at_risk = halt_days * DAILY_REV
    # Only affected products contribute proportionally
    prod_frac = len(sc["products"]) / 5  # 5 total products in demo
    revenue_at_risk *= min(1.0, prod_frac * 1.8)  # adjustment for product coverage

    alt_capacity = sc.get("alt_capacity_pct", 50) / 100
    alt_transition_days = halt_days * (1 - alt_capacity) * 0.5
    alt_cost = sc["contract_value_eur"] * sc["alt_cost_pct"] * (halt_days / 90)
    extra_logistics = sc.get("extra_logistics_eur", 0)

    total = (
        revenue_at_risk
        + alt_cost
        + sc["legal_exposure_eur"]
        + sc.get("cbam_delta_eur", 0)
        + extra_logistics
    )
    return {
        "revenue_at_risk": revenue_at_risk,
        "alt_cost":        alt_cost,
        "legal_exposure":  sc["legal_exposure_eur"],
        "cbam_delta":      sc.get("cbam_delta_eur", 0),
        "extra_logistics": extra_logistics,
        "halt_days":       halt_days,
        "total":           total,
    }


def run_monte_carlo(
    scenario_ids: Optional[List[str]] = None,
    n_trials: int = 10_000,
    seed: int = 42,
) -> dict:
    """Run N_TRIALS Monte Carlo simulation.

    Returns per-scenario P10/P50/P90, portfolio totals, and correlation stats.
    """
    random.seed(seed)
    scen_list = [SCENARIOS[sid] for sid in (scenario_ids or list(SCENARIOS.keys()))]
    scen_ids = scenario_ids or list(SCENARIOS.keys())

    # Per-scenario outcome lists
    outcomes: Dict[str, List[float]] = defaultdict(list)
    halt_days_dist: Dict[str, List[float]] = defaultdict(list)
    portfolio_totals: List[float] = []

    for _ in range(n_trials):
        trial_total = 0.0
        fired_groups = set()

        for sid, sc in zip(scen_ids, scen_list):
            p = sc["prob_annual"]

            # Correlation boost: if a correlated group already fired
            if sc.get("corr_group"):
                for grp in fired_groups:
                    mult = CORR_MULTIPLIERS.get(
                        (grp, sc["corr_group"]),
                        CORR_MULTIPLIERS.get((sc["corr_group"], grp), 1.0)
                    )
                    p = min(0.99, p * mult)

            fires = random.random() < p
            if fires:
                if sc.get("corr_group"):
                    fired_groups.add(sc["corr_group"])
                a, c, b = sc["halt_days"]
                halt = _triangular_sample(a, c, b)
                impact = _compute_impact(sc, halt)
                outcomes[sid].append(impact["total"])
                halt_days_dist[sid].append(halt)
                trial_total += impact["total"]
            else:
                outcomes[sid].append(0.0)
                halt_days_dist[sid].append(0.0)

        portfolio_totals.append(trial_total)

    def percentile(data: List[float], pct: float) -> float:
        sorted_d = sorted(data)
        idx = (len(sorted_d) - 1) * pct / 100
        lo, hi = int(idx), min(int(idx) + 1, len(sorted_d) - 1)
        return sorted_d[lo] + (sorted_d[hi] - sorted_d[lo]) * (idx - lo)

    def scenario_stats(sid: str, sc: dict) -> dict:
        vals = outcomes[sid]
        halts = halt_days_dist[sid]
        nonzero = [v for v in vals if v > 0]
        nonzero_h = [h for h in halts if h > 0]
        fire_rate = len(nonzero) / len(vals)
        return {
            "id":          sid,
            "name":        sc["name"],
            "supplier":    sc["supplier"],
            "type":        sc["type"],
            "prob_annual": sc["prob_annual"],
            "fire_rate":   round(fire_rate, 4),
            "p10":         round(percentile(vals, 10)),
            "p50":         round(percentile(vals, 50)),
            "p90":         round(percentile(vals, 90)),
            "expected":    round(sum(vals) / len(vals)),
            "max_single":  round(max(vals)),
            "halt_p50":    round(percentile(nonzero_h, 50) if nonzero_h else 0, 1),
            "halt_p90":    round(percentile(nonzero_h, 90) if nonzero_h else 0, 1),
            "products":    sc["products"],
            "alt_suppliers": sc.get("alt_suppliers", []),
            "alt_capacity_pct": sc.get("alt_capacity_pct", 50),
        }

    scenario_results = [scenario_stats(sid, sc) for sid, sc in zip(scen_ids, scen_list)]
    scenario_results.sort(key=lambda x: x["expected"], reverse=True)

    portfolio_p10  = round(percentile(portfolio_totals, 10))
    portfolio_p50  = round(percentile(portfolio_totals, 50))
    portfolio_p90  = round(percentile(portfolio_totals, 90))
    portfolio_mean = round(sum(portfolio_totals) / len(portfolio_totals))

    # Sensitivity: contribution of each scenario to portfolio variance
    portfolio_var = sum((t - portfolio_mean) ** 2 for t in portfolio_totals) / len(portfolio_totals)
    sensitivity = {}
    for sid in scen_ids:
        cov = sum(
            (outcomes[sid][i] - (sum(outcomes[sid]) / n_trials))
            * (portfolio_totals[i] - portfolio_mean)
            for i in range(n_trials)
        ) / n_trials
        sensitivity[sid] = round(cov / portfolio_var * 100, 1) if portfolio_var > 0 else 0

    # Histogram data for portfolio totals (20 buckets)
    min_t, max_t = min(portfolio_totals), max(portfolio_totals)
    bucket_size = (max_t - min_t) / 20 if max_t > min_t else 1
    hist_buckets = [0] * 20
    for t in portfolio_totals:
        idx = min(19, int((t - min_t) / bucket_size))
        hist_buckets[idx] += 1
    histogram = [
        {"x": round(min_t + i * bucket_size), "count": hist_buckets[i]}
        for i in range(20)
    ]

    return {
        "n_trials":     n_trials,
        "n_scenarios":  len(scen_ids),
        "scenarios":    scenario_results,
        "portfolio": {
            "p10":       portfolio_p10,
            "p50":       portfolio_p50,
            "p90":       portfolio_p90,
            "expected":  portfolio_mean,
            "histogram": histogram,
        },
        "sensitivity": {
            sid: sensitivity.get(sid, 0) for sid in scen_ids
        },
        "annual_revenue": SCANIA_ANNUAL_REVENUE_EUR,
        "daily_revenue":  round(DAILY_REV),
    }


def print_report(data: dict) -> None:
    p = data["portfolio"]
    print(f"\n{'='*70}")
    print(f"  Monte Carlo Simulation  —  {data['n_trials']:,} trials, {data['n_scenarios']} scenarios")
    print(f"{'='*70}")
    print(f"  Portfolio Annual Risk (EUR):")
    print(f"    P10: €{p['p10']/1e9:.2f}B   P50: €{p['p50']/1e9:.2f}B   "
          f"P90: €{p['p90']/1e9:.2f}B   Expected: €{p['expected']/1e9:.2f}B")
    print(f"\n  Scenario Breakdown (sorted by Expected impact):")
    print(f"  {'Scenario':<40} {'P50':>10} {'P90':>10} {'ExpImpact':>10} {'FireRate':>8}")
    print(f"  {'-'*40} {'-'*10} {'-'*10} {'-'*10} {'-'*8}")
    for sc in data["scenarios"]:
        p50 = f"€{sc['p50']/1e6:.0f}M" if sc['p50'] > 0 else "€0"
        p90 = f"€{sc['p90']/1e6:.0f}M" if sc['p90'] > 0 else "€0"
        exp = f"€{sc['expected']/1e6:.0f}M" if sc['expected'] > 0 else "€0"
        rate = f"{sc['fire_rate']*100:.1f}%"
        print(f"  {sc['name'][:40]:<40} {p50:>10} {p90:>10} {exp:>10} {rate:>8}")
    print(f"\n  Top Sensitivity Drivers:")
    sens = sorted(data["sensitivity"].items(), key=lambda x: abs(x[1]), reverse=True)
    for sid, pct in sens[:5]:
        sc = next(s for s in data["scenarios"] if s["id"] == sid)
        print(f"    {sc['name'][:50]:<50} {pct:>6.1f}% of portfolio variance")
    print()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", nargs="*", default=None,
                    help="Scenario IDs (default: all). Use --list to see them.")
    ap.add_argument("--trials", type=int, default=10_000)
    ap.add_argument("--seed",   type=int, default=42)
    ap.add_argument("--json",   action="store_true")
    ap.add_argument("--list",   action="store_true")
    args = ap.parse_args()

    if args.list:
        for sid, sc in SCENARIOS.items():
            print(f"  {sid:<30} {sc['name']}")
        sys.exit(0)

    ids = args.scenarios if args.scenarios else list(SCENARIOS.keys())
    invalid = [i for i in ids if i not in SCENARIOS]
    if invalid:
        print(f"Unknown scenarios: {invalid}", file=sys.stderr)
        sys.exit(1)

    result = run_monte_carlo(ids, n_trials=args.trials, seed=args.seed)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_report(result)
