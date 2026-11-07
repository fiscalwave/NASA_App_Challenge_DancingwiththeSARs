"""
Download manager for NASA Earthdata / ASF-hosted NISAR GCOV granules.

Implements the efficient download strategy required for large (multi-GB)
NISAR L2 GCOV products:
  - Real authenticated streaming downloads (reuses asf_search.ASFSession,
    which correctly handles the Earthdata Login OAuth/cookie redirect dance -
    this is NOT reimplemented here).
  - Chunk-based streaming writes (no full-file buffering in memory).
  - Resumable downloads via HTTP Range requests against a partial ".part" file.
  - A persisted JSON manifest so progress/status survives across requests and
    process restarts - status is always read from real bytes on disk, never
    a fabricated progress value.
  - Local caching with dedup: a granule already fully downloaded and size-
    verified is never re-downloaded.
  - Controlled concurrency via a bounded thread pool, so multiple large
    downloads cannot overwhelm memory/bandwidth/disk simultaneously.
"""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, Optional

import asf_search
import requests

from app.utils.errors import DataIngestionError
from app.utils.logging import get_logger

logger = get_logger(__name__)

CHUNK_SIZE = 1024 * 1024  # 1 MB streaming chunks
MANIFEST_SAVE_INTERVAL_BYTES = 10 * 1024 * 1024  # persist progress every ~10MB


class DownloadManager:
    """Manages efficient, resumable, cached downloads of real NISAR GCOV granules."""

    def __init__(
        self,
        cache_dir: Path,
        username: str,
        password: str,
        max_concurrent_downloads: int = 2,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.cache_dir / "manifest.json"
        self.username = username
        self.password = password
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(
            max_workers=max_concurrent_downloads, thread_name_prefix="gcov-download"
        )
        self._session: Optional[requests.Session] = None
        self._futures: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Manifest persistence (status tracking)
    # ------------------------------------------------------------------

    def _load_manifest(self) -> Dict[str, Any]:
        if not self.manifest_path.exists():
            return {}
        try:
            with open(self.manifest_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Manifest unreadable ({e}), starting fresh")
            return {}

    def _save_manifest(self, manifest: Dict[str, Any]) -> None:
        tmp_path = self.manifest_path.with_suffix(".tmp")
        with open(tmp_path, "w") as f:
            json.dump(manifest, f, indent=2)
        tmp_path.replace(self.manifest_path)

    def _update_entry(self, granule_id: str, **fields: Any) -> None:
        with self._lock:
            manifest = self._load_manifest()
            entry = manifest.get(granule_id, {})
            entry.update(fields)
            manifest[granule_id] = entry
            self._save_manifest(manifest)

    # ------------------------------------------------------------------
    # Public status / cache inspection (always reflects real disk state)
    # ------------------------------------------------------------------

    def get_status(self, granule_id: str) -> Dict[str, Any]:
        """Return the real current download status for a granule, verifying
        against the actual file on disk rather than trusting stale manifest
        state alone."""
        with self._lock:
            manifest = self._load_manifest()
        entry = manifest.get(granule_id)
        if not entry:
            return {"granule_id": granule_id, "status": "not_found"}

        local_path = Path(entry["local_path"])
        part_path = local_path.with_suffix(local_path.suffix + ".part")

        if entry.get("status") == "complete" and local_path.exists():
            entry["downloaded_bytes"] = local_path.stat().st_size
        elif part_path.exists():
            entry["downloaded_bytes"] = part_path.stat().st_size

        total = entry.get("total_bytes") or 0
        downloaded = entry.get("downloaded_bytes") or 0
        entry["progress_percent"] = round(100 * downloaded / total, 1) if total else None
        return entry

    def list_cache(self) -> Dict[str, Any]:
        """List all granules known to the local cache (complete, partial, or failed)."""
        with self._lock:
            return self._load_manifest()

    def register_existing_file(self, granule_id: str, local_path: Path, url: str = "") -> Dict[str, Any]:
        """Register an already-downloaded file (e.g. a sample granule obtained
        outside this manager) into the cache manifest, so dedup logic treats
        it as complete without re-downloading or re-verifying from network."""
        local_path = Path(local_path)
        if not local_path.exists():
            raise DataIngestionError(f"Cannot register missing file: {local_path}")
        size = local_path.stat().st_size
        self._update_entry(
            granule_id,
            url=url,
            local_path=str(local_path),
            total_bytes=size,
            downloaded_bytes=size,
            status="complete",
            registered_externally=True,
            completed_at=time.time(),
        )
        logger.info(f"Registered existing file for {granule_id}: {local_path} ({size / 1e6:.1f} MB)")
        return self.get_status(granule_id)

    # ------------------------------------------------------------------
    # Authenticated session (reuses asf_search's proven EDL auth flow)
    # ------------------------------------------------------------------

    def _get_session(self) -> requests.Session:
        if self._session is None:
            session = asf_search.ASFSession()
            session.auth_with_creds(self.username, self.password)
            self._session = session
            logger.info("Authenticated Earthdata session created for downloads")
        return self._session

    # ------------------------------------------------------------------
    # Download orchestration
    # ------------------------------------------------------------------

    def start_download(self, granule_id: str, url: str, expected_size_mb: Optional[float] = None) -> Dict[str, Any]:
        """
        Start (or resume, or skip if already cached) a real download for a
        granule. Runs in a background thread from the bounded pool; returns
        immediately with the current status.

        Returns:
            Current status dict. If status is already "complete", no network
            activity occurs (dedup). If a download is already in progress for
            this granule_id, the existing job is returned rather than starting
            a duplicate.
        """
        current = self.get_status(granule_id)
        if current.get("status") == "complete":
            logger.info(f"Granule {granule_id} already cached complete; skipping download")
            return current

        if granule_id in self._futures and not self._futures[granule_id].done():
            logger.info(f"Download already in progress for {granule_id}")
            return self.get_status(granule_id)

        local_path = self.cache_dir / f"{granule_id}.h5"
        expected_bytes = int(expected_size_mb * 1024 * 1024) if expected_size_mb else None

        self._update_entry(
            granule_id,
            url=url,
            local_path=str(local_path),
            total_bytes=expected_bytes,
            downloaded_bytes=0,
            status="downloading",
            started_at=time.time(),
            error=None,
        )

        future = self._executor.submit(self._download_worker, granule_id, url, local_path, expected_bytes)
        self._futures[granule_id] = future
        return self.get_status(granule_id)

    def _download_worker(self, granule_id: str, url: str, local_path: Path, expected_bytes: Optional[int]) -> None:
        part_path = local_path.with_suffix(local_path.suffix + ".part")
        resume_from = part_path.stat().st_size if part_path.exists() else 0

        try:
            session = self._get_session()
            headers = {"Range": f"bytes={resume_from}-"} if resume_from else {}

            logger.info(f"Downloading {granule_id} from {url} (resume_from={resume_from} bytes)")
            with session.get(url, headers=headers, stream=True, timeout=60) as response:
                if response.status_code not in (200, 206):
                    raise DataIngestionError(
                        f"Download failed for {granule_id}: HTTP {response.status_code}"
                    )

                content_length = response.headers.get("Content-Length")
                total_bytes = expected_bytes
                if content_length:
                    total_bytes = resume_from + int(content_length) if response.status_code == 206 else int(content_length)

                mode = "ab" if resume_from and response.status_code == 206 else "wb"
                if mode == "wb":
                    resume_from = 0

                downloaded = resume_from
                last_saved_at = downloaded

                with open(part_path, mode) as f:
                    for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)
                        if downloaded - last_saved_at >= MANIFEST_SAVE_INTERVAL_BYTES:
                            self._update_entry(
                                granule_id,
                                downloaded_bytes=downloaded,
                                total_bytes=total_bytes,
                                status="downloading",
                            )
                            last_saved_at = downloaded

            final_size = part_path.stat().st_size
            if total_bytes and final_size != total_bytes:
                raise DataIngestionError(
                    f"Size mismatch for {granule_id}: expected {total_bytes}, got {final_size}"
                )

            part_path.rename(local_path)
            self._update_entry(
                granule_id,
                downloaded_bytes=final_size,
                total_bytes=total_bytes or final_size,
                status="complete",
                completed_at=time.time(),
                error=None,
            )
            logger.info(f"Download complete for {granule_id}: {final_size / 1e6:.1f} MB -> {local_path}")

        except Exception as e:
            logger.error(f"Download failed for {granule_id}: {e}")
            self._update_entry(granule_id, status="failed", error=str(e))
