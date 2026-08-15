"""
carbon_tracker.py — Scope 1/2/3 emissions tracker + CBAM carbon cost estimator

Tracks supplier carbon footprints, estimates CBAM liability for EU imports,
and monitors Science Based Targets (SBTi) commitments.

Usage:
  python3 src/carbon_tracker.py --demo
  python3 src/carbon_tracker.py --supplier "SSAB" --show-cbam
  python3 src/carbon_tracker.py --top-emitters --n 10
  python3 src/carbon_tracker.py --cbam-total --json
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Optional

# ── CBAM price (EU ETS carbon price, EUR/tCO2) ──────────────────────────────
# Historical + forecast
CBAM_ETS_PRICE_EUR = {
    2021: 54.0,
    2022: 81.0,
    2023: 70.0,
    2024: 62.0,   # current
    2025: 72.0,   # forecast
    2026: 85.0,   # forecast
}
CURRENT_YEAR = 2024
CBAM_PRICE = CBAM_ETS_PRICE_EUR[CURRENT_YEAR]

# CBAM-regulated sectors (as of 2024 transitional phase)
CBAM_SECTORS = {"Steel", "Aluminium", "Cement", "Fertilizers", "Electricity", "Hydrogen", "Iron"}

# SBTi target temperature levels
SBTI_LEVELS = {"1.5C": "#22c55e", "Well-below 2C": "#86efac",
                "2C": "#fbbf24", "Committed": "#93c5fd", "None": "#f87171"}


@dataclass
class EmissionProfile:
    supplier: str
    country: str
    industry: str
    tier: int
    # Scope 1: direct emissions (tCO2e/year)
    scope1_ktco2: float
    # Scope 2: purchased electricity/heat (tCO2e/year)
    scope2_ktco2: float
    # Scope 3: value chain (tCO2e/year) — upstream + downstream
    scope3_ktco2: Optional[float]
    # Carbon intensity (tCO2e per tonne product or per €M revenue)
    carbon_intensity_tco2_per_trev: float
    # CBAM
    cbam_sector: Optional[str]           # Steel / Aluminium / None
    cbam_tonnes_imported: Optional[float]  # tonnes imported by Scania per year
    cbam_embedded_co2_tco2_per_t: Optional[float]  # embedded CO2 in product
    # SBTi
    sbti_status: str  # "1.5C" | "Well-below 2C" | "2C" | "Committed" | "None"
    sbti_base_year: Optional[int]
    sbti_target_year: Optional[int]
    sbti_reduction_pct: Optional[float]
    # CDP score
    cdp_score: Optional[str]             # A, A-, B, C, D, F
    # Reduction vs base year
    yoy_reduction_pct: float             # % change in total emissions YoY
    # Revenue (for intensity calc)
    revenue_beur: float


# ── Embedded supplier emission data ──────────────────────────────────────────

EMISSIONS: list[EmissionProfile] = [
    EmissionProfile(
        supplier="SSAB",
        country="Sweden", industry="High-Strength Steel", tier=1,
        scope1_ktco2=2100.0,
        scope2_ktco2=420.0,
        scope3_ktco2=3800.0,
        carbon_intensity_tco2_per_trev=312.0,
        cbam_sector="Steel",
        cbam_tonnes_imported=18000.0,
        cbam_embedded_co2_tco2_per_t=1.8,
        sbti_status="1.5C",
        sbti_base_year=2018,
        sbti_target_year=2030,
        sbti_reduction_pct=35.0,
        cdp_score="A-",
        yoy_reduction_pct=-4.2,
        revenue_beur=9.8,
    ),
    EmissionProfile(
        supplier="ZF Friedrichshafen",
        country="Germany", industry="Drivetrain Systems", tier=1,
        scope1_ktco2=830.0,
        scope2_ktco2=1240.0,
        scope3_ktco2=18400.0,
        carbon_intensity_tco2_per_trev=91.0,
        cbam_sector=None,
        cbam_tonnes_imported=None,
        cbam_embedded_co2_tco2_per_t=None,
        sbti_status="Well-below 2C",
        sbti_base_year=2019,
        sbti_target_year=2030,
        sbti_reduction_pct=30.0,
        cdp_score="B",
        yoy_reduction_pct=-3.1,
        revenue_beur=43.8,
    ),
    EmissionProfile(
        supplier="CATL",
        country="China", industry="Battery Systems", tier=1,
        scope1_ktco2=2450.0,
        scope2_ktco2=8900.0,
        scope3_ktco2=42000.0,
        carbon_intensity_tco2_per_trev=245.0,
        cbam_sector=None,
        cbam_tonnes_imported=None,
        cbam_embedded_co2_tco2_per_t=None,
        sbti_status="Committed",
        sbti_base_year=None,
        sbti_target_year=2035,
        sbti_reduction_pct=None,
        cdp_score="C",
        yoy_reduction_pct=+2.8,  # emissions rising with production
        revenue_beur=38.7,
    ),
    EmissionProfile(
        supplier="TSMC",
        country="Taiwan", industry="Semiconductors", tier=1,
        scope1_ktco2=189.0,
        scope2_ktco2=14200.0,
        scope3_ktco2=2100.0,
        carbon_intensity_tco2_per_trev=195.0,
        cbam_sector=None,
        cbam_tonnes_imported=None,
        cbam_embedded_co2_tco2_per_t=None,
        sbti_status="Well-below 2C",
        sbti_base_year=2020,
        sbti_target_year=2030,
        sbti_reduction_pct=25.0,
        cdp_score="A-",
        yoy_reduction_pct=-1.8,
        revenue_beur=69.3,
    ),
    EmissionProfile(
        supplier="Bosch",
        country="Germany", industry="Electronics / Fuel Systems", tier=1,
        scope1_ktco2=410.0,
        scope2_ktco2=890.0,
        scope3_ktco2=32000.0,
        carbon_intensity_tco2_per_trev=52.0,
        cbam_sector=None,
        cbam_tonnes_imported=None,
        cbam_embedded_co2_tco2_per_t=None,
        sbti_status="1.5C",
        sbti_base_year=2018,
        sbti_target_year=2030,
        sbti_reduction_pct=40.0,
        cdp_score="A",
        yoy_reduction_pct=-6.1,
        revenue_beur=91.6,
    ),
    EmissionProfile(
        supplier="Norilsk Nickel",
        country="Russia", industry="Mining", tier=2,
        scope1_ktco2=9800.0,
        scope2_ktco2=3200.0,
        scope3_ktco2=None,
        carbon_intensity_tco2_per_trev=880.0,
        cbam_sector=None,
        cbam_tonnes_imported=None,
        cbam_embedded_co2_tco2_per_t=None,
        sbti_status="None",
        sbti_base_year=None,
        sbti_target_year=None,
        sbti_reduction_pct=None,
        cdp_score="D",
        yoy_reduction_pct=+1.2,
        revenue_beur=14.8,
    ),
    EmissionProfile(
        supplier="Glencore DRC",
        country="DRC", industry="Cobalt Mining", tier=3,
        scope1_ktco2=1100.0,
        scope2_ktco2=280.0,
        scope3_ktco2=None,
        carbon_intensity_tco2_per_trev=740.0,
        cbam_sector=None,
        cbam_tonnes_imported=None,
        cbam_embedded_co2_tco2_per_t=None,
        sbti_status="None",
        sbti_base_year=None,
        sbti_target_year=None,
        sbti_reduction_pct=None,
        cdp_score="D",
        yoy_reduction_pct=+3.5,
        revenue_beur=1.9,
    ),
    EmissionProfile(
        supplier="LKAB",
        country="Sweden", industry="Iron Ore Mining", tier=2,
        scope1_ktco2=1920.0,
        scope2_ktco2=180.0,
        scope3_ktco2=None,
        carbon_intensity_tco2_per_trev=820.0,
        cbam_sector="Iron",
        cbam_tonnes_imported=None,
        cbam_embedded_co2_tco2_per_t=8.5,
        sbti_status="1.5C",
        sbti_base_year=2020,
        sbti_target_year=2035,
        sbti_reduction_pct=50.0,
        cdp_score="A-",
        yoy_reduction_pct=-2.1,
        revenue_beur=4.2,
    ),
    EmissionProfile(
        supplier="Saarstahl AG",
        country="Germany", industry="Steel", tier=2,
        scope1_ktco2=3400.0,
        scope2_ktco2=420.0,
        scope3_ktco2=None,
        carbon_intensity_tco2_per_trev=540.0,
        cbam_sector="Steel",
        cbam_tonnes_imported=8500.0,
        cbam_embedded_co2_tco2_per_t=1.92,
        sbti_status="2C",
        sbti_base_year=2019,
        sbti_target_year=2030,
        sbti_reduction_pct=20.0,
        cdp_score="C",
        yoy_reduction_pct=-1.5,
        revenue_beur=5.1,
    ),
    EmissionProfile(
        supplier="Infineon Technologies",
        country="Germany", industry="Semiconductors", tier=2,
        scope1_ktco2=142.0,
        scope2_ktco2=1860.0,
        scope3_ktco2=8900.0,
        carbon_intensity_tco2_per_trev=128.0,
        cbam_sector=None,
        cbam_tonnes_imported=None,
        cbam_embedded_co2_tco2_per_t=None,
        sbti_status="1.5C",
        sbti_base_year=2019,
        sbti_target_year=2030,
        sbti_reduction_pct=70.0,
        cdp_score="A",
        yoy_reduction_pct=-8.2,
        revenue_beur=14.5,
    ),
    EmissionProfile(
        supplier="Thaisarco (Thailand Smelting)",
        country="Thailand", industry="Tin Smelting", tier=3,
        scope1_ktco2=95.0,
        scope2_ktco2=210.0,
        scope3_ktco2=None,
        carbon_intensity_tco2_per_trev=420.0,
        cbam_sector=None,
        cbam_tonnes_imported=None,
        cbam_embedded_co2_tco2_per_t=None,
        sbti_status="None",
        sbti_base_year=None,
        sbti_target_year=None,
        sbti_reduction_pct=None,
        cdp_score="C",
        yoy_reduction_pct=+0.8,
        revenue_beur=0.7,
    ),
    EmissionProfile(
        supplier="China Rare Earth Group",
        country="China", industry="Rare Earth Mining/Processing", tier=4,
        scope1_ktco2=4800.0,
        scope2_ktco2=2200.0,
        scope3_ktco2=None,
        carbon_intensity_tco2_per_trev=950.0,
        cbam_sector=None,
        cbam_tonnes_imported=None,
        cbam_embedded_co2_tco2_per_t=None,
        sbti_status="None",
        sbti_base_year=None,
        sbti_target_year=None,
        sbti_reduction_pct=None,
        cdp_score="F",
        yoy_reduction_pct=+4.1,
        revenue_beur=7.2,
    ),
]


# ── Analytics ─────────────────────────────────────────────────────────────────

def cbam_cost(profile: EmissionProfile, year: int = CURRENT_YEAR) -> Optional[float]:
    """Estimated CBAM certificate cost in EUR for a given year."""
    if not profile.cbam_sector:
        return None
    if profile.cbam_tonnes_imported is None:
        return None
    price = CBAM_ETS_PRICE_EUR.get(year, CBAM_PRICE)
    embedded = profile.cbam_embedded_co2_tco2_per_t or 0.0
    return profile.cbam_tonnes_imported * embedded * price


def total_scope12(p: EmissionProfile) -> float:
    return p.scope1_ktco2 + p.scope2_ktco2


def total_all_scopes(p: EmissionProfile) -> float:
    return p.scope1_ktco2 + p.scope2_ktco2 + (p.scope3_ktco2 or 0.0)


def sbti_on_track(p: EmissionProfile) -> Optional[bool]:
    """True if supplier's YoY reduction is at least matching linear SBTi path."""
    if p.sbti_status in ("None", "Committed") or p.sbti_reduction_pct is None:
        return None
    years_remaining = (p.sbti_target_year or 2030) - CURRENT_YEAR
    total_years = (p.sbti_target_year or 2030) - (p.sbti_base_year or 2020)
    if total_years <= 0:
        return None
    required_annual_pct = p.sbti_reduction_pct / total_years
    return p.yoy_reduction_pct <= -required_annual_pct  # negative = reduction


def emissions_summary(profiles: list[EmissionProfile]) -> dict:
    total_s1 = sum(p.scope1_ktco2 for p in profiles)
    total_s2 = sum(p.scope2_ktco2 for p in profiles)
    total_s3 = sum(p.scope3_ktco2 or 0 for p in profiles)
    cbam_costs = [c for p in profiles if (c := cbam_cost(p)) is not None]
    sbti_committed = sum(1 for p in profiles if p.sbti_status != "None")
    cdp_a = sum(1 for p in profiles if p.cdp_score in ("A", "A-"))

    return {
        "suppliers": len(profiles),
        "scope1_total_ktco2": round(total_s1, 1),
        "scope2_total_ktco2": round(total_s2, 1),
        "scope3_total_ktco2": round(total_s3, 1),
        "total_ktco2": round(total_s1 + total_s2 + total_s3, 1),
        "cbam_total_eur": round(sum(cbam_costs), 0),
        "sbti_committed_count": sbti_committed,
        "cdp_a_count": cdp_a,
        "highest_emitter": max(profiles, key=total_scope12).supplier,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Supply chain carbon tracker")
    ap.add_argument("--demo", action="store_true", help="Print full emissions table")
    ap.add_argument("--supplier", help="Show one supplier detail")
    ap.add_argument("--top-emitters", action="store_true")
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--cbam-total", action="store_true", help="Sum CBAM liability")
    ap.add_argument("--show-cbam", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--year", type=int, default=CURRENT_YEAR)
    args = ap.parse_args()

    if args.supplier:
        hit = next((p for p in EMISSIONS if args.supplier.lower() in p.supplier.lower()), None)
        if not hit:
            print(f"Supplier not found: {args.supplier}")
            sys.exit(1)
        profiles = [hit]
    else:
        profiles = EMISSIONS

    if args.top_emitters:
        profiles = sorted(profiles, key=total_scope12, reverse=True)[:args.n]

    if args.cbam_total:
        total = sum(c for p in profiles if (c := cbam_cost(p, args.year)) is not None)
        if args.json:
            print(json.dumps({"cbam_eur": total, "year": args.year, "ets_price": CBAM_ETS_PRICE_EUR.get(args.year)}))
        else:
            print(f"CBAM total liability ({args.year}): EUR {total:,.0f}")
            print(f"ETS price: EUR {CBAM_ETS_PRICE_EUR.get(args.year, CBAM_PRICE)}/tCO2")
        return

    if args.json:
        out = []
        for p in profiles:
            out.append({
                "supplier": p.supplier,
                "country": p.country,
                "scope1_ktco2": p.scope1_ktco2,
                "scope2_ktco2": p.scope2_ktco2,
                "scope3_ktco2": p.scope3_ktco2,
                "cbam_eur": cbam_cost(p, args.year),
                "sbti_status": p.sbti_status,
                "sbti_on_track": sbti_on_track(p),
                "cdp_score": p.cdp_score,
                "yoy_reduction_pct": p.yoy_reduction_pct,
            })
        print(json.dumps(out, indent=2))
        return

    # Table output
    print(f"{'Supplier':<28} {'Cntry':5} {'S1':>7} {'S2':>7} {'S3':>8} {'CBAM€':>10} {'SBTi':^12} {'CDP':^5} {'YoY%':>6}")
    print("-" * 100)
    for p in profiles:
        cbam = cbam_cost(p, args.year)
        cbam_str = f"€{cbam:,.0f}" if cbam is not None else "—"
        s3_str = f"{p.scope3_ktco2:>8.0f}" if p.scope3_ktco2 else "       —"
        track = sbti_on_track(p)
        track_str = "✓" if track is True else ("✗" if track is False else "—")
        sbti_str = f"{p.sbti_status[:10]:10} {track_str}"
        yoy_str = f"{p.yoy_reduction_pct:+.1f}%"
        print(f"{p.supplier:<28} {p.country[:5]:5} {p.scope1_ktco2:>7.0f} {p.scope2_ktco2:>7.0f} {s3_str} {cbam_str:>10} {sbti_str} {p.cdp_score or '—':^5} {yoy_str:>6}")

    if args.demo:
        print()
        summ = emissions_summary(profiles)
        print(f"Total Scope 1+2+3: {summ['total_ktco2']:,.0f} ktCO2e")
        print(f"CBAM total (2024): EUR {summ['cbam_total_eur']:,.0f}")
        print(f"SBTi committed: {summ['sbti_committed_count']}/{summ['suppliers']}")
        print(f"CDP A/A-: {summ['cdp_a_count']}/{summ['suppliers']}")
        print(f"Highest emitter: {summ['highest_emitter']}")


if __name__ == "__main__":
    main()
