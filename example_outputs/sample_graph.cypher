// UC4 Supply Chain — Sample Neo4j Graph
// Scania R-series Truck supply chain + Knopenkoning (Button) demo
// Run in Neo4j Browser (http://10.0.1.114:7474) or via cypher-shell
// Credentials: neo4j / <KeePass UC4 -> Neo4j>

// ============================================================
// CLEAR DEMO DATA (optional — comment out to preserve existing)
// ============================================================
// MATCH (n) WHERE n.demo = true DETACH DELETE n;

// ============================================================
// TIER 0 — Product
// ============================================================
MERGE (p1:Product {sku: 'SCANIA-R-500', name: 'Scania R-series Heavy Truck', category: 'Commercial Vehicles', demo: true});
MERGE (p2:Product {sku: 'BTN-001', name: 'Button 12mm', category: 'Fasteners', demo: true});

// ============================================================
// TIER 1 — Direct Suppliers
// ============================================================
MERGE (zf:Supplier {name: 'ZF Friedrichshafen', country: 'DE', tier: 1, website: 'https://www.zf.com', demo: true});
MERGE (bosch:Supplier {name: 'Bosch', country: 'DE', tier: 1, website: 'https://www.bosch.com', demo: true});
MERGE (ssab:Supplier {name: 'SSAB', country: 'SE', tier: 1, website: 'https://www.ssab.com', demo: true});
MERGE (mich:Supplier {name: 'Michelin', country: 'FR', tier: 1, website: 'https://www.michelin.com', demo: true});
MERGE (dana:Supplier {name: 'Dana Incorporated', country: 'US', tier: 1, website: 'https://www.dana.com', demo: true});
MERGE (ams:Supplier {name: 'AMS Buttons BV', country: 'NL', tier: 1, website: 'https://www.amsbuttons.nl', demo: true});

// ============================================================
// TIER 2 — Sub-suppliers
// ============================================================
MERGE (saar:Supplier {name: 'Saarstahl AG', country: 'DE', tier: 2, demo: true});
MERGE (inf:Supplier {name: 'Infineon Technologies', country: 'DE', tier: 2, demo: true});
MERGE (sen:Supplier {name: 'Sensata Technologies', country: 'NL', tier: 2, demo: true});
MERGE (lkab:Supplier {name: 'LKAB', country: 'SE', tier: 2, demo: true});
MERGE (shen:Supplier {name: 'Shenzhen Metal Co', country: 'CN', tier: 2, demo: true});

// ============================================================
// RAW MATERIALS
// ============================================================
MERGE (r_steelbillet:RawMaterial {name: 'Steel Billets', origin: 'DE', material_type: 'Metal', demo: true});
MERGE (r_ironore:RawMaterial {name: 'Iron Ore Pellets', origin: 'SE', material_type: 'Mineral', demo: true});
MERGE (r_silicon:RawMaterial {name: 'Raw Silicon', origin: 'CN', material_type: 'Semiconductor', demo: true});
MERGE (r_plastic:RawMaterial {name: 'Plastic Pellets', origin: 'DE', material_type: 'Polymer', demo: true});
MERGE (r_metalpins:RawMaterial {name: 'Metal Pins', origin: 'CN', material_type: 'Steel', demo: true});
MERGE (r_dye:RawMaterial {name: 'Textile Dye', origin: 'IN', material_type: 'Chemical', inferred: true, demo: true});
MERGE (r_rubber:RawMaterial {name: 'Natural Rubber', origin: 'TH', material_type: 'Polymer', demo: true});
MERGE (r_carbon:RawMaterial {name: 'Carbon Black', origin: 'RU', material_type: 'Chemical', demo: true,
  risk_flags: ['GEOPOLITICAL_RISK']});

// ============================================================
// CERTIFICATES
// ============================================================
MERGE (iso9001:Certificate {name: 'ISO 9001:2015', issuer: 'TUV', valid_until: '2027-12-31', demo: true});
MERGE (iatf:Certificate {name: 'IATF 16949:2016', issuer: 'Bureau Veritas', valid_until: '2026-09-30', demo: true});
MERGE (reach:Certificate {name: 'REACH Compliance', issuer: 'EU', valid_until: '2030-01-01', demo: true});

// ============================================================
// COMPANIES (parent corporations)
// ============================================================
MERGE (scania_co:Company {name: 'Scania AB', country: 'SE', industry: 'Automotive', demo: true});
MERGE (zf_co:Company {name: 'ZF Group', country: 'DE', industry: 'Automotive Components', demo: true});
MERGE (bosch_co:Company {name: 'Robert Bosch GmbH', country: 'DE', industry: 'Technology/Automotive', demo: true});

// ============================================================
// RELATIONSHIPS — Product → Tier 1
// ============================================================
MATCH (p:Product {sku: 'SCANIA-R-500'}), (s:Supplier {name: 'ZF Friedrichshafen'})
MERGE (p)-[:SUPPLIED_BY {since: '2015-01-01', component: 'TraXon gearbox', demo: true}]->(s);

MATCH (p:Product {sku: 'SCANIA-R-500'}), (s:Supplier {name: 'Bosch'})
MERGE (p)-[:SUPPLIED_BY {since: '2018-03-01', component: 'Fuel injection system', demo: true}]->(s);

MATCH (p:Product {sku: 'SCANIA-R-500'}), (s:Supplier {name: 'SSAB'})
MERGE (p)-[:SUPPLIED_BY {since: '2010-06-01', component: 'High-strength chassis steel', demo: true}]->(s);

MATCH (p:Product {sku: 'SCANIA-R-500'}), (s:Supplier {name: 'Michelin'})
MERGE (p)-[:SUPPLIED_BY {since: '2020-01-01', component: 'X Line Energy tyres', demo: true}]->(s);

MATCH (p:Product {sku: 'SCANIA-R-500'}), (s:Supplier {name: 'Dana Incorporated'})
MERGE (p)-[:SUPPLIED_BY {since: '2017-01-01', component: 'Driveshafts and axles', demo: true, risk_flags: ['SINGLE_SOURCE']}]->(s);

// Button product
MATCH (p:Product {sku: 'BTN-001'}), (s:Supplier {name: 'AMS Buttons BV'})
MERGE (p)-[:SUPPLIED_BY {since: '2022-01-01', demo: true}]->(s);

// ============================================================
// RELATIONSHIPS — Tier 1 → Tier 2
// ============================================================
MATCH (s1:Supplier {name: 'ZF Friedrichshafen'}), (s2:Supplier {name: 'Saarstahl AG'})
MERGE (s1)-[:SOURCED_FROM {volume_kg_year: 180000, component: 'Steel billets for gear shafts', demo: true}]->(s2);

MATCH (s1:Supplier {name: 'Bosch'}), (s2:Supplier {name: 'Infineon Technologies'})
MERGE (s1)-[:SOURCED_FROM {component: 'Semiconductors for ECU', demo: true}]->(s2);

MATCH (s1:Supplier {name: 'Bosch'}), (s2:Supplier {name: 'Sensata Technologies'})
MERGE (s1)-[:SOURCED_FROM {component: 'Pressure and temperature sensors', demo: true}]->(s2);

MATCH (s1:Supplier {name: 'SSAB'}), (s2:Supplier {name: 'LKAB'})
MERGE (s1)-[:SOURCED_FROM {volume_kg_year: 5000000, component: 'Iron ore pellets', demo: true}]->(s2);

MATCH (s1:Supplier {name: 'AMS Buttons BV'}), (s2:Supplier {name: 'Shenzhen Metal Co'})
MERGE (s1)-[:SOURCED_FROM {volume_kg_year: 2500, demo: true}]->(s2);

// ============================================================
// RELATIONSHIPS — Tier 2 → Raw Materials
// ============================================================
MATCH (s:Supplier {name: 'Saarstahl AG'}), (r:RawMaterial {name: 'Iron Ore Pellets'})
MERGE (s)-[:SOURCED_FROM {demo: true}]->(r);

MATCH (s:Supplier {name: 'Saarstahl AG'}), (r:RawMaterial {name: 'Steel Billets'})
MERGE (s)-[:SOURCED_FROM {demo: true}]->(r);

MATCH (s:Supplier {name: 'Infineon Technologies'}), (r:RawMaterial {name: 'Raw Silicon'})
MERGE (s)-[:SOURCED_FROM {demo: true, risk_flags: ['GEOPOLITICAL_RISK']}]->(r);

MATCH (s:Supplier {name: 'Shenzhen Metal Co'}), (r:RawMaterial {name: 'Metal Pins'})
MERGE (s)-[:SOURCED_FROM {demo: true}]->(r);

MATCH (s:Supplier {name: 'AMS Buttons BV'}), (r:RawMaterial {name: 'Plastic Pellets'})
MERGE (s)-[:SOURCED_FROM {demo: true}]->(r);

// LLM-inferred links (marked inferred: true)
MATCH (s:Supplier {name: 'AMS Buttons BV'}), (r:RawMaterial {name: 'Textile Dye'})
MERGE (s)-[:SOURCED_FROM {confidence: 0.7, source: 'LLM inference', inferred: true, demo: true}]->(r);

MATCH (s:Supplier {name: 'Michelin'}), (r:RawMaterial {name: 'Natural Rubber'})
MERGE (s)-[:SOURCED_FROM {origin: 'Thailand', demo: true}]->(r);

MATCH (s:Supplier {name: 'Michelin'}), (r:RawMaterial {name: 'Carbon Black'})
MERGE (s)-[:SOURCED_FROM {demo: true, risk_flags: ['GEOPOLITICAL_RISK']}]->(r);

// ============================================================
// CERTIFICATIONS
// ============================================================
MATCH (s:Supplier {name: 'ZF Friedrichshafen'}), (c:Certificate {name: 'IATF 16949:2016'})
MERGE (s)-[:CERTIFIED_BY {demo: true}]->(c);

MATCH (s:Supplier {name: 'AMS Buttons BV'}), (c:Certificate {name: 'REACH Compliance'})
MERGE (s)-[:CERTIFIED_BY {demo: true}]->(c);

MATCH (s:Supplier {name: 'SSAB'}), (c:Certificate {name: 'ISO 9001:2015'})
MERGE (s)-[:CERTIFIED_BY {demo: true}]->(c);

// ============================================================
// CORPORATE OWNERSHIP
// ============================================================
MATCH (s:Supplier {name: 'ZF Friedrichshafen'}), (c:Company {name: 'ZF Group'})
MERGE (s)-[:OWNED_BY {demo: true}]->(c);

MATCH (s:Supplier {name: 'Bosch'}), (c:Company {name: 'Robert Bosch GmbH'})
MERGE (s)-[:OWNED_BY {demo: true}]->(c);

// ============================================================
// VERIFICATION QUERY
// Run after loading to confirm graph is populated:
// ============================================================
// MATCH (p:Product)-[:SUPPLIED_BY|SOURCED_FROM*1..3]->(n)
// WHERE p.sku = 'SCANIA-R-500'
// RETURN count(DISTINCT n) AS nodes_reachable;
// Expected: 10+

// Full path query:
// MATCH path = (p:Product {sku:'SCANIA-R-500'})-[:SUPPLIED_BY|SOURCED_FROM*1..3]->(n)
// RETURN [node IN nodes(path) | coalesce(node.name, node.sku)] AS chain,
//        length(path) AS depth
// ORDER BY depth;

// ============================================================
// ADVANCED GRAPH EXTENSION (2026-08-12)
// Tier 3 suppliers, deeper corporate structure, more risk flags
// ============================================================

// ---- Tier 3 Suppliers ----
MERGE (lkab_mine:Supplier {name: 'LKAB Kiruna Mine', country: 'SE', tier: 3,
  website: 'https://www.lkab.com/kiruna', demo: true,
  risk_flags: ['CLIMATE_RISK', 'ARCTIC_OPERATIONS']});

MERGE (vale:Supplier {name: 'Vale SA', country: 'BR', tier: 3,
  website: 'https://www.vale.com', demo: true,
  risk_flags: ['ESG_RISK', 'TAILINGS_RISK']});

MERGE (codelco:Supplier {name: 'Codelco', country: 'CL', tier: 3,
  website: 'https://www.codelco.com', demo: true});

MERGE (tantalum_trader:Supplier {name: 'AVX Tantalum', country: 'US', tier: 3,
  website: 'https://www.avx.com', demo: true,
  risk_flags: ['CONFLICT_MINERAL']});

MERGE (rare_earth:Supplier {name: 'China Rare Earth Group', country: 'CN', tier: 3,
  website: 'https://www.chinarareearth.com', demo: true,
  risk_flags: ['GEOPOLITICAL_RISK', 'SINGLE_SOURCE', 'SANCTIONS_RISK']});

MERGE (basf_chem:Supplier {name: 'BASF SE', country: 'DE', tier: 3,
  website: 'https://www.basf.com', demo: true});

MERGE (thai_rubber:Supplier {name: 'Sri Trang Agro-Industry', country: 'TH', tier: 3,
  website: 'https://www.sritranggroup.com', demo: true,
  risk_flags: ['DEFORESTATION_RISK']});

MERGE (cabot_carbon:Supplier {name: 'Cabot Corporation', country: 'US', tier: 3,
  website: 'https://www.cabotcorp.com', demo: true});

// ---- Additional Tier 1 for Scania ----
MERGE (cummins:Supplier {name: 'Cummins Inc', country: 'US', tier: 1,
  website: 'https://www.cummins.com', demo: true,
  risk_flags: ['SINGLE_SOURCE']});

MERGE (continental:Supplier {name: 'Continental AG', country: 'DE', tier: 1,
  website: 'https://www.continental.com', demo: true});

// ---- Tier 2 additions ----
MERGE (outokumpu:Supplier {name: 'Outokumpu Oyj', country: 'FI', tier: 2,
  website: 'https://www.outokumpu.com', demo: true});

MERGE (ams_osram:Supplier {name: 'ams-OSRAM', country: 'AT', tier: 2,
  website: 'https://www.ams-osram.com', demo: true});

// ---- Additional Raw Materials ----
MERGE (r_tantalum:RawMaterial {name: 'Tantalum Ore', origin: 'CD',
  material_type: 'Metal', demo: true,
  risk_flags: ['CONFLICT_MINERAL', 'DODD_FRANK_REPORTABLE']});

MERGE (r_cobalt:RawMaterial {name: 'Cobalt', origin: 'CD',
  material_type: 'Metal', demo: true,
  risk_flags: ['CONFLICT_MINERAL', 'CHILD_LABOUR_RISK']});

MERGE (r_rareearth:RawMaterial {name: 'Rare Earth Elements', origin: 'CN',
  material_type: 'Mineral', demo: true,
  risk_flags: ['GEOPOLITICAL_RISK', 'SINGLE_SOURCE']});

MERGE (r_copper:RawMaterial {name: 'Copper Cathode', origin: 'CL',
  material_type: 'Metal', demo: true});

MERGE (r_ironore2:RawMaterial {name: 'Iron Ore Pellets (Brazil)', origin: 'BR',
  material_type: 'Mineral', demo: true,
  risk_flags: ['ESG_RISK']});

MERGE (r_abs:RawMaterial {name: 'ABS Plastic Resin', origin: 'DE',
  material_type: 'Polymer', demo: true});

MERGE (r_graphite:RawMaterial {name: 'Synthetic Graphite', origin: 'CN',
  material_type: 'Carbon', demo: true,
  risk_flags: ['GEOPOLITICAL_RISK']});

// ---- Additional Certificates ----
MERGE (iso14001:Certificate {name: 'ISO 14001:2015', issuer: 'TUV', valid_until: '2027-06-30',
  demo: true});
MERGE (conflict_free:Certificate {name: 'Conflict Minerals Free (CFSI)', issuer: 'RBA',
  valid_until: '2026-12-31', demo: true});
MERGE (rba:Certificate {name: 'RBA Code of Conduct', issuer: 'Responsible Business Alliance',
  valid_until: '2027-01-01', demo: true});

// ---- Additional Companies ----
MERGE (infineon_co:Company {name: 'Infineon Technologies AG', country: 'DE',
  industry: 'Semiconductors', demo: true});
MERGE (michelin_co:Company {name: 'Compagnie Générale des Établissements Michelin',
  country: 'FR', industry: 'Tyres/Rubber', demo: true});
MERGE (scania_parent:Company {name: 'Volkswagen Truck & Bus', country: 'DE',
  industry: 'Automotive', demo: true});

// ---- Corporate ownership ----
MATCH (s:Supplier {name: 'Scania AB'}), (c:Company {name: 'Volkswagen Truck & Bus'})
MERGE (s)-[:OWNED_BY {demo: true}]->(c);

MATCH (s:Supplier {name: 'Infineon Technologies'}), (c:Company {name: 'Infineon Technologies AG'})
MERGE (s)-[:OWNED_BY {demo: true}]->(c);

MATCH (s:Supplier {name: 'Michelin'}), (c:Company {name: 'Compagnie Générale des Établissements Michelin'})
MERGE (s)-[:OWNED_BY {demo: true}]->(c);

// ---- Scania Tier 1 additions ----
MATCH (p:Product {sku: 'SCANIA-R-500'}), (s:Supplier {name: 'Cummins Inc'})
MERGE (p)-[:SUPPLIED_BY {since: '2019-01-01', component: 'Euro6 engine variants', demo: true,
  risk_flags: ['SINGLE_SOURCE']}]->(s);

MATCH (p:Product {sku: 'SCANIA-R-500'}), (s:Supplier {name: 'Continental AG'})
MERGE (p)-[:SUPPLIED_BY {since: '2021-06-01', component: 'ADAS sensors and braking', demo: true}]->(s);

// ---- Tier 1 → Tier 2 additional ----
MATCH (s1:Supplier {name: 'Continental AG'}), (s2:Supplier {name: 'ams-OSRAM'})
MERGE (s1)-[:SOURCED_FROM {component: 'Optical sensors for LiDAR', demo: true}]->(s2);

MATCH (s1:Supplier {name: 'ZF Friedrichshafen'}), (s2:Supplier {name: 'Outokumpu Oyj'})
MERGE (s1)-[:SOURCED_FROM {component: 'Stainless steel for housings', demo: true}]->(s2);

// ---- Tier 2 → Tier 3 ----
MATCH (s1:Supplier {name: 'LKAB'}), (s2:Supplier {name: 'LKAB Kiruna Mine'})
MERGE (s1)-[:SOURCED_FROM {component: 'Iron ore extraction (Kiruna deposit)', demo: true}]->(s2);

MATCH (s1:Supplier {name: 'LKAB'}), (s2:Supplier {name: 'Vale SA'})
MERGE (s1)-[:SOURCED_FROM {component: 'Supplemental iron ore', demo: true}]->(s2);

MATCH (s1:Supplier {name: 'Infineon Technologies'}), (s2:Supplier {name: 'China Rare Earth Group'})
MERGE (s1)-[:SOURCED_FROM {component: 'Rare earth for magnets and phosphors', demo: true,
  risk_flags: ['GEOPOLITICAL_RISK', 'SINGLE_SOURCE']}]->(s2);

MATCH (s1:Supplier {name: 'Infineon Technologies'}), (s2:Supplier {name: 'AVX Tantalum'})
MERGE (s1)-[:SOURCED_FROM {component: 'Tantalum capacitors for ECU', demo: true}]->(s2);

MATCH (s1:Supplier {name: 'AMS Buttons BV'}), (s2:Supplier {name: 'BASF SE'})
MERGE (s1)-[:SOURCED_FROM {component: 'ABS resin for button bodies', demo: true}]->(s2);

MATCH (s1:Supplier {name: 'Michelin'}), (s2:Supplier {name: 'Sri Trang Agro-Industry'})
MERGE (s1)-[:SOURCED_FROM {component: 'Natural rubber sheets', demo: true}]->(s2);

MATCH (s1:Supplier {name: 'Michelin'}), (s2:Supplier {name: 'Cabot Corporation'})
MERGE (s1)-[:SOURCED_FROM {component: 'Carbon black reinforcement', demo: true}]->(s2);

// ---- Tier 3 → Raw materials ----
MATCH (s:Supplier {name: 'AVX Tantalum'}), (r:RawMaterial {name: 'Tantalum Ore'})
MERGE (s)-[:SOURCED_FROM {demo: true, risk_flags: ['CONFLICT_MINERAL']}]->(r);

MATCH (s:Supplier {name: 'China Rare Earth Group'}), (r:RawMaterial {name: 'Rare Earth Elements'})
MERGE (s)-[:SOURCED_FROM {demo: true}]->(r);

MATCH (s:Supplier {name: 'China Rare Earth Group'}), (r:RawMaterial {name: 'Synthetic Graphite'})
MERGE (s)-[:SOURCED_FROM {demo: true, risk_flags: ['GEOPOLITICAL_RISK']}]->(r);

MATCH (s:Supplier {name: 'Vale SA'}), (r:RawMaterial {name: 'Iron Ore Pellets (Brazil)'})
MERGE (s)-[:SOURCED_FROM {demo: true}]->(r);

MATCH (s:Supplier {name: 'Codelco'}), (r:RawMaterial {name: 'Copper Cathode'})
MERGE (s)-[:SOURCED_FROM {demo: true}]->(r);

MATCH (s:Supplier {name: 'BASF SE'}), (r:RawMaterial {name: 'ABS Plastic Resin'})
MERGE (s)-[:SOURCED_FROM {demo: true}]->(r);

MATCH (s:Supplier {name: 'Sri Trang Agro-Industry'}), (r:RawMaterial {name: 'Natural Rubber'})
MERGE (s)-[:SOURCED_FROM {demo: true, risk_flags: ['DEFORESTATION_RISK']}]->(r);

// ---- Certifications (additional) ----
MATCH (s:Supplier {name: 'Infineon Technologies'}), (c:Certificate {name: 'RBA Code of Conduct'})
MERGE (s)-[:CERTIFIED_BY {demo: true}]->(c);

MATCH (s:Supplier {name: 'AVX Tantalum'}), (c:Certificate {name: 'Conflict Minerals Free (CFSI)'})
MERGE (s)-[:CERTIFIED_BY {demo: true}]->(c);

MATCH (s:Supplier {name: 'SSAB'}), (c:Certificate {name: 'ISO 14001:2015'})
MERGE (s)-[:CERTIFIED_BY {demo: true}]->(c);

MATCH (s:Supplier {name: 'Michelin'}), (c:Certificate {name: 'ISO 14001:2015'})
MERGE (s)-[:CERTIFIED_BY {demo: true}]->(c);

// ============================================================
// VERIFICATION (extended)
// MATCH (n) WHERE n.demo = true RETURN labels(n)[0] AS type, count(n) AS count
// ORDER BY count DESC;
// Expected: Supplier ~18, RawMaterial ~12, Certificate ~6, Company ~6, Product ~2
// ============================================================
