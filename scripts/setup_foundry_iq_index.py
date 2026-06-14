"""
Foundry IQ Knowledge Base Setup Script
========================================
Creates an Azure AI Search index (Foundry IQ backend) and uploads:
  - 110 historical incidents from data/incident_dataset.csv
  - 8 runbook documents from knowledge_base/runbooks/

Run this ONCE after setting up your Azure AI Search resource and adding
credentials to .env:

    python scripts/setup_foundry_iq_index.py

Requires: azure-search-documents
    pip install azure-search-documents
"""

import os
import sys
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

AZURE_SEARCH_ENDPOINT  = os.getenv("AZURE_SEARCH_ENDPOINT", "")
AZURE_SEARCH_ADMIN_KEY = os.getenv("AZURE_SEARCH_ADMIN_KEY", "")
INDEX_NAME             = os.getenv("AZURE_SEARCH_INDEX_NAME", "noc-incident-knowledge")

DATA_PATH = os.path.join(os.path.dirname(__file__), "../data/incident_dataset.csv")
RUNBOOKS_DIR = os.path.join(os.path.dirname(__file__), "../knowledge_base/runbooks")


def main():
    if not AZURE_SEARCH_ENDPOINT or not AZURE_SEARCH_ADMIN_KEY:
        print("ERROR: AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_ADMIN_KEY must be set in .env")
        print("See .env.example for the full list of required variables.")
        sys.exit(1)

    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        SearchIndex, SimpleField, SearchableField, SearchFieldDataType,
        SemanticConfiguration, SemanticPrioritizedFields, SemanticField,
        SemanticSearch,
    )
    from azure.search.documents import SearchClient

    credential = AzureKeyCredential(AZURE_SEARCH_ADMIN_KEY)
    index_client = SearchIndexClient(endpoint=AZURE_SEARCH_ENDPOINT, credential=credential)

    print(f"Creating index '{INDEX_NAME}'...")

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SimpleField(name="incident_id", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="doc_type", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="category", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="service", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="region", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="severity", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="title", type=SearchFieldDataType.String),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SearchableField(name="root_cause", type=SearchFieldDataType.String),
        SearchableField(name="resolution", type=SearchFieldDataType.String),
        SimpleField(name="resolution_time_min", type=SearchFieldDataType.Int32),
    ]

    semantic_config = SemanticConfiguration(
        name="default",
        prioritized_fields=SemanticPrioritizedFields(
            title_field=SemanticField(field_name="title"),
            content_fields=[
                SemanticField(field_name="content"),
                SemanticField(field_name="root_cause"),
                SemanticField(field_name="resolution"),
            ],
            keywords_fields=[
                SemanticField(field_name="category"),
                SemanticField(field_name="service"),
            ],
        ),
    )

    index = SearchIndex(
        name=INDEX_NAME,
        fields=fields,
        semantic_search=SemanticSearch(configurations=[semantic_config]),
    )

    index_client.create_or_update_index(index)
    print(f"Index '{INDEX_NAME}' created.")

    search_client = SearchClient(
        endpoint=AZURE_SEARCH_ENDPOINT, index_name=INDEX_NAME, credential=credential,
    )

    # ── Upload incidents ────────────────────────────────────────────────────
    print(f"Loading incidents from {DATA_PATH}...")
    df = pd.read_csv(DATA_PATH)

    docs = []
    for _, row in df.iterrows():
        docs.append({
            "id": row["incident_id"],
            "incident_id": row["incident_id"],
            "doc_type": "incident",
            "category": row["category"],
            "service": row["service"],
            "region": row["region"],
            "severity": row["severity"],
            "title": row["title"],
            "content": row["description"],
            "root_cause": row["root_cause"],
            "resolution": row["resolution"],
            "resolution_time_min": int(row["resolution_time_min"]),
        })

    print(f"Uploading {len(docs)} incidents...")
    for i in range(0, len(docs), 50):
        batch = docs[i:i+50]
        result = search_client.upload_documents(documents=batch)
        failed = [r for r in result if not r.succeeded]
        if failed:
            print(f"  WARNING: {len(failed)} documents failed in batch {i//50 + 1}")

    print(f"Uploaded {len(docs)} incidents.")

    # ── Upload runbooks ──────────────────────────────────────────────────────
    print(f"Loading runbooks from {RUNBOOKS_DIR}...")
    runbook_docs = []
    for fname in os.listdir(RUNBOOKS_DIR):
        if not fname.endswith(".md"):
            continue
        runbook_id = fname.replace(".md", "")
        with open(os.path.join(RUNBOOKS_DIR, fname)) as f:
            content = f.read()

        # crude category guess from runbook ID prefix
        category_map = {
            "RB-DB-CONN": "DB Connectivity", "RB-PAY-GW": "Payment Gateway",
            "RB-AUTH-SVC": "Auth Service", "RB-FX-FEED": "FX Feed",
            "RB-SWIFT-MQ": "SWIFT Queue", "RB-BATCH-EOD": "Batch Job",
            "RB-NET-VPC": "Network", "RB-APP-ERR": "Application Error",
        }
        category = next((v for k, v in category_map.items() if runbook_id.startswith(k)), "General")

        runbook_docs.append({
            "id": runbook_id,
            "incident_id": runbook_id,
            "doc_type": "runbook",
            "category": category,
            "service": "",
            "region": "",
            "severity": "",
            "title": f"Runbook {runbook_id}",
            "content": content,
            "root_cause": "",
            "resolution": "",
            "resolution_time_min": 0,
        })

    print(f"Uploading {len(runbook_docs)} runbooks...")
    result = search_client.upload_documents(documents=runbook_docs)
    failed = [r for r in result if not r.succeeded]
    if failed:
        print(f"  WARNING: {len(failed)} runbook documents failed")

    print(f"Uploaded {len(runbook_docs)} runbooks.")
    print()
    print("Foundry IQ knowledge base setup complete.")
    print(f"Index: {INDEX_NAME}")
    print(f"Total documents: {len(docs) + len(runbook_docs)}")
    print()
    print("Your agent will now use this index automatically (foundry_iq_configured() == True).")


if __name__ == "__main__":
    main()
