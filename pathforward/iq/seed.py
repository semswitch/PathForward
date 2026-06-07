"""Synthetic ontology seed — NO real people, NO PII.

Identifiers are obviously fabricated (EMP-001, S01, R-CLOUD, AZ-204). EMP-001..006
are hand-crafted hero cases with clear, demoable reskilling gaps; the remainder are
generated deterministically (seeded RNG) so the dataset is reproducible run to run.

Cert codes (AZ-204 etc.) are public Microsoft certification identifiers used as
synthetic labels — they are not personal or customer data.
"""
from __future__ import annotations

import random

from .models import Certification, Ontology, Role, Skill, Worker

# ---- skills (30) ------------------------------------------------------------
_SKILLS = [
    ("S01", "API Development", "cloud"), ("S02", "Azure Functions", "cloud"),
    ("S03", "Blob Storage", "cloud"), ("S04", "Cosmos DB", "cloud"),
    ("S05", "App Service", "cloud"), ("S06", "CI/CD Pipelines", "devops"),
    ("S07", "GitHub Actions", "devops"), ("S08", "Infrastructure as Code", "devops"),
    ("S09", "Containers", "devops"), ("S10", "Kubernetes", "devops"),
    ("S11", "Monitoring", "devops"), ("S12", "Networking", "infra"),
    ("S13", "Identity & Access", "security"), ("S14", "Key Vault", "security"),
    ("S15", "SQL", "data"), ("S16", "Data Pipelines", "data"),
    ("S17", "Spark", "data"), ("S18", "Data Lake", "data"),
    ("S19", "Stream Processing", "data"), ("S20", "ETL", "data"),
    ("S21", "Machine Learning", "ai"), ("S22", "Prompt Engineering", "ai"),
    ("S23", "Model Deployment", "ai"), ("S24", "Responsible AI", "ai"),
    ("S25", "Vector Search", "ai"), ("S26", "Threat Detection", "security"),
    ("S27", "SIEM", "security"), ("S28", "Incident Response", "security"),
    ("S29", "Cost Management", "architecture"), ("S30", "Solution Design", "architecture"),
]

# ---- certifications (8) -----------------------------------------------------
_CERTS = [
    ("AZ-204", "Developing Solutions for Azure", ("S01", "S02", "S03", "S04", "S05"), 20),
    ("AZ-400", "DevOps Engineer Expert", ("S06", "S07", "S08", "S11"), 25),
    ("DP-203", "Data Engineering on Azure", ("S15", "S16", "S17", "S18", "S19", "S20"), 22),
    ("AZ-305", "Azure Solutions Architect", ("S08", "S12", "S13", "S29", "S30"), 30),
    ("AI-102", "Azure AI Engineer", ("S21", "S22", "S23", "S24", "S25"), 24),
    ("SC-200", "Security Operations Analyst", ("S26", "S27", "S28", "S13"), 20),
    ("AZ-104", "Azure Administrator", ("S05", "S11", "S12", "S13", "S14"), 22),
    ("PL-300", "Power BI Data Analyst", ("S15", "S16", "S20"), 18),
]

# ---- target roles (6) -------------------------------------------------------
_ROLES = [
    ("R-CLOUD", "Cloud Engineer", ("S01", "S02", "S03", "S05", "S08", "S12")),
    ("R-DEVOPS", "DevOps Engineer", ("S06", "S07", "S08", "S09", "S11")),
    ("R-DATA", "Data Engineer", ("S15", "S16", "S17", "S18", "S20")),
    ("R-AI", "AI Engineer", ("S21", "S22", "S23", "S24", "S25")),
    ("R-SEC", "Security Analyst", ("S13", "S26", "S27", "S28")),
    ("R-ARCH", "Solutions Architect", ("S08", "S12", "S13", "S29", "S30")),
]

# at-risk current roles (free-text narrative; being automated/displaced)
_AT_RISK_TITLES = [
    "Data Center Technician (role at risk of automation)",
    "Manual QA Tester (role being automated)",
    "On-prem Sysadmin (workload migrating to cloud)",
    "Report Builder / Spreadsheet Analyst (automation risk)",
    "NOC Operator (tooling consolidation)",
    "Help Desk Technician (AI deflection risk)",
]

# Hand-crafted hero workers: (id, name, current_title, target_role, has_skills, capacity, a11y)
_HERO_WORKERS = [
    ("EMP-001", "Worker EMP-001", _AT_RISK_TITLES[0], "R-CLOUD",
     ("S05", "S12", "S03"), 4.0, ("low-vision", "prefers-audio", "screen-reader")),
    ("EMP-002", "Worker EMP-002", _AT_RISK_TITLES[1], "R-DEVOPS",
     ("S06", "S11"), 6.0, ("dyslexia",)),
    ("EMP-003", "Worker EMP-003", _AT_RISK_TITLES[2], "R-CLOUD",
     ("S05", "S12", "S01", "S03"), 8.0, ()),
    ("EMP-004", "Worker EMP-004", _AT_RISK_TITLES[3], "R-DATA",
     ("S15", "S20"), 5.0, ("ADHD-focus-windows",)),
    ("EMP-005", "Worker EMP-005", _AT_RISK_TITLES[4], "R-SEC",
     ("S13", "S26"), 3.0, ("hard-of-hearing", "captions-required")),
    ("EMP-006", "Worker EMP-006", _AT_RISK_TITLES[5], "R-AI",
     ("S22",), 7.0, ()),
]


def build_seed(n_workers: int = 45) -> Ontology:
    """Deterministic synthetic ontology. EMP-001..006 are hero cases."""
    onto = Ontology()
    for sid, name, domain in _SKILLS:
        onto.skills[sid] = Skill(sid, name, domain)
    for cid, name, skills, hours in _CERTS:
        onto.certifications[cid] = Certification(cid, name, skills, hours)
    for rid, name, req in _ROLES:
        onto.roles[rid] = Role(rid, name, req)

    for wid, name, title, target, has, cap, a11y in _HERO_WORKERS:
        onto.workers[wid] = Worker(wid, name, title, target, has, cap, a11y)

    rng = random.Random(42)  # fixed seed -> reproducible
    role_ids = [r[0] for r in _ROLES]
    skill_ids = [s[0] for s in _SKILLS]
    a11y_pool = ["low-vision", "dyslexia", "ADHD-focus-windows", "captions-required",
                 "screen-reader", "prefers-audio", "color-blind"]
    start = len(_HERO_WORKERS) + 1
    for i in range(start, n_workers + 1):
        wid = f"EMP-{i:03d}"
        target = rng.choice(role_ids)
        required = next(r[2] for r in _ROLES if r[0] == target)
        # have a partial, adjacent skill set: a subset of required + some neighbours
        k = rng.randint(1, max(1, len(required) - 1))
        have = set(rng.sample(list(required), k))
        # add 0-2 adjacent skills outside the requirement to look realistic
        for _ in range(rng.randint(0, 2)):
            have.add(rng.choice(skill_ids))
        a11y: tuple[str, ...] = ()
        if rng.random() < 0.35:
            a11y = tuple(rng.sample(a11y_pool, rng.randint(1, 2)))
        onto.workers[wid] = Worker(
            wid, f"Worker {wid}", rng.choice(_AT_RISK_TITLES), target,
            tuple(sorted(have)), float(rng.randint(2, 10)), a11y,
        )
    return onto


# convenience constants for tests / demo
HERO_WORKER_ID = "EMP-001"
HERO_TARGET_ROLE_ID = "R-CLOUD"
HERO_EXPECTED_GAP = ["S01", "S02", "S08"]   # CertGap(EMP-001, Cloud Engineer)
HERO_EXPECTED_READINESS = 0.5               # 3 of 6 required skills covered
