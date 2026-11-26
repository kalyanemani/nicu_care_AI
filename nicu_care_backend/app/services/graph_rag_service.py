"""
Graph RAG Service:
Neonatal Clinical Entity-Relation Graph with Multi-Hop Safety Traversal
and pluggable Neo4j AuraDB / Bolt driver integration.
"""
import os
import re
from typing import Dict, List, Any, Optional, Tuple, Set


class ClinicalKnowledgeGraph:
    """
    In-memory property graph modeling neonatal clinical relationships,
    guideline dependencies, and hard contraindications.
    Zero-external dependency fallback for permanent Free Tier deployment.
    """

    def __init__(self):
        # Nodes: id -> {type, label, attributes}
        self.nodes: Dict[str, Dict[str, Any]] = {}
        # Adjacency list: source_id -> list of (relation, target_id, properties)
        self.edges: Dict[str, List[Tuple[str, str, Dict[str, Any]]]] = {}
        self._seed_neonatal_ontology()

    def add_node(self, node_id: str, node_type: str, label: str, attributes: Optional[Dict[str, Any]] = None):
        self.nodes[node_id] = {
            "type": node_type,
            "label": label,
            "attributes": attributes or {},
        }
        if node_id not in self.edges:
            self.edges[node_id] = []

    def add_edge(self, source_id: str, relation: str, target_id: str, properties: Optional[Dict[str, Any]] = None):
        if source_id not in self.nodes:
            self.add_node(source_id, "CONCEPT", source_id)
        if target_id not in self.nodes:
            self.add_node(target_id, "CONCEPT", target_id)
        if source_id not in self.edges:
            self.edges[source_id] = []
        self.edges[source_id].append((relation, target_id, properties or {}))

    def _seed_neonatal_ontology(self):
        """Populates authoritative AAP/WHO/NICU clinical knowledge graph."""
        # 1. Red Flag Danger Symptoms
        self.add_node("symptom_green_vomit", "SYMPTOM", "Bilious Green Vomit", {"severity": "CRITICAL"})
        self.add_node("symptom_cyanosis", "SYMPTOM", "Central Dusky Cyanosis", {"severity": "CRITICAL"})
        self.add_node("symptom_retractions", "SYMPTOM", "Subcostal Chest Retractions", {"severity": "CRITICAL"})
        self.add_node("symptom_fever", "SYMPTOM", "Rectal Temperature >= 38.0 C", {"severity": "CRITICAL"})
        self.add_node("symptom_apnea", "SYMPTOM", "Apnea > 20 Seconds", {"severity": "CRITICAL"})

        # 2. Diagnoses & Emergencies
        self.add_node("condition_bowel_obstruction", "DIAGNOSIS", "Neonatal Bowel Obstruction / Malrotation")
        self.add_node("condition_respiratory_distress", "DIAGNOSIS", "Acute Neonatal Respiratory Distress")
        self.add_node("condition_neonatal_sepsis", "DIAGNOSIS", "Neonatal Sepsis / Severe Infection")

        # 3. Clinical Interventions & Regimens
        self.add_node("regimen_fluid_target", "REGIMEN", "AAP Preterm Fluid Protocol (150-180 mL/kg/day)")
        self.add_node("regimen_fortified_milk", "REGIMEN", "Human Milk Fortifier / 24 kcal/oz Formula")
        self.add_node("regimen_iron_drops", "REGIMEN", "Elemental Iron 2-4 mg/kg/day")
        self.add_node("regimen_vitamin_d3", "REGIMEN", "Vitamin D3 400 IU Daily")
        self.add_node("regimen_kmc", "REGIMEN", "WHO Kangaroo Mother Care Skin-to-Skin")
        self.add_node("regimen_safe_sleep", "REGIMEN", "AAP Back to Sleep on Firm Flat Surface")

        # 4. Strict Contraindications (Hard Safety Gates)
        self.add_node("contra_oral_feeds_if_green_vomit", "CONTRAINDICATION", "Do NOT give oral milk/formula during green vomit")
        self.add_node("contra_water_for_newborn", "CONTRAINDICATION", "Water is strictly contraindicated for infants under 6 months")
        self.add_node("contra_honey", "CONTRAINDICATION", "Honey is strictly contraindicated under 12 months (Infant Botulism)")
        self.add_node("contra_adult_bed_sharing", "CONTRAINDICATION", "Bed sharing / co-sleeping on sofa/adult bed is contraindicated")

        # 5. Escalation Facilities
        self.add_node("facility_rainbow_vijayawada", "FACILITY", "BirthRight by Rainbow Hospital Vijayawada", {
            "emergency_phone": "+91 866 666 9000",
            "nicu_helpline": "+91 866 669 0000",
            "ambulance": "0866-2459999",
        })
        self.add_node("facility_national_108", "FACILITY", "National Ambulance Dispatch (108)", {"phone": "108"})

        # Relationships (Edges)
        # Green Vomit -> Bowel Obstruction -> Contraindicates Oral Feeds -> Escalates to Surgery / 108
        self.add_edge("symptom_green_vomit", "INDICATES", "condition_bowel_obstruction")
        self.add_edge("condition_bowel_obstruction", "ENFORCES_CONTRAINDICATION", "contra_oral_feeds_if_green_vomit")
        self.add_edge("condition_bowel_obstruction", "ESCALATES_TO", "facility_rainbow_vijayawada")
        self.add_edge("condition_bowel_obstruction", "ESCALATES_TO", "facility_national_108")

        # Respiratory Distress
        self.add_edge("symptom_cyanosis", "INDICATES", "condition_respiratory_distress")
        self.add_edge("symptom_retractions", "INDICATES", "condition_respiratory_distress")
        self.add_edge("symptom_apnea", "INDICATES", "condition_respiratory_distress")
        self.add_edge("condition_respiratory_distress", "ESCALATES_TO", "facility_rainbow_vijayawada")
        self.add_edge("condition_respiratory_distress", "ESCALATES_TO", "facility_national_108")

        # Sepsis
        self.add_edge("symptom_fever", "INDICATES", "condition_neonatal_sepsis")
        self.add_edge("condition_neonatal_sepsis", "ESCALATES_TO", "facility_rainbow_vijayawada")

        # Care Regimen Connections
        self.add_edge("regimen_fortified_milk", "ASSOCIATED_WITH", "regimen_fluid_target")
        self.add_edge("regimen_safe_sleep", "PREVENTS", "contra_adult_bed_sharing")

    def traverse_safety_path(self, query: str) -> Dict[str, Any]:
        """
        Multi-hop traversal to discover clinical relationships and contraindications.
        """
        q_lower = query.lower()
        active_symptoms = []
        active_contraindications = []
        escalation_targets = []
        multi_hop_paths = []

        # 1. Match symptoms
        if any(w in q_lower for w in ["green vomit", "green liquid", "bilious", "threw up green"]):
            active_symptoms.append("symptom_green_vomit")
        if any(w in q_lower for w in ["blue", "cyanosis", "dusky"]):
            active_symptoms.append("symptom_cyanosis")
        if any(w in q_lower for w in ["retraction", "retracting", "chest pulling"]):
            active_symptoms.append("symptom_retractions")
        if any(w in q_lower for w in ["fever", "38.", "39.", "hot to touch"]):
            active_symptoms.append("symptom_fever")
        if any(w in q_lower for w in ["water", "honey", "adult bed", "tummy sleep", "co-sleep"]):
            if "water" in q_lower:
                active_contraindications.append(self.nodes["contra_water_for_newborn"]["label"])
            if "honey" in q_lower:
                active_contraindications.append(self.nodes["contra_honey"]["label"])
            if "adult bed" in q_lower or "co-sleep" in q_lower:
                active_contraindications.append(self.nodes["contra_adult_bed_sharing"]["label"])

        # 2. Multi-hop traversal from active symptoms
        for sym_id in active_symptoms:
            sym_label = self.nodes[sym_id]["label"]
            for rel, target_id, _ in self.edges.get(sym_id, []):
                target_label = self.nodes[target_id]["label"]
                hop1_path = f"({sym_label}) -[{rel}]-> ({target_label})"

                # 2nd hop: Diagnosis -> Contraindications and Escalations
                for rel2, target2_id, _ in self.edges.get(target_id, []):
                    target2_node = self.nodes[target2_id]
                    target2_label = target2_node["label"]
                    full_path = f"{hop1_path} -[{rel2}]-> ({target2_label})"
                    multi_hop_paths.append(full_path)

                    if target2_node["type"] == "CONTRAINDICATION":
                        active_contraindications.append(target2_label)
                    elif target2_node["type"] == "FACILITY":
                        escalation_targets.append({
                            "facility": target2_label,
                            "attributes": target2_node["attributes"]
                        })

        has_critical_block = len(active_symptoms) > 0

        return {
            "has_graph_escalation": has_critical_block,
            "active_symptoms": [self.nodes[s]["label"] for s in active_symptoms],
            "contraindications": list(set(active_contraindications)),
            "multi_hop_paths": multi_hop_paths,
            "escalation_targets": escalation_targets,
        }


class GraphRAGService:
    """
    Facade providing Graph-Enhanced Retrieval-Augmented Generation.
    Connects to Neo4j AuraDB if available, otherwise executes local in-memory ClinicalKnowledgeGraph.
    """

    def __init__(self):
        self.local_graph = ClinicalKnowledgeGraph()
        self.neo4j_uri = os.getenv("NEO4J_URI", "neo4j+ssc://b3ba6fd2.databases.neo4j.io")
        self.neo4j_user = os.getenv("NEO4J_USER", "b3ba6fd2")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "3nmgQQezZSICxVBT1oM_hoJ-2iVEY28MZoAxFqbx9cs")
        self.driver = None
        self.ensure_connected()

    def ensure_connected(self) -> bool:
        """Lazily connects or reconnects to Neo4j Aura Cloud."""
        if self.driver:
            return True
        if self.neo4j_uri and self.neo4j_password:
            try:
                from neo4j import GraphDatabase
                self.driver = GraphDatabase.driver(
                    self.neo4j_uri,
                    auth=(self.neo4j_user, self.neo4j_password),
                    max_connection_lifetime=300
                )
                self.driver.verify_connectivity()
                print(f"[GraphRAG] Connected to Neo4j Aura at {self.neo4j_uri}")
                return True
            except Exception as e:
                print(f"[GraphRAG] Neo4j Aura connection notice ({e}), using embedded clinical graph.")
                self.driver = None
                return False
        return False

    def get_connection_status(self) -> Dict[str, Any]:
        """Returns health and status of the Neo4j Aura property graph."""
        is_live = self.ensure_connected()
        if is_live and self.driver:
            try:
                with self.driver.session() as session:
                    res = session.run("MATCH (n) RETURN count(n) AS node_count")
                    count = res.single()["node_count"]
                    return {
                        "status": "CONNECTED",
                        "provider": "Neo4j AuraDB (Cloud Instance b3ba6fd2)",
                        "uri": self.neo4j_uri,
                        "total_nodes": count,
                        "embedded_fallback_available": True
                    }
            except Exception as e:
                pass

        return {
            "status": "EMBEDDED_ACTIVE",
            "provider": "Local Clinical In-Memory Property Graph",
            "uri": self.neo4j_uri,
            "total_nodes": len(self.local_graph.nodes),
            "embedded_fallback_available": True
        }

    def query_graph_context(self, query: str) -> Dict[str, Any]:
        """Queries the clinical property graph for multi-hop safety relations."""
        self.ensure_connected()
        if self.driver:
            try:
                q_lower = query.lower()
                with self.driver.session() as session:
                    cypher = """
                    MATCH (s:Symptom)
                    WHERE toLower($query) CONTAINS toLower(s.name)
                       OR ($query CONTAINS 'green' AND s.name CONTAINS 'Green')
                       OR ($query CONTAINS 'blue' AND s.name CONTAINS 'Cyanosis')
                       OR ($query CONTAINS 'retraction' AND s.name CONTAINS 'Retractions')
                       OR ($query CONTAINS 'fever' AND s.name CONTAINS 'Fever')
                    MATCH (s)-[:INDICATES]->(d:Diagnosis)
                    OPTIONAL MATCH (d)-[:ENFORCES_CONTRAINDICATION]->(c:Contraindication)
                    OPTIONAL MATCH (d)-[:ESCALATES_TO]->(f:Facility)
                    RETURN s.name AS symptom, d.name AS diagnosis,
                           [x IN collect(DISTINCT c.name) WHERE x IS NOT NULL] AS contraindications,
                           [fac IN collect(DISTINCT {name: f.name, phone: coalesce(f.phone, f.nicu_helpline)}) WHERE fac.name IS NOT NULL] AS facilities
                    """
                    result = session.run(cypher, parameters={"query": q_lower})
                    records = [r.data() for r in result]
                    if records:
                        all_contras = []
                        all_symptoms = []
                        multi_hops = []
                        escalations = []
                        for rec in records:
                            sym = rec["symptom"]
                            diag = rec["diagnosis"]
                            all_symptoms.append(sym)
                            all_contras.extend(rec["contraindications"])
                            for c in rec["contraindications"]:
                                multi_hops.append(f"({sym}) -[INDICATES]-> ({diag}) -[ENFORCES_CONTRAINDICATION]-> ({c})")
                            for fac in rec["facilities"]:
                                escalations.append({"facility": fac["name"], "phone": fac.get("phone")})
                                multi_hops.append(f"({sym}) -[INDICATES]-> ({diag}) -[ESCALATES_TO]-> ({fac['name']})")

                        return {
                            "has_graph_escalation": True,
                            "active_symptoms": list(set(all_symptoms)),
                            "contraindications": list(set(all_contras)),
                            "multi_hop_paths": multi_hops,
                            "escalation_targets": escalations,
                            "source": "Neo4j AuraDB (Cloud Instance b3ba6fd2)",
                        }
            except Exception as e:
                print(f"[GraphRAG] Live Neo4j query failed ({e}), using embedded graph fallback.")

        # Fast, 100% reliable local embedded property graph
        return self.local_graph.traverse_safety_path(query)


# Global Singleton Graph RAG Service
graph_rag_service = GraphRAGService()
