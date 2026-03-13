"""T011 validation — delete after use."""
import uuid
from app.clients.storage_client import (
    StorageClient, get_storage_client, _content_type_for,
)
from app.dependencies import StorageDep

print("1. Imports OK")

key = StorageClient.build_storage_key(
    company_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
    doc_type="10-K", fiscal_year=2024, fiscal_quarter=None,
    filename="apple-10k-2024.pdf",
)
assert key == "550e8400-e29b-41d4-a716-446655440000/10-K/2024/apple-10k-2024.pdf"
print(f"2. Annual key: {key}")

key_q = StorageClient.build_storage_key(
    company_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),
    doc_type="10-Q", fiscal_year=2024, fiscal_quarter=3,
    filename="apple-10q-2024q3.pdf",
)
assert "Q3" in key_q
print(f"3. Quarterly key: {key_q}")

assert _content_type_for("report.pdf") == "application/pdf"
assert _content_type_for("filing.html") == "text/html"
assert _content_type_for("data.json") == "application/json"
assert _content_type_for("export.csv") == "text/csv"
assert _content_type_for("unknown.xyz") == "application/octet-stream"
print("4. Content type detection OK")

try:
    get_storage_client()
    print("ERROR: should have raised")
except RuntimeError:
    print("5. Uninitialised guard OK")

print("\nAll T011 validations passed!")
