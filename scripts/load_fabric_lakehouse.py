"""Load the exported Fabric tables into the PathForward Lakehouse as managed
Delta tables, via OneLake, authenticated as the service principal.

Prereqs: the Fabric workspace + lakehouse exist, the SP is a workspace Admin,
and FABRIC_WORKSPACE_ID + FABRIC_LAKEHOUSE_ID are set in .env. Source CSVs come
from scripts/export_fabric_tables.py (data/generated/fabric/).

    python scripts/load_fabric_lakehouse.py

Verified method: OneLake accepts ONLY Storage-audience tokens, so we fetch an SP
token for https://storage.azure.com/.default via DefaultAzureCredential and hand
it to delta-rs. The GUID ABFSS path takes NO `.Lakehouse` suffix; once written,
Fabric auto-discovers the folders under the lakehouse 'Tables' section.
"""
from __future__ import annotations

import glob
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from pathforward.config import _load_dotenv  # noqa: E402

ONELAKE_HOST = "onelake.dfs.fabric.microsoft.com"
STORAGE_SCOPE = "https://storage.azure.com/.default"  # OneLake requires the Storage audience


def main() -> int:
    _load_dotenv(os.path.join(_ROOT, ".env"))
    ws = os.environ.get("FABRIC_WORKSPACE_ID", "").strip()
    lh = os.environ.get("FABRIC_LAKEHOUSE_ID", "").strip()
    if not ws or not lh:
        print("FAIL: set FABRIC_WORKSPACE_ID and FABRIC_LAKEHOUSE_ID in .env")
        return 1

    import pyarrow.csv as pacsv
    from azure.identity import DefaultAzureCredential
    from deltalake import write_deltalake

    token = DefaultAzureCredential().get_token(STORAGE_SCOPE).token
    storage_options = {"bearer_token": token, "use_fabric_endpoint": "true"}

    src = os.path.join(_ROOT, "data", "generated", "fabric")
    files = sorted(glob.glob(os.path.join(src, "*.csv")))
    if not files:
        print(f"FAIL: no CSVs in {src} (run scripts/export_fabric_tables.py first)")
        return 1

    print(f"loading {len(files)} tables into lakehouse {lh} ...")
    for path in files:
        name = os.path.splitext(os.path.basename(path))[0].strip().lower().replace("-", "_")
        tbl = pacsv.read_csv(path)
        uri = f"abfss://{ws}@{ONELAKE_HOST}/{lh}/Tables/{name}"
        write_deltalake(uri, tbl, mode="overwrite", storage_options=storage_options)
        print(f"  {name:24} {tbl.num_rows:>4} rows -> Tables/{name}")
    print("done -- open PathForwardLH in Fabric; tables appear under 'Tables'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
