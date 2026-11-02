"""
Local file adapter for GCOV data.

Handles discovery and loading of locally stored GCOV HDF5 files.
"""

from pathlib import Path
from typing import List
from app.utils.errors import DataIngestionError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class LocalAdapter:
    """Adapter for local GCOV files."""

    @staticmethod
    def discover_gcov_files(directory: Path) -> List[Path]:
        """
        Discover GCOV HDF5 files in a directory.
        
        Args:
            directory: Directory to search
            
        Returns:
            List of paths to HDF5 files
            
        Raises:
            DataIngestionError: If directory doesn't exist
        """
        try:
            if not directory.is_dir():
                raise DataIngestionError(f"Directory not found: {directory}")
            
            h5_files = sorted(directory.glob("*.h5"))
            logger.info(f"Found {len(h5_files)} HDF5 files in {directory}")
            
            return h5_files
            
        except DataIngestionError:
            raise
        except Exception as e:
            raise DataIngestionError(f"Failed to discover files: {str(e)}")

    @staticmethod
    def validate_file(path: Path) -> bool:
        """
        Validate that a file exists and is readable.
        
        Args:
            path: File path
            
        Returns:
            True if valid, False otherwise
        """
        try:
            return path.is_file() and path.stat().st_size > 0
        except Exception:
            return False
