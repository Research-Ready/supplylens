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
// VERIFICATION (extended v4)
// MATCH (n) WHERE n.demo = true RETURN labels(n)[0] AS type, count(n) AS count ORDER BY count DESC;
// Expected: Supplier ~30+, RawMaterial ~17, Certificate ~9, Company ~6, Product ~5, Event ~4
//
// Check financial data loaded:
// MATCH (p)-[r:SUPPLIED_BY]->(s) WHERE r.contract_value_eur IS NOT NULL
// RETURN p.name, s.name, r.contract_value_eur ORDER BY r.contract_value_eur DESC;
//
// Top contract: ZF Friedrichshafen €1.2B — single source, T1
// ============================================================
