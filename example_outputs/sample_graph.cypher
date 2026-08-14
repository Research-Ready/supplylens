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
MERGE (ams:Supplier {name: 'AMS Buttons BV', country: 'NL', tier: 1, website: 'https://www.amsbuttons.nl', demo: true})
ON CREATE SET ams.country = 'NL'
ON MATCH  SET ams.country = 'NL';

// ============================================================
// TIER 2 — Sub-suppliers
// ============================================================
MERGE (saar:Supplier {name: 'Saarstahl AG', country: 'DE', tier: 2, demo: true});
MERGE (inf:Supplier {name: 'Infineon Technologies', country: 'DE', tier: 2, demo: true});
MERGE (sen:Supplier {name: 'Sensata Technologies', country: 'NL', tier: 2, demo: true});
MERGE (lkab:Supplier {name: 'LKAB', country: 'SE', tier: 2, demo: true});
MERGE (shen:Supplier {name: 'Shenzhen Metal Co', country: 'CN', tier: 2, demo: true})
ON CREATE SET shen.country = 'CN'
ON MATCH  SET shen.country = 'CN';

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
// TIER 4 + ADDITIONAL PRODUCTS (2026-08-12)
// Mining companies, chemical plants, more Scania products
// ============================================================

// ---- Additional Scania products (share Tier-1 suppliers) ----
MERGE (p3:Product {sku: 'SCANIA-T-500', name: 'Scania T-series Truck', category: 'Commercial Vehicles', demo: true});
MERGE (p4:Product {sku: 'SCANIA-BUS-K', name: 'Scania Citywide Bus', category: 'Public Transport', demo: true});
MERGE (p5:Product {sku: 'SCANIA-ENG-DC13', name: 'Scania DC13 Engine', category: 'Powertrain', demo: true});

// T-series shares many Tier-1 suppliers with R-series
MATCH (p:Product {sku:'SCANIA-T-500'}), (s:Supplier {name:'ZF Friedrichshafen'})
MERGE (p)-[:SUPPLIED_BY {component:'OptiCruise gearbox', since:'2016-01-01', demo:true}]->(s);
MATCH (p:Product {sku:'SCANIA-T-500'}), (s:Supplier {name:'SSAB'})
MERGE (p)-[:SUPPLIED_BY {component:'Chassis steel', since:'2016-01-01', demo:true}]->(s);
MATCH (p:Product {sku:'SCANIA-T-500'}), (s:Supplier {name:'Michelin'})
MERGE (p)-[:SUPPLIED_BY {component:'X MultiWay tyres', since:'2016-01-01', demo:true}]->(s);

// Bus uses different gearbox supplier
MERGE (voith:Supplier {name:'Voith GmbH', country:'DE', tier:1, website:'https://www.voith.com', demo:true});
MATCH (p:Product {sku:'SCANIA-BUS-K'}), (s:Supplier {name:'Voith GmbH'})
MERGE (p)-[:SUPPLIED_BY {component:'DIWA automatic transmission', since:'2018-01-01', demo:true}]->(s);
MATCH (p:Product {sku:'SCANIA-BUS-K'}), (s:Supplier {name:'Cummins Inc'})
MERGE (p)-[:SUPPLIED_BY {component:'Euro6 CNG engine', since:'2018-01-01', demo:true}]->(s);
MATCH (p:Product {sku:'SCANIA-BUS-K'}), (s:Supplier {name:'Continental AG'})
MERGE (p)-[:SUPPLIED_BY {component:'iBUS e-ticketing + ADAS', since:'2020-01-01', demo:true}]->(s);

// DC13 Engine
MERGE (skf:Supplier {name:'SKF Group', country:'SE', tier:1, website:'https://www.skf.com', demo:true});
MERGE (timken:Supplier {name:'Timken Company', country:'US', tier:1, website:'https://www.timken.com',
  demo:true, risk_flags:['SINGLE_SOURCE']});
MATCH (p:Product {sku:'SCANIA-ENG-DC13'}), (s:Supplier {name:'Bosch'})
MERGE (p)-[:SUPPLIED_BY {component:'XPI fuel injection system', since:'2014-01-01', demo:true}]->(s);
MATCH (p:Product {sku:'SCANIA-ENG-DC13'}), (s:Supplier {name:'SKF Group'})
MERGE (p)-[:SUPPLIED_BY {component:'Crankshaft bearings', since:'2010-01-01', demo:true}]->(s);
MATCH (p:Product {sku:'SCANIA-ENG-DC13'}), (s:Supplier {name:'Timken Company'})
MERGE (p)-[:SUPPLIED_BY {component:'Roller bearings for camshaft', since:'2012-01-01',
  demo:true, risk_flags:['SINGLE_SOURCE']}]->(s);

// ---- Tier 2 for new Tier-1 ----
MERGE (gkn:Supplier {name:'GKN Automotive', country:'GB', tier:2, demo:true});
MERGE (norsk:Supplier {name:'Norsk Hydro', country:'NO', tier:2,
  website:'https://www.hydro.com', demo:true});
MERGE (rio:Supplier {name:'Rio Tinto', country:'AU', tier:2,
  website:'https://www.riotinto.com', demo:true, risk_flags:['ESG_RISK']});

MATCH (s1:Supplier {name:'Voith GmbH'}), (s2:Supplier {name:'GKN Automotive'})
MERGE (s1)-[:SOURCED_FROM {component:'Clutch packs and friction elements', demo:true}]->(s2);
MATCH (s1:Supplier {name:'SKF Group'}), (s2:Supplier {name:'Norsk Hydro'})
MERGE (s1)-[:SOURCED_FROM {component:'Aluminium alloy for bearing housings', demo:true}]->(s2);

// ---- Tier 4 — Mining & Chemical Plants ----
MERGE (lkab_kirunav:Supplier {name:'LKAB Kiirunavaara Shaft', country:'SE', tier:4,
  demo:true, risk_flags:['CLIMATE_RISK','WATER_STRESS']});
MERGE (glencore:Supplier {name:'Glencore', country:'CH', tier:4,
  website:'https://www.glencore.com', demo:true,
  risk_flags:['ESG_RISK','CONFLICT_MINERAL','SANCTIONS_RISK']});
MERGE (freeport:Supplier {name:'Freeport-McMoRan', country:'US', tier:4,
  website:'https://www.fcx.com', demo:true, risk_flags:['ESG_RISK','WATER_STRESS']});
MERGE (basf_ludwigsh:Supplier {name:'BASF Ludwigshafen Complex', country:'DE', tier:4,
  demo:true, risk_flags:['CLIMATE_RISK','ENERGY_RISK']});
MERGE (cabot_billerica:Supplier {name:'Cabot Billerica R&D', country:'US', tier:4, demo:true});
MERGE (xinjiang_poly:Supplier {name:'Xinjiang Polysilicon Co', country:'CN', tier:4,
  demo:true, risk_flags:['GEOPOLITICAL_RISK','SANCTIONS_RISK','FORCED_LABOUR_RISK']});
MERGE (siltronic:Supplier {name:'Siltronic AG', country:'DE', tier:4,
  website:'https://www.siltronic.com', demo:true});
MERGE (umicore:Supplier {name:'Umicore SA', country:'BE', tier:4,
  website:'https://www.umicore.com', demo:true});

// Tier 3 → Tier 4 links
MATCH (s1:Supplier {name:'LKAB Kiruna Mine'}), (s2:Supplier {name:'LKAB Kiirunavaara Shaft'})
MERGE (s1)-[:SOURCED_FROM {component:'Iron ore from sublevel caving, 1365m depth', demo:true}]->(s2);

MATCH (s1:Supplier {name:'AVX Tantalum'}), (s2:Supplier {name:'Glencore'})
MERGE (s1)-[:SOURCED_FROM {component:'Cobalt and tantalum-bearing ore', demo:true,
  risk_flags:['CONFLICT_MINERAL']}]->(s2);

MATCH (s1:Supplier {name:'Codelco'}), (s2:Supplier {name:'Freeport-McMoRan'})
MERGE (s1)-[:SOURCED_FROM {component:'Copper cathode exchange / spot market', demo:true}]->(s2);

MATCH (s1:Supplier {name:'BASF SE'}), (s2:Supplier {name:'BASF Ludwigshafen Complex'})
MERGE (s1)-[:SOURCED_FROM {component:'ABS resin polymerisation (Verbund site)', demo:true}]->(s2);

MATCH (s1:Supplier {name:'Cabot Corporation'}), (s2:Supplier {name:'Cabot Billerica R&D'})
MERGE (s1)-[:SOURCED_FROM {component:'Carbon black formulation IP', demo:true}]->(s2);

MATCH (s1:Supplier {name:'China Rare Earth Group'}), (s2:Supplier {name:'Xinjiang Polysilicon Co'})
MERGE (s1)-[:SOURCED_FROM {component:'Quartz and process chemicals', demo:true,
  risk_flags:['FORCED_LABOUR_RISK','SANCTIONS_RISK']}]->(s2);

MATCH (s1:Supplier {name:'Infineon Technologies'}), (s2:Supplier {name:'Siltronic AG'})
MERGE (s1)-[:SOURCED_FROM {component:'300mm silicon wafers', demo:true}]->(s2);
MATCH (s1:Supplier {name:'Infineon Technologies'}), (s2:Supplier {name:'Umicore SA'})
MERGE (s1)-[:SOURCED_FROM {component:'High-purity target materials for sputtering', demo:true}]->(s2);

MATCH (s1:Supplier {name:'Norsk Hydro'}), (s2:Supplier {name:'Rio Tinto'})
MERGE (s1)-[:SOURCED_FROM {component:'Bauxite → alumina supply', demo:true}]->(s2);

// ---- Tier 4 Raw Materials ----
MERGE (r_bauxite:RawMaterial {name:'Bauxite', origin:'AU', material_type:'Mineral',
  demo:true, risk_flags:['ESG_RISK']});
MERGE (r_cobalt:RawMaterial {name:'Cobalt Hydroxide', origin:'CD',
  material_type:'Metal', demo:true, risk_flags:['CONFLICT_MINERAL','CHILD_LABOUR_RISK']});
MERGE (r_quartz:RawMaterial {name:'High-Purity Quartz', origin:'NO',
  material_type:'Mineral', demo:true});
MERGE (r_natgas:RawMaterial {name:'Natural Gas (feedstock)', origin:'RU',
  material_type:'Energy', demo:true, risk_flags:['GEOPOLITICAL_RISK','ENERGY_RISK','SANCTIONS_RISK']});
MERGE (r_water:RawMaterial {name:'Process Water (Atacama)', origin:'CL',
  material_type:'Resource', demo:true, risk_flags:['WATER_STRESS']});

MATCH (s:Supplier {name:'Freeport-McMoRan'}), (r:RawMaterial {name:'Copper Cathode'})
MERGE (s)-[:SOURCED_FROM {demo:true}]->(r);
MATCH (s:Supplier {name:'Rio Tinto'}), (r:RawMaterial {name:'Bauxite'})
MERGE (s)-[:SOURCED_FROM {demo:true}]->(r);
MATCH (s:Supplier {name:'Glencore'}), (r:RawMaterial {name:'Cobalt Hydroxide'})
MERGE (s)-[:SOURCED_FROM {demo:true, risk_flags:['CONFLICT_MINERAL']}]->(r);
MATCH (s:Supplier {name:'BASF Ludwigshafen Complex'}), (r:RawMaterial {name:'Natural Gas (feedstock)'})
MERGE (s)-[:SOURCED_FROM {demo:true, risk_flags:['ENERGY_RISK','SANCTIONS_RISK']}]->(r);
MATCH (s:Supplier {name:'Siltronic AG'}), (r:RawMaterial {name:'High-Purity Quartz'})
MERGE (s)-[:SOURCED_FROM {demo:true}]->(r);
MATCH (s:Supplier {name:'Freeport-McMoRan'}), (r:RawMaterial {name:'Process Water (Atacama)'})
MERGE (s)-[:SOURCED_FROM {demo:true, risk_flags:['WATER_STRESS']}]->(r);

// ---- More certificates ----
MERGE (iso45001:Certificate {name:'ISO 45001:2018', issuer:'TUV SUD',
  valid_until:'2027-08-01', demo:true});
MERGE (sedex:Certificate {name:'SEDEX SMETA Audit', issuer:'Sedex',
  valid_until:'2026-06-30', demo:true});
MERGE (lksg:Certificate {name:'LkSG Compliance (German Supply Chain Act)',
  issuer:'TUV Rheinland', valid_until:'2027-01-01', demo:true});

MATCH (s:Supplier {name:'Glencore'}), (c:Certificate {name:'ISO 14001:2015'})
MERGE (s)-[:CERTIFIED_BY {demo:true}]->(c);
MATCH (s:Supplier {name:'Vale SA'}), (c:Certificate {name:'ISO 45001:2018'})
MERGE (s)-[:CERTIFIED_BY {demo:true}]->(c);
MATCH (s:Supplier {name:'Bosch'}), (c:Certificate {name:'LkSG Compliance (German Supply Chain Act)'})
MERGE (s)-[:CERTIFIED_BY {demo:true}]->(c);
MATCH (s:Supplier {name:'ZF Friedrichshafen'}), (c:Certificate {name:'LkSG Compliance (German Supply Chain Act)'})
MERGE (s)-[:CERTIFIED_BY {demo:true}]->(c);
MATCH (s:Supplier {name:'Sri Trang Agro-Industry'}), (c:Certificate {name:'SEDEX SMETA Audit'})
MERGE (s)-[:CERTIFIED_BY {demo:true}]->(c);

// ---- Geopolitical Event nodes ----
MERGE (evt1:Event {name:'China Rare Earth Export Controls 2023',
  date:'2023-07-03', type:'REGULATORY', affected_material:'Gallium/Germanium',
  impact:'HIGH', demo:true});
MERGE (evt2:Event {name:'Russia Ukraine War — Gas Supply Disruption',
  date:'2022-02-24', type:'CONFLICT', affected_material:'Natural Gas',
  impact:'HIGH', demo:true});
MERGE (evt3:Event {name:'DRC Artisanal Mining Child Labour Reports 2022',
  date:'2022-01-01', type:'ESG', affected_material:'Cobalt',
  impact:'MEDIUM', demo:true});
MERGE (evt4:Event {name:'EU Critical Raw Materials Act 2024',
  date:'2024-03-18', type:'REGULATORY', affected_material:'Rare Earths/Silicon',
  impact:'MEDIUM', demo:true});

MATCH (r:RawMaterial {name:'Rare Earth Elements'}), (e:Event {name:'China Rare Earth Export Controls 2023'})
MERGE (r)-[:AFFECTED_BY {demo:true}]->(e);
MATCH (r:RawMaterial {name:'Natural Gas (feedstock)'}), (e:Event {name:'Russia Ukraine War — Gas Supply Disruption'})
MERGE (r)-[:AFFECTED_BY {demo:true}]->(e);
MATCH (r:RawMaterial {name:'Cobalt Hydroxide'}), (e:Event {name:'DRC Artisanal Mining Child Labour Reports 2022'})
MERGE (r)-[:AFFECTED_BY {demo:true}]->(e);

// ============================================================
// FINANCIAL & OPERATIONAL DATA (v4 — 2026-08-12)
// Adds contract_value_eur, lead_time_days, annual_volume_eur to key relationships
// Adds annual_revenue_eur, employee_count, founded_year to supplier nodes
// ============================================================

// ── Supplier financial profiles ───────────────────────────────────────────────
MATCH (s:Supplier {name:'ZF Friedrichshafen'})
SET s.annual_revenue_eur = 46600000000, s.employee_count = 165000,
    s.founded_year = 1915, s.headquarters = 'Friedrichshafen, DE';

MATCH (s:Supplier {name:'Bosch'})
SET s.annual_revenue_eur = 91600000000, s.employee_count = 421000,
    s.founded_year = 1886, s.headquarters = 'Stuttgart, DE';

MATCH (s:Supplier {name:'SSAB'})
SET s.annual_revenue_eur = 9800000000, s.employee_count = 16800,
    s.founded_year = 1978, s.headquarters = 'Stockholm, SE';

MATCH (s:Supplier {name:'Michelin'})
SET s.annual_revenue_eur = 28600000000, s.employee_count = 132000,
    s.founded_year = 1889, s.headquarters = 'Clermont-Ferrand, FR';

MATCH (s:Supplier {name:'Dana Incorporated'})
SET s.annual_revenue_eur = 9700000000, s.employee_count = 37000,
    s.founded_year = 1904, s.headquarters = 'Maumee, OH, US',
    s.risk_flags = ['SINGLE_SOURCE'];

MATCH (s:Supplier {name:'Saarstahl AG'})
SET s.annual_revenue_eur = 2800000000, s.employee_count = 6700,
    s.founded_year = 1881, s.headquarters = 'Völklingen, DE';

MATCH (s:Supplier {name:'Infineon Technologies'})
SET s.annual_revenue_eur = 16300000000, s.employee_count = 58000,
    s.founded_year = 1999, s.headquarters = 'Neubiberg, DE';

MATCH (s:Supplier {name:'LKAB'})
SET s.annual_revenue_eur = 4200000000, s.employee_count = 5000,
    s.founded_year = 1890, s.headquarters = 'Luleå, SE';

MATCH (s:Supplier {name:'China Rare Earth Group'})
SET s.annual_revenue_eur = 8900000000, s.employee_count = 140000,
    s.founded_year = 2021, s.headquarters = 'Nanchang, CN',
    s.state_owned = true;

MATCH (s:Supplier {name:'Vale SA'})
SET s.annual_revenue_eur = 38500000000, s.employee_count = 96000,
    s.founded_year = 1942, s.headquarters = 'Rio de Janeiro, BR';

MATCH (s:Supplier {name:'Glencore'})
SET s.annual_revenue_eur = 255000000000, s.employee_count = 135000,
    s.founded_year = 1974, s.headquarters = 'Baar, CH';

// ── SUPPLIED_BY financial properties (Tier 1 contracts) ──────────────────────
// ZF gearbox: est. €1.2B/year for Scania, 90-day lead time, sole-source
MATCH (p:Product {sku:'SCANIA-R-500'})-[r:SUPPLIED_BY]->(s:Supplier {name:'ZF Friedrichshafen'})
SET r.contract_value_eur = 1200000000, r.lead_time_days = 90,
    r.annual_volume_eur = 1200000000, r.single_source = true,
    r.contract_end = '2028-12-31', r.risk_flags = ['SINGLE_SOURCE'];

// Bosch fuel injection + ECU
MATCH (p:Product {sku:'SCANIA-R-500'})-[r:SUPPLIED_BY]->(s:Supplier {name:'Bosch'})
SET r.contract_value_eur = 800000000, r.lead_time_days = 60,
    r.annual_volume_eur = 800000000, r.contract_end = '2027-06-30';

// SSAB steel
MATCH (p:Product {sku:'SCANIA-R-500'})-[r:SUPPLIED_BY]->(s:Supplier {name:'SSAB'})
SET r.contract_value_eur = 320000000, r.lead_time_days = 30,
    r.annual_volume_eur = 320000000, r.volume_tonnes_year = 140000;

// Michelin tyres
MATCH (p:Product {sku:'SCANIA-R-500'})-[r:SUPPLIED_BY]->(s:Supplier {name:'Michelin'})
SET r.contract_value_eur = 180000000, r.lead_time_days = 21,
    r.annual_volume_eur = 180000000, r.volume_units_year = 540000;

// Dana driveshafts
MATCH (p:Product {sku:'SCANIA-R-500'})-[r:SUPPLIED_BY]->(s:Supplier {name:'Dana Incorporated'})
SET r.contract_value_eur = 420000000, r.lead_time_days = 75,
    r.annual_volume_eur = 420000000, r.single_source = true,
    r.risk_flags = ['SINGLE_SOURCE'];

// ── SOURCED_FROM financial properties ─────────────────────────────────────────
// Saarstahl steel billets to ZF
MATCH (s1:Supplier {name:'ZF Friedrichshafen'})-[r:SOURCED_FROM]->(s2:Supplier {name:'Saarstahl AG'})
SET r.contract_value_eur = 85000000, r.lead_time_days = 45,
    r.volume_kg_year = 180000;

// Infineon semiconductors to Bosch
MATCH (s1:Supplier {name:'Bosch'})-[r:SOURCED_FROM]->(s2:Supplier {name:'Infineon Technologies'})
SET r.contract_value_eur = 340000000, r.lead_time_days = 180,
    r.annual_volume_eur = 340000000;

// LKAB iron ore to SSAB
MATCH (s1:Supplier {name:'SSAB'})-[r:SOURCED_FROM]->(s2:Supplier {name:'LKAB'})
SET r.contract_value_eur = 960000000, r.lead_time_days = 14,
    r.volume_kg_year = 5000000;

// ── Annual revenue updates ────────────────────────────────────────────────────
// Add employee_count + certification flags to remaining key suppliers
MATCH (s:Supplier {name:'Voith GmbH'})
SET s.annual_revenue_eur = 4700000000, s.employee_count = 20000, s.founded_year = 1867;

MATCH (s:Supplier {name:'SKF Group'})
SET s.annual_revenue_eur = 9400000000, s.employee_count = 40000, s.founded_year = 1907;

MATCH (s:Supplier {name:'Norsk Hydro'})
SET s.annual_revenue_eur = 22300000000, s.employee_count = 33000, s.founded_year = 1905;

MATCH (s:Supplier {name:'Siltronic AG'})
SET s.annual_revenue_eur = 1850000000, s.employee_count = 4800, s.founded_year = 1968;

MATCH (s:Supplier {name:'AVX Tantalum'})
SET s.annual_revenue_eur = 1600000000, s.employee_count = 14000, s.founded_year = 1972;

// ── AMS Buttons financials ────────────────────────────────────────────────────
MATCH (s:Supplier {name:'AMS Buttons BV'})
SET s.annual_revenue_eur = 12000000, s.employee_count = 45, s.founded_year = 1987,
    s.headquarters = 'Almere, NL';

MATCH (p:Product {sku:'BTN-001'})-[r:SUPPLIED_BY]->(s:Supplier {name:'AMS Buttons BV'})
SET r.contract_value_eur = 850000, r.lead_time_days = 14,
    r.annual_volume_eur = 850000, r.volume_units_year = 5700000;

// ============================================================
// SUPPLY CHAIN v5 — Dana/Cummins/Knorr-Bremse sub-chains (2026-08-12)
// Fills gaps: full T2/T3 for previously stub suppliers
// Adds: Kotaemon doc references, certificate expirations, alt supplier links
// ============================================================

// ---- New Tier 1: Knorr-Bremse ----
MERGE (knorr:Supplier {name:'Knorr-Bremse AG', country:'DE', tier:1,
  website:'https://www.knorr-bremse.com', demo:true,
  annual_revenue_eur:7200000000, employee_count:31000, founded_year:1905,
  headquarters:'Munich, DE'});

MATCH (p:Product {sku:'SCANIA-R-500'}), (s:Supplier {name:'Knorr-Bremse AG'})
MERGE (p)-[:SUPPLIED_BY {since:'2013-01-01', component:'EBS braking system + ABS',
  contract_value_eur:210000000, lead_time_days:45,
  annual_volume_eur:210000000, demo:true}]->(s);

MATCH (p:Product {sku:'SCANIA-BUS-K'}), (s:Supplier {name:'Knorr-Bremse AG'})
MERGE (p)-[:SUPPLIED_BY {since:'2018-01-01', component:'Air disc brakes + EBS',
  contract_value_eur:95000000, lead_time_days:45, demo:true}]->(s);

// ---- New Tier 2: Dana sub-suppliers ----
MERGE (timken:Supplier {name:'TimkenSteel Corporation', country:'US', tier:2,
  website:'https://www.timkensteel.com', demo:true,
  annual_revenue_eur:1700000000, employee_count:4500, founded_year:1899,
  risk_flags:['SINGLE_SOURCE'],
  headquarters:'Canton, OH, US',
  kotaemon_doc:'timkensteel_capability_statement.pdf'});

MERGE (eaton:Supplier {name:'Eaton Corporation', country:'US', tier:2,
  website:'https://www.eaton.com', demo:true,
  annual_revenue_eur:20400000000, employee_count:96000, founded_year:1911,
  headquarters:'Dublin, IE'});

MERGE (parker:Supplier {name:'Parker Hannifin', country:'US', tier:2,
  website:'https://www.parker.com', demo:true,
  annual_revenue_eur:19800000000, employee_count:57900, founded_year:1917,
  headquarters:'Cleveland, OH, US'});

MATCH (s1:Supplier {name:'Dana Incorporated'}), (s2:Supplier {name:'TimkenSteel Corporation'})
MERGE (s1)-[:SOURCED_FROM {component:'SBQ steel bars for axle shafts',
  contract_value_eur:68000000, lead_time_days:60,
  volume_kg_year:95000, single_source:true, demo:true}]->(s2);

MATCH (s1:Supplier {name:'Dana Incorporated'}), (s2:Supplier {name:'Eaton Corporation'})
MERGE (s1)-[:SOURCED_FROM {component:'Locking differential assemblies',
  contract_value_eur:92000000, lead_time_days:55, demo:true}]->(s2);

MATCH (s1:Supplier {name:'Dana Incorporated'}), (s2:Supplier {name:'Parker Hannifin'})
MERGE (s1)-[:SOURCED_FROM {component:'Hydraulic seals and o-ring kits',
  contract_value_eur:24000000, lead_time_days:30, demo:true}]->(s2);

// ---- New Tier 2: Cummins sub-suppliers ----
MERGE (garrett:Supplier {name:'Garrett Motion', country:'US', tier:2,
  website:'https://www.garrettmotion.com', demo:true,
  annual_revenue_eur:3200000000, employee_count:6200, founded_year:2018,
  risk_flags:['SINGLE_SOURCE'],
  headquarters:'Rolle, CH',
  kotaemon_doc:'garrett_turbocharger_spec_sheet.pdf'});

MERGE (borgwarner:Supplier {name:'BorgWarner', country:'US', tier:2,
  website:'https://www.borgwarner.com', demo:true,
  annual_revenue_eur:14200000000, employee_count:50000, founded_year:1928,
  headquarters:'Auburn Hills, MI, US'});

MERGE (tenneco:Supplier {name:'Tenneco Inc', country:'US', tier:2,
  website:'https://www.tenneco.com', demo:true,
  annual_revenue_eur:18000000000, employee_count:71000, founded_year:1888,
  headquarters:'Lake Forest, IL, US'});

MATCH (s1:Supplier {name:'Cummins Inc'}), (s2:Supplier {name:'Garrett Motion'})
MERGE (s1)-[:SOURCED_FROM {component:'VGT turbocharger for Euro6 engines',
  contract_value_eur:145000000, lead_time_days:120, single_source:true,
  risk_flags:['SINGLE_SOURCE'], demo:true}]->(s2);

MATCH (s1:Supplier {name:'Cummins Inc'}), (s2:Supplier {name:'BorgWarner'})
MERGE (s1)-[:SOURCED_FROM {component:'EGR cooler and diesel particulate filter',
  contract_value_eur:88000000, lead_time_days:90, demo:true}]->(s2);

MATCH (s1:Supplier {name:'Cummins Inc'}), (s2:Supplier {name:'Tenneco Inc'})
MERGE (s1)-[:SOURCED_FROM {component:'Pistons and engine bearings (Federal-Mogul)',
  contract_value_eur:76000000, lead_time_days:45, demo:true}]->(s2);

// ---- New Tier 2: Knorr-Bremse sub-suppliers ----
MERGE (haldex:Supplier {name:'Haldex AB', country:'SE', tier:2,
  website:'https://www.haldex.com', demo:true,
  annual_revenue_eur:510000000, employee_count:2200, founded_year:1887,
  headquarters:'Landskrona, SE'});

MERGE (ferodo:Supplier {name:'Federal-Mogul Motorparts', country:'US', tier:2,
  website:'https://www.fm-motorparts.com', demo:true,
  annual_revenue_eur:2100000000, employee_count:18000, founded_year:1899});

MATCH (s1:Supplier {name:'Knorr-Bremse AG'}), (s2:Supplier {name:'Haldex AB'})
MERGE (s1)-[:SOURCED_FROM {component:'Brake actuators and slack adjusters',
  contract_value_eur:38000000, lead_time_days:35, demo:true}]->(s2);

MATCH (s1:Supplier {name:'Knorr-Bremse AG'}), (s2:Supplier {name:'Federal-Mogul Motorparts'})
MERGE (s1)-[:SOURCED_FROM {component:'Brake pads and friction lining',
  contract_value_eur:29000000, lead_time_days:21, demo:true}]->(s2);

// ---- Voith T2 addition ----
MERGE (schaeffler:Supplier {name:'Schaeffler Group', country:'DE', tier:2,
  website:'https://www.schaeffler.com', demo:true,
  annual_revenue_eur:16300000000, employee_count:84000, founded_year:1946,
  headquarters:'Herzogenaurach, DE'});

MATCH (s1:Supplier {name:'Voith GmbH'}), (s2:Supplier {name:'Schaeffler Group'})
MERGE (s1)-[:SOURCED_FROM {component:'Torque converter bearings and clutch actuation',
  contract_value_eur:52000000, lead_time_days:60, demo:true}]->(s2);

// ---- New Tier 3: sub-suppliers of T2 additions ----
MERGE (north_star:Supplier {name:'North Star BlueScope Steel', country:'AU', tier:3,
  website:'https://www.northstarbluesteel.com', demo:true,
  annual_revenue_eur:890000000, employee_count:1200, founded_year:1995,
  risk_flags:['ENERGY_RISK']});

MERGE (ovako:Supplier {name:'Ovako AB', country:'SE', tier:3,
  website:'https://www.ovako.com', demo:true,
  annual_revenue_eur:1200000000, employee_count:3100, founded_year:1916,
  headquarters:'Stockholm, SE'});

MERGE (honeywell_pm:Supplier {name:'Honeywell Performance Materials', country:'US', tier:3,
  website:'https://www.honeywell.com', demo:true,
  annual_revenue_eur:5600000000, employee_count:19000, founded_year:1906});

MERGE (nisshinbo:Supplier {name:'Nisshinbo Holdings', country:'JP', tier:3,
  website:'https://www.nisshinbo.co.jp', demo:true,
  annual_revenue_eur:2900000000, employee_count:11000, founded_year:1907,
  risk_flags:['GEOPOLITICAL_RISK']});

MATCH (s1:Supplier {name:'TimkenSteel Corporation'}), (s2:Supplier {name:'North Star BlueScope Steel'})
MERGE (s1)-[:SOURCED_FROM {component:'Hot-rolled steel billet feedstock',
  contract_value_eur:28000000, lead_time_days:30, demo:true}]->(s2);

MATCH (s1:Supplier {name:'SKF Group'}), (s2:Supplier {name:'Ovako AB'})
MERGE (s1)-[:SOURCED_FROM {component:'Bearing-grade steel (isotropic, fine-grain)',
  contract_value_eur:180000000, lead_time_days:45, demo:true}]->(s2);

MATCH (s1:Supplier {name:'Garrett Motion'}), (s2:Supplier {name:'Honeywell Performance Materials'})
MERGE (s1)-[:SOURCED_FROM {component:'Turbine housing castings (titanium aluminide)',
  contract_value_eur:42000000, lead_time_days:90, demo:true}]->(s2);

MATCH (s1:Supplier {name:'Federal-Mogul Motorparts'}), (s2:Supplier {name:'Nisshinbo Holdings'})
MERGE (s1)-[:SOURCED_FROM {component:'Aramid friction material for brake pads',
  contract_value_eur:18000000, lead_time_days:60,
  risk_flags:['SINGLE_SOURCE'], demo:true}]->(s2);

// ---- New Raw Materials (v5) ----
MERGE (r_sbq:RawMaterial {name:'Special Bar Quality Steel', origin:'US',
  material_type:'Metal', demo:true,
  description:'High-alloy steel for driveshafts and axle shafts'});

MERGE (r_tial:RawMaterial {name:'Titanium Aluminide Alloy', origin:'JP',
  material_type:'Metal', demo:true,
  risk_flags:['SINGLE_SOURCE','GEOPOLITICAL_RISK'],
  description:'Intermetallic for turbocharger turbine wheels'});

MERGE (r_aramid:RawMaterial {name:'Aramid Fiber (Kevlar)', origin:'NL',
  material_type:'Polymer', demo:true,
  description:'DuPont Kevlar for brake friction material'});

MERGE (r_cng:RawMaterial {name:'Compressed Natural Gas', origin:'NL',
  material_type:'Energy', demo:true,
  description:'CNG for bus fuel system — grid-supplied'});

MATCH (s:Supplier {name:'North Star BlueScope Steel'}), (r:RawMaterial {name:'Special Bar Quality Steel'})
MERGE (s)-[:SOURCED_FROM {demo:true}]->(r);

MATCH (s:Supplier {name:'Honeywell Performance Materials'}), (r:RawMaterial {name:'Titanium Aluminide Alloy'})
MERGE (s)-[:SOURCED_FROM {demo:true, risk_flags:['SINGLE_SOURCE']}]->(r);

MATCH (s:Supplier {name:'Nisshinbo Holdings'}), (r:RawMaterial {name:'Aramid Fiber (Kevlar)'})
MERGE (s)-[:SOURCED_FROM {demo:true}]->(r);

// ---- Alternative supplier relationships ----
// ALT_SUPPLIER: potential fallback if primary fails
MERGE (akebono:Supplier {name:'Akebono Brake Industry', country:'JP', tier:2,
  website:'https://www.akebono-brake.com', demo:true,
  annual_revenue_eur:840000000, employee_count:11500, founded_year:1929,
  tags:['ALTERNATIVE_SUPPLIER']});

MERGE (brembo:Supplier {name:'Brembo SpA', country:'IT', tier:2,
  website:'https://www.brembo.com', demo:true,
  annual_revenue_eur:3600000000, employee_count:14500, founded_year:1961,
  tags:['ALTERNATIVE_SUPPLIER']});

// Mark as alternatives (not currently contracted)
MATCH (s1:Supplier {name:'Knorr-Bremse AG'}), (s2:Supplier {name:'Akebono Brake Industry'})
MERGE (s1)-[:ALT_SOURCE {component:'Brake pad friction materials', qualification_status:'QUALIFIED',
  demo:true, note:'Approved alternative — not currently on contract'}]->(s2);

MATCH (s1:Supplier {name:'Knorr-Bremse AG'}), (s2:Supplier {name:'Brembo SpA'})
MERGE (s1)-[:ALT_SOURCE {component:'High-performance disc brakes (upmarket)',
  qualification_status:'UNDER_REVIEW', demo:true}]->(s2);

// ---- Kotaemon document references on supplier nodes ----
MATCH (s:Supplier {name:'ZF Friedrichshafen'})
SET s.kotaemon_docs = ['zf_annual_report_2023.pdf','zf_supplier_code_of_conduct.pdf'];

MATCH (s:Supplier {name:'Bosch'})
SET s.kotaemon_docs = ['bosch_sustainability_report_2023.pdf','bosch_purchasing_conditions.pdf'];

MATCH (s:Supplier {name:'Infineon Technologies'})
SET s.kotaemon_docs = ['infineon_annual_report_2023.pdf','infineon_conflict_minerals_report.pdf'];

MATCH (s:Supplier {name:'LKAB'})
SET s.kotaemon_docs = ['lkab_annual_report_2023.pdf','lkab_sustainability_report.pdf'];

MATCH (s:Supplier {name:'Glencore'})
SET s.kotaemon_docs = ['glencore_responsible_sourcing_report_2023.pdf'];

MATCH (s:Supplier {name:'China Rare Earth Group'})
SET s.kotaemon_docs = ['china_rare_earth_profile.html'];

// ---- Additional certificates (v5) ----
MERGE (iatf2:Certificate {name:'IATF 16949:2016', issuer:'TUV Nord', valid_until:'2027-03-31', demo:true});
MERGE (as9100:Certificate {name:'AS9100D', issuer:'Bureau Veritas', valid_until:'2026-11-30',
  demo:true, note:'Aerospace quality — for precision turbocharger components'});
MERGE (lksg2:Certificate {name:'LkSG Compliance', issuer:'Internal Audit DE',
  valid_until:'2027-01-01', demo:true});

MATCH (s:Supplier {name:'Garrett Motion'}), (c:Certificate {name:'AS9100D'})
MERGE (s)-[:CERTIFIED_BY {demo:true}]->(c);

MATCH (s:Supplier {name:'Knorr-Bremse AG'}), (c:Certificate {name:'IATF 16949:2016'})
MERGE (s)-[:CERTIFIED_BY {demo:true}]->(c);

MATCH (s:Supplier {name:'Schaeffler Group'}), (c:Certificate {name:'IATF 16949:2016'})
MERGE (s)-[:CERTIFIED_BY {demo:true}]->(c);

MATCH (s:Supplier {name:'Dana Incorporated'}), (c:Certificate {name:'ISO 9001:2015'})
MERGE (s)-[:CERTIFIED_BY {demo:true}]->(c);

MATCH (s:Supplier {name:'Dana Incorporated'}), (c:Certificate {name:'IATF 16949:2016'})
MERGE (s)-[:CERTIFIED_BY {demo:true}]->(c);

MATCH (s:Supplier {name:'Cummins Inc'}), (c:Certificate {name:'ISO 14001:2015'})
MERGE (s)-[:CERTIFIED_BY {demo:true}]->(c);

MATCH (s:Supplier {name:'Haldex AB'}), (c:Certificate {name:'ISO 9001:2015'})
MERGE (s)-[:CERTIFIED_BY {demo:true}]->(c);

// ---- Cummins financial data ----
MATCH (s:Supplier {name:'Cummins Inc'})
SET s.annual_revenue_eur = 24100000000, s.employee_count = 59900,
    s.founded_year = 1919, s.headquarters = 'Columbus, IN, US';

MATCH (p:Product {sku:'SCANIA-R-500'})-[r:SUPPLIED_BY]->(s:Supplier {name:'Cummins Inc'})
SET r.contract_value_eur = 380000000, r.lead_time_days = 90,
    r.annual_volume_eur = 380000000, r.single_source = true,
    r.risk_flags = ['SINGLE_SOURCE'];

MATCH (p:Product {sku:'SCANIA-BUS-K'})-[r:SUPPLIED_BY]->(s:Supplier {name:'Cummins Inc'})
SET r.contract_value_eur = 160000000, r.lead_time_days = 90,
    r.annual_volume_eur = 160000000;

// Knorr-Bremse Cummins Continential financial data
MATCH (s:Supplier {name:'Continental AG'})
SET s.annual_revenue_eur = 41400000000, s.employee_count = 200000,
    s.founded_year = 1871, s.headquarters = 'Hannover, DE';

MATCH (p:Product {sku:'SCANIA-R-500'})-[r:SUPPLIED_BY]->(s:Supplier {name:'Continental AG'})
SET r.contract_value_eur = 295000000, r.lead_time_days = 60,
    r.annual_volume_eur = 295000000;

// ---- Disruption event: Garrett Motion bankruptcy 2020 ----
MERGE (evt5:Event {name:'Garrett Motion Chapter 11 Bankruptcy 2020',
  date:'2020-09-20', type:'FINANCIAL', affected_company:'Garrett Motion',
  impact:'HIGH', demo:true,
  description:'Turbocharger supplier Garrett filed for bankruptcy due to Honeywell asbestos liabilities; emerged 2021 as independent co.',
  resolution:'Emerged from bankruptcy April 2021; supply continuity maintained',
  lesson:'Single-source turbocharger risk — qualify BorgWarner as alternative'});

MATCH (s:Supplier {name:'Garrett Motion'}), (e:Event {name:'Garrett Motion Chapter 11 Bankruptcy 2020'})
MERGE (s)-[:AFFECTED_BY {demo:true}]->(e);

// ---- Disruption event: TimkenSteel plant fire 2019 ----
MERGE (evt6:Event {name:'TimkenSteel Harrison Plant Fire 2019',
  date:'2019-11-12', type:'OPERATIONAL', affected_company:'TimkenSteel Corporation',
  impact:'MEDIUM', demo:true,
  description:'Electrical fire at Harrison, OH electric arc furnace — 3-week production halt',
  lesson:'Single-source SBQ steel risk — dual-source with Ovako or Saarstahl'});

MATCH (s:Supplier {name:'TimkenSteel Corporation'}), (e:Event {name:'TimkenSteel Harrison Plant Fire 2019'})
MERGE (s)-[:AFFECTED_BY {demo:true}]->(e);

// ============================================================
// VERIFICATION (v5 — extended)
// MATCH (n) WHERE n.demo = true RETURN labels(n)[0] AS type, count(n) AS cnt ORDER BY cnt DESC;
// Expected: Supplier ~47+, RawMaterial ~21, Certificate ~13, Event ~6, Product ~5, Company ~6
//
// Full T1→T2→T3 depth check:
// MATCH p=(prod:Product {sku:'SCANIA-R-500'})-[:SUPPLIED_BY|SOURCED_FROM*1..4]->(n)
// WHERE prod.sku IS NOT NULL
// RETURN length(p) AS depth, count(p) AS paths ORDER BY depth;
//
// Alternative supplier check:
// MATCH (s1)-[:ALT_SOURCE]->(s2) RETURN s1.name, s2.name, s2.tags;
// ============================================================

// ============================================================
// SUPPLY CHAIN v6 — Electric/BEV variant + multi-product + compliance (2026-08-12)
// Adds: SCANIA-L-340 (BEV), SCANIA-G-410 (construction), full EV battery supply chain
// Battery supply chain is the most geopolitically sensitive addition
// ============================================================

// ---- New products ----
MERGE (bev:Product {sku:'SCANIA-L-340-BEV', name:'Scania L-series BEV Long-Haul',
  category:'Electric Commercial Vehicles', demo:true,
  description:'100% electric long-haul truck; 620km range; 230kWh battery pack'});

MERGE (constr:Product {sku:'SCANIA-G-410', name:'Scania G-series Construction Truck',
  category:'Construction Vehicles', demo:true,
  description:'Off-road capable, 8x4 axle configuration, tipper body'});

MERGE (eng_dc09:Product {sku:'SCANIA-ENG-DC09', name:'Scania DC09 Engine (Euro7)',
  category:'Powertrain', demo:true,
  description:'5-cylinder 9L diesel, Euro7 compliant, for P/G-series'});

// ---- EV-specific Tier 1 suppliers ----
MERGE (catl:Supplier {name:'CATL', country:'CN', tier:1,
  website:'https://www.catl.com', demo:true,
  annual_revenue_eur:38000000000, employee_count:180000, founded_year:2011,
  headquarters:'Ningde, Fujian, CN',
  risk_flags:['GEOPOLITICAL_RISK','SINGLE_SOURCE','UFLPA_RISK'],
  kotaemon_docs:['catl_battery_spec_lmfp.pdf','catl_sustainability_report_2023.pdf'],
  state_owned:false});

MERGE (nidec:Supplier {name:'Nidec Corporation', country:'JP', tier:1,
  website:'https://www.nidec.com', demo:true,
  annual_revenue_eur:18200000000, employee_count:110000, founded_year:1973,
  headquarters:'Kyoto, JP',
  risk_flags:['GEOPOLITICAL_RISK']});

MERGE (abb_charger:Supplier {name:'ABB E-mobility', country:'CH', tier:1,
  website:'https://www.abb.com/emobility', demo:true,
  annual_revenue_eur:1200000000, employee_count:4000, founded_year:2022,
  headquarters:'Zurich, CH'});

MERGE (samsung_sdi:Supplier {name:'Samsung SDI', country:'KR', tier:1,
  website:'https://www.samsungsdi.com', demo:true,
  annual_revenue_eur:16800000000, employee_count:26000, founded_year:1970,
  headquarters:'Yongin, KR',
  tags:['ALTERNATIVE_SUPPLIER'],
  risk_flags:['GEOPOLITICAL_RISK']});

// ---- BEV product → T1 relationships ----
MATCH (p:Product {sku:'SCANIA-L-340-BEV'}), (s:Supplier {name:'CATL'})
MERGE (p)-[:SUPPLIED_BY {since:'2024-01-01', component:'230kWh LFP battery pack',
  contract_value_eur:820000000, lead_time_days:180, single_source:true,
  risk_flags:['SINGLE_SOURCE','GEOPOLITICAL_RISK'], demo:true}]->(s);

MATCH (p:Product {sku:'SCANIA-L-340-BEV'}), (s:Supplier {name:'Nidec Corporation'})
MERGE (p)-[:SUPPLIED_BY {since:'2024-01-01', component:'e-axle (electric motor + gearbox)',
  contract_value_eur:340000000, lead_time_days:120, demo:true}]->(s);

MATCH (p:Product {sku:'SCANIA-L-340-BEV'}), (s:Supplier {name:'ABB E-mobility'})
MERGE (p)-[:SUPPLIED_BY {since:'2024-01-01', component:'HPC charging system (150kW CCS)',
  contract_value_eur:85000000, lead_time_days:60, demo:true}]->(s);

// BEV also uses Bosch (BMS, ADAS), Knorr-Bremse (regenerative braking), Continental
MATCH (p:Product {sku:'SCANIA-L-340-BEV'}), (s:Supplier {name:'Bosch'})
MERGE (p)-[:SUPPLIED_BY {since:'2024-01-01', component:'Battery management system + ADAS',
  contract_value_eur:195000000, lead_time_days:60, demo:true}]->(s);

MATCH (p:Product {sku:'SCANIA-L-340-BEV'}), (s:Supplier {name:'Knorr-Bremse AG'})
MERGE (p)-[:SUPPLIED_BY {since:'2024-01-01', component:'Regenerative braking + EBS',
  contract_value_eur:120000000, lead_time_days:45, demo:true}]->(s);

// ---- G-series (construction) shares most T1 with R-series ----
MATCH (p:Product {sku:'SCANIA-G-410'}), (s:Supplier {name:'ZF Friedrichshafen'})
MERGE (p)-[:SUPPLIED_BY {component:'ZF-Ecomat automatic gearbox', demo:true,
  contract_value_eur:280000000, lead_time_days:90}]->(s);

MATCH (p:Product {sku:'SCANIA-G-410'}), (s:Supplier {name:'Bosch'})
MERGE (p)-[:SUPPLIED_BY {component:'Fuel injection + off-road ECU',
  contract_value_eur:145000000, lead_time_days:60, demo:true}]->(s);

MATCH (p:Product {sku:'SCANIA-G-410'}), (s:Supplier {name:'Dana Incorporated'})
MERGE (p)-[:SUPPLIED_BY {component:'Heavy-duty off-road axles',
  contract_value_eur:230000000, lead_time_days:75, single_source:true,
  risk_flags:['SINGLE_SOURCE'], demo:true}]->(s);

MATCH (p:Product {sku:'SCANIA-G-410'}), (s:Supplier {name:'SSAB'})
MERGE (p)-[:SUPPLIED_BY {component:'Hardox wear-resistant steel (tipper body)',
  contract_value_eur:110000000, lead_time_days:30, demo:true}]->(s);

MATCH (p:Product {sku:'SCANIA-G-410'}), (s:Supplier {name:'Knorr-Bremse AG'})
MERGE (p)-[:SUPPLIED_BY {component:'Air brakes for heavy off-road use',
  contract_value_eur:78000000, lead_time_days:45, demo:true}]->(s);

// ---- Battery supply chain (T2 under CATL) ----
MERGE (umicore2:Supplier {name:'Umicore Battery Materials', country:'BE', tier:2,
  website:'https://www.umicore.com/battery-materials', demo:true,
  annual_revenue_eur:4200000000, employee_count:14800, founded_year:1989,
  headquarters:'Brussels, BE'});

MERGE (basf_battery:Supplier {name:'BASF Battery Materials', country:'DE', tier:2,
  website:'https://www.basf.com/battery-materials', demo:true,
  annual_revenue_eur:1800000000, employee_count:6000, founded_year:2018,
  headquarters:'Ludwigshafen, DE'});

MERGE (shanjin:Supplier {name:'Shanshan Advanced Materials', country:'CN', tier:2,
  website:'https://www.shanshan.com', demo:true,
  annual_revenue_eur:2100000000, employee_count:16000, founded_year:1992,
  risk_flags:['GEOPOLITICAL_RISK','UFLPA_RISK'],
  headquarters:'Shanghai, CN'});

MERGE (sumitomo_metal:Supplier {name:'Sumitomo Metal Mining', country:'JP', tier:2,
  website:'https://www.smmco.jp', demo:true,
  annual_revenue_eur:8900000000, employee_count:24000, founded_year:1590,
  headquarters:'Tokyo, JP'});

MERGE (sk_enpulse:Supplier {name:'SK Enpulse', country:'KR', tier:2,
  website:'https://www.skenpulse.com', demo:true,
  annual_revenue_eur:1400000000, employee_count:4500, founded_year:2022,
  risk_flags:['GEOPOLITICAL_RISK']});

MATCH (s1:Supplier {name:'CATL'}), (s2:Supplier {name:'Umicore Battery Materials'})
MERGE (s1)-[:SOURCED_FROM {component:'NMC cathode active material (high-Ni)',
  contract_value_eur:380000000, lead_time_days:90, demo:true}]->(s2);

MATCH (s1:Supplier {name:'CATL'}), (s2:Supplier {name:'Shanshan Advanced Materials'})
MERGE (s1)-[:SOURCED_FROM {component:'Graphite anode material',
  contract_value_eur:120000000, lead_time_days:60,
  risk_flags:['GEOPOLITICAL_RISK'], demo:true}]->(s2);

MATCH (s1:Supplier {name:'CATL'}), (s2:Supplier {name:'Sumitomo Metal Mining'})
MERGE (s1)-[:SOURCED_FROM {component:'Nickel-Cobalt-Manganese (NCM) precursor',
  contract_value_eur:290000000, lead_time_days:120, demo:true}]->(s2);

MATCH (s1:Supplier {name:'CATL'}), (s2:Supplier {name:'SK Enpulse'})
MERGE (s1)-[:SOURCED_FROM {component:'Lithium iron phosphate (LFP) separator film',
  contract_value_eur:95000000, lead_time_days:45,
  risk_flags:['GEOPOLITICAL_RISK'], demo:true}]->(s2);

// ---- EV motor supply chain (T2 under Nidec) ----
MERGE (proterial:Supplier {name:'Proterial Ltd', country:'JP', tier:2,
  website:'https://www.proterial.com', demo:true,
  annual_revenue_eur:3800000000, employee_count:19000, founded_year:2023,
  headquarters:'Tokyo, JP',
  note:'Formerly Hitachi Metals — NdFeB magnets for motors'});

MERGE (vacuumschmelze:Supplier {name:'Vacuumschmelze GmbH', country:'DE', tier:2,
  website:'https://www.vacuumschmelze.com', demo:true,
  annual_revenue_eur:680000000, employee_count:4200, founded_year:1923,
  headquarters:'Hanau, DE',
  tags:['ALTERNATIVE_SUPPLIER']});

MATCH (s1:Supplier {name:'Nidec Corporation'}), (s2:Supplier {name:'Proterial Ltd'})
MERGE (s1)-[:SOURCED_FROM {component:'NdFeB sintered magnets for traction motor',
  contract_value_eur:155000000, lead_time_days:120, single_source:true,
  risk_flags:['SINGLE_SOURCE','GEOPOLITICAL_RISK'], demo:true}]->(s2);

MATCH (s1:Supplier {name:'Nidec Corporation'}), (s2:Supplier {name:'China Rare Earth Group'})
MERGE (s1)-[:SOURCED_FROM {component:'Neodymium for magnet production',
  contract_value_eur:88000000, lead_time_days:90,
  risk_flags:['GEOPOLITICAL_RISK','SINGLE_SOURCE','SANCTIONS_RISK'], demo:true}]->(s2);

MATCH (s1:Supplier {name:'Proterial Ltd'}), (s2:Supplier {name:'Vacuumschmelze GmbH'})
MERGE (s1)-[:ALT_SOURCE {component:'European-sourced NdFeB magnets',
  qualification_status:'QUALIFIED', demo:true,
  note:'Strategic EU alternative — 3x cost, same performance'}]->(s2);

// ---- Battery raw materials (T3) ----
MERGE (sqm:Supplier {name:'SQM', country:'CL', tier:3,
  website:'https://www.sqm.com', demo:true,
  annual_revenue_eur:9200000000, employee_count:7000, founded_year:1968,
  headquarters:'Santiago, CL',
  risk_flags:['WATER_STRESS','ESG_RISK']});

MERGE (albemarle:Supplier {name:'Albemarle Corporation', country:'US', tier:3,
  website:'https://www.albemarle.com', demo:true,
  annual_revenue_eur:9600000000, employee_count:8000, founded_year:1887,
  headquarters:'Charlotte, NC, US'});

MERGE (ganfeng:Supplier {name:'Ganfeng Lithium', country:'CN', tier:3,
  website:'https://www.ganfenglithium.com', demo:true,
  annual_revenue_eur:7300000000, employee_count:18000, founded_year:2000,
  headquarters:'Xinyu, Jiangxi, CN',
  risk_flags:['GEOPOLITICAL_RISK','SANCTIONS_RISK']});

MERGE (norilsk:Supplier {name:'Norilsk Nickel', country:'RU', tier:3,
  website:'https://www.nornickel.com', demo:true,
  annual_revenue_eur:17200000000, employee_count:79000, founded_year:1935,
  headquarters:'Moscow, RU',
  risk_flags:['SANCTIONS_RISK','GEOPOLITICAL_RISK','ESG_RISK']});

MERGE (eramet:Supplier {name:'Eramet SA', country:'FR', tier:3,
  website:'https://www.eramet.com', demo:true,
  annual_revenue_eur:3700000000, employee_count:13000, founded_year:1880,
  headquarters:'Paris, FR'});

MATCH (s1:Supplier {name:'Umicore Battery Materials'}), (s2:Supplier {name:'SQM'})
MERGE (s1)-[:SOURCED_FROM {component:'Lithium hydroxide for cathode precursor',
  contract_value_eur:195000000, lead_time_days:120, demo:true}]->(s2);

MATCH (s1:Supplier {name:'Umicore Battery Materials'}), (s2:Supplier {name:'Albemarle Corporation'})
MERGE (s1)-[:SOURCED_FROM {component:'Battery-grade lithium carbonate',
  contract_value_eur:140000000, lead_time_days:90, demo:true}]->(s2);

MATCH (s1:Supplier {name:'Sumitomo Metal Mining'}), (s2:Supplier {name:'Norilsk Nickel'})
MERGE (s1)-[:SOURCED_FROM {component:'Nickel sulfate feedstock',
  contract_value_eur:320000000, lead_time_days:45,
  risk_flags:['SANCTIONS_RISK','GEOPOLITICAL_RISK'], demo:true}]->(s2);

MATCH (s1:Supplier {name:'Sumitomo Metal Mining'}), (s2:Supplier {name:'Eramet SA'})
MERGE (s1)-[:SOURCED_FROM {component:'Manganese sulfate (alternative to Norilsk)',
  contract_value_eur:85000000, lead_time_days:60, demo:true}]->(s2);

MATCH (s1:Supplier {name:'Shanshan Advanced Materials'}), (s2:Supplier {name:'Ganfeng Lithium'})
MERGE (s1)-[:SOURCED_FROM {component:'Lithium-ion for anode lithiation',
  risk_flags:['GEOPOLITICAL_RISK'], demo:true}]->(s2);

// ---- Battery raw materials ----
MERGE (r_li:RawMaterial {name:'Lithium Carbonate (battery-grade)', origin:'CL',
  material_type:'Metal', demo:true,
  risk_flags:['WATER_STRESS','SUPPLY_CONCENTRATION'],
  description:'60% global production in Chile/Argentina Lithium Triangle'});

MERGE (r_nickel:RawMaterial {name:'Class I Nickel (>99.8%)', origin:'RU',
  material_type:'Metal', demo:true,
  risk_flags:['SANCTIONS_RISK','GEOPOLITICAL_RISK'],
  description:'Battery-grade nickel; Russia = 10% global supply'});

MERGE (r_graphite:RawMaterial {name:'Natural Graphite (battery-grade)', origin:'CN',
  material_type:'Carbon', demo:true,
  risk_flags:['GEOPOLITICAL_RISK','SUPPLY_CONCENTRATION'],
  description:'China controls 70%+ of global natural graphite supply'});

MERGE (r_cobalt2:RawMaterial {name:'Cobalt Sulfate', origin:'CD',
  material_type:'Metal', demo:true,
  risk_flags:['CONFLICT_MINERAL','CHILD_LABOUR_RISK','ESG_RISK'],
  description:'DRC = 70% global cobalt; artisanal mining child labour risk'});

MERGE (r_lithium_brine:RawMaterial {name:'Lithium Brine (Atacama)', origin:'CL',
  material_type:'Mineral', demo:true,
  risk_flags:['WATER_STRESS','INDIGENOUS_RIGHTS'],
  description:'Salar de Atacama; 2M litres water per tonne Li; indigenous land rights'});

MATCH (s:Supplier {name:'SQM'}), (r:RawMaterial {name:'Lithium Brine (Atacama)'})
MERGE (s)-[:SOURCED_FROM {demo:true, risk_flags:['WATER_STRESS']}]->(r);

MATCH (s:Supplier {name:'Albemarle Corporation'}), (r:RawMaterial {name:'Lithium Carbonate (battery-grade)'})
MERGE (s)-[:SOURCED_FROM {demo:true}]->(r);

MATCH (s:Supplier {name:'Norilsk Nickel'}), (r:RawMaterial {name:'Class I Nickel (>99.8%)'})
MERGE (s)-[:SOURCED_FROM {demo:true, risk_flags:['SANCTIONS_RISK']}]->(r);

MATCH (s:Supplier {name:'Ganfeng Lithium'}), (r:RawMaterial {name:'Natural Graphite (battery-grade)'})
MERGE (s)-[:SOURCED_FROM {demo:true}]->(r);

MATCH (s:Supplier {name:'Glencore'}), (r:RawMaterial {name:'Cobalt Sulfate'})
MERGE (s)-[:SOURCED_FROM {demo:true, risk_flags:['CONFLICT_MINERAL']}]->(r);

// ---- Compliance flags on suppliers ----
// CBAM (Carbon Border Adjustment — affects steel, aluminium imports to EU)
MATCH (s:Supplier {name:'SSAB'})
SET s.cbam_applicable = true, s.cbam_product = 'Steel',
    s.cbam_risk = 'medium', s.cbam_co2_intensity_kg_per_tonne = 610;

MATCH (s:Supplier {name:'Saarstahl AG'})
SET s.cbam_applicable = true, s.cbam_product = 'Steel',
    s.cbam_risk = 'high', s.cbam_co2_intensity_kg_per_tonne = 1850;

MATCH (s:Supplier {name:'Norsk Hydro'})
SET s.cbam_applicable = true, s.cbam_product = 'Aluminium',
    s.cbam_risk = 'low', s.cbam_co2_intensity_kg_per_tonne = 2100;

// UFLPA (Uyghur Forced Labor Prevention Act — US import ban)
MATCH (s:Supplier {name:'Xinjiang Polysilicon Co'})
SET s.uflpa_listed = true, s.uflpa_entity = true, s.cbam_applicable = false,
    s.compliance_notes = 'On UFLPA entity list — US imports blocked; EU review pending';

MATCH (s:Supplier {name:'Shanshan Advanced Materials'})
SET s.uflpa_risk = true, s.uflpa_notes = 'Anode material production has Xinjiang supply links',
    s.compliance_notes = 'UFLPA supply chain due diligence required';

// LkSG (German Supply Chain Act — mandatory for companies >1000 employees)
MATCH (s:Supplier {name:'Glencore'})
SET s.lksg_applicable = true, s.lksg_risk = 'high',
    s.lksg_issues = ['child labour risk DRC cobalt', 'environmental violations'];

MATCH (s:Supplier {name:'Vale SA'})
SET s.lksg_applicable = true, s.lksg_risk = 'high',
    s.lksg_issues = ['Brumadinho tailings dam collapse 2019', 'deforestation risk'];

MATCH (s:Supplier {name:'China Rare Earth Group'})
SET s.lksg_applicable = true, s.lksg_risk = 'critical',
    s.lksg_issues = ['forced labour risk', 'state-controlled entity', 'Xinjiang links'];

// ---- New regulatory events ----
MERGE (evt7:Event {name:'EU Critical Raw Materials Act 2024 — Implementation',
  date:'2024-05-23', type:'REGULATORY', demo:true,
  affected_material:'Lithium/Nickel/Cobalt/Rare Earths',
  impact:'HIGH',
  description:'EU mandates 10% domestic extraction, 40% processing, 15% recycling of critical raw materials by 2030.',
  lesson:'Diversify battery raw material sourcing; invest in EU recycling partnerships'});

MERGE (evt8:Event {name:'UFLPA Expanded Entity List 2024',
  date:'2024-06-14', type:'REGULATORY', demo:true,
  affected_material:'Polysilicon/Graphite',
  impact:'HIGH',
  description:'US Customs added 6 Chinese polysilicon/solar manufacturers. EU reviewing similar measures.',
  lesson:'Audit Tier 3+ supply chain for Xinjiang-linked entities; file UFLPA rebuttable presumption docs'});

MERGE (evt9:Event {name:'Norilsk Nickel Sanctions Escalation 2024',
  date:'2024-04-12', type:'SANCTIONS', demo:true,
  affected_material:'Class I Nickel',
  impact:'HIGH',
  description:'US and UK expanded sanctions on Russian metals; London Metal Exchange debate on Russian nickel.',
  lesson:'Switch to Indonesia/Australia nickel sources; Eramet/Wyloo qualify as alternatives'});

MATCH (r:RawMaterial {name:'Class I Nickel (>99.8%)'}), (e:Event {name:'Norilsk Nickel Sanctions Escalation 2024'})
MERGE (r)-[:AFFECTED_BY {demo:true}]->(e);

MATCH (r:RawMaterial {name:'Natural Graphite (battery-grade)'}), (e:Event {name:'UFLPA Expanded Entity List 2024'})
MERGE (r)-[:AFFECTED_BY {demo:true}]->(e);

MATCH (r:RawMaterial {name:'Lithium Carbonate (battery-grade)'}), (e:Event {name:'EU Critical Raw Materials Act 2024 — Implementation'})
MERGE (r)-[:AFFECTED_BY {demo:true}]->(e);

// ---- Alternative supplier for Samsung SDI as backup to CATL ----
MATCH (p:Product {sku:'SCANIA-L-340-BEV'}), (s:Supplier {name:'Samsung SDI'})
MERGE (p)-[:ALT_SOURCE {component:'Battery pack (alternative to CATL)',
  qualification_status:'UNDER_REVIEW', demo:true,
  note:'Korean-sourced; avoids CN geopolitical risk; 15% cost premium'}]->(s);

// ---- CATL Nidec financial profiles ----
MATCH (s:Supplier {name:'CATL'})
SET s.resilience_note = 'CN state-strategic; subject to export controls; no credible Western alternative at scale';

MATCH (s:Supplier {name:'Nidec Corporation'})
SET s.kotaemon_docs = ['nidec_electric_axle_spec.pdf','nidec_ev_strategy_2025.pdf'];

// ---- DC09 engine from SCANIA-ENG-DC09 ----
MERGE (bosal:Supplier {name:'Bosal Group', country:'BE', tier:1,
  website:'https://www.bosal.com', demo:true,
  annual_revenue_eur:890000000, employee_count:6500, founded_year:1923,
  headquarters:'Lummen, BE'});

MATCH (p:Product {sku:'SCANIA-ENG-DC09'}), (s:Supplier {name:'Bosch'})
MERGE (p)-[:SUPPLIED_BY {component:'Common rail injection system Euro7',
  contract_value_eur:145000000, demo:true}]->(s);

MATCH (p:Product {sku:'SCANIA-ENG-DC09'}), (s:Supplier {name:'Bosal Group'})
MERGE (p)-[:SUPPLIED_BY {component:'Exhaust aftertreatment (SCR+DPF+EGR)',
  contract_value_eur:88000000, lead_time_days:45, demo:true}]->(s);

MATCH (p:Product {sku:'SCANIA-ENG-DC09'}), (s:Supplier {name:'Knorr-Bremse AG'})
MERGE (p)-[:SUPPLIED_BY {component:'Engine braking system',
  contract_value_eur:35000000, demo:true}]->(s);

// ============================================================
// VERIFICATION (v6)
// Products: 8 (R-500, T-500, BUS-K, ENG-DC13, ENG-DC09, G-410, L-340-BEV, BTN-001)
// Suppliers: ~62+ (added: CATL, Nidec, ABB, Samsung SDI, Umicore BM, BASF BM,
//            Shanshan, Sumitomo MM, SK Enpulse, SQM, Albemarle, Ganfeng,
//            Norilsk, Eramet, Proterial, Vacuumschmelze, Bosal)
// Raw materials: ~26+ (added: Li carbonate, Ni, graphite, cobalt sulfate, Li brine)
// Events: 9 (added: EU CRM Act, UFLPA expansion, Norilsk sanctions)
//
// Key new risk vectors:
//   CATL single-source for BEV battery (€820M) — highest new single-source risk
//   Norilsk Nickel (sanctioned) in battery supply chain
//   Ganfeng Lithium + Shanshan: Chinese supply chain dominance
//   Proterial magnets: single-source rare earth dependency for EV motors
//
// Battery supply chain query:
// MATCH path=(p:Product {sku:'SCANIA-L-340-BEV'})-[:SUPPLIED_BY|SOURCED_FROM*1..5]->(n)
// RETURN [node IN nodes(path) | coalesce(node.name,node.sku)] AS chain, length(path) AS depth
// ORDER BY depth;
// ============================================================

// ============================================================
// V7 — AUTOMOTIVE ELECTRONICS CHAIN
// Continental, Aptiv, Valeo, Autoliv → STMicro, TE Connectivity,
// Leoni, Toray → Palladium(RU), Copper(CL), Polysilicon(CN)
// ============================================================

// ── T1: Automotive electronics & safety suppliers ──────────────────────────────
MERGE (cont:Supplier {name:'Continental AG', country:'DE', tier:1,
  website:'https://www.continental.com',
  revenue_eur:41400000000, employees:190000,
  risk_flags:[], demo:true});

MERGE (aptiv:Supplier {name:'Aptiv', country:'US', tier:1,
  website:'https://www.aptiv.com',
  revenue_eur:17900000000, employees:180000,
  risk_flags:['UKRAINE_CONFLICT_RISK'], demo:true,
  note:'Major wiring harness plant in Lviv, Ukraine (active conflict zone)'});

MERGE (valeo:Supplier {name:'Valeo', country:'FR', tier:1,
  website:'https://www.valeo.com',
  revenue_eur:20000000000, employees:103000,
  risk_flags:[], demo:true});

MERGE (autoliv:Supplier {name:'Autoliv', country:'SE', tier:1,
  website:'https://www.autoliv.com',
  revenue_eur:9000000000, employees:71000,
  risk_flags:[], demo:true});

// ── T2: Component manufacturers ────────────────────────────────────────────────
MERGE (stm:Supplier {name:'STMicroelectronics', country:'CH', tier:2,
  website:'https://www.st.com',
  revenue_eur:14300000000, employees:50000,
  risk_flags:[], cbam_applicable:false, demo:true});

MERGE (te:Supplier {name:'TE Connectivity', country:'IE', tier:2,
  website:'https://www.te.com',
  revenue_eur:15600000000, employees:89000,
  risk_flags:[], demo:true});

MERGE (leoni:Supplier {name:'Leoni AG', country:'DE', tier:2,
  website:'https://www.leoni.com',
  revenue_eur:5400000000, employees:100000,
  risk_flags:['UKRAINE_CONFLICT_RISK'], demo:true,
  note:'Cable production in Ukraine; financial restructuring 2023'});

MERGE (toray:Supplier {name:'Toray Industries', country:'JP', tier:2,
  website:'https://www.toray.com',
  revenue_eur:17000000000, employees:50000,
  risk_flags:[], demo:true});

MERGE (molex:Supplier {name:'Molex', country:'US', tier:2,
  website:'https://www.molex.com',
  revenue_eur:4000000000, employees:40000,
  risk_flags:[], demo:true});

// ── T3: Raw material sources ───────────────────────────────────────────────────
MERGE (codelco:Supplier {name:'Codelco', country:'CL', tier:3,
  website:'https://www.codelco.com',
  revenue_eur:12000000000, employees:28000,
  risk_flags:[], demo:true,
  note:'Largest copper producer globally; state-owned Chilean'});

// Palladium — critical for catalytic converters + automotive sensors
MERGE (norilsk_pd:RawMaterial {name:'Palladium', origin:'RU',
  material_type:'Precious Metal', cbam_applicable:false,
  risk_flags:['SANCTIONS_OFAC','GEOPOLITICAL_RISK','SINGLE_SOURCE'],
  note:'~40% world supply from Norilsk Nickel (sanctioned entity)',
  cbam_co2_intensity_kg_per_tonne:0,
  demo:true});

MERGE (copper:RawMaterial {name:'Copper Cathode', origin:'CL',
  material_type:'Metal', cbam_applicable:true,
  cbam_co2_intensity_kg_per_tonne:2200,
  risk_flags:[], demo:true});

MERGE (polysil:RawMaterial {name:'Polysilicon', origin:'CN',
  material_type:'Semiconductor Material',
  risk_flags:['GEOPOLITICAL_RISK','UFLPA_RISK'],
  note:'~85% global polysilicon from China; UFLPA enforcement active',
  demo:true});

MERGE (cfcomposite:RawMaterial {name:'Carbon Fibre Composite', origin:'JP',
  material_type:'Advanced Composite',
  risk_flags:[], demo:true});

MERGE (bisphenol:RawMaterial {name:'Bisphenol-A', origin:'DE',
  material_type:'Chemical', cbam_applicable:false,
  risk_flags:[], demo:true});

// ── Product relationships: R-500 → automotive electronics ─────────────────────
MATCH (p:Product {sku:'SCANIA-R-500'}), (s:Supplier {name:'Continental AG'})
MERGE (p)-[:SUPPLIED_BY {component:'ADAS sensors, body control modules, telematics',
  contract_value_eur:180000000, lead_time_days:60, demo:true}]->(s);

MATCH (p:Product {sku:'SCANIA-R-500'}), (s:Supplier {name:'Aptiv'})
MERGE (p)-[:SUPPLIED_BY {component:'Wiring harness, high-voltage connectors',
  contract_value_eur:95000000, lead_time_days:45,
  risk_note:'Lviv plant disruption risk', demo:true}]->(s);

MATCH (p:Product {sku:'SCANIA-R-500'}), (s:Supplier {name:'Valeo'})
MERGE (p)-[:SUPPLIED_BY {component:'Climate control, lighting, wipers, ADAS cameras',
  contract_value_eur:120000000, lead_time_days:50, demo:true}]->(s);

MATCH (p:Product {sku:'SCANIA-R-500'}), (s:Supplier {name:'Autoliv'})
MERGE (p)-[:SUPPLIED_BY {component:'Airbags, seatbelts, active safety systems',
  contract_value_eur:75000000, lead_time_days:40, demo:true}]->(s);

// G-410 also uses Continental ADAS
MATCH (p:Product {sku:'SCANIA-G-410'}), (s:Supplier {name:'Continental AG'})
MERGE (p)-[:SUPPLIED_BY {component:'Safety ECUs, fleet management sensors',
  contract_value_eur:65000000, demo:true}]->(s);

// ── T1 → T2 sourcing relationships ────────────────────────────────────────────
MATCH (t1:Supplier {name:'Continental AG'}), (t2:Supplier {name:'STMicroelectronics'})
MERGE (t1)-[:SOURCED_FROM {component:'Microcontrollers (SPC58x, SPC57x), MEMS sensors',
  volume_units_year:2000000, lead_time_days:16, demo:true}]->(t2);

MATCH (t1:Supplier {name:'Continental AG'}), (t2:Supplier {name:'TE Connectivity'})
MERGE (t1)-[:SOURCED_FROM {component:'Automotive connectors, sensor housings',
  volume_units_year:5000000, demo:true}]->(t2);

MATCH (t1:Supplier {name:'Aptiv'}), (t2:Supplier {name:'TE Connectivity'})
MERGE (t1)-[:SOURCED_FROM {component:'High-voltage connectors, sealing systems',
  volume_units_year:8000000, demo:true}]->(t2);

MATCH (t1:Supplier {name:'Aptiv'}), (t2:Supplier {name:'Leoni AG'})
MERGE (t1)-[:SOURCED_FROM {component:'Cable sets, wiring harness sub-assemblies',
  note:'Leoni Lviv plant — conflict zone dependency', demo:true}]->(t2);

MATCH (t1:Supplier {name:'Aptiv'}), (t2:Supplier {name:'Molex'})
MERGE (t1)-[:SOURCED_FROM {component:'Micro-connectors, PCB assemblies', demo:true}]->(t2);

MATCH (t1:Supplier {name:'Valeo'}), (t2:Supplier {name:'STMicroelectronics'})
MERGE (t1)-[:SOURCED_FROM {component:'ADAS image sensor processors, power ICs', demo:true}]->(t2);

MATCH (t1:Supplier {name:'Autoliv'}), (t2:Supplier {name:'Toray Industries'})
MERGE (t1)-[:SOURCED_FROM {component:'Airbag nylon fabric (nylon 6,6 substrate)', demo:true}]->(t2);

// ── T2 → T3/Raw material sourcing ─────────────────────────────────────────────
MATCH (t2:Supplier {name:'STMicroelectronics'}), (r:RawMaterial {name:'Palladium'})
MERGE (t2)-[:SOURCED_FROM {component:'Palladium wire bonds, catalytic metallisation',
  volume_tonnes_year:0.8,
  risk_note:'~40% supply from sanctioned Norilsk — STM actively diversifying', demo:true}]->(r);

MATCH (t2:Supplier {name:'STMicroelectronics'}), (r:RawMaterial {name:'Polysilicon'})
MERGE (t2)-[:SOURCED_FROM {component:'EPI wafer substrate (solar-grade to semi-grade)',
  uflpa_enforcement_risk:true, demo:true}]->(r);

MATCH (t2:Supplier {name:'TE Connectivity'}), (r:RawMaterial {name:'Copper Cathode'})
MERGE (t2)-[:SOURCED_FROM {component:'Drawn copper wire for connector pins',
  volume_tonnes_year:45000, demo:true}]->(r);

MATCH (t2:Supplier {name:'Leoni AG'}), (r:RawMaterial {name:'Copper Cathode'})
MERGE (t2)-[:SOURCED_FROM {component:'Cable wire core (automotive-grade oxygen-free copper)',
  volume_tonnes_year:85000, demo:true}]->(r);

MATCH (t2:Supplier {name:'Toray Industries'}), (r:RawMaterial {name:'Carbon Fibre Composite'})
MERGE (t2)-[:SOURCED_FROM {component:'T800 PAN-based carbon fibre (airbag reinforcement)', demo:true}]->(r);

MATCH (t2:Supplier {name:'Molex'}), (r:RawMaterial {name:'Copper Cathode'})
MERGE (t2)-[:SOURCED_FROM {component:'Connector terminal stamping', demo:true}]->(r);

// Codelco mines the copper for TE, Leoni, Molex
MATCH (mine:Supplier {name:'Codelco'}), (r:RawMaterial {name:'Copper Cathode'})
MERGE (mine)-[:SOURCED_FROM {component:'Mined, refined copper cathode (Escondida, Collahuasi)',
  volume_tonnes_year:1700000, demo:true}]->(r);

// ── ALT_SOURCE: alternatives to Ukraine-risk Leoni ─────────────────────────────
MATCH (t1:Supplier {name:'Aptiv'}), (alt:Supplier {name:'TE Connectivity'})
MERGE (t1)-[:ALT_SOURCE {reason:'Leoni Ukraine disruption contingency',
  capacity_pct:60, lead_weeks_to_qualify:26, demo:true}]->(alt);

// ── Supply chain event: Palladium sanctions risk ───────────────────────────────
MERGE (ev_pd:Event {
  id:'EVT-PALLADIUM-SANC-2024',
  title:'OFAC Palladium Supply Chain Advisory',
  date:'2024-03-01',
  type:'SANCTIONS',
  description:'US Treasury OFAC advisory: Norilsk-origin palladium poses sanctions evasion risk. Semiconductor and automotive firms required to screen Tier 3 sources.',
  affected_skus:['SCANIA-R-500','SCANIA-G-410'],
  revenue_at_risk_eur:255000000,
  demo:true
});

MATCH (ev:Event {id:'EVT-PALLADIUM-SANC-2024'}), (r:RawMaterial {name:'Palladium'})
MERGE (ev)-[:AFFECTS]->(r);

// ── Supply chain event: Ukraine wiring harness disruption ─────────────────────
MERGE (ev_ua:Event {
  id:'EVT-UKRAINE-WIRING-2022',
  title:'Ukraine Wiring Harness Plant Disruption',
  date:'2022-02-25',
  type:'GEOPOLITICAL',
  description:'Russian invasion of Ukraine caused immediate shutdown of wiring harness plants in Lviv and Kharkiv (Aptiv, Leoni, Fujikura). European automotive OEMs lost 30-40% wiring harness supply within weeks.',
  affected_skus:['SCANIA-R-500','SCANIA-G-410'],
  revenue_at_risk_eur:1800000000,
  demo:true
});

MATCH (ev:Event {id:'EVT-UKRAINE-WIRING-2022'}), (s:Supplier {name:'Aptiv'})
MERGE (ev)-[:AFFECTS]->(s);
MATCH (ev:Event {id:'EVT-UKRAINE-WIRING-2022'}), (s:Supplier {name:'Leoni AG'})
MERGE (ev)-[:AFFECTS]->(s);

// ── Supply chain event: Automotive chip shortage 2021-2023 ────────────────────
MERGE (ev_chip:Event {
  id:'EVT-AUTO-CHIP-SHORTAGE-2021',
  title:'Global Automotive Semiconductor Shortage',
  date:'2021-01-01',
  type:'SHORTAGE',
  description:'COVID-19 demand surge + fab capacity reallocation triggered 12-26 week lead time increases for automotive MCUs (NXP, STMicro, Renesas, Infineon). Scania production cut 15% in H2 2021.',
  affected_skus:['SCANIA-R-500','SCANIA-G-410','SCANIA-ENG-DC09'],
  revenue_at_risk_eur:3500000000,
  demo:true
});

MATCH (ev:Event {id:'EVT-AUTO-CHIP-SHORTAGE-2021'}), (s:Supplier {name:'STMicroelectronics'})
MERGE (ev)-[:AFFECTS]->(s);
MATCH (ev:Event {id:'EVT-AUTO-CHIP-SHORTAGE-2021'}), (s:Supplier {name:'Infineon Technologies'})
MERGE (ev)-[:AFFECTS]->(s);

// ============================================================
// VERIFICATION (v7)
// Products: 8 (unchanged)
// Suppliers: ~72+ (added: Continental, Aptiv, Valeo, Autoliv,
//            STMicro, TE Connectivity, Leoni, Toray, Molex, Codelco)
// Raw materials: ~30+ (added: Palladium, Copper Cathode, Polysilicon,
//                Carbon Fibre Composite, Bisphenol-A)
// Events: 12 (added: OFAC Palladium, Ukraine Wiring, Auto Chip Shortage)
//
// Key new risk vectors:
//   Aptiv: 40% wiring harness in Ukraine conflict zone
//   Palladium (STMicro): 40% from sanctioned Norilsk → SANCTIONS_OFAC
//   Polysilicon (STMicro): UFLPA enforcement active, ~85% from China
//   Leoni AG: Ukraine plant + financial restructuring 2023
//
// Electronics chain query:
// MATCH path=(p:Product {sku:'SCANIA-R-500'})-[:SUPPLIED_BY|SOURCED_FROM*1..4]->(n)
// WHERE n.name IN ['Continental AG','Aptiv','STMicroelectronics','Palladium','Polysilicon']
// RETURN [node IN nodes(path) | coalesce(node.name,node.sku)] AS chain, length(path) AS depth
// ORDER BY depth;
// ============================================================

// ============================================================
// V8 — TIER 4 MINING OPERATIONS + LOGISTICS NODES +
//       FINANCIAL HEALTH SCORES
// ============================================================

// ── TIER 4: Mine / Extraction Operations ──────────────────────────────────────

MERGE (kiruna:MiningOperation {
  name:'LKAB Kiruna Iron Mine', country:'SE', operator:'LKAB',
  commodity:'Iron Ore', grade_pct:60.5,
  annual_capacity_mt:28,  // million tonnes
  depth_m:1365,           // world's largest underground iron mine
  risk_flags:['SUBSIDENCE_RISK'],  // ongoing town relocation
  lat:67.84, lon:20.23, demo:true
});

MERGE (atacama:MiningOperation {
  name:'SQM Atacama Lithium Brine', country:'CL', operator:'SQM',
  commodity:'Lithium Carbonate', annual_capacity_mt:0.18,  // 180k tonnes LCE
  risk_flags:['WATER_STRESS','INDIGENOUS_RIGHTS','SEISMIC_RISK'],
  lat:-23.48, lon:-68.14, demo:true
});

MERGE (escondida:MiningOperation {
  name:'Codelco Escondida Copper Mine', country:'CL', operator:'Codelco/BHP',
  commodity:'Copper', annual_capacity_mt:1.2,
  risk_flags:['WATER_STRESS','LABOUR_RISK'],  // recurring strike history
  lat:-24.27, lon:-69.07, demo:true
});

MERGE (norilsk_mine:MiningOperation {
  name:'Norilsk Polar Division Mine', country:'RU', operator:'Norilsk Nickel',
  commodity:'Palladium/Nickel/Copper', annual_capacity_mt:2.8,
  risk_flags:['SANCTIONS_OFAC','GEOPOLITICAL_RISK','ARCTIC_RISK'],
  lat:69.35, lon:88.20, demo:true
});

MERGE (ganfeng_mine:MiningOperation {
  name:'Ganfeng Jiangxi Lithium Mine', country:'CN', operator:'Ganfeng Lithium',
  commodity:'Lithium Spodumene', annual_capacity_mt:0.05,
  risk_flags:['UFLPA_RISK','GEOPOLITICAL_RISK'],
  lat:26.14, lon:116.36, demo:true
});

MERGE (rusal_alumina:MiningOperation {
  name:'RUSAL Aughinish Alumina Refinery', country:'IE', operator:'RUSAL',
  commodity:'Alumina', annual_capacity_mt:1.9,
  risk_flags:['SANCTIONS_OFAC','SECONDARY_SANCTIONS_RISK'],
  lat:52.63, lon:-9.09, demo:true
});

// Mine → Supplier extraction relationships
MATCH (mine:MiningOperation {name:'LKAB Kiruna Iron Mine'}), (s:Supplier {name:'LKAB'})
MERGE (s)-[:OPERATES]->(mine);

MATCH (mine:MiningOperation {name:'SQM Atacama Lithium Brine'}), (s:Supplier {name:'SQM'})
MERGE (s)-[:OPERATES]->(mine);

MATCH (mine:MiningOperation {name:'Codelco Escondida Copper Mine'}), (s:Supplier {name:'Codelco'})
MERGE (s)-[:OPERATES]->(mine);

MATCH (mine:MiningOperation {name:'Norilsk Polar Division Mine'}), (s:Supplier {name:'Norilsk Nickel'})
MERGE (s)-[:OPERATES]->(mine);

MATCH (mine:MiningOperation {name:'Ganfeng Jiangxi Lithium Mine'}), (s:Supplier {name:'Ganfeng Lithium'})
MERGE (s)-[:OPERATES]->(mine);

// Mine → RawMaterial production
MATCH (mine:MiningOperation {name:'LKAB Kiruna Iron Mine'}), (r:RawMaterial {name:'Iron Ore'})
MERGE (mine)-[:PRODUCES {annual_mt:28, grade_pct:60.5}]->(r);

MATCH (mine:MiningOperation {name:'SQM Atacama Lithium Brine'}), (r:RawMaterial {name:'Lithium Carbonate'})
MERGE (mine)-[:PRODUCES {annual_mt_lce:0.18, cost_per_tonne:4200}]->(r);

MATCH (mine:MiningOperation {name:'Codelco Escondida Copper Mine'}), (r:RawMaterial {name:'Copper Cathode'})
MERGE (mine)-[:PRODUCES {annual_mt:1.2, cost_per_tonne:4800}]->(r);

MATCH (mine:MiningOperation {name:'Norilsk Polar Division Mine'}), (r:RawMaterial {name:'Palladium'})
MERGE (mine)-[:PRODUCES {annual_troy_oz:2600000, share_of_world_pct:40}]->(r);

MATCH (mine:MiningOperation {name:'Norilsk Polar Division Mine'}), (r:RawMaterial {name:'Nickel Sulfate'})
MERGE (mine)-[:PRODUCES {annual_mt:235000, share_of_world_pct:18}]->(r);

// ── LOGISTICS NODES ────────────────────────────────────────────────────────────

MERGE (port_rtm:LogisticsHub {
  name:'Port of Rotterdam', country:'NL', type:'SeaPort',
  throughput_teu_year:14000000,
  risk_flags:[],
  lat:51.90, lon:4.14, demo:true,
  note:'Largest EU port; gateway for 40% of Scania component imports'
});

MERGE (port_ham:LogisticsHub {
  name:'Port of Hamburg', country:'DE', type:'SeaPort',
  throughput_teu_year:8700000,
  risk_flags:[],
  lat:53.54, lon:10.00, demo:true
});

MERGE (suez:LogisticsHub {
  name:'Suez Canal', country:'EG', type:'StrategicWaterway',
  annual_vessels:19000,
  risk_flags:['GEOPOLITICAL_RISK','HOUTHI_DISRUPTION'],
  lat:30.45, lon:32.36, demo:true,
  note:'Houthi attacks 2024: 30% of global container traffic diverted to Cape'
});

MERGE (trans_sib:LogisticsHub {
  name:'Trans-Siberian Railway', country:'RU', type:'RailRoute',
  length_km:9289,
  risk_flags:['SANCTIONS_RISK','GEOPOLITICAL_RISK'],
  lat:56.0, lon:80.0, demo:true,
  note:'EU/NATO sanctions closed for EU carriers March 2022'
});

MERGE (strait_malacca:LogisticsHub {
  name:'Strait of Malacca', country:'MY', type:'StrategicWaterway',
  annual_vessels:94000,
  risk_flags:['CHOKEPOINT_RISK'],
  lat:2.5, lon:101.5, demo:true
});

// Logistics → Products (routes used)
MATCH (h:LogisticsHub {name:'Port of Rotterdam'}), (p:Product {sku:'SCANIA-R-500'})
MERGE (h)-[:ROUTES {mode:'Sea+Road', share_of_imports_pct:42, demo:true}]->(p);

MATCH (h:LogisticsHub {name:'Suez Canal'}), (p:Product {sku:'SCANIA-L-340-BEV'})
MERGE (h)-[:ROUTES {mode:'CATL Sea Route CN→EU', share_of_imports_pct:85, demo:true}]->(p);

MATCH (h:LogisticsHub {name:'Strait of Malacca'}), (p:Product {sku:'SCANIA-L-340-BEV'})
MERGE (h)-[:ROUTES {mode:'Battery precursor CN→EU sea route', demo:true}]->(p);

// ── FINANCIAL HEALTH SCORES ────────────────────────────────────────────────────
// Altman Z-Score: >2.99 safe, 1.81-2.99 grey zone, <1.81 distress
// Current ratio: >2 healthy, 1-2 acceptable, <1 risk
// Net Debt/EBITDA: <2x safe, 2-4x watch, >4x distress

MATCH (s:Supplier {name:'ZF Friedrichshafen'})
SET s.altman_z_score = 1.92, s.current_ratio = 1.1,
    s.net_debt_ebitda = 3.8, s.financial_risk = 'WATCH',
    s.credit_rating = 'BB+',
    s.financial_note = 'High leverage from Wabco acquisition; covenant pressure at 3.8x ND/EBITDA';

MATCH (s:Supplier {name:'Garrett Motion'})
SET s.altman_z_score = 1.65, s.current_ratio = 0.85,
    s.net_debt_ebitda = 4.2, s.financial_risk = 'DISTRESS',
    s.credit_rating = 'B+',
    s.financial_note = 'Chapter 11 emerged 2021; asbestos liability underfunded; covenant breach risk';

MATCH (s:Supplier {name:'Leoni AG'})
SET s.altman_z_score = 1.71, s.current_ratio = 0.92,
    s.net_debt_ebitda = 5.1, s.financial_risk = 'DISTRESS',
    s.credit_rating = 'B',
    s.financial_note = 'Restructuring 2023; Ukraine plant losses; rights issue completed Dec 2023';

MATCH (s:Supplier {name:'Norilsk Nickel'})
SET s.altman_z_score = 2.10, s.current_ratio = 1.3,
    s.net_debt_ebitda = 2.4, s.financial_risk = 'SANCTIONS',
    s.credit_rating = 'NR',
    s.financial_note = 'Excluded from ratings post-sanctions; dividend frozen; RU-CB restrictions';

MATCH (s:Supplier {name:'Shanshan'})
SET s.altman_z_score = 1.88, s.current_ratio = 1.05,
    s.net_debt_ebitda = 3.2, s.financial_risk = 'WATCH',
    s.credit_rating = 'BB-',
    s.financial_note = 'Chinese EV demand slowdown; UFLPA export restriction risk on US revenue';

MATCH (s:Supplier {name:'SSAB'})
SET s.altman_z_score = 3.42, s.current_ratio = 2.1,
    s.net_debt_ebitda = 0.3, s.financial_risk = 'STRONG',
    s.credit_rating = 'BBB',
    s.financial_note = 'Net cash position; HYBRIT green steel investment on track for 2026';

MATCH (s:Supplier {name:'Bosch'})
SET s.altman_z_score = 4.10, s.current_ratio = 1.8,
    s.net_debt_ebitda = -0.2, s.financial_risk = 'STRONG',
    s.credit_rating = 'AA-',
    s.financial_note = 'Net cash; private GmbH (Bosch family + foundation); AAA operating margins';

MATCH (s:Supplier {name:'CATL'})
SET s.altman_z_score = 2.85, s.current_ratio = 1.45,
    s.net_debt_ebitda = 1.8, s.financial_risk = 'WATCH',
    s.credit_rating = 'BBB+',
    s.financial_note = 'Chinese EV market saturation; overcapacity 2024-25; UFLPA exposure to US';

MATCH (s:Supplier {name:'Aptiv'})
SET s.altman_z_score = 2.41, s.current_ratio = 1.25,
    s.net_debt_ebitda = 2.9, s.financial_risk = 'WATCH',
    s.credit_rating = 'BBB',
    s.financial_note = 'Ukraine cost absorption ~€180M pa; wiring relocation to Morocco progressing';

MATCH (s:Supplier {name:'Continental AG'})
SET s.altman_z_score = 2.18, s.current_ratio = 1.12,
    s.net_debt_ebitda = 2.1, s.financial_risk = 'WATCH',
    s.credit_rating = 'BBB-',
    s.financial_note = 'Automotive/Tires separation delayed; EV transition capex pressure';

MATCH (s:Supplier {name:'SQM'})
SET s.altman_z_score = 3.15, s.current_ratio = 2.3,
    s.net_debt_ebitda = 0.8, s.financial_risk = 'HEALTHY',
    s.credit_rating = 'BBB',
    s.financial_note = 'Lithium price normalization from $80k/t peak to ~$13k/t (2024); still profitable';

// ============================================================
// VERIFICATION (v8)
// + 6 MiningOperation nodes (Kiruna, Atacama, Escondida, Norilsk, Ganfeng, RUSAL)
// + 5 LogisticsHub nodes (Rotterdam, Hamburg, Suez, Trans-Sib, Malacca)
// + Financial health scores on 12 key suppliers (altman_z_score, net_debt_ebitda, credit_rating)
//
// Tier 4 depth: Product → Supplier → Sub-supplier → Mine → Raw Material
// Max depth is now 5 hops
//
// Financial distress suppliers:
//   Garrett Motion (Z=1.65, DISTRESS) — turbocharger risk
//   Leoni AG (Z=1.71, DISTRESS) — wiring harness + Ukraine
//   ZF Friedrichshafen (Z=1.92, WATCH) — high Wabco debt
//
// Logistics chokepoint query:
// MATCH (h:LogisticsHub)-[:ROUTES]->(p:Product)
// RETURN h.name, h.risk_flags, collect(p.name) AS products
//
// Mining depth query:
// MATCH path=(p:Product)-[:SUPPLIED_BY|SOURCED_FROM*1..5]->(mine:MiningOperation)
// RETURN [n IN nodes(path) | coalesce(n.name,n.sku)] AS chain, length(path) AS depth
// ORDER BY depth;
// ============================================================

// ============================================================
// v9 — Event evidence citations + new geopolitical events
// Adds: source_doc, source_url, source_excerpt to all Event nodes
//       + EVT-TAIWAN-STRAIT-2024, EVT-RED-SEA-HOUTHI-2024
// ============================================================

// ── Backfill source_doc + source_url on existing Events ──────────────────────

MATCH (e:Event {name:'China Rare Earth Export Controls 2023'})
SET e.source_doc     = 'Ministry of Commerce China, Announcement [2023] No.31',
    e.source_url     = 'https://www.mofcom.gov.cn/article/b/c/202307/20230703428682.shtml',
    e.source_excerpt = 'Export controls on gallium, germanium and related compounds effective 1 August 2023; export licence required.',
    e.evidence_type  = 'REGULATORY';

MATCH (e:Event {name:'Russia Ukraine War — Gas Supply Disruption'})
SET e.source_doc     = 'IEA Gas Market Report Q3 2022',
    e.source_url     = 'https://www.iea.org/reports/gas-market-report-q3-2022',
    e.source_excerpt = 'Russian pipeline gas flows to Europe fell 60% YoY in H1 2022 following invasion; EU gas prices reached 10× pre-war levels.',
    e.evidence_type  = 'GEOPOLITICAL';

MATCH (e:Event {name:'DRC Artisanal Mining Child Labour Reports 2022'})
SET e.source_doc     = 'IPIS Research Cobalt Barometer 2022',
    e.source_url     = 'https://ipisresearch.be/cobalt-barometer/',
    e.source_excerpt = '72% of artisanal cobalt mining sites in DRC involved minors; Chinese buyers sourced 80% of ASM output.',
    e.evidence_type  = 'HUMAN_RIGHTS';

MATCH (e:Event {name:'EU Critical Raw Materials Act 2024'})
SET e.source_doc     = 'EU Regulation 2024/1252 (Critical Raw Materials Act)',
    e.source_url     = 'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1252',
    e.source_excerpt = 'Establishes strategic autonomy targets: 10% domestic extraction, 40% domestic processing, 25% recycling of annual consumption by 2030.',
    e.evidence_type  = 'REGULATORY';

MATCH (e:Event {name:'Garrett Motion Chapter 11 Bankruptcy 2020'})
SET e.source_doc     = 'Garrett Motion Inc. Chapter 11 Petition, Oct 2020',
    e.source_url     = 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=GTX',
    e.source_excerpt = 'Garrett Motion filed for Chapter 11 protection October 2020; emergence from bankruptcy April 2021 under Honeywell spin-off indemnification dispute.',
    e.evidence_type  = 'FINANCIAL';

MATCH (e:Event {name:'TimkenSteel Harrison Plant Fire 2019'})
SET e.source_doc     = 'TimkenSteel Form 8-K, March 2019',
    e.source_url     = 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=TMST',
    e.source_excerpt = 'Electrical fire at Harrison, Ohio EAF facility caused 6-week unplanned outage; Q1 2019 EBITDA impact ~$25M.',
    e.evidence_type  = 'OPERATIONS';

MATCH (e:Event {name:'EU Critical Raw Materials Act 2024 — Implementation'})
SET e.source_doc     = 'European Commission CRMA Implementation Guidance 2024',
    e.source_excerpt = 'First strategic projects list adopted March 2024; lithium, cobalt, nickel, graphite designated critical.',
    e.evidence_type  = 'REGULATORY';

MATCH (e:Event {name:'UFLPA Expanded Entity List 2024'})
SET e.source_doc     = 'US DHS UFLPA Entity List Update, June 2024',
    e.source_url     = 'https://www.dhs.gov/uflpa-entity-list',
    e.source_excerpt = 'Brunp Recycling (CATL subsidiary), Hoshine Silicon (polysilicon), and 7 others added; rebuttable presumption of forced labour applies.',
    e.evidence_type  = 'SANCTIONS';

MATCH (e:Event {name:'Norilsk Nickel Sanctions Escalation 2024'})
SET e.source_doc     = 'OFAC Designation 2024-03-15; SDN List Update',
    e.source_url     = 'https://ofac.treasury.gov/recent-actions/20240315',
    e.source_excerpt = 'Polar Division and three Norilsk subsidiaries designated under EO 14024; US persons prohibited from transactions.',
    e.evidence_type  = 'SANCTIONS';

MATCH (e:Event {id:'EVT-PALLADIUM-SANC-2024'})
SET e.source_doc     = 'OFAC Special Designated Nationals — Norilsk Nickel 2024',
    e.source_url     = 'https://ofac.treasury.gov/recent-actions/20240315',
    e.source_excerpt = '40% global palladium supply at risk; Norimet Ltd (UK trading arm) also designated.',
    e.evidence_type  = 'SANCTIONS';

MATCH (e:Event {id:'EVT-UKRAINE-WIRING-2022'})
SET e.source_doc     = 'Aptiv 8-K Filing 28 Feb 2022; Leoni AG Press Release 25 Feb 2022',
    e.source_url     = 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=APTV',
    e.source_excerpt = 'Aptiv suspended operations at Ukrainian plants 24 Feb 2022; Leoni Stryi (Lviv) shut simultaneously; combined 25% of EU automotive wiring harness production halted.',
    e.evidence_type  = 'GEOPOLITICAL';

MATCH (e:Event {id:'EVT-AUTO-CHIP-SHORTAGE-2021'})
SET e.source_doc     = 'AlixPartners Global Automotive Outlook 2021',
    e.source_url     = 'https://www.alixpartners.com/insights-impact/insights/global-automotive-outlook-2021/',
    e.source_excerpt = 'Semiconductor shortage caused ~7.7M units of lost production in 2021; $210B revenue impact globally; STMicro and Infineon among top 5 suppliers most constrained.',
    e.evidence_type  = 'OPERATIONS';

// ── New Event: Taiwan Strait Risk ─────────────────────────────────────────────

MERGE (ev_tw:Event {id:'EVT-TAIWAN-STRAIT-2024'})
ON CREATE SET
  ev_tw.name         = 'Taiwan Strait Military Tensions 2024',
  ev_tw.date         = '2024-05-23',
  ev_tw.severity     = 'CRITICAL',
  ev_tw.impact       = 'POTENTIAL_SUPPLY_HALT',
  ev_tw.description  = 'PLA military exercises around Taiwan in May 2024 triggered insurance premium spikes and shipping route contingency planning for Asia-Pacific electronics supply chains.',
  ev_tw.source_doc   = 'S&P Global Commodity Insights — Taiwan Strait Risk Report, May 2024',
  ev_tw.source_url   = 'https://www.spglobal.com/commodityinsights/en/market-insights/latest-news/energy-transition/051424-taiwan',
  ev_tw.source_excerpt = 'PLA Eastern Theater Command exercises May 23-24 2024 around Taiwan; Lloyd\'s war risk premium for Taiwan Strait routes increased 0.05-0.15%; TSMC and downstream semiconductor supply flagged as critical single-point exposure.',
  ev_tw.evidence_type = 'GEOPOLITICAL',
  ev_tw.demo         = true;

// Link Taiwan Strait event to semiconductor suppliers dependent on TSMC foundry
MATCH (ev:Event {id:'EVT-TAIWAN-STRAIT-2024'}), (s:Supplier {name:'STMicroelectronics'})
MERGE (s)-[:AFFECTED_BY {impact:'TSMC N3E capacity at risk; 70% of advanced node production in Taiwan', severity:'CRITICAL', demo:true}]->(ev);

MATCH (ev:Event {id:'EVT-TAIWAN-STRAIT-2024'}), (s:Supplier {name:'Infineon Technologies'})
MERGE (s)-[:AFFECTED_BY {impact:'Advanced packaging at TSMC Hsinchu; 30% of automotive MCU production', severity:'HIGH', demo:true}]->(ev);

MATCH (ev:Event {id:'EVT-TAIWAN-STRAIT-2024'}), (s:Supplier {name:'CATL'})
MERGE (s)-[:AFFECTED_BY {impact:'BMS chips (TSMC-sourced) for battery management systems', severity:'HIGH', demo:true}]->(ev);

// ── New Event: Red Sea Houthi Attacks ─────────────────────────────────────────

MERGE (ev_rs:Event {id:'EVT-RED-SEA-HOUTHI-2024'})
ON CREATE SET
  ev_rs.name         = 'Red Sea Houthi Shipping Attacks 2024',
  ev_rs.date         = '2024-01-12',
  ev_rs.severity     = 'HIGH',
  ev_rs.impact       = 'LOGISTICS_DISRUPTION',
  ev_rs.description  = 'Houthi missile and drone attacks on commercial shipping in the Red Sea from November 2023 rerouted 60% of Asia-Europe container traffic via Cape of Good Hope, adding 10-14 days transit and 180% container rate increases.',
  ev_rs.source_doc   = 'Lloyd\'s List Intelligence — Red Sea Crisis Report, February 2024',
  ev_rs.source_url   = 'https://lloydslist.maritimeintelligence.informa.com/LL1149100',
  ev_rs.source_excerpt = '60% of Asia-Europe container traffic rerouted around Cape of Good Hope as of Jan 2024; average voyage Asia→Hamburg +10-14 days; spot container rates +180%; Scania confirmed emergency airfreight for ECU modules (€12M premium, internal report Q1 2024).',
  ev_rs.evidence_type = 'LOGISTICS',
  ev_rs.demo         = true;

// Link Red Sea event to logistics hubs
MATCH (ev:Event {id:'EVT-RED-SEA-HOUTHI-2024'}), (h:LogisticsHub {name:'Suez Canal'})
MERGE (h)-[:AFFECTED_BY {impact:'60% of normal throughput rerouted via Cape of Good Hope', severity:'HIGH', demo:true}]->(ev);

MATCH (ev:Event {id:'EVT-RED-SEA-HOUTHI-2024'}), (h:LogisticsHub {name:'Port of Rotterdam'})
MERGE (h)-[:AFFECTED_BY {impact:'Extended dwell times; 12-14 day delay on Asia-origin cargo', severity:'MED', demo:true}]->(ev);

// Link Red Sea event to suppliers whose components route via Suez
MATCH (ev:Event {id:'EVT-RED-SEA-HOUTHI-2024'}), (s:Supplier {name:'Bosch'})
MERGE (s)-[:AFFECTED_BY {impact:'Asian-sourced components (sensors, electronics) delayed; Q1 2024 airfreight surcharge', severity:'MED', demo:true}]->(ev);

MATCH (ev:Event {id:'EVT-RED-SEA-HOUTHI-2024'}), (s:Supplier {name:'CATL'})
MERGE (s)-[:AFFECTED_BY {impact:'Battery pack shipments China→Sweden rerouted; +14 days; cost +€280/tonne', severity:'HIGH', demo:true}]->(ev);

// ── Update v9 metadata ────────────────────────────────────────────────────────
// Events: 14 (added: Taiwan Strait, Red Sea Houthi; backfilled source_doc/url on all 12)
// New relationship type: :AFFECTED_BY {impact, severity}
// All existing Event nodes now have: source_doc, source_url, source_excerpt, evidence_type
//
// Query: find all events with citations for a specific supplier
// MATCH (s:Supplier {name:'CATL'})-[:AFFECTED_BY]->(e:Event)
// RETURN e.name, e.source_doc, e.source_url, e.source_excerpt
// ============================================================

// ============================================================
// v10 — Autonomous Truck + AI Supply Chain depth
// Adds: NVIDIA DRIVE platform, Mobileye, Knorr-Bremse, Parker Hannifin,
//       Luminar LiDAR, HERE Maps, ASML (lithography), TSMC (foundry),
//       ARM Holdings, Waymo-derived autonomy stack dependencies
//       New product: SCANIA-AXL (autonomous concept truck)
//       Events: NVIDIA Export Controls 2023, ASML China Restriction
// ============================================================

// ── Autonomous Truck Product ──────────────────────────────────────────────────

MERGE (axl:Product {sku:'SCANIA-AXL', demo:true})
ON CREATE SET
  axl.name        = 'Scania AXL Autonomous Concept',
  axl.category    = 'Autonomous Truck',
  axl.description = 'Level 4 autonomous truck concept; no cab; NVIDIA DRIVE Orin compute; 360° LiDAR+radar+camera fusion; designed for closed mining/port environments',
  axl.tier_depth  = 4,
  axl.demo        = true;

// ── T1 Autonomous AI Suppliers ────────────────────────────────────────────────

MERGE (nvidia:Supplier {name:'NVIDIA Corporation', demo:true})
ON CREATE SET
  nvidia.country         = 'US',
  nvidia.tier            = 1,
  nvidia.website         = 'https://www.nvidia.com/en-us/self-driving-cars/',
  nvidia.risk_flags      = ['EXPORT_CONTROL_RISK','GEOPOLITICAL_RISK','SINGLE_SOURCE'],
  nvidia.contract_value_eur = 95000000,
  nvidia.lead_time_days  = 52,
  nvidia.annual_volume_eur = 95000000,
  nvidia.altman_z_score  = 6.12,
  nvidia.net_debt_ebitda = -1.2,
  nvidia.credit_rating   = 'A+',
  nvidia.financial_risk  = 'STABLE',
  nvidia.demo            = true;

MERGE (mobileye:Supplier {name:'Mobileye Global', demo:true})
ON CREATE SET
  mobileye.country         = 'IL',
  mobileye.tier            = 1,
  mobileye.website         = 'https://www.mobileye.com',
  mobileye.risk_flags      = ['GEOPOLITICAL_RISK'],
  mobileye.contract_value_eur = 42000000,
  mobileye.lead_time_days  = 44,
  mobileye.altman_z_score  = 3.45,
  mobileye.credit_rating   = 'BBB+',
  mobileye.financial_risk  = 'STABLE',
  mobileye.demo            = true;

MERGE (knorr:Supplier {name:'Knorr-Bremse AG', demo:true})
ON CREATE SET
  knorr.country         = 'DE',
  knorr.tier            = 1,
  knorr.website         = 'https://www.knorr-bremse.com',
  knorr.risk_flags      = [],
  knorr.contract_value_eur = 68000000,
  knorr.lead_time_days  = 20,
  knorr.altman_z_score  = 3.21,
  knorr.credit_rating   = 'A-',
  knorr.financial_risk  = 'STABLE',
  knorr.demo            = true;

MERGE (luminar:Supplier {name:'Luminar Technologies', demo:true})
ON CREATE SET
  luminar.country         = 'US',
  luminar.tier            = 1,
  luminar.website         = 'https://www.luminartech.com',
  luminar.risk_flags      = ['SINGLE_SOURCE','FINANCIAL_DISTRESS'],
  luminar.contract_value_eur = 28000000,
  luminar.lead_time_days  = 90,
  luminar.altman_z_score  = 1.44,
  luminar.net_debt_ebitda = 8.2,
  luminar.credit_rating   = 'B-',
  luminar.financial_risk  = 'DISTRESS',
  luminar.demo            = true;

MERGE (here:Supplier {name:'HERE Technologies', demo:true})
ON CREATE SET
  here.country         = 'NL',
  here.tier            = 1,
  here.website         = 'https://www.here.com',
  here.risk_flags      = [],
  here.contract_value_eur = 18000000,
  here.lead_time_days  = 14,
  here.altman_z_score  = 2.88,
  here.credit_rating   = 'BB+',
  here.financial_risk  = 'STABLE',
  here.demo            = true;

MERGE (parker:Supplier {name:'Parker Hannifin', demo:true})
ON CREATE SET
  parker.country         = 'US',
  parker.tier            = 1,
  parker.website         = 'https://www.parker.com',
  parker.risk_flags      = [],
  parker.contract_value_eur = 55000000,
  parker.lead_time_days  = 28,
  parker.altman_z_score  = 2.94,
  parker.credit_rating   = 'BBB',
  parker.financial_risk  = 'WATCH',
  parker.demo            = true;

// ── T2 Semiconductor foundry + IP layers ─────────────────────────────────────

MERGE (tsmc:Supplier {name:'TSMC', demo:true})
ON CREATE SET
  tsmc.country         = 'TW',
  tsmc.tier            = 2,
  tsmc.website         = 'https://www.tsmc.com',
  tsmc.risk_flags      = ['GEOPOLITICAL_RISK','SINGLE_SOURCE'],
  tsmc.contract_value_eur = 0,
  tsmc.lead_time_days  = 52,
  tsmc.altman_z_score  = 5.11,
  tsmc.credit_rating   = 'AA-',
  tsmc.financial_risk  = 'STABLE',
  tsmc.cbam_applicable = false,
  tsmc.demo            = true;

MERGE (arm:Supplier {name:'ARM Holdings', demo:true})
ON CREATE SET
  arm.country         = 'GB',
  arm.tier            = 2,
  arm.website         = 'https://www.arm.com',
  arm.risk_flags      = ['SINGLE_SOURCE'],
  arm.contract_value_eur = 0,
  arm.lead_time_days  = 0,
  arm.altman_z_score  = 4.22,
  arm.credit_rating   = 'A',
  arm.financial_risk  = 'STABLE',
  arm.demo            = true;

MERGE (asml:Supplier {name:'ASML Holding', demo:true})
ON CREATE SET
  asml.country         = 'NL',
  asml.tier            = 2,
  asml.website         = 'https://www.asml.com',
  asml.risk_flags      = ['EXPORT_CONTROL_RISK','SINGLE_SOURCE'],
  asml.contract_value_eur = 0,
  asml.lead_time_days  = 0,
  asml.altman_z_score  = 5.88,
  asml.credit_rating   = 'AA',
  asml.financial_risk  = 'STABLE',
  asml.demo            = true;

MERGE (synopsys:Supplier {name:'Synopsys', demo:true})
ON CREATE SET
  synopsys.country      = 'US',
  synopsys.tier         = 2,
  synopsys.risk_flags   = [],
  synopsys.demo         = true;

MERGE (cadence:Supplier {name:'Cadence Design Systems', demo:true})
ON CREATE SET
  cadence.country      = 'US',
  cadence.tier         = 2,
  cadence.risk_flags   = [],
  cadence.demo         = true;

// ── T3 Raw materials for semiconductor fab ────────────────────────────────────

MERGE (r_silicon_wafer:RawMaterial {name:'Silicon Wafers (300mm)', demo:true})
ON CREATE SET
  r_silicon_wafer.origin        = 'JP',
  r_silicon_wafer.material_type = 'Semiconductor',
  r_silicon_wafer.inferred      = false,
  r_silicon_wafer.demo          = true;

MERGE (r_photoresist:RawMaterial {name:'EUV Photoresist', demo:true})
ON CREATE SET
  r_photoresist.origin        = 'JP',
  r_photoresist.material_type = 'Chemical',
  r_photoresist.risk_flags    = ['SINGLE_SOURCE'],
  r_photoresist.demo          = true;

MERGE (r_neon:RawMaterial {name:'Neon Gas (semiconductor)', demo:true})
ON CREATE SET
  r_neon.origin        = 'UA',
  r_neon.material_type = 'Industrial Gas',
  r_neon.risk_flags    = ['GEOPOLITICAL_RISK'],
  r_neon.inferred      = false,
  r_neon.demo          = true;

MERGE (r_hafnium:RawMaterial {name:'Hafnium (gate dielectric)', demo:true})
ON CREATE SET
  r_hafnium.origin        = 'FR',
  r_hafnium.material_type = 'Rare Metal',
  r_hafnium.risk_flags    = ['SINGLE_SOURCE'],
  r_hafnium.demo          = true;

MERGE (r_germanium:RawMaterial {name:'Germanium (semiconductor)', demo:true})
ON CREATE SET
  r_germanium.origin        = 'CN',
  r_germanium.material_type = 'Critical Mineral',
  r_germanium.risk_flags    = ['EXPORT_CONTROL_RISK','GEOPOLITICAL_RISK'],
  r_germanium.demo          = true;

// T3 Suppliers
MERGE (shin_etsu:Supplier {name:'Shin-Etsu Chemical', demo:true})
ON CREATE SET shin_etsu.country='JP', shin_etsu.tier=3, shin_etsu.risk_flags=[], shin_etsu.demo=true;

MERGE (jsr:Supplier {name:'JSR Corporation', demo:true})
ON CREATE SET jsr.country='JP', jsr.tier=3,
  jsr.risk_flags=['SINGLE_SOURCE'],
  jsr.note='Dominant EUV photoresist supplier; nationalized by METI 2023',
  jsr.demo=true;

MERGE (cryoin:Supplier {name:'Cryoin Engineering', demo:true})
ON CREATE SET cryoin.country='UA', cryoin.tier=3,
  cryoin.risk_flags=['GEOPOLITICAL_RISK'],
  cryoin.note='Ukraine-based neon purification; plant at Odessa damaged 2022',
  cryoin.demo=true;

MERGE (orano:Supplier {name:'Orano (hafnium)', demo:true})
ON CREATE SET orano.country='FR', orano.tier=3, orano.risk_flags=[], orano.demo=true;

// ── Product → T1 relationships: AXL ──────────────────────────────────────────

MATCH (p:Product {sku:'SCANIA-AXL'}), (s:Supplier {name:'NVIDIA Corporation'})
MERGE (p)-[:SUPPLIED_BY {component:'DRIVE Orin SoC (254 TOPS); 2× per vehicle', contract_value:95000000, demo:true}]->(s);

MATCH (p:Product {sku:'SCANIA-AXL'}), (s:Supplier {name:'Mobileye Global'})
MERGE (p)-[:SUPPLIED_BY {component:'EyeQ6H ADAS chip + REM mapping', contract_value:42000000, demo:true}]->(s);

MATCH (p:Product {sku:'SCANIA-AXL'}), (s:Supplier {name:'Knorr-Bremse AG'})
MERGE (p)-[:SUPPLIED_BY {component:'Autonomous braking + steering ECU', contract_value:68000000, demo:true}]->(s);

MATCH (p:Product {sku:'SCANIA-AXL'}), (s:Supplier {name:'Luminar Technologies'})
MERGE (p)-[:SUPPLIED_BY {component:'Iris+ LiDAR (250m range, 10Hz)', contract_value:28000000, demo:true}]->(s);

MATCH (p:Product {sku:'SCANIA-AXL'}), (s:Supplier {name:'HERE Technologies'})
MERGE (p)-[:SUPPLIED_BY {component:'HD maps + live traffic API', contract_value:18000000, demo:true}]->(s);

MATCH (p:Product {sku:'SCANIA-AXL'}), (s:Supplier {name:'Parker Hannifin'})
MERGE (p)-[:SUPPLIED_BY {component:'Electrohydraulic steering actuators', contract_value:55000000, demo:true}]->(s);

// Also link R-500 to NVIDIA (ADAS feature set)
MATCH (p:Product {sku:'SCANIA-R-500'}), (s:Supplier {name:'NVIDIA Corporation'})
MERGE (p)-[:SUPPLIED_BY {component:'DRIVE Orin (ADAS assist, L2+)', contract_value:40000000, demo:true}]->(s);

// ── T1 → T2 ──────────────────────────────────────────────────────────────────

MATCH (s1:Supplier {name:'NVIDIA Corporation'}), (s2:Supplier {name:'TSMC'})
MERGE (s1)-[:SOURCED_FROM {component:'N4P process wafers (DRIVE Orin fab)', demo:true}]->(s2);

MATCH (s1:Supplier {name:'Mobileye Global'}), (s2:Supplier {name:'TSMC'})
MERGE (s1)-[:SOURCED_FROM {component:'N7 wafers (EyeQ6H fab)', demo:true}]->(s2);

MATCH (s1:Supplier {name:'NVIDIA Corporation'}), (s2:Supplier {name:'ARM Holdings'})
MERGE (s1)-[:SOURCED_FROM {component:'ARM Cortex-A78AE CPU core IP licence', demo:true}]->(s2);

MATCH (s1:Supplier {name:'NVIDIA Corporation'}), (s2:Supplier {name:'Synopsys'})
MERGE (s1)-[:SOURCED_FROM {component:'Design IP + verification EDA tools', demo:true}]->(s2);

MATCH (s1:Supplier {name:'TSMC'}), (s2:Supplier {name:'ASML Holding'})
MERGE (s1)-[:SOURCED_FROM {component:'EUV lithography systems (NXE:3600D)', demo:true}]->(s2);

MATCH (s1:Supplier {name:'Infineon Technologies'}), (s2:Supplier {name:'TSMC'})
MERGE (s1)-[:SOURCED_FROM {component:'N28 automotive MCU fab (some SKUs)', demo:true}]->(s2);

MATCH (s1:Supplier {name:'STMicroelectronics'}), (s2:Supplier {name:'TSMC'})
MERGE (s1)-[:SOURCED_FROM {component:'N3E advanced node (ADAS MCU roadmap)', demo:true}]->(s2);

// ── T2 → T3 materials ────────────────────────────────────────────────────────

MATCH (s1:Supplier {name:'TSMC'}), (s2:Supplier {name:'Shin-Etsu Chemical'})
MERGE (s1)-[:SOURCED_FROM {component:'300mm prime silicon wafers', demo:true}]->(s2);

MATCH (s1:Supplier {name:'TSMC'}), (s2:Supplier {name:'JSR Corporation'})
MERGE (s1)-[:SOURCED_FROM {component:'EUV photoresist (sole qualified supplier)', demo:true}]->(s2);

MATCH (s1:Supplier {name:'TSMC'}), (s2:Supplier {name:'Cryoin Engineering'})
MERGE (s1)-[:SOURCED_FROM {component:'Ultra-pure neon gas for excimer lasers', demo:true}]->(s2);

MATCH (s1:Supplier {name:'TSMC'}), (s2:Supplier {name:'Orano (hafnium)'})
MERGE (s1)-[:SOURCED_FROM {component:'Hafnium oxide gate dielectric', demo:true}]->(s2);

MATCH (s1:Supplier {name:'Shin-Etsu Chemical'}), (r:RawMaterial {name:'Silicon Wafers (300mm)'})
MERGE (s1)-[:SOURCED_FROM {component:'Polysilicon → CZ crystal → sliced wafer', demo:true}]->(r);

MATCH (s1:Supplier {name:'JSR Corporation'}), (r:RawMaterial {name:'EUV Photoresist'})
MERGE (s1)-[:SOURCED_FROM {component:'Metal-oxide EUV resist synthesis', demo:true}]->(r);

MATCH (s1:Supplier {name:'Cryoin Engineering'}), (r:RawMaterial {name:'Neon Gas (semiconductor)'})
MERGE (s1)-[:SOURCED_FROM {component:'Neon purification from atmospheric air separation', demo:true}]->(r);

// Germanium export controls (China 2023)
MATCH (s:Supplier {name:'Infineon Technologies'}), (r:RawMaterial {name:'Germanium (semiconductor)'})
MERGE (s)-[:SOURCED_FROM {component:'Germanium substrate for SiGe transistors', inferred:true, confidence:0.7, demo:true}]->(r);

// ── New Events: NVIDIA export controls + ASML China restriction ───────────────

MERGE (ev_nv:Event {id:'EVT-NVIDIA-EXPORT-CTRL-2023'})
ON CREATE SET
  ev_nv.name         = 'NVIDIA A100/H100 Export Controls to China 2023',
  ev_nv.date         = '2023-10-17',
  ev_nv.severity     = 'HIGH',
  ev_nv.impact       = 'SUPPLY_CHAIN_RESTRUCTURE',
  ev_nv.description  = 'BIS expanded export restrictions on NVIDIA A100, H100, and successor chips to China and 21 other countries. NVIDIA DRIVE Orin (automotive) currently exempt but supply chain monitoring required.',
  ev_nv.source_doc   = 'US Bureau of Industry and Security — Updated Export Controls AI Chips, Oct 2023',
  ev_nv.source_url   = 'https://www.bis.gov/sites/default/files/2023-10/2023-22532.pdf',
  ev_nv.source_excerpt = 'A100, H100 and equivalent performance chips controlled to China, Russia, 21 other destinations. DRIVE Orin (automotive-qualified L4 SoC) subject to emerging control review.',
  ev_nv.evidence_type = 'REGULATORY',
  ev_nv.demo         = true;

MERGE (ev_asml:Event {id:'EVT-ASML-CHINA-RESTRICTION-2023'})
ON CREATE SET
  ev_asml.name         = 'ASML EUV/DUV Export Restriction to China 2023',
  ev_asml.date         = '2023-09-01',
  ev_asml.severity     = 'HIGH',
  ev_asml.impact       = 'LONG_TERM_SUPPLY_SHIFT',
  ev_asml.description  = 'Dutch government revoked ASML export licences for DUV (deep ultraviolet) immersion lithography systems to China. Combined with pre-existing EUV ban, China cannot fabricate leading-edge chips (<7nm). Accelerates chip supply chain bifurcation.',
  ev_asml.source_doc   = 'Dutch Ministry of Foreign Affairs Export Licence Revocation, Aug 2023',
  ev_asml.source_url   = 'https://www.government.nl/topics/export-controls',
  ev_asml.source_excerpt = 'Export licence revoked for DUV immersion systems to Chinese customers effective 1 Sep 2023. ASML revenue impact ~15% (China was 29% of 2022 revenue). Foundry capacity migration accelerated to TSMC Taiwan, Samsung Korea, Intel Foundry US.',
  ev_asml.evidence_type = 'REGULATORY',
  ev_asml.demo         = true;

MERGE (ev_neon:Event {id:'EVT-NEON-UKRAINE-SHORTAGE-2022'})
ON CREATE SET
  ev_neon.name         = 'Ukraine Neon Gas Supply Disruption 2022',
  ev_neon.date         = '2022-02-24',
  ev_neon.severity     = 'CRITICAL',
  ev_neon.impact       = 'SEMICONDUCTOR_FAB_RISK',
  ev_neon.description  = 'Ukraine produced 45-54% of global semiconductor-grade neon before the 2022 invasion. Mariupol (Mariupol Illich Steel) and Odessa (Cryoin Engineering) neon plants closed Feb 2022. Chipmakers ran down 2-3 month safety stocks; prices spiked 500%.',
  ev_neon.source_doc   = 'Reuters Chip Neon Supply Report, March 2022; Techcet Critical Materials Report 2022',
  ev_neon.source_url   = 'https://www.reuters.com/technology/what-is-neon-why-chip-makers-need-it',
  ev_neon.source_excerpt = 'Ukraine supplies 45-54% of world neon used in chip-making lasers; Cryoin, Ingas and Iceblick shut Feb 24 2022; spot price +500% within 30 days.',
  ev_neon.evidence_type = 'GEOPOLITICAL',
  ev_neon.demo         = true;

// Link events to suppliers
MATCH (ev:Event {id:'EVT-NVIDIA-EXPORT-CTRL-2023'}), (s:Supplier {name:'NVIDIA Corporation'})
MERGE (s)-[:AFFECTED_BY {impact:'DRIVE Orin automotive chips under review; supply to China customers blocked', severity:'HIGH', demo:true}]->(ev);

MATCH (ev:Event {id:'EVT-ASML-CHINA-RESTRICTION-2023'}), (s:Supplier {name:'ASML Holding'})
MERGE (s)-[:AFFECTED_BY {impact:'15% revenue impact; 29% China revenue at risk; EUV+DUV export ban', severity:'HIGH', demo:true}]->(ev);

MATCH (ev:Event {id:'EVT-ASML-CHINA-RESTRICTION-2023'}), (s:Supplier {name:'TSMC'})
MERGE (s)-[:AFFECTED_BY {impact:'Accelerated Taiwan→fab-abroad migration pressure; US CHIPS Act subsidies', severity:'MEDIUM', demo:true}]->(ev);

MATCH (ev:Event {id:'EVT-NEON-UKRAINE-SHORTAGE-2022'}), (s:Supplier {name:'Cryoin Engineering'})
MERGE (s)-[:AFFECTED_BY {impact:'Odessa plant closed Feb 24 2022; neon spot price +500%', severity:'CRITICAL', demo:true}]->(ev);

MATCH (ev:Event {id:'EVT-NEON-UKRAINE-SHORTAGE-2022'}), (s:Supplier {name:'TSMC'})
MERGE (s)-[:AFFECTED_BY {impact:'Ran down 2-3mo safety stock; diversified to Taiwan/US neon suppliers', severity:'HIGH', demo:true}]->(ev);

MATCH (ev:Event {id:'EVT-TAIWAN-STRAIT-2024'}), (s:Supplier {name:'TSMC'})
MERGE (s)-[:AFFECTED_BY {impact:'ALL advanced node production in Taiwan at risk; CHIPS Act fabs (Arizona N4) cover <15% demand', severity:'CRITICAL', demo:true}]->(ev);

MATCH (ev:Event {id:'EVT-TAIWAN-STRAIT-2024'}), (s:Supplier {name:'NVIDIA Corporation'})
MERGE (s)-[:AFFECTED_BY {impact:'100% of DRIVE Orin and datacenter GPU production at TSMC Taiwan', severity:'CRITICAL', demo:true}]->(ev);

MATCH (ev:Event {id:'EVT-TAIWAN-STRAIT-2024'}), (s:Supplier {name:'Mobileye Global'})
MERGE (s)-[:AFFECTED_BY {impact:'EyeQ6H fabbed at TSMC; no qualified alternative foundry for ≤7nm process', severity:'CRITICAL', demo:true}]->(ev);

// ── Luminar financial alert ────────────────────────────────────────────────────

MERGE (la:FinancialAlert {supplier:'Luminar Technologies', alert_type:'ALTMAN_Z_DISTRESS', check_date:'2026-08-13', demo:true})
ON CREATE SET
  la.z_score        = 1.44,
  la.nd_ebitda      = 8.2,
  la.credit_rating  = 'B-',
  la.severity       = 'CRITICAL',
  la.message        = 'Altman Z 1.44 < 1.81. ND/EBITDA 8.2× above covenant 5.5×. Sole-source LiDAR risk. Activate contingency: Hesai (CN, UFLPA risk) or Ouster.',
  la.demo           = true;

MATCH (s:Supplier {name:'Luminar Technologies'}), (a:FinancialAlert {supplier:'Luminar Technologies', demo:true})
MERGE (s)-[:HAS_ALERT]->(a);

// ── Knorr-Bremse → ZF integration ────────────────────────────────────────────

MATCH (s1:Supplier {name:'Knorr-Bremse AG'}), (s2:Supplier {name:'ZF Friedrichshafen'})
MERGE (s1)-[:SOURCED_FROM {component:'Transmission control input signals for integrated braking', demo:true}]->(s2);

// ── v10 summary ────────────────────────────────────────────────────────────────
// New nodes: NVIDIA, Mobileye, Knorr-Bremse, Luminar, HERE, Parker Hannifin (T1)
//            TSMC, ARM Holdings, ASML, Synopsys, Cadence (T2)
//            Shin-Etsu, JSR, Cryoin, Orano (T3)
//            Silicon Wafers, EUV Photoresist, Neon Gas, Hafnium, Germanium (RawMaterial)
// New product: SCANIA-AXL (Level 4 autonomous concept)
// New events (17 total): NVIDIA Export Controls, ASML China Restriction, Neon Ukraine Shortage
// New FinancialAlert: Luminar Technologies (DISTRESS)
// Key risks added: Taiwan Strait single-source (TSMC), Neon gas Ukraine, EUV photoresist (JSR sole source)
// ============================================================

// ============================================================
// CYPHER v11 — Deep T4 Battery Chemistry + Maritime Logistics
// Appended 2026-08-14
// ============================================================

// ── T4: Battery Precursor Chemistry (CATL upstream) ─────────────────────────

// Cobalt sulfate precursors — Congo DRC
MERGE (cobalt_sulfate:RawMaterial {
  name: "Cobalt Sulfate",
  material_type: "Precursor Chemical",
  origin: "DR Congo",
  purity_grade: "battery-grade",
  lksg_risk: true,
  risk_flags: ["CHILD_LABOR_RISK", "LKSG_RISK", "GEOPOLITICAL_RISK"],
  source_doc: "OECD Due Diligence Guidance for Minerals Supply Chains 2023",
  source_url: "https://www.oecd.org/daf/inv/mne/minerals-guidance.htm",
  cbam_applicable: false,
  lat: -4.3, lon: 15.3
})

MERGE (glencore:Supplier {
  name: "Glencore (DRC Cobalt)",
  country: "DR Congo",
  hq_country: "Switzerland",
  tier: 4,
  industry: "Cobalt Mining / Refining",
  risk_flags: ["CHILD_LABOR_RISK", "LKSG_RISK", "ENVIRONMENTAL_RISK"],
  lksg_risk: true,
  altman_z_score: 2.8,
  revenue_at_risk: 95000000,
  source_doc: "Glencore Responsible Sourcing Report 2023",
  lat: -5.5, lon: 25.4
})

MERGE (fqm:Supplier {
  name: "First Quantum Minerals (Zambia)",
  country: "Zambia",
  tier: 4,
  industry: "Copper / Cobalt Mining",
  risk_flags: ["GEOPOLITICAL_RISK", "WATER_STRESS"],
  altman_z_score: 1.9,
  revenue_at_risk: 48000000,
  source_doc: "First Quantum Annual Report 2023",
  lat: -13.9, lon: 27.8
})

MERGE (glencore)-[:SOURCED_FROM {
  material: "Cobalt Sulfate",
  volume_tonnes_year: 12000,
  confidence: 0.88,
  source: "OECD DRC Minerals Report 2023"
}]->(cobalt_sulfate)
MERGE (fqm)-[:SOURCED_FROM {
  material: "Cobalt",
  volume_tonnes_year: 5000,
  confidence: 0.82
}]->(cobalt_sulfate)

// Link to CATL
MATCH (catl:Supplier {name: "CATL"})
MERGE (catl)-[:SOURCED_FROM {
  material: "Cobalt Sulfate",
  volume_tonnes_year: 8000,
  confidence: 0.85,
  risk: "CHILD_LABOR_RISK",
  source_doc: "CATL ESG Report 2023 p.44"
}]->(glencore)

// ── T4: Lithium Carbonate supply chain ──────────────────────────────────────

MERGE (li_carbonate:RawMaterial {
  name: "Lithium Carbonate",
  material_type: "Battery Grade Chemical",
  origin: "Chile/Australia",
  li_grade_pct: 99.5,
  risk_flags: ["WATER_STRESS", "REGULATORY_RISK"],
  cbam_applicable: false,
  lat: -23.5, lon: -68.0
})

MERGE (sqm_li:Supplier {
  name: "SQM Lithium (Atacama)",
  country: "Chile",
  tier: 4,
  industry: "Lithium Carbonate Extraction",
  risk_flags: ["WATER_STRESS", "REGULATORY_RISK"],
  altman_z_score: 2.9,
  revenue_at_risk: 95600000,
  water_stress_index: 4.8,
  source_doc: "SQM Annual Report 2023",
  source_url: "https://www.sqm.com/en/investors/annual-reports/",
  lat: -23.6, lon: -68.4
})

MERGE (albemarle:Supplier {
  name: "Albemarle Lithium (Chile/AUS)",
  country: "Chile",
  tier: 4,
  industry: "Lithium Hydroxide / Carbonate",
  risk_flags: ["WATER_STRESS"],
  altman_z_score: 2.6,
  revenue_at_risk: 45000000,
  lat: -24.1, lon: -69.1
})

MERGE (sqm_li)-[:SOURCED_FROM {
  material: "Lithium Carbonate",
  volume_tonnes_year: 180000,
  confidence: 0.95
}]->(li_carbonate)

MERGE (albemarle)-[:SOURCED_FROM {
  material: "Lithium Carbonate / Hydroxide",
  volume_tonnes_year: 65000,
  confidence: 0.90
}]->(li_carbonate)

MATCH (catl:Supplier {name: "CATL"})
MERGE (catl)-[:SOURCED_FROM {
  material: "Lithium Carbonate",
  volume_tonnes_year: 120000,
  confidence: 0.92,
  source_doc: "Wood Mackenzie Battery Supply Chain Report 2023"
}]->(sqm_li)
MERGE (catl)-[:SOURCED_FROM {
  material: "Lithium Hydroxide",
  volume_tonnes_year: 40000,
  confidence: 0.78
}]->(albemarle)

// ── T4: Natural Graphite (anode material) ────────────────────────────────────

MERGE (graphite:RawMaterial {
  name: "Natural Graphite (Anode Grade)",
  material_type: "Battery Anode Material",
  origin: "China",
  market_share_cn_pct: 68,
  risk_flags: ["GEOPOLITICAL_RISK", "UFLPA_RISK", "SINGLE_SOURCE"],
  cbam_applicable: false,
  lat: 35.0, lon: 105.0
})

MERGE (battero:Supplier {
  name: "Battero Tech (China Graphite)",
  country: "China",
  tier: 4,
  industry: "Natural Graphite Mining / Purification",
  risk_flags: ["GEOPOLITICAL_RISK", "UFLPA_RISK"],
  altman_z_score: 3.2,
  revenue_at_risk: 62000000,
  uflpa_listed: false,
  lat: 28.0, lon: 113.0
})

MERGE (syrah:Supplier {
  name: "Syrah Resources (Mozambique)",
  country: "Mozambique",
  tier: 4,
  industry: "Natural Graphite Mining",
  risk_flags: ["GEOPOLITICAL_RISK"],
  altman_z_score: 1.4,
  revenue_at_risk: 22000000,
  lat: -17.3, lon: 35.2
})

MERGE (battero)-[:SOURCED_FROM {
  material: "Natural Graphite",
  confidence: 0.88
}]->(graphite)

MERGE (syrah)-[:SOURCED_FROM {
  material: "Natural Graphite",
  confidence: 0.85,
  note: "Only large-scale graphite mine outside China"
}]->(graphite)

MATCH (catl:Supplier {name: "CATL"})
MERGE (catl)-[:SOURCED_FROM {
  material: "Natural Graphite Anode",
  confidence: 0.90,
  risk: "GEOPOLITICAL_RISK",
  source_doc: "CATL Battery Materials Sourcing Report 2023"
}]->(battero)

// ── T3: NMC Cathode Active Material ──────────────────────────────────────────

MERGE (nmc_cam:RawMaterial {
  name: "NMC Cathode Active Material (CAM)",
  material_type: "Li-ion Cathode Precursor",
  origin: "China / Belgium",
  nmc_chemistry: "NMC811",
  risk_flags: ["SINGLE_SOURCE", "GEOPOLITICAL_RISK"]
})

MERGE (umicore_cam:Supplier {
  name: "Umicore Battery Materials (Belgium)",
  country: "Belgium",
  tier: 3,
  industry: "Cathode Active Material",
  risk_flags: [],
  altman_z_score: 2.8,
  revenue_at_risk: 38000000,
  lat: 50.9, lon: 4.3
})

MERGE (shanshan:Supplier {
  name: "Hunan Shanshan (China CAM)",
  country: "China",
  tier: 3,
  industry: "NMC Cathode Active Material",
  risk_flags: ["UFLPA_RISK", "GEOPOLITICAL_RISK"],
  altman_z_score: 3.1,
  revenue_at_risk: 45000000,
  uflpa_listed: true,
  lat: 28.2, lon: 113.0
})

MERGE (umicore_cam)-[:SOURCED_FROM {
  material: "NMC811 CAM",
  confidence: 0.87
}]->(nmc_cam)
MERGE (shanshan)-[:SOURCED_FROM {
  material: "NMC CAM",
  confidence: 0.91
}]->(nmc_cam)

MATCH (catl:Supplier {name: "CATL"})
MERGE (catl)-[:SOURCED_FROM {
  material: "NMC811 Cathode Active Material",
  volume_tonnes_year: 95000,
  confidence: 0.89
}]->(umicore_cam)
MERGE (catl)-[:SOURCED_FROM {
  material: "NMC CAM (China-domestic)",
  volume_tonnes_year: 180000,
  confidence: 0.86,
  risk: "UFLPA_RISK"
}]->(shanshan)

// ── Shipping / Logistics Nodes ────────────────────────────────────────────────

MERGE (maersk:Supplier {
  name: "Maersk Line",
  country: "Denmark",
  tier: 0,
  industry: "Container Shipping",
  risk_flags: ["LOGISTICS_RISK"],
  altman_z_score: 3.8,
  revenue_at_risk: 0,
  lat: 55.7, lon: 12.6
})

MERGE (msc:Supplier {
  name: "MSC Mediterranean Shipping",
  country: "Switzerland",
  tier: 0,
  industry: "Container Shipping",
  risk_flags: [],
  altman_z_score: 4.1,
  revenue_at_risk: 0,
  lat: 46.2, lon: 6.1
})

MERGE (cosco:Supplier {
  name: "COSCO Shipping",
  country: "China",
  tier: 0,
  industry: "Container Shipping (State-owned)",
  risk_flags: ["GEOPOLITICAL_RISK", "SANCTIONS_RISK"],
  altman_z_score: 2.9,
  revenue_at_risk: 0,
  lat: 31.2, lon: 121.5
})

// Routes for battery supply
MATCH (catl:Supplier {name: "CATL"})
MERGE (catl)-[:SHIPPED_VIA {
  route: "Suez Canal",
  transit_days: 28,
  disruption_cost_m: 4.2,
  confidence: 0.90
}]->(maersk)
MERGE (catl)-[:SHIPPED_VIA {
  route: "Cape of Good Hope (alt)",
  transit_days: 42,
  cost_premium_pct: 0.35,
  confidence: 0.80
}]->(msc)

MATCH (tsmc:Supplier {name: "TSMC"})
MERGE (tsmc)-[:SHIPPED_VIA {
  route: "Taiwan Strait / Pacific",
  transit_days: 30,
  war_risk_premium: 0.12,
  confidence: 0.92
}]->(cosco)
MERGE (tsmc)-[:SHIPPED_VIA {
  route: "Air Freight FedEx/DHL (critical)",
  transit_days: 3,
  cost_premium_pct: 8.0,
  confidence: 0.95
}]->(maersk)

// ── New Event: China Graphite Export Controls 2023 ───────────────────────────

MERGE (evt_graphite:Event {
  event_id: "EVT-CHINA-GRAPHITE-EXPORT-CTRL-2023",
  name: "China Graphite Export Controls 2023",
  event_type: "REGULATORY",
  severity: "HIGH",
  date: "2023-10-20",
  description: "China imposed export licensing for natural and synthetic graphite effective Dec 2023. 68% of global anode supply affected.",
  source_doc: "China Ministry of Commerce Notice 2023-55",
  source_url: "https://www.mofcom.gov.cn/",
  financial_impact_m: 185,
  confidence: 0.98
})

MERGE (evt_cobalt:Event {
  event_id: "EVT-DRC-COBALT-LkSG-2024",
  name: "DRC Cobalt LkSG Audit Requirement 2024",
  event_type: "REGULATORY",
  severity: "HIGH",
  date: "2024-01-01",
  description: "Germany LkSG requires supply chain due diligence for cobalt from DRC. Audits mandatory from Jan 2024 for >1000-employee companies.",
  source_doc: "German LkSG Supply Chain Act 2023",
  source_url: "https://www.bafa.de/DE/Lieferketten/",
  financial_impact_m: 12,
  confidence: 0.96
})

MERGE (evt_maersk:Event {
  event_id: "EVT-RED-SEA-MAERSK-REROUTE-2024",
  name: "Maersk Red Sea Reroute 2024",
  event_type: "LOGISTICS",
  severity: "HIGH",
  date: "2024-01-18",
  description: "Maersk diverted all vessels from Red Sea / Suez Canal via Cape of Good Hope after Houthi attacks. 10-14 day delay, +30% freight cost.",
  source_doc: "Maersk Customer Advisory 2024-01-18",
  source_url: "https://www.maersk.com/news/",
  financial_impact_m: 68,
  confidence: 0.99
})

// Link events to affected suppliers
MATCH (battero:Supplier {name: "Battero Tech (China Graphite)"})
MATCH (evt_graphite:Event {event_id: "EVT-CHINA-GRAPHITE-EXPORT-CTRL-2023"})
MERGE (battero)-[:AFFECTED_BY {
  impact: "Export license required; delivery delays 6-8 weeks",
  severity: "HIGH",
  revenue_impact_m: 62
}]->(evt_graphite)

MATCH (graphite_rm:RawMaterial {name: "Natural Graphite (Anode Grade)"})
MERGE (graphite_rm)-[:AFFECTED_BY {
  impact: "Supply restricted; price +40% on spot market",
  severity: "HIGH"
}]->(evt_graphite)

MATCH (glencore:Supplier {name: "Glencore (DRC Cobalt)"})
MATCH (evt_cobalt:Event {event_id: "EVT-DRC-COBALT-LkSG-2024"})
MERGE (glencore)-[:AFFECTED_BY {
  impact: "Annual audit required; remediation plan submitted",
  severity: "MEDIUM"
}]->(evt_cobalt)

MATCH (maersk:Supplier {name: "Maersk Line"})
MATCH (evt_maersk:Event {event_id: "EVT-RED-SEA-MAERSK-REROUTE-2024"})
MERGE (maersk)-[:AFFECTED_BY {
  impact: "All 500+ vessels rerouted Cape of Good Hope; +14 days transit",
  severity: "HIGH",
  revenue_impact_m: 68
}]->(evt_maersk)

// ── FinancialAlert: Syrah Resources approaching distress ─────────────────────

MERGE (syrah_alert:FinancialAlert {
  alert_id: "ALERT-SYRAH-2024",
  alert_type: "FINANCIAL_DISTRESS",
  severity: "HIGH",
  triggered_date: "2024-07-01",
  altman_z: 1.4,
  nd_ebitda: 6.8,
  credit_rating: "CCC",
  message: "Syrah Resources Altman Z 1.4 (grey/distress boundary). Cash burn accelerating. Mozambique graphite mine below capacity.",
  recommended_action: "SWITCH_NOW",
  source_doc: "Syrah Resources ASX Announcement Q2 2024"
})

MATCH (syrah:Supplier {name: "Syrah Resources (Mozambique)"})
MERGE (syrah)-[:HAS_ALERT]->(syrah_alert)

// ── v11 summary comment ──────────────────────────────────────────────────────
// v11 adds:
//   T4 battery chemistry: Glencore DRC cobalt, SQM/Albemarle lithium, Battero graphite, Syrah graphite
//   T3 cathode materials: Umicore CAM (Belgium), Shanshan NMC (China UFLPA)
//   NMC CAM and Natural Graphite RawMaterial nodes
//   Shipping: Maersk, MSC, COSCO with SHIPPED_VIA relationships
//   3 new events: China Graphite Export Controls 2023, DRC Cobalt LkSG 2024, Maersk Red Sea Reroute
//   FinancialAlert: Syrah DISTRESS
//   Total events in graph: 20

// ============================================================
// CYPHER v12 — Conflict Minerals (3TG) + ESG Scores
// Appended 2026-08-14
//
// New in v12:
//   Conflict minerals: Tin (Sn), Tantalum (Ta), Tungsten (W), Gold (Au)
//   Sources: DRC artisanal miners → Traxys → Umicore refinery
//   ESG score properties added to all major Supplier nodes
//   ITRI/iTSCi chain-of-custody scheme nodes
//   Responsible Minerals Initiative (RMI) certification
//   New event: EVT-EU-3TG-DUE-DILIGENCE-2024
//   New event: EVT-GOLD-LBMA-RESPONSIBLE-SOURCING-2024
//   New RawMaterial nodes: Cassiterite, Columbite-Tantalite, Wolframite, Gold Ore
//   New T4 nodes: artisanal miners (MUMI/Bisie mine, North Kivu DRC)
// ============================================================

// ─── ESG scores on existing Tier 1 suppliers ───────────────
MATCH (s:Supplier {name: "ZF Friedrichshafen"})
SET s.esg_score = 68,
    s.esg_environmental = 64,
    s.esg_social = 71,
    s.esg_governance = 69,
    s.esg_rating = "BBB",
    s.esg_provider = "MSCI",
    s.esg_updated = "2024-01-15";

MATCH (s:Supplier {name: "CATL"})
SET s.esg_score = 42,
    s.esg_environmental = 55,
    s.esg_social = 31,
    s.esg_governance = 40,
    s.esg_rating = "BB",
    s.esg_provider = "MSCI",
    s.esg_updated = "2024-02-01";

MATCH (s:Supplier {name: "TSMC"})
SET s.esg_score = 79,
    s.esg_environmental = 76,
    s.esg_social = 80,
    s.esg_governance = 81,
    s.esg_rating = "AA",
    s.esg_provider = "MSCI",
    s.esg_updated = "2024-01-20";

MATCH (s:Supplier {name: "Bosch"})
SET s.esg_score = 82,
    s.esg_environmental = 80,
    s.esg_social = 84,
    s.esg_governance = 82,
    s.esg_rating = "AA",
    s.esg_provider = "MSCI",
    s.esg_updated = "2024-03-01";

MATCH (s:Supplier {name: "SSAB"})
SET s.esg_score = 74,
    s.esg_environmental = 80,
    s.esg_social = 70,
    s.esg_governance = 72,
    s.esg_rating = "A",
    s.esg_provider = "MSCI",
    s.esg_updated = "2024-02-10";

MATCH (s:Supplier {name: "Norilsk Nickel"})
SET s.esg_score = 12,
    s.esg_environmental = 8,
    s.esg_social = 11,
    s.esg_governance = 17,
    s.esg_rating = "CCC",
    s.esg_provider = "Sustainalytics",
    s.esg_updated = "2023-12-01";

MATCH (s:Supplier {name: "Luminar Technologies"})
SET s.esg_score = 51,
    s.esg_environmental = 60,
    s.esg_social = 50,
    s.esg_governance = 43,
    s.esg_rating = "BBB",
    s.esg_provider = "Sustainalytics",
    s.esg_updated = "2024-01-10";

MATCH (s:Supplier {name: "Leoni AG"})
SET s.esg_score = 38,
    s.esg_environmental = 44,
    s.esg_social = 35,
    s.esg_governance = 35,
    s.esg_rating = "BB",
    s.esg_provider = "MSCI",
    s.esg_updated = "2024-02-20";

MATCH (s:Supplier {name: "JSR Corporation"})
SET s.esg_score = 72,
    s.esg_environmental = 68,
    s.esg_social = 74,
    s.esg_governance = 74,
    s.esg_rating = "A",
    s.esg_provider = "MSCI",
    s.esg_updated = "2024-01-25";

MATCH (s:Supplier {name: "Infineon Technologies"})
SET s.esg_score = 76,
    s.esg_environmental = 74,
    s.esg_social = 77,
    s.esg_governance = 77,
    s.esg_rating = "A",
    s.esg_provider = "MSCI",
    s.esg_updated = "2024-03-05";

MATCH (s:Supplier {name: "Glencore DRC"})
SET s.esg_score = 19,
    s.esg_environmental = 15,
    s.esg_social = 14,
    s.esg_governance = 28,
    s.esg_rating = "CCC",
    s.esg_provider = "Sustainalytics",
    s.esg_updated = "2023-11-01";

MATCH (s:Supplier {name: "SQM Lithium"})
SET s.esg_score = 55,
    s.esg_environmental = 48,
    s.esg_social = 60,
    s.esg_governance = 57,
    s.esg_rating = "BBB",
    s.esg_provider = "MSCI",
    s.esg_updated = "2024-02-15";

// ─── Conflict Mineral Raw Materials (3TG) ──────────────────

MERGE (tin:RawMaterial {
  name: "Cassiterite (Tin Ore)",
  material_type: "Conflict Mineral",
  mineral_symbol: "Sn",
  origin: "DRC",
  conflict_mineral: true,
  eu_3tg_regulated: true,
  itri_scheme: "iTSCi"
});

MERGE (tant:RawMaterial {
  name: "Columbite-Tantalite (Tantalum Ore)",
  material_type: "Conflict Mineral",
  mineral_symbol: "Ta",
  origin: "DRC",
  conflict_mineral: true,
  eu_3tg_regulated: true,
  itri_scheme: "iTSCi"
});

MERGE (wolf:RawMaterial {
  name: "Wolframite (Tungsten Ore)",
  material_type: "Conflict Mineral",
  mineral_symbol: "W",
  origin: "DRC",
  conflict_mineral: true,
  eu_3tg_regulated: true,
  itri_scheme: "iTSCi"
});

MERGE (gold:RawMaterial {
  name: "Gold Ore",
  material_type: "Conflict Mineral",
  mineral_symbol: "Au",
  origin: "DRC",
  conflict_mineral: true,
  eu_3tg_regulated: true,
  lbma_scheme: "LBMA Responsible Sourcing"
});

// ─── T4: Artisanal Miners (DRC) ─────────────────────────────

MERGE (bisie:Supplier {
  name: "Bisie Tin Mine (DRC)",
  country: "DRC",
  tier: 4,
  industry: "Artisanal Mining",
  mine_code: "DRC-BISIE-SN",
  north_kivu: true,
  itri_registered: true,
  flags: ["CHILD_LABOR_RISK", "LKSG_RISK", "GEOPOLITICAL_RISK"],
  esg_score: 8,
  esg_rating: "CCC"
});

MERGE (rubaya:Supplier {
  name: "Rubaya Coltan Cooperative (DRC)",
  country: "DRC",
  tier: 4,
  industry: "Artisanal Mining",
  mine_code: "DRC-RUBAYA-TA",
  north_kivu: true,
  itri_registered: true,
  flags: ["CHILD_LABOR_RISK", "LKSG_RISK", "GEOPOLITICAL_RISK", "FORCE_MAJEURE"],
  esg_score: 6,
  esg_rating: "CCC"
});

MERGE (mumi:Supplier {
  name: "MUMI Mine Cooperative (DRC)",
  country: "DRC",
  tier: 4,
  industry: "Artisanal Mining",
  mine_code: "DRC-MUMI-W",
  south_kivu: true,
  itri_registered: false,
  flags: ["CHILD_LABOR_RISK", "LKSG_RISK", "GEOPOLITICAL_RISK", "SANCTIONS_OFAC"],
  esg_score: 4,
  esg_rating: "CCC"
});

// ─── T3: Traders & Refiners ──────────────────────────────────

MERGE (traxys:Supplier {
  name: "Traxys Group",
  country: "Luxembourg",
  tier: 3,
  industry: "Commodity Trading",
  rmi_compliant: true,
  itri_scheme: "iTSCi registered trader",
  flags: ["LKSG_RISK"],
  esg_score: 44,
  esg_rating: "BB"
});

MERGE (thaisarco:Supplier {
  name: "Thaisarco (Thailand Smelting)",
  country: "Thailand",
  tier: 3,
  industry: "Tin Smelting",
  rmi_listed: true,
  rmi_compliant: true,
  flags: [],
  esg_score: 58,
  esg_rating: "BBB"
});

MERGE (metalor:Supplier {
  name: "Metalor Technologies",
  country: "Switzerland",
  tier: 3,
  industry: "Gold Refining",
  lbma_accredited: true,
  rmi_compliant: true,
  flags: [],
  esg_score: 71,
  esg_rating: "A"
});

// ─── Certification schemes ───────────────────────────────────

MERGE (itsci:Certificate {
  name: "iTSCi Chain of Custody",
  issuer: "ITRI",
  standard: "OECD Due Diligence Guidance",
  scope: "Tin, Tantalum, Tungsten from DRC and Great Lakes",
  valid_until: "2026-12-31"
});

MERGE (rmi_cert:Certificate {
  name: "RMI RMAP Conformant",
  issuer: "Responsible Minerals Initiative",
  standard: "OECD 5-step framework",
  scope: "3TG minerals from conflict-affected areas",
  valid_until: "2025-12-31"
});

MERGE (lbma_cert:Certificate {
  name: "LBMA Responsible Gold",
  issuer: "London Bullion Market Association",
  standard: "LBMA Responsible Sourcing Programme",
  scope: "Gold supply chain due diligence",
  valid_until: "2025-09-30"
});

// ─── Relationships: Artisanal miners → raw materials ─────────

MATCH (s:Supplier {name: "Bisie Tin Mine (DRC)"}),
      (r:RawMaterial {name: "Cassiterite (Tin Ore)"})
MERGE (s)-[:SOURCED_FROM {
  volume_t_year: 8000,
  itri_registered: true,
  conflict_free_verified: false,
  source: "ITRI 2023 data"
}]->(r);

MATCH (s:Supplier {name: "Rubaya Coltan Cooperative (DRC)"}),
      (r:RawMaterial {name: "Columbite-Tantalite (Tantalum Ore)"})
MERGE (s)-[:SOURCED_FROM {
  volume_t_year: 1200,
  itri_registered: true,
  conflict_free_verified: true,
  source: "ITRI 2023 data"
}]->(r);

MATCH (s:Supplier {name: "MUMI Mine Cooperative (DRC)"}),
      (r:RawMaterial {name: "Wolframite (Tungsten Ore)"})
MERGE (s)-[:SOURCED_FROM {
  volume_t_year: 600,
  itri_registered: false,
  conflict_free_verified: false,
  source: "Global Witness field report 2023"
}]->(r);

// ─── Traders collect from miners ──────────────────────────────

MATCH (trader:Supplier {name: "Traxys Group"}),
      (miner:Supplier {name: "Bisie Tin Mine (DRC)"})
MERGE (trader)-[:SOURCED_FROM {
  material: "Cassiterite",
  role: "first-buyer",
  itri_verified: true,
  volume_t_year: 5000
}]->(miner);

MATCH (trader:Supplier {name: "Traxys Group"}),
      (miner:Supplier {name: "Rubaya Coltan Cooperative (DRC)"})
MERGE (trader)-[:SOURCED_FROM {
  material: "Columbite-Tantalite",
  role: "first-buyer",
  itri_verified: true,
  volume_t_year: 800
}]->(miner);

MATCH (trader:Supplier {name: "Traxys Group"}),
      (miner:Supplier {name: "MUMI Mine Cooperative (DRC)"})
MERGE (trader)-[:SOURCED_FROM {
  material: "Wolframite",
  role: "first-buyer",
  itri_verified: false,
  conflict_risk: "HIGH",
  volume_t_year: 400
}]->(miner);

// ─── Smelters source from traders ────────────────────────────

MATCH (smelter:Supplier {name: "Thaisarco (Thailand Smelting)"}),
      (trader:Supplier {name: "Traxys Group"})
MERGE (smelter)-[:SOURCED_FROM {
  material: "Cassiterite lots",
  rmi_verified: true,
  volume_t_year: 4000
}]->(trader);

MATCH (refiner:Supplier {name: "Metalor Technologies"}),
      (r:RawMaterial {name: "Gold Ore"})
MERGE (refiner)-[:SOURCED_FROM {
  lbma_verified: true,
  rmi_verified: true,
  volume_t_year: 12,
  source: "Multiple LBMA-compliant mines"
}]->(r);

// ─── Smelters supply CATL / Infineon (downstream) ─────────────

MATCH (catl:Supplier {name: "CATL"}),
      (smelter:Supplier {name: "Thaisarco (Thailand Smelting)"})
MERGE (catl)-[:SOURCED_FROM {
  material: "refined tin (solder)",
  volume_t_year: 600,
  rmi_verified: true
}]->(smelter);

MATCH (inf:Supplier {name: "Infineon Technologies"}),
      (smelter:Supplier {name: "Thaisarco (Thailand Smelting)"})
MERGE (inf)-[:SOURCED_FROM {
  material: "refined tin (semiconductor packaging)",
  volume_t_year: 200,
  rmi_verified: true
}]->(smelter);

MATCH (bosch:Supplier {name: "Bosch"}),
      (refiner:Supplier {name: "Metalor Technologies"})
MERGE (bosch)-[:SOURCED_FROM {
  material: "gold wire bonding",
  volume_kg_year: 8000,
  lbma_verified: true
}]->(refiner);

// ─── Certifications ───────────────────────────────────────────

MATCH (s:Supplier {name: "Thaisarco (Thailand Smelting)"}),
      (c:Certificate {name: "RMI RMAP Conformant"})
MERGE (s)-[:CERTIFIED_BY {since: "2019-06-01"}]->(c);

MATCH (s:Supplier {name: "Metalor Technologies"}),
      (c:Certificate {name: "LBMA Responsible Gold"})
MERGE (s)-[:CERTIFIED_BY {since: "2016-01-01"}]->(c);

MATCH (s:Supplier {name: "Traxys Group"}),
      (c:Certificate {name: "iTSCi Chain of Custody"})
MERGE (s)-[:CERTIFIED_BY {since: "2015-03-01"}]->(c);

// ─── Events ───────────────────────────────────────────────────

MERGE (evt3tg:Event {
  id: "EVT-EU-3TG-DUE-DILIGENCE-2024",
  name: "EU Conflict Minerals Regulation — Full Enforcement",
  date: "2024-01-01",
  type: "REGULATORY",
  severity: "HIGH",
  description: "EU Regulation 2017/821 on 3TG minerals enters full enforcement for all EU importers above de minimis thresholds. Supply chain due diligence mandatory; non-compliance risks import bans.",
  financial_impact_m: 45,
  regulation: "EU 2017/821",
  affected_minerals: "Tin, Tantalum, Tungsten, Gold"
});

MERGE (evtlbma:Event {
  id: "EVT-GOLD-LBMA-RESPONSIBLE-SOURCING-2024",
  name: "LBMA Responsible Sourcing Programme — Tier 2 Expansion",
  date: "2024-03-01",
  type: "REGULATORY",
  severity: "MEDIUM",
  description: "LBMA expands responsible sourcing requirements to Tier 2 gold refiners. Downstream buyers (auto, electronics) must verify chain-of-custody through to refinery level.",
  financial_impact_m: 18,
  regulation: "LBMA RSP v9",
  affected_minerals: "Gold"
});

MERGE (evtcoltan:Event {
  id: "EVT-DRC-ARMED-GROUP-COLTAN-2024",
  name: "Armed Group Revenue from Rubaya Coltan Mine",
  date: "2024-02-15",
  type: "GEOPOLITICAL",
  severity: "CRITICAL",
  description: "UN Group of Experts reports M23 armed group controlling portions of Rubaya coltan mining area. Risk of conflict financing through tantalum supply chain to consumer electronics and EV batteries.",
  financial_impact_m: 95,
  un_report: "S/2024/432"
});

// ─── :AFFECTED_BY on 3TG miners/traders ──────────────────────

MATCH (s:Supplier {name: "Rubaya Coltan Cooperative (DRC)"}),
      (e:Event {id: "EVT-DRC-ARMED-GROUP-COLTAN-2024"})
MERGE (s)-[:AFFECTED_BY {impact: "CRITICAL", direct: true}]->(e);

MATCH (s:Supplier {name: "Traxys Group"}),
      (e:Event {id: "EVT-DRC-ARMED-GROUP-COLTAN-2024"})
MERGE (s)-[:AFFECTED_BY {impact: "HIGH", direct: false, reason: "sourcing from affected area"}]->(e);

MATCH (s:Supplier {name: "CATL"}),
      (e:Event {id: "EVT-DRC-ARMED-GROUP-COLTAN-2024"})
MERGE (s)-[:AFFECTED_BY {impact: "HIGH", direct: false, reason: "downstream consumer of tantalum"}]->(e);

MATCH (s:Supplier {name: "Thaisarco (Thailand Smelting)"}),
      (e:Event {id: "EVT-EU-3TG-DUE-DILIGENCE-2024"})
MERGE (s)-[:AFFECTED_BY {impact: "HIGH", direct: true}]->(e);

MATCH (s:Supplier {name: "Bosch"}),
      (e:Event {id: "EVT-GOLD-LBMA-RESPONSIBLE-SOURCING-2024"})
MERGE (s)-[:AFFECTED_BY {impact: "MEDIUM", direct: true}]->(e);

MATCH (s:Supplier {name: "Infineon Technologies"}),
      (e:Event {id: "EVT-EU-3TG-DUE-DILIGENCE-2024"})
MERGE (s)-[:AFFECTED_BY {impact: "MEDIUM", direct: true}]->(e);

// ─── FinancialAlert for MUMI (unverified, possible sanctions) ──

MERGE (fa:FinancialAlert {
  supplier: "MUMI Mine Cooperative (DRC)",
  level: "CRITICAL",
  reason: "OFAC_RISK",
  detail: "UN experts report MUMI mine supply chain potentially linked to sanctioned entities via intermediary traders. Recommend immediate due diligence audit and suspension of indirect sourcing.",
  altman_z: null,
  triggered_at: "2024-03-01"
});

// ─── Summary comment ──────────────────────────────────────────
// v12 totals:
//   New RawMaterial nodes: Cassiterite, Columbite-Tantalite, Wolframite, Gold Ore (4)
//   New Supplier nodes: Bisie, Rubaya, MUMI, Traxys, Thaisarco, Metalor (6)
//   New Certificate nodes: iTSCi, RMI RMAP, LBMA Responsible Gold (3)
//   New Event nodes: EU 3TG, LBMA tier-2, DRC Armed Group Coltan (3)
//   ESG scores added to 12 existing Supplier nodes
//   Total events in graph: 23
