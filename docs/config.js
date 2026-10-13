// SupplyLens — runtime config
// Local dev: edit this file directly.
// Server/Docker: this file is auto-generated at container startup from
//   docker/config.js.template via envsubst (see docker/docker-compose.yml uc4-viz service).
// Never commit real credentials to the public branch — use changeme there.

window.UC4_CONFIG = {
  NEO4J_HOST: "http://localhost:7474",
  NEO4J_USER: "neo4j",
  NEO4J_PASS: "bmtKQuCO9vOzyBwyVvt2LrFU",  // local Docker stack
  NEO4J_DB:   "neo4j",
  APP_ENV:    "local"   // "local" | "server" — shown as badge in UI
};
