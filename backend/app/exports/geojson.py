"""
GeoJSON export functionality.

Converts raster masks to vector polygons in GeoJSON format suitable for
web mapping and data interchange.
"""

from typing import Dict, List, Any
import json
import numpy as np
import rasterio
from rasterio.features import shapes
from rasterio.warp import transform_bounds
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from app.utils.errors import ProcessingError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class GeoJSONExporter:
    """Export raster masks as GeoJSON polygons."""

    @staticmethod
    def raster_to_geojson(
        mask: np.ndarray,
        transform: rasterio.Affine,
        crs: str,
        simplify_tolerance: float = 0.0,
    ) -> str:
        """
        Convert raster mask to GeoJSON FeatureCollection.
        
        Process:
        1. Extract polygons from raster mask using rasterio
        2. Convert to geographic coordinates (EPSG:4326)
        3. Optionally simplify geometries
        4. Format as GeoJSON
        
        Args:
            mask: 2D binary/float array (values > 0.5 considered selected)
            transform: rasterio Affine transform
            crs: Source coordinate reference system
            simplify_tolerance: Simplification tolerance in degrees (0 = no simplification)
            
        Returns:
            GeoJSON string with feature collection
            
        Raises:
            ProcessingError: If conversion fails
        """
        try:
            # Create binary mask
            binary_mask = (mask >= 0.5).astype(np.uint8)
            
            # Extract polygons from raster
            features = []
            for geom, val in shapes(binary_mask, transform=transform):
                if val > 0:
                    shape_geom = shape(geom)

                    # Compute real area in m2 while still in the original
                    # projected CRS (meters). Computing this AFTER
                    # reprojecting to EPSG:4326 would silently give square
                    # degrees instead of square meters.
                    area_m2 = shape_geom.area if crs != "EPSG:4326" else None

                    # Reproject to EPSG:4326
                    if crs != "EPSG:4326":
                        from rasterio.warp import transform as rasterio_transform
                        from pyproj import Transformer
                        
                        transformer = Transformer.from_crs(crs, "EPSG:4326")
                        coords = list(shape_geom.exterior.coords)
                        transformed_coords = [
                            transformer.transform(x, y)[::-1] for x, y in coords
                        ]
                        from shapely.geometry import Polygon
                        shape_geom = Polygon(transformed_coords)
                    else:
                        area_m2 = shape_geom.area
                    
                    # Simplify if requested
                    if simplify_tolerance > 0:
                        shape_geom = shape_geom.simplify(simplify_tolerance)
                    
                    # Create feature
                    feature = {
                        "type": "Feature",
                        "geometry": mapping(shape_geom),
                        "properties": {
                            "class": "detected_feature",
                            "area_m2": area_m2,
                        }
                    }
                    features.append(feature)
            
            # Create FeatureCollection
            geojson = {
                "type": "FeatureCollection",
                "crs": {
                    "type": "name",
                    "properties": {"name": "EPSG:4326"}
                },
                "features": features,
            }
            
            logger.info(f"Converted raster to GeoJSON: {len(features)} features")
            return json.dumps(geojson)
            
        except Exception as e:
            raise ProcessingError(f"GeoJSON export failed: {str(e)}")

    @staticmethod
    def geojson_from_metadata(
        aoi_bounds: tuple[float, float, float, float],
        properties: Dict[str, Any],
    ) -> str:
        """
        Create a GeoJSON polygon from bounds and metadata.
        
        Args:
            aoi_bounds: (west, south, east, north) in EPSG:4326
            properties: Feature properties (metadata)
            
        Returns:
            GeoJSON FeatureCollection string
        """
        try:
            west, south, east, north = aoi_bounds
            
            # Create bounding box polygon
            coordinates = [[
                [west, south],
                [east, south],
                [east, north],
                [west, north],
                [west, south],
            ]]
            
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": coordinates,
                },
                "properties": properties,
            }
            
            geojson = {
                "type": "FeatureCollection",
                "features": [feature],
                "crs": {
                    "type": "name",
                    "properties": {"name": "EPSG:4326"}
                }
            }
            
            return json.dumps(geojson)
            
        except Exception as e:
            raise ProcessingError(f"GeoJSON creation failed: {str(e)}")
