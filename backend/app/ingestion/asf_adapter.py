"""
ASF (Alaska Satellite Facility) data adapter.

Handles discovery and retrieval of NISAR GCOV data via ASF Search API.
"""

from datetime import date, datetime
from typing import List
from urllib.parse import urlparse
from pathlib import Path
import asf_search as asf
from app.config import get_config
from app.utils.errors import DataIngestionError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ASFAdapter:
    """Adapter for ASF Search API."""

    SEARCH_PATTERN = r"^(?!.*QA_STATS).*"

    @staticmethod
    def bounds_to_wkt(bounds: tuple[float, float, float, float]) -> str:
        """
        Convert geographic bounds to WKT POLYGON format for ASF Search.
        
        Args:
            bounds: (west, south, east, north)
            
        Returns:
            WKT POLYGON string
        """
        west, south, east, north = bounds
        return (
            f"POLYGON(({west} {south},{east} {south},{east} {north},"
            f"{west} {north},{west} {south}))"
        )

    @classmethod
    def search_gcov(
        cls,
        username: str,
        password: str,
        bounds: tuple[float, float, float, float],
        start: date,
        end: date,
    ) -> List[str]:
        """
        Search ASF for NISAR GCOV scenes.
        
        Args:
            username: Earthdata username
            password: Earthdata password
            bounds: Geographic bounds (west, south, east, north)
            start: Search start date
            end: Search end date
            
        Returns:
            List of download URLs for GCOV products
            
        Raises:
            DataIngestionError: If search fails
        """
        try:
            config = get_config()
            
            session = asf.ASFSession()
            session.auth_with_creds(username, password)
            
            logger.info(f"Searching ASF for NISAR GCOV between {start} and {end}")
            
            options = asf.ASFSearchOptions(
                maxResults=250,
                intersectsWith=cls.bounds_to_wkt(bounds),
                start=datetime.combine(start, datetime.min.time()),
                end=datetime.combine(end, datetime.max.time()),
                processingLevel=[config.NISAR_PROCESSING_LEVEL],
                dataset=[config.NISAR_DATASET],
                productionConfiguration=[config.NISAR_PRODUCTION_CONFIG],
                dataMaturity=config.NISAR_DATA_MATURITY,
                session=session,
            )
            
            results = asf.search(opts=options)
            
            urls = list(
                dict.fromkeys(
                    results.find_urls(
                        extension=".h5",
                        pattern=cls.SEARCH_PATTERN,
                        directAccess=False,
                    )
                )
            )
            
            logger.info(f"Found {len(urls)} GCOV scenes")
            return urls
            
        except asf.ASFError as e:
            raise DataIngestionError(f"ASF search failed: {str(e)}")
        except Exception as e:
            raise DataIngestionError(f"Unexpected error during ASF search: {str(e)}")

    @staticmethod
    def download_gcov(url: str, username: str, password: str, output_dir: Path) -> Path:
        """
        Download a GCOV HDF5 file from ASF.
        
        Args:
            url: Download URL
            username: Earthdata username
            password: Earthdata password
            output_dir: Directory to save file
            
        Returns:
            Path to downloaded file
            
        Raises:
            DataIngestionError: If download fails
        """
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            
            session = asf.ASFSession()
            session.auth_with_creds(username, password)
            
            logger.info(f"Downloading: {url}")
            asf.download_url(url, output_dir, session=session)
            
            filename = Path(urlparse(url).path).name
            local_path = output_dir / filename
            
            if not local_path.is_file() or local_path.stat().st_size == 0:
                raise FileNotFoundError(f"ASF did not create the expected file: {local_path}")
            
            file_size_mb = local_path.stat().st_size / (1024 ** 2)
            logger.info(f"Downloaded successfully: {local_path} ({file_size_mb:.1f} MB)")
            
            return local_path
            
        except asf.ASFError as e:
            raise DataIngestionError(f"ASF download failed: {str(e)}")
        except FileNotFoundError as e:
            raise DataIngestionError(str(e))
        except Exception as e:
            raise DataIngestionError(f"Unexpected error during download: {str(e)}")
