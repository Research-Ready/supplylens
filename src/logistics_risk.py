"""SupplyLens Logistics Risk Scorer — UC4

Scores major global shipping routes by disruption probability, estimates which
Scania supply chain products halt, and identifies alternative routes with cost
premiums.

Routes covered:
  Suez Canal        — Asia↔Europe primary choke point
  Malacca Strait    — Pacific Asia gateway
  Trans-Siberian    — Russia rail route (currently sanctioned)
  Cape of Good Hope — Suez alternative, +10-14 days
  Panama Canal      — Americas throughput
  Bosphorus Strait  — Black Sea entry
  Strait of Hormuz  — Gulf oil export

Usage:
    python3 src/logistics_risk.py
    python3 src/logistics_risk.py --route suez
    python3 src/logistics_risk.py --json
    python3 src/logistics_risk.py --affected "CATL"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

# ─── Route definitions ────────────────────────────────────────────────────────

@dataclass
class Route:
    id: str
    name: str
    region: str
    annual_trade_pct: float       # % of world trade (by value)
    daily_ships: int              # avg ships per day
    chokepoint: bool
    disruption_prob_base: float   # annual probability of significant disruption
    disruption_prob_current: float  # current assessed probability (risk-adjusted)
    current_threats: List[str]
    last_disruption_year: Optional[int]
    normal_transit_days: float    # average transit days (one way)
    alt_routes: List[str]         # fallback route IDs
    cost_premium_pct: float       # cost premium vs normal if disrupted (%)
    transit_delay_days: float     # extra days if forced to alt route
    products_at_risk: List[str]   # which Scania supply chain commodities
    suppliers_at_risk: List[str]  # which suppliers route through here
    evidence_doc: str
    evidence_excerpt: str
    risk_level: str = "LOW"       # LOW | MEDIUM | HIGH | CRITICAL (computed)

    def __post_init__(self):
        p = self.disruption_prob_current
        if p >= 0.60:
            self.risk_level = "CRITICAL"
        elif p >= 0.35:
            self.risk_level = "HIGH"
        elif p >= 0.15:
            self.risk_level = "MEDIUM"
        else:
            self.risk_level = "LOW"


ROUTES: Dict[str, Route] = {
    r.id: r for r in [
        Route(
            id="suez",
            name="Suez Canal",
            region="Middle East / Red Sea",
            annual_trade_pct=12.0,
            daily_ships=50,
            chokepoint=True,
            disruption_prob_base=0.15,
            disruption_prob_current=0.65,   # elevated: Houthi attacks 2024
            current_threats=["Houthi missile/drone attacks", "Yemen conflict escalation",
                             "US/UK retaliatory strikes"],
            last_disruption_year=2024,
            normal_transit_days=1.0,
            alt_routes=["cape_good_hope"],
            cost_premium_pct=35.0,
            transit_delay_days=12.0,
            products_at_risk=["Battery packs", "Semiconductors", "Wiring harnesses",
                              "Sensors", "Electronics", "Copper", "Lithium carbonate"],
            suppliers_at_risk=["CATL", "STMicroelectronics", "Bosch", "Infineon Technologies",
                               "Leoni AG", "Ganfeng Lithium", "Toray Industries",
                               "Nidec Corporation", "Samsung SDI"],
            evidence_doc="Lloyd's List Intelligence — Red Sea Crisis Report, Feb 2024",
            evidence_excerpt="60% of Asia-Europe container traffic rerouted via Cape of Good Hope; "
                             "spot container rates +180%; Scania emergency airfreight €12M Q1 2024.",
        ),
        Route(
            id="malacca",
            name="Strait of Malacca",
            region="Southeast Asia",
            annual_trade_pct=25.0,
            daily_ships=200,
            chokepoint=True,
            disruption_prob_base=0.05,
            disruption_prob_current=0.10,
            current_threats=["Piracy (low)", "Vessel congestion", "Monsoon weather"],
            last_disruption_year=None,
            normal_transit_days=0.5,
            alt_routes=["lombok_strait", "sunda_strait"],
            cost_premium_pct=8.0,
            transit_delay_days=4.0,
            products_at_risk=["Semiconductors", "Rare earth elements", "Battery cells",
                              "Electronics components", "Natural rubber"],
            suppliers_at_risk=["CATL", "STMicroelectronics", "China Rare Earth Group",
                               "Ganfeng Lithium", "Sri Trang Agro-Industry", "Toray Industries"],
            evidence_doc="IMO Malacca Strait Patrol — Annual Report 2023",
            evidence_excerpt="25% of global oil trade and $5.3T in goods transits Malacca annually; "
                             "no major disruptions 2020-2024; piracy incidents at 30-year low.",
        ),
        Route(
            id="trans_sib",
            name="Trans-Siberian Railway",
            region="Russia / Central Asia",
            annual_trade_pct=1.5,
            daily_ships=0,        # rail, not maritime
            chokepoint=False,
            disruption_prob_base=0.10,
            disruption_prob_current=0.95,   # EU sanctions block usage
            current_threats=["EU/UK/US sanctions on Russia", "OFAC restrictions",
                             "Insurance prohibition", "EU import/export bans"],
            last_disruption_year=2022,
            normal_transit_days=14.0,       # Moscow to Hamburg equiv.
            alt_routes=["suez", "cape_good_hope"],
            cost_premium_pct=180.0,         # sea freight 3× rail cost
            transit_delay_days=25.0,        # rail 14d → sea 39d
            products_at_risk=["Steel", "Aluminium", "Palladium", "Nickel",
                              "Rare earth elements", "Electronics"],
            suppliers_at_risk=["Norilsk Nickel", "Norilsk Polar Division",
                               "RUSAL Aughinish", "Leoni AG"],
            evidence_doc="Internal Logistics Advisory 2022-03-01; EU Council Regulation 833/2014",
            evidence_excerpt="Trans-Sib route used for 12% of Scania Södertälje↔China flows; "
                             "fully substituted by sea freight March 2022 following EU sanctions.",
        ),
        Route(
            id="cape_good_hope",
            name="Cape of Good Hope",
            region="South Africa",
            annual_trade_pct=4.5,   # surged to ~7.2% during Suez disruption
            daily_ships=25,
            chokepoint=False,
            disruption_prob_base=0.03,
            disruption_prob_current=0.05,
            current_threats=["Cape Town weather", "Vessel technical issues"],
            last_disruption_year=None,
            normal_transit_days=11.0,       # additional vs Suez
            alt_routes=["suez"],
            cost_premium_pct=0.0,           # the alt route itself
            transit_delay_days=0.0,
            products_at_risk=["Any Asia→Europe cargo diverted from Suez"],
            suppliers_at_risk=["All Asian-origin suppliers"],
            evidence_doc="Clarksons Research — Cape Route Diversion Analysis, Q1 2024",
            evidence_excerpt="Cape route traffic increased 120% during Red Sea crisis; "
                             "Cape Town bunker fuel demand +45%; weather risk ~15 days Nov-Feb.",
        ),
        Route(
            id="panama",
            name="Panama Canal",
            region="Central America",
            annual_trade_pct=5.0,
            daily_ships=40,
            chokepoint=True,
            disruption_prob_base=0.08,
            disruption_prob_current=0.25,   # drought reduced water levels 2023-24
            current_threats=["El Niño drought (low water levels)", "Vessel queue backlogs",
                             "Draft restrictions -3m"],
            last_disruption_year=2023,
            normal_transit_days=0.4,
            alt_routes=["cape_horn"],
            cost_premium_pct=18.0,
            transit_delay_days=22.0,        # Cape Horn alternative
            products_at_risk=["LNG", "Grain", "Chemical tankers", "Container cargo"],
            suppliers_at_risk=["Dana Incorporated", "Cummins Inc",
                               "Cabot Corporation", "Albemarle Corp"],
            evidence_doc="Panama Canal Authority — Water Level Advisory, Nov 2023",
            evidence_excerpt="Gatun Lake water levels reached record lows Oct 2023; "
                             "vessel slots reduced 40%; Neo-Panamax draft restrictions -3.05m.",
        ),
        Route(
            id="bosphorus",
            name="Bosphorus Strait",
            region="Turkey / Black Sea",
            annual_trade_pct=1.8,
            daily_ships=45,
            chokepoint=True,
            disruption_prob_base=0.12,
            disruption_prob_current=0.35,
            current_threats=["Ukraine war spillover", "Russian mine risk in Black Sea",
                             "Montreux Convention vessel restrictions"],
            last_disruption_year=2022,
            normal_transit_days=0.25,
            alt_routes=["cape_good_hope"],
            cost_premium_pct=55.0,
            transit_delay_days=30.0,
            products_at_risk=["Steel", "Grain", "Sunflower oil", "Iron ore"],
            suppliers_at_risk=["Saarstahl AG", "SSAB", "Vale SA"],
            evidence_doc="BIMCO Black Sea Risk Assessment, Q3 2022",
            evidence_excerpt="Montreux Convention bars warship transit; Ukraine declared "
                             "temporary navigation warning zones in NW Black Sea; "
                             "mine risk assessment elevated CRITICAL for commercial vessels.",
        ),
        Route(
            id="hormuz",
            name="Strait of Hormuz",
            region="Persian Gulf / Iran",
            annual_trade_pct=21.0,   # oil & gas value
            daily_ships=20,          # tankers
            chokepoint=True,
            disruption_prob_base=0.15,
            disruption_prob_current=0.30,
            current_threats=["Iran-Israel tensions", "Iranian vessel seizures",
                             "IRGC harassment of tankers", "US-Iran geopolitical risk"],
            last_disruption_year=2019,
            normal_transit_days=0.25,
            alt_routes=["saudi_pipeline", "oman_bypass"],
            cost_premium_pct=45.0,
            transit_delay_days=14.0,
            products_at_risk=["Crude oil", "LNG", "Chemical feedstocks",
                              "Polymer resins", "Plastics"],
            suppliers_at_risk=["BASF SE", "AMS Buttons BV"],  # polymer feedstocks
            evidence_doc="EIA Strait of Hormuz Fact Sheet 2024",
            evidence_excerpt="20% of global petroleum liquids and significant LNG flows transit "
                             "Hormuz daily; Iran seized two tankers 2023; "
                             "Houthi solidarity attacks increased threat radius.",
        ),
    ]
}


# ─── Supplier routing map ──────────────────────────────────────────────────────

# Which routes does each Scania supplier's output transit?
SUPPLIER_ROUTES: Dict[str, List[str]] = {
    "CATL":                   ["malacca", "suez"],
    "Ganfeng Lithium":        ["malacca", "suez"],
    "SQM":                    ["panama"],               # Pacific coast Chile → Europe
    "Codelco":                ["panama"],
    "Norilsk Nickel":         ["bosphorus"],            # Black Sea route (sanctioned)
    "Norilsk Polar Division": ["trans_sib"],            # Arctic → Trans-Sib (sanctioned)
    "RUSAL Aughinish":        [],                       # Ireland → EU direct
    "China Rare Earth Group": ["malacca", "suez"],
    "STMicroelectronics":     [],                       # EU-manufactured
    "Infineon Technologies":  ["malacca"],              # some Asia production
    "Leoni AG":               ["bosphorus"],            # Ukraine/North Africa plants
    "Toray Industries":       ["malacca", "suez"],
    "Samsung SDI":            ["malacca", "suez"],
    "Nidec Corporation":      ["malacca", "suez"],
    "SK Enpulse":             ["malacca", "suez"],
    "Sri Trang Agro-Industry":["malacca", "suez"],
    "AVX Tantalum":           ["panama"],               # DRC → US processing → Europe
    "Albemarle Corp":         ["panama"],
    "Vale SA":                ["cape_good_hope"],
    "BASF SE":                [],                       # Germany domestic
    "Dana Incorporated":      ["panama"],
    "Cummins Inc":            ["panama"],
    "Cabot Corporation":      ["panama"],
}


# ─── Score computation ─────────────────────────────────────────────────────────

@dataclass
class RouteRiskScore:
    route_id: str
    route_name: str
    risk_level: str
    disruption_prob: float
    affected_suppliers: List[str]
    affected_products: List[str]
    alt_route: str
    cost_premium_pct: float
    delay_days: float
    revenue_at_risk_eur_m: float   # rough estimate based on €1.1B annual Scania supply


def score_all_routes(annual_supply_eur_m: float = 1100.0) -> List[RouteRiskScore]:
    """Score all routes. annual_supply_eur_m = total Scania supply spend (external)."""
    results = []
    for route in ROUTES.values():
        # Build list of Scania suppliers that route through here
        affected = [sup for sup, routes in SUPPLIER_ROUTES.items()
                    if route.id in routes]
        # Rough revenue-at-risk: proportion of supply spend * disruption probability
        affected_frac = len(affected) / max(len(SUPPLIER_ROUTES), 1)
        rev_risk = annual_supply_eur_m * affected_frac * route.disruption_prob_current

        results.append(RouteRiskScore(
            route_id=route.id,
            route_name=route.name,
            risk_level=route.risk_level,
            disruption_prob=route.disruption_prob_current,
            affected_suppliers=affected,
            affected_products=route.products_at_risk,
            alt_route=route.alt_routes[0] if route.alt_routes else "none",
            cost_premium_pct=route.cost_premium_pct,
            delay_days=route.transit_delay_days,
            revenue_at_risk_eur_m=round(rev_risk, 1),
        ))

    results.sort(key=lambda r: r.disruption_prob, reverse=True)
    return results


def affected_routes_for_supplier(supplier_name: str) -> List[Route]:
    """Return Route objects that a given supplier's cargo transits."""
    route_ids = SUPPLIER_ROUTES.get(supplier_name, [])
    return [ROUTES[rid] for rid in route_ids if rid in ROUTES]


def route_detail(route_id: str) -> Optional[dict]:
    """Return full detail dict for a route."""
    r = ROUTES.get(route_id)
    if not r:
        return None
    d = asdict(r)
    d["affected_scania_suppliers"] = [
        s for s, routes in SUPPLIER_ROUTES.items() if route_id in routes
    ]
    return d


# ─── CLI ──────────────────────────────────────────────────────────────────────

def _print_table(scores: List[RouteRiskScore]) -> None:
    RISK_COLOR = {"CRITICAL": "\033[91m", "HIGH": "\033[93m",
                  "MEDIUM": "\033[94m", "LOW": "\033[92m"}
    RST = "\033[0m"

    print(f"\n{'Route':<28} {'Risk':<10} {'P(disrupt)':<12} {'Rev@Risk':<12} "
          f"{'Delay':<8} {'Premium':<10} {'Suppliers'}")
    print("─" * 110)
    for s in scores:
        col = RISK_COLOR.get(s.risk_level, "")
        sups = ", ".join(s.affected_suppliers[:3])
        if len(s.affected_suppliers) > 3:
            sups += f" +{len(s.affected_suppliers)-3}"
        print(f"{s.route_name:<28} {col}{s.risk_level:<10}{RST} "
              f"{s.disruption_prob:>8.0%}    "
              f"€{s.revenue_at_risk_eur_m:>6.1f}M    "
              f"{s.delay_days:>4.0f}d    "
              f"{s.cost_premium_pct:>5.0f}%    "
              f"{sups}")
    print()


def _print_route_detail(route_id: str) -> None:
    d = route_detail(route_id)
    if not d:
        print(f"Route '{route_id}' not found. Available: {', '.join(ROUTES)}")
        return
    print(f"\n=== {d['name']} ({route_id.upper()}) ===")
    print(f"Region:              {d['region']}")
    print(f"Risk Level:          {d['risk_level']}")
    print(f"Disruption Prob:     {d['disruption_prob_current']:.0%} (base: {d['disruption_prob_base']:.0%})")
    print(f"World Trade Share:   {d['annual_trade_pct']}%")
    print(f"Daily Ships:         {d['daily_ships']}")
    print(f"Alt Routes:          {', '.join(d['alt_routes']) or 'none'}")
    print(f"Cost Premium:        +{d['cost_premium_pct']}%")
    print(f"Transit Delay:       +{d['transit_delay_days']} days")
    print(f"\nCurrent Threats:")
    for t in d['current_threats']:
        print(f"  • {t}")
    print(f"\nProducts at Risk: {', '.join(d['products_at_risk'][:5])}")
    print(f"Scania Suppliers Affected: {', '.join(d['affected_scania_suppliers'])}")
    print(f"\nEvidence: {d['evidence_doc']}")
    print(f'Excerpt:  "{d["evidence_excerpt"]}"')
    print()


def _print_supplier_routes(supplier: str) -> None:
    routes = affected_routes_for_supplier(supplier)
    if not routes:
        print(f"\n{supplier}: no tracked logistics routes (likely EU domestic)")
        return
    print(f"\n{supplier} cargo transits:")
    for r in routes:
        print(f"  • {r.name} — {r.risk_level} risk ({r.disruption_prob_current:.0%}) "
              f"| alt: {r.alt_routes[0] if r.alt_routes else 'none'} "
              f"| delay: +{r.transit_delay_days}d | premium: +{r.cost_premium_pct}%")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="SupplyLens Logistics Risk Scorer")
    parser.add_argument("--route", help="Show detail for one route by ID")
    parser.add_argument("--affected", help="Show routes for a named supplier")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--supply-spend", type=float, default=1100.0,
                        help="Annual supply spend in EUR millions (default: 1100)")
    args = parser.parse_args()

    scores = score_all_routes(annual_supply_eur_m=args.supply_spend)

    if args.json:
        out = {"routes": [asdict(s) for s in scores],
               "total_revenue_at_risk_eur_m": round(sum(s.revenue_at_risk_eur_m for s in scores), 1)}
        print(json.dumps(out, indent=2))
        return

    if args.route:
        _print_route_detail(args.route)
        return

    if args.affected:
        _print_supplier_routes(args.affected)
        return

    # Default: summary table
    print("SupplyLens — Logistics Route Risk Scorecard")
    print(f"Annual supply spend basis: €{args.supply_spend}M | Routes tracked: {len(ROUTES)}")
    _print_table(scores)
    total_rev = sum(s.revenue_at_risk_eur_m for s in scores)
    critical = [s for s in scores if s.risk_level in ("CRITICAL", "HIGH")]
    print(f"Total estimated revenue at risk: €{total_rev:.1f}M")
    print(f"Critical/High risk routes: {len(critical)} / {len(scores)}")
    print(f"\nTop threat: {scores[0].route_name} ({scores[0].disruption_prob:.0%} probability)")
    print(f"  Alt route: {scores[0].alt_route} | delay: +{scores[0].delay_days}d | cost: +{scores[0].cost_premium_pct}%")
    print()


if __name__ == "__main__":
    main()
