"""Build/refresh the Azure AI Search index the agent's AzureAISearchTool retrieves over.

GA Floor (Phase 1): the index is PUSHED from the canonical Python mirror
(derivation.py -> mirror.build_search_docs), so it can never disagree with the
Fabric sink or the offline core. Keyless via DefaultAzureCredential (the RG-scoped
SP holds Search Service Contributor + Index Data Contributor).

    python scripts/build_search_index.py --dry-run   # offline: docs + schema only, NO Azure
    python scripts/build_search_index.py             # live: create/update index + upload docs

`--dry-run` still constructs the SearchIndex object, so a schema error fails offline too.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from pathforward.config import load_settings            # noqa: E402
from pathforward.iq import derivation as dv             # noqa: E402
from pathforward.iq import mirror                        # noqa: E402
from pathforward.iq.models import SOURCE_MIRROR          # noqa: E402
from pathforward.iq.seed import build_seed               # noqa: E402

SEMANTIC_CONFIG = "pathforward-semantic"   # named default semantic config (L2 ranking, mandatory)


def build_docs() -> list[dict]:
    onto = build_seed()
    edges = dv.build_all_edges(onto, source_badge=SOURCE_MIRROR)
    docs = mirror.build_search_docs(onto, edges)
    mirror.assert_search_corpus(docs)   # fail loud if the inference / hero grounding didn't materialize
    return docs


def build_index(name: str):
    from azure.search.documents.indexes.models import (
        SearchField, SearchFieldDataType, SearchIndex,
        SemanticConfiguration, SemanticField, SemanticPrioritizedFields, SemanticSearch,
    )
    s = SearchFieldDataType.String

    def field(fname, *, key=False, searchable=False, filterable=False,
              facetable=False, sortable=False):
        return SearchField(name=fname, type=s, key=key, searchable=searchable,
                           filterable=filterable, facetable=facetable, sortable=sortable)

    fields = [
        field("id", key=True, filterable=True, sortable=True),   # search-safe key (ref_id with '::' -> '__')
        field("ref_id", filterable=True),                        # the derivation id the gate matches on
        field("kind", filterable=True, facetable=True),
        field("title", searchable=True),
        field("content", searchable=True),                       # the field the L2 ranker + model read
        field("edge_type", filterable=True, facetable=True),
        field("worker_id", filterable=True, facetable=True),
        field("skill_id", filterable=True, facetable=True),
        field("role_id", filterable=True, facetable=True),
        field("cert_id", filterable=True, facetable=True),
        field("source_badge", filterable=True),
    ]
    semantic = SemanticSearch(
        default_configuration_name=SEMANTIC_CONFIG,
        configurations=[SemanticConfiguration(
            name=SEMANTIC_CONFIG,
            prioritized_fields=SemanticPrioritizedFields(
                title_field=SemanticField(field_name="title"),
                content_fields=[SemanticField(field_name="content")],
                keywords_fields=[SemanticField(field_name="kind")],
            ),
        )],
    )
    return SearchIndex(name=name, fields=fields, semantic_search=semantic)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the PathForward Azure AI Search index.")
    ap.add_argument("--dry-run", action="store_true",
                    help="build docs + schema and write search_docs.json; make NO Azure calls")
    args = ap.parse_args()

    settings = load_settings(os.path.join(_ROOT, ".env"))
    name = (settings.search_index or "").strip()
    endpoint = (settings.search_endpoint or "").strip()
    if not name or name.lower() == "undefined":
        print("FAIL: AZURE_SEARCH_INDEX is blank/undefined in .env")
        return 1

    docs = build_docs()
    index = build_index(name)   # construct the schema now so a schema error surfaces offline too
    print(f"built {len(docs)} docs; kinds={sorted(set(d['kind'] for d in docs))}; "
          f"index '{name}' fields={len(index.fields)} semantic='{SEMANTIC_CONFIG}'")

    out = os.path.join(_ROOT, "data", "generated", "mirror", "search_docs.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(docs, fh, indent=2)
    print(f"wrote {out}")

    if args.dry_run:
        print("DRY RUN: no Azure calls made.")
        return 0

    if not endpoint:
        print("FAIL: AZURE_SEARCH_ENDPOINT is blank in .env (required for a live push)")
        return 1

    from azure.identity import DefaultAzureCredential
    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient

    cred = DefaultAzureCredential()
    SearchIndexClient(endpoint=endpoint, credential=cred).create_or_update_index(index)
    print(f"index '{name}' created/updated on {endpoint}")

    client = SearchClient(endpoint=endpoint, index_name=name, credential=cred)
    uploaded = 0
    batch = 1000
    for i in range(0, len(docs), batch):
        results = client.upload_documents(documents=docs[i:i + batch])
        uploaded += sum(1 for r in results if r.succeeded)
    print(f"uploaded {uploaded}/{len(docs)} docs")
    if uploaded != len(docs):
        print("FAIL: not every doc uploaded")
        return 1
    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
