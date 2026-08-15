"""
dual_sourcing.py — Dual sourcing optimizer

Given a supplier portfolio with risk scores and transition costs,
recommends which suppliers to dual-source first, within a budget.

Uses a greedy risk-weighted priority algorithm (not LP — keeps it
dependency-free and fast).

Usage:
  python3 src/dual_sourcing.py --demo
  python3 src/dual_sourcing.py --budget 5000000 --json
  python3 src/dual_sourcing.py --supplier "TSMC" --show-alts
  python3 src/dual_sourcing.py --critical-only
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Alternative:
    name: str
    country: str
    qualification_cost_keur: float    # one-time cost to qualify this supplier
    transition_months: int            # months to fully transition
    capacity_match_pct: float         # % of current supplier capacity they can cover
    risk_score: int                   # 0–100, their own risk score
    quality_match: str                # FULL | PARTIAL | LIMITED
    notes: str = ""


@dataclass
class SupplierRecord:
    name: str
    country: str
    tier: int
    risk_score: int
    flags: list[str]
    revenue_at_risk_m: float        # EUR M/year if this supplier fails
    annual_spend_m: float           # EUR M/year we buy from them
    is_single_source: bool
    category: str
    alternatives: list[Alternative]
    current_coverage_pct: float = 100.0  # % of demand from single source


@dataclass
class DualSourcingRecommendation:
    supplier: str
    alternative: Alternative
    priority_score: float           # higher = more urgent
    qualification_cost_keur: float
    expected_risk_reduction_pct: float
    roi_months: int                 # months to recover qualification cost via risk reduction
    action: str                     # "IMMEDIATE" | "SHORT_TERM" | "MEDIUM_TERM" | "MONITOR"
    rationale: str


# ── Data ─────────────────────────────────────────────────────────────────────

SUPPLIERS: list[SupplierRecord] = [
    SupplierRecord(
        name="TSMC",
        country="Taiwan", tier=1, risk_score=84,
        flags=["GEOPOLITICAL_RISK", "EXPORT_CTRL", "SINGLE_SOURCE"],
        revenue_at_risk_m=680,
        annual_spend_m=170,
        is_single_source=True,
        category="Semiconductors",
        alternatives=[
            Alternative("Samsung Foundry", "South Korea", 1800, 36, 60, 62, "PARTIAL",
                        "Needs N+1 node process adaptation; 2nm gap"),
            Alternative("Intel Foundry Services", "USA", 2400, 42, 40, 58, "LIMITED",
                        "Process migration significant; positive geopolitical profile"),
            Alternative("GlobalFoundries", "USA/Germany", 900, 18, 30, 55, "LIMITED",
                        "Trailing node only; suitable for non-leading edge MCUs"),
        ],
    ),
    SupplierRecord(
        name="Luminar Technologies",
        country="USA", tier=1, risk_score=89,
        flags=["FINANCIAL_DISTRESS", "SINGLE_SOURCE"],
        revenue_at_risk_m=95,
        annual_spend_m=24,
        is_single_source=True,
        category="LiDAR",
        alternatives=[
            Alternative("Waymo LiDAR", "USA", 320, 12, 90, 48, "FULL",
                        "Similar spec; already qualified for AXL variant"),
            Alternative("Innoviz Technologies", "Israel", 180, 8, 80, 55, "FULL",
                        "InnovizTwo 905nm; faster qualification path"),
            Alternative("Luminar Backup (Velodyne ODM)", "USA", 120, 6, 70, 60, "PARTIAL",
                        "Emergency bridge; lower resolution"),
        ],
    ),
    SupplierRecord(
        name="Norilsk Nickel",
        country="Russia", tier=2, risk_score=96,
        flags=["SANCTIONS_OFAC", "GEOPOLITICAL_RISK"],
        revenue_at_risk_m=140,
        annual_spend_m=35,
        is_single_source=False,
        category="Nickel/Palladium",
        current_coverage_pct=65,  # 65% from Norilsk, 35% from others
        alternatives=[
            Alternative("Vale Nickel", "Brazil/Canada", 450, 9, 80, 38, "FULL",
                        "PTVI Indonesia site also available; RMI-compliant"),
            Alternative("Glencore Nickel", "Switzerland", 280, 6, 70, 45, "FULL",
                        "Murrin Murrin Australia; existing Glencore relationship"),
            Alternative("BHP Nickel", "Australia", 380, 8, 60, 35, "PARTIAL",
                        "Nickel West Kwinana; Class 1 nickel"),
        ],
    ),
    SupplierRecord(
        name="JSR Corporation",
        country="Japan", tier=2, risk_score=73,
        flags=["SINGLE_SOURCE", "EXPORT_CTRL"],
        revenue_at_risk_m=320,
        annual_spend_m=80,
        is_single_source=True,
        category="EUV Photoresist",
        alternatives=[
            Alternative("Shin-Etsu Chemical", "Japan", 1200, 30, 50, 44, "PARTIAL",
                        "KrF resists available; EUV still qualifying"),
            Alternative("DuPont EUV Materials", "USA", 1600, 36, 40, 48, "LIMITED",
                        "ArF immersion crossover; positive ITAR profile"),
        ],
    ),
    SupplierRecord(
        name="ZF Friedrichshafen",
        country="Germany", tier=1, risk_score=67,
        flags=["FINANCIAL_STRESS", "SINGLE_SOURCE"],
        revenue_at_risk_m=380,
        annual_spend_m=94,
        is_single_source=True,
        category="Gearbox/Drivetrain",
        alternatives=[
            Alternative("Tremec (Sensata)", "USA/Mexico", 680, 24, 75, 52, "FULL",
                        "TR-4050 compatible; US ITAR-free"),
            Alternative("Getrag (Magna)", "Germany/Hungary", 520, 18, 85, 48, "FULL",
                        "Same OEM platform; closest drop-in"),
        ],
    ),
    SupplierRecord(
        name="Leoni AG",
        country="Germany", tier=1, risk_score=85,
        flags=["FINANCIAL_DISTRESS", "FORCE_MAJEURE"],
        revenue_at_risk_m=210,
        annual_spend_m=52,
        is_single_source=False,
        category="Wiring Harness",
        current_coverage_pct=70,
        alternatives=[
            Alternative("Aptiv", "Ireland", 340, 12, 90, 34, "FULL",
                        "GEN 6 smart harness; already Tier 1 at BMW"),
            Alternative("Yazaki", "Japan", 220, 10, 80, 40, "FULL",
                        "Strong cost position; SE Asia manufacturing"),
            Alternative("Sumitomo Electric", "Japan", 280, 14, 85, 38, "FULL",
                        "Existing SEAT/VW relationship; fast ramp"),
        ],
    ),
    SupplierRecord(
        name="Cryoin Engineering",
        country="Ukraine", tier=3, risk_score=88,
        flags=["FORCE_MAJEURE", "GEOPOLITICAL_RISK"],
        revenue_at_risk_m=190,
        annual_spend_m=47,
        is_single_source=True,
        category="Neon Gas (EUV)",
        alternatives=[
            Alternative("Linde plc", "UK/Ireland", 150, 4, 100, 28, "FULL",
                        "Global inventory; Western Europe stock increase post-2022"),
            Alternative("Air Products", "USA", 120, 3, 100, 30, "FULL",
                        "Expanded production; Scania already has MSA"),
            Alternative("Resonac (Showa Denko)", "Japan", 180, 6, 80, 35, "FULL",
                        "Japan backup; longer lead time"),
        ],
    ),
    SupplierRecord(
        name="Glencore DRC",
        country="DRC", tier=3, risk_score=91,
        flags=["CHILD_LABOR_RISK", "LKSG_RISK", "GEOPOLITICAL_RISK"],
        revenue_at_risk_m=75,
        annual_spend_m=19,
        is_single_source=False,
        category="Cobalt",
        current_coverage_pct=55,
        alternatives=[
            Alternative("Vale Cobalt (Brazil)", "Brazil", 240, 9, 80, 32, "FULL",
                        "Voisey Bay; RMI-verified; no LkSG exposure"),
            Alternative("Umicore Battery Recycling", "Belgium", 180, 6, 60, 28, "PARTIAL",
                        "Secondary cobalt from end-of-life batteries; ESG premium"),
        ],
    ),
    SupplierRecord(
        name="China Rare Earth Group",
        country="China", tier=4, risk_score=92,
        flags=["GEOPOLITICAL_RISK", "EXPORT_CTRL", "SINGLE_SOURCE"],
        revenue_at_risk_m=420,
        annual_spend_m=105,
        is_single_source=True,
        category="Rare Earth (NdFeB)",
        alternatives=[
            Alternative("MP Materials", "USA", 2800, 48, 30, 42, "LIMITED",
                        "Mountain Pass; ramping HRE separation 2025+"),
            Alternative("Lynas REE", "Australia", 2200, 36, 40, 38, "PARTIAL",
                        "LAMP Malaysia; dysprosium supply limited"),
            Alternative("Urban Mining (EU Recycling)", "Germany/France", 1400, 24, 20, 35, "LIMITED",
                        "Cyclic Materials / Less Common Metals; small volumes"),
        ],
    ),
]


# ── Optimizer ─────────────────────────────────────────────────────────────────

def priority_score(rec: SupplierRecord, alt: Alternative) -> float:
    """
    Priority = risk_score * revenue_at_risk / qualification_cost
    Adjusted upward for SINGLE_SOURCE, SANCTIONS, DISTRESS flags.
    """
    base = (rec.risk_score / 100.0) * rec.revenue_at_risk_m / max(alt.qualification_cost_keur / 1000.0, 0.1)
    flag_mult = 1.0
    if "SINGLE_SOURCE" in rec.flags or rec.is_single_source:
        flag_mult *= 1.5
    if "SANCTIONS_OFAC" in rec.flags:
        flag_mult *= 2.0
    if "FINANCIAL_DISTRESS" in rec.flags:
        flag_mult *= 1.8
    if "FORCE_MAJEURE" in rec.flags:
        flag_mult *= 1.6
    if alt.capacity_match_pct >= 80:
        flag_mult *= 1.2
    if alt.quality_match == "FULL":
        flag_mult *= 1.1
    return base * flag_mult


def risk_reduction(rec: SupplierRecord, alt: Alternative) -> float:
    """Expected risk reduction % if this alternative is qualified."""
    # Coverage gained × supplier's risk contribution
    coverage_gain = (alt.capacity_match_pct / 100.0) * (rec.current_coverage_pct / 100.0)
    return min(coverage_gain * 60.0, 75.0)  # cap at 75% reduction


def roi_months(rec: SupplierRecord, alt: Alternative) -> int:
    """Months to recover qualification cost via avoided disruption risk."""
    annual_risk_cost = rec.revenue_at_risk_m * (rec.risk_score / 100.0) * 0.15  # 15% annual disruption prob
    monthly_risk_cost = annual_risk_cost / 12.0
    qual_cost_m = alt.qualification_cost_keur / 1000.0
    if monthly_risk_cost <= 0:
        return 999
    return max(1, round(qual_cost_m / monthly_risk_cost))


def action_tier(score: float, rec: SupplierRecord) -> str:
    crit = any(f in rec.flags for f in ("SANCTIONS_OFAC", "FINANCIAL_DISTRESS", "FORCE_MAJEURE"))
    if crit and score > 50:
        return "IMMEDIATE"
    if score > 80:
        return "IMMEDIATE"
    if score > 30:
        return "SHORT_TERM"
    if score > 10:
        return "MEDIUM_TERM"
    return "MONITOR"


def rationale(rec: SupplierRecord, alt: Alternative, ps: float) -> str:
    parts = []
    if "SINGLE_SOURCE" in rec.flags or rec.is_single_source:
        parts.append("single source — zero redundancy")
    if "SANCTIONS_OFAC" in rec.flags:
        parts.append("OFAC sanctions active — must exit")
    if "FINANCIAL_DISTRESS" in rec.flags:
        parts.append("supplier distress — imminent failure risk")
    if "FORCE_MAJEURE" in rec.flags:
        parts.append("force majeure event — supply disrupted")
    parts.append(f"€{rec.revenue_at_risk_m}M revenue at risk")
    parts.append(f"{alt.name} ({alt.quality_match} match, {alt.capacity_match_pct}% capacity)")
    return "; ".join(parts)


def optimize(
    suppliers: list[SupplierRecord],
    budget_keur: Optional[float] = None,
    critical_only: bool = False,
    top_n: int = 20,
) -> list[DualSourcingRecommendation]:
    """Generate ranked dual-sourcing recommendations."""
    recs = []
    for s in suppliers:
        if critical_only and s.risk_score < 70:
            continue
        best_alt = max(s.alternatives, key=lambda a: (a.capacity_match_pct, -a.risk_score))
        ps = priority_score(s, best_alt)
        recs.append(DualSourcingRecommendation(
            supplier=s.name,
            alternative=best_alt,
            priority_score=round(ps, 2),
            qualification_cost_keur=best_alt.qualification_cost_keur,
            expected_risk_reduction_pct=round(risk_reduction(s, best_alt), 1),
            roi_months=roi_months(s, best_alt),
            action=action_tier(ps, s),
            rationale=rationale(s, best_alt, ps),
        ))

    recs.sort(key=lambda r: r.priority_score, reverse=True)

    if budget_keur:
        selected = []
        spent = 0.0
        for r in recs:
            if spent + r.qualification_cost_keur <= budget_keur:
                selected.append(r)
                spent += r.qualification_cost_keur
        return selected[:top_n]

    return recs[:top_n]


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Dual sourcing optimizer")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--budget", type=float, help="Budget in EUR (e.g. 5000000)")
    ap.add_argument("--supplier", help="Show alternatives for one supplier")
    ap.add_argument("--show-alts", action="store_true")
    ap.add_argument("--critical-only", action="store_true")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    budget_keur = args.budget / 1000.0 if args.budget else None

    if args.supplier:
        src = [s for s in SUPPLIERS if args.supplier.lower() in s.name.lower()]
        if not src:
            print(f"Not found: {args.supplier}")
            sys.exit(1)
        if args.show_alts:
            s = src[0]
            print(f"\nAlternatives for {s.name} (risk={s.risk_score}, RAR=€{s.revenue_at_risk_m}M):")
            for a in sorted(s.alternatives, key=lambda x: -x.capacity_match_pct):
                ps = priority_score(s, a)
                print(f"  {a.name:<35} {a.country:<15} cap={a.capacity_match_pct:>3}% "
                      f"cost=€{a.qualification_cost_keur:>5}k months={a.transition_months:>2} "
                      f"quality={a.quality_match:<8} priority={ps:.1f}")
            return
        src_list = src
    else:
        src_list = SUPPLIERS

    recs = optimize(src_list, budget_keur=budget_keur,
                    critical_only=args.critical_only, top_n=args.top)

    if args.json:
        out = [{
            "supplier": r.supplier,
            "alternative": r.alternative.name,
            "alternative_country": r.alternative.country,
            "priority_score": r.priority_score,
            "qualification_cost_keur": r.qualification_cost_keur,
            "expected_risk_reduction_pct": r.expected_risk_reduction_pct,
            "roi_months": r.roi_months,
            "action": r.action,
            "rationale": r.rationale,
        } for r in recs]
        print(json.dumps(out, indent=2))
        return

    total_cost = sum(r.qualification_cost_keur for r in recs)
    total_rar = sum(
        next(s.revenue_at_risk_m for s in SUPPLIERS if s.name == r.supplier)
        for r in recs
    )

    print(f"\nDual Sourcing Recommendations — {len(recs)} suppliers")
    if budget_keur:
        print(f"Budget: €{budget_keur:.0f}k | Total qualification cost: €{total_cost:.0f}k")
    print(f"Total revenue at risk covered: €{total_rar:.0f}M")
    print()
    print(f"{'#':<3} {'Action':<12} {'Supplier':<26} {'Alternative':<28} {'Cost(k€)':>8} {'RAR(M€)':>8} {'RiskRed%':>9} {'ROI(mo)':>8}")
    print("-" * 106)
    for i, r in enumerate(recs, 1):
        print(f"{i:<3} {r.action:<12} {r.supplier:<26} {r.alternative.name:<28} "
              f"{r.qualification_cost_keur:>8.0f} "
              f"{next(s.revenue_at_risk_m for s in SUPPLIERS if s.name==r.supplier):>8.0f} "
              f"{r.expected_risk_reduction_pct:>8.1f}% "
              f"{r.roi_months:>8}")

    if args.demo:
        print(f"\nTotal qualification cost: €{total_cost:,.0f}k")
        print(f"Revenue protected: €{total_rar:,.0f}M")
        immediate = sum(1 for r in recs if r.action == "IMMEDIATE")
        print(f"IMMEDIATE actions: {immediate}")


if __name__ == "__main__":
    main()
