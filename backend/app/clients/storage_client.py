# filepath: backend/app/clients/storage_client.py
"""
Azure Blob Storage client for file operations.

Supports both real Azure Blob Storage and Azurite (local emulator).
All methods are async. The client is initialised once at app startup
and shared across requests via FastAPI dependency injection.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from azure.storage.blob import (
    BlobSasPermissions,
    ContentSettings,
    generate_blob_sas,
)
from azure.storage.blob.aio import BlobServiceClient, ContainerClient

if TYPE_CHECKING:
    import uuid

    from app.config import Settings

# Content-type mapping for uploaded filings
_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".html": "text/html",
    ".htm": "text/html",
    ".json": "application/json",
    ".csv": "text/csv",
    ".txt": "text/plain",
}


def _content_type_for(filename: str) -> str:
    """Resolve content type from file extension."""
    ext = filename.rsplit(".", maxsplit=1)[-1].lower() if "." in filename else ""
    return _CONTENT_TYPES.get(f".{ext}", "application/octet-stream")


class StorageClient:
    """Async wrapper around Azure Blob Storage SDK."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._connection_string = settings.azure_storage_connection_string
        self._account_name = settings.azure_storage_account_name
        self._container_filings = settings.azure_storage_container_filings
        self._container_exports = settings.azure_storage_container_exports
        self._service_client: BlobServiceClient | None = None

    # ── Lifecycle ────────────────────────────────────────────────

    async def init(self) -> None:
        """Create the service client and ensure containers exist."""
        if self._connection_string:
            self._service_client = BlobServiceClient.from_connection_string(
                self._connection_string,
            )
        else:
            # Fall back to account name + default credential (managed identity)
            account_url = f"https://{self._account_name}.blob.core.windows.net"
            from azure.identity.aio import DefaultAzureCredential

            credential = DefaultAzureCredential()
            self._service_client = BlobServiceClient(
                account_url, credential=credential,
            )

        # Ensure required containers exist
        for container_name in (self._container_filings, self._container_exports):
            container_client = self._service_client.get_container_client(container_name)
            try:
                await container_client.get_container_properties()
            except Exception:
                await container_client.create_container()

    async def close(self) -> None:
        """Close the underlying HTTP connections."""
        if self._service_client is not None:
            await self._service_client.close()
            self._service_client = None

    @property
    def client(self) -> BlobServiceClient:
        """Return the service client, raising if not initialised."""
        if self._service_client is None:
            raise RuntimeError("StorageClient not initialised — call init() first")
        return self._service_client

    # ── Container helpers ────────────────────────────────────────

    def _get_container(self, container: str | None = None) -> ContainerClient:
        """Get a container client. Defaults to the filings container."""
        name = container or self._container_filings
        return self.client.get_container_client(name)

    # ── Key generation ───────────────────────────────────────────

    @staticmethod
    def build_storage_key(
        company_id: uuid.UUID,
        doc_type: str,
        fiscal_year: int,
        fiscal_quarter: int | None,
        filename: str,
    ) -> str:
        """
        Build a hierarchical blob key for a filing document.

        Format: {company_id}/{doc_type}/{fiscal_year}/[Q{quarter}/]{filename}
        Example: 550e8400-.../10-K/2024/apple-10k-2024.pdf
        """
        parts = [str(company_id), doc_type, str(fiscal_year)]
        if fiscal_quarter is not None:
            parts.append(f"Q{fiscal_quarter}")
        parts.append(filename)
        return "/".join(parts)

    # ── Upload ───────────────────────────────────────────────────

    async def upload_blob(
        self,
        key: str,
        data: bytes,
        content_type: str | None = None,
        container: str | None = None,
        metadata: dict | None = None,
        overwrite: bool = False,
    ) -> str:
        """
        Upload bytes to a blob.

        Args:
            key: The blob name / path within the container.
            data: Raw file bytes.
            content_type: MIME type. Auto-detected from key if omitted.
            container: Target container name. Defaults to filings container.
            metadata: Optional blob metadata dict.
            overwrite: Whether to overwrite an existing blob.

        Returns:
            The blob key (same as input key).
        """
        container_client = self._get_container(container)
        blob_client = container_client.get_blob_client(key)

        resolved_ct = content_type or _content_type_for(key)
        content_settings = ContentSettings(content_type=resolved_ct)

        await blob_client.upload_blob(
            data,
            overwrite=overwrite,
            content_settings=content_settings,
            metadata=metadata,
        )
        return key

    async def upload_file(
        self,
        key: str,
        file_path: str,
        content_type: str | None = None,
        container: str | None = None,
        overwrite: bool = False,
    ) -> str:
        """Upload a local file to a blob."""
        with open(file_path, "rb") as f:
            data = f.read()
        return await self.upload_blob(
            key=key, data=data, content_type=content_type,
            container=container, overwrite=overwrite,
        )

    # ── Download ─────────────────────────────────────────────────

    async def download_blob(
        self,
        key: str,
        container: str | None = None,
    ) -> bytes:
        """Download a blob's contents as bytes."""
        container_client = self._get_container(container)
        blob_client = container_client.get_blob_client(key)
        stream = await blob_client.download_blob()
        return await stream.readall()

    # ── Delete ───────────────────────────────────────────────────

    async def delete_blob(
        self,
        key: str,
        container: str | None = None,
    ) -> None:
        """Delete a blob. No error if it doesn't exist."""
        container_client = self._get_container(container)
        blob_client = container_client.get_blob_client(key)
        await blob_client.delete_blob(delete_snapshots="include")

    async def delete_prefix(
        self,
        prefix: str,
        container: str | None = None,
    ) -> int:
        """
        Delete all blobs under a prefix (e.g. company cleanup).

        Returns the number of blobs deleted.
        """
        container_client = self._get_container(container)
        count = 0
        async for blob in container_client.list_blobs(name_starts_with=prefix):
            await container_client.delete_blob(blob.name, delete_snapshots="include")
            count += 1
        return count

    # ── List ─────────────────────────────────────────────────────

    async def list_blobs(
        self,
        prefix: str | None = None,
        container: str | None = None,
        max_results: int | None = None,
    ) -> list[dict]:
        """
        List blobs under an optional prefix.

        Returns a list of dicts with keys: name, size, content_type, last_modified.
        """
        container_client = self._get_container(container)
        results: list[dict] = []
        async for blob in container_client.list_blobs(name_starts_with=prefix):
            results.append({
                "name": blob.name,
                "size": blob.size,
                "content_type": blob.content_settings.content_type if blob.content_settings else None,
                "last_modified": blob.last_modified,
            })
            if max_results and len(results) >= max_results:
                break
        return results

    # ── Blob existence ───────────────────────────────────────────

    async def blob_exists(
        self,
        key: str,
        container: str | None = None,
    ) -> bool:
        """Check whether a blob exists."""
        container_client = self._get_container(container)
        blob_client = container_client.get_blob_client(key)
        return await blob_client.exists()

    # ── SAS URL generation ───────────────────────────────────────

    def generate_sas_url(
        self,
        key: str,
        container: str | None = None,
        expiry_minutes: int = 60,
        permissions: str = "r",
    ) -> str:
        """
        Generate a time-limited SAS URL for direct blob access.

        Only works when using connection string auth (not managed identity).
        For managed identity, use user-delegation SAS instead.
        """
        container_name = container or self._container_filings

        # Extract account key from connection string for SAS generation
        account_key: str | None = None
        if self._connection_string:
            for part in self._connection_string.split(";"):
                if part.startswith("AccountKey="):
                    account_key = part[len("AccountKey="):]
                    break

        if not account_key:
            raise ValueError(
                "Cannot generate SAS URL without an account key. "
                "Use user-delegation SAS for managed identity deployments."
            )

        sas_token = generate_blob_sas(
            account_name=self._account_name,
            container_name=container_name,
            blob_name=key,
            account_key=account_key,
            permission=BlobSasPermissions(read="r" in permissions),
            expiry=datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes),
        )

        # Build the full URL — handle Azurite vs real Azure
        if "127.0.0.1" in self._connection_string or "localhost" in self._connection_string:
            # Azurite uses path-based URLs
            base_url = f"http://127.0.0.1:10000/{self._account_name}"
        else:
            base_url = f"https://{self._account_name}.blob.core.windows.net"

        return f"{base_url}/{container_name}/{key}?{sas_token}"

    # ── Health check ─────────────────────────────────────────────

    async def health_check(self) -> bool:
        """Return True if the blob service is reachable."""
        try:
            # List containers (limit 1) to verify connectivity
            async for _ in self.client.list_containers(results_per_page=1):
                break
            return True
        except Exception:
            return False


# ── Module-level singleton ───────────────────────────────────────

_storage_client: StorageClient | None = None


def get_storage_client() -> StorageClient:
    """Return the module-level StorageClient singleton."""
    if _storage_client is None:
        raise RuntimeError(
            "StorageClient not initialised — call init_storage_client() at startup"
        )
    return _storage_client


async def init_storage_client(settings: Settings) -> StorageClient:
    """Create and initialise the global StorageClient."""
    global _storage_client
    client = StorageClient(settings)
    await client.init()
    _storage_client = client
    return client


async def close_storage_client() -> None:
    """Shut down the global StorageClient."""
    global _storage_client
    if _storage_client is not None:
        await _storage_client.close()
        _storage_client = None
