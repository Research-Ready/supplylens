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
