"""
NISAR Imagery Handler - Downloads and serves SAR backscatter visualization
Provides raster imagery tiles for before/after comparison in swipe view
"""

import numpy as np
import io
from PIL import Image, ImageDraw, ImageFont
from typing import Tuple, Optional, Dict, Any
import colorsys


class SARBackscatterRenderer:
    """Renders SAR backscatter data as visualization images for UI display."""
    
    def __init__(self, width: int = 512, height: int = 512):
        """Initialize renderer with dimensions."""
        self.width = width
        self.height = height
    
    @staticmethod
    def db_to_linear(db_value: float) -> float:
        """Convert dB value to linear scale."""
        if db_value is None or db_value == 0:
            return 0
        return 10 ** (db_value / 10)
    
    @staticmethod
    def linear_to_uint8(linear_val: float, min_val: float = 0, max_val: float = 1) -> int:
        """Convert linear value to 0-255 range."""
        if max_val <= min_val:
            return 128
        normalized = (linear_val - min_val) / (max_val - min_val)
        normalized = np.clip(normalized, 0, 1)
        return int(normalized * 255)
    
    def render_sar_backscatter(self, 
                               backscatter_db: Optional[np.ndarray] = None,
                               title: str = "SAR Backscatter",
                               colormap: str = "grayscale",
                               inundation_mask: Optional[np.ndarray] = None,
                               vegetation_flood_mask: Optional[np.ndarray] = None) -> Image.Image:
        """
        Render SAR backscatter as a visualization image.
        
        Args:
            backscatter_db: 2D array of backscatter values in dB (or None for synthetic)
            title: Title text to display
            colormap: Color scheme ('grayscale', 'radar', 'thermal')
            inundation_mask: Optional binary mask for open-water flood areas (radar-dark)
            vegetation_flood_mask: Optional binary mask for flooded-vegetation areas
                (radar-bright, double-bounce signature - distinct from open water)
        
        Returns:
            PIL Image object
        """
        
        # If no real data provided, generate synthetic NISAR-like backscatter
        if backscatter_db is None:
            backscatter_db = self._generate_synthetic_nisar_data()
        
        # Convert to PIL image
        if colormap == "grayscale":
            img = self._render_grayscale(backscatter_db)
        elif colormap == "radar":
            img = self._render_radar_colors(backscatter_db)
        elif colormap == "thermal":
            img = self._render_thermal(backscatter_db)
        else:
            img = self._render_grayscale(backscatter_db)
        
        # Add inundation overlay(s) if provided
        if inundation_mask is not None or vegetation_flood_mask is not None:
            img = self._add_inundation_overlay(img, inundation_mask, vegetation_flood_mask)
        
        # Add metadata and title
        img = self._add_metadata(img, title)
        
        return img
    
    def _generate_synthetic_nisar_data(self, rng: Optional[np.random.RandomState] = None) -> np.ndarray:
        """Generate synthetic NISAR-like SAR backscatter data for visualization.

        Args:
            rng: Optional seeded random generator so the terrain/urban/water layout
                 and speckle noise are deterministic per search location instead of
                 always identical (defaults to global numpy randomness if omitted).
        """
        if rng is None:
            rng = np.random

        # Create base terrain with realistic SAR characteristics
        y, x = np.ogrid[:self.height, :self.width]

        # Natural terrain variation (typically -20 to -5 dB for vegetation)
        terrain_base = -15 + 5 * np.sin(y * 0.01) * np.cos(x * 0.01)

        # Add urban/built-up areas (typically -8 to -2 dB for buildings)
        # Position/size vary per seed so different search locations don't look identical
        urban_x = int(rng.uniform(0.2, 0.5) * self.width)
        urban_y = int(rng.uniform(0.2, 0.5) * self.height)
        urban_radius = rng.uniform(60, 110)
        urban_dist = np.sqrt((x - urban_x)**2 + (y - urban_y)**2)
        urban_areas = np.where(urban_dist < urban_radius, -5, 0)

        # Add water features (very low backscatter, typically -25 to -18 dB)
        water_x = int(rng.uniform(0.5, 0.8) * self.width)
        water_y = int(rng.uniform(0.5, 0.8) * self.height)
        water_radius = rng.uniform(40, 80)
        water_dist = np.sqrt((x - water_x)**2 + (y - water_y)**2)
        water_areas = np.where(water_dist < water_radius, -22, 0)

        # Combine layers
        backscatter = terrain_base + urban_areas + water_areas

        # Add speckle noise (SAR characteristic)
        speckle = rng.normal(0, 1, (self.height, self.width))
        backscatter += speckle * 0.5

        # Clip to realistic SAR range (-30 to 0 dB)
        backscatter = np.clip(backscatter, -30, 0)

        return backscatter
    
    def _render_grayscale(self, backscatter_db: np.ndarray) -> Image.Image:
        """Render as grayscale (typical SAR visualization)."""
        
        # Normalize to 0-255 range
        min_db = -30
        max_db = 0
        backscatter_normalized = (backscatter_db - min_db) / (max_db - min_db)
        backscatter_normalized = np.clip(backscatter_normalized, 0, 1)
        
        # Convert to 8-bit
        img_array = (backscatter_normalized * 255).astype(np.uint8)
        
        # Convert to PIL
        img = Image.fromarray(img_array, mode='L')
        
        return img
    
    def _render_radar_colors(self, backscatter_db: np.ndarray) -> Image.Image:
        """Render with radar-style color scheme (green-red for low-high backscatter)."""
        
        # Normalize to 0-1 range
        min_db = -30
        max_db = 0
        backscatter_norm = (backscatter_db - min_db) / (max_db - min_db)
        backscatter_norm = np.clip(backscatter_norm, 0, 1)
        
        # Create RGB image: Low backscatter = green (water), high = red (buildings)
        img_array = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        for i in range(self.height):
            for j in range(self.width):
                val = backscatter_norm[i, j]
                # Green for low values (water/smooth), red for high (urban)
                img_array[i, j, 0] = int(val * 255)  # Red channel
                img_array[i, j, 1] = int((1 - val) * 255)  # Green channel
                img_array[i, j, 2] = int(50)  # Blue channel (low)
        
        img = Image.fromarray(img_array, mode='RGB')
        return img
    
    def _render_thermal(self, backscatter_db: np.ndarray) -> Image.Image:
        """Render with thermal-style color scheme."""
        
        # Normalize to 0-1 range
        min_db = -30
        max_db = 0
        backscatter_norm = (backscatter_db - min_db) / (max_db - min_db)
        backscatter_norm = np.clip(backscatter_norm, 0, 1)
        
        # Create thermal colormap
        img_array = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        for i in range(self.height):
            for j in range(self.width):
                val = backscatter_norm[i, j]
                # Thermal: blue (cold/water) -> cyan -> green -> yellow -> red (hot/urban)
                if val < 0.25:
                    # Blue to cyan
                    t = val / 0.25
                    img_array[i, j] = [0, int(t * 255), 255]
                elif val < 0.5:
                    # Cyan to green
                    t = (val - 0.25) / 0.25
                    img_array[i, j] = [0, 255, int((1 - t) * 255)]
                elif val < 0.75:
                    # Green to yellow
                    t = (val - 0.5) / 0.25
                    img_array[i, j] = [int(t * 255), 255, 0]
                else:
                    # Yellow to red
                    t = (val - 0.75) / 0.25
                    img_array[i, j] = [255, int((1 - t) * 255), 0]
        
        img = Image.fromarray(img_array, mode='RGB')
        return img
    
    def _add_inundation_overlay(self,
                                img: Image.Image,
                                inundation_mask: Optional[np.ndarray],
                                vegetation_flood_mask: Optional[np.ndarray] = None) -> Image.Image:
        """Add distinct overlay colors for the two real SAR flood signatures:
        neon orange for open-water inundation (radar-dark, specular
        scattering) and lime green for flooded vegetation (radar-bright,
        double-bounce scattering) - see NASA/JPL "Floods" StoryMap
        (https://storymaps.arcgis.com/stories/c00d7691b8004b20a14f28df710d05fd).

        Vectorized with numpy boolean indexing (not a per-pixel Python loop +
        putpixel(), which measured 2+ minutes for a real multi-million-pixel
        AOI image) - same 47%-opacity alpha-blend result, computed in bulk."""

        if img.mode == 'L':
            img = img.convert('RGB')

        img_array = np.array(img, dtype=np.float32)
        alpha = 120 / 255.0

        def blend(mask: np.ndarray, color: Tuple[int, int, int]) -> None:
            region = mask > 0.5  # NaN (invalid) pixels compare False, same as the original loop
            color_arr = np.array(color, dtype=np.float32)
            img_array[region] = img_array[region] * (1 - alpha) + color_arr * alpha

        if inundation_mask is not None:
            blend(inundation_mask, (255, 107, 0))  # Neon orange, 47% opacity

        if vegetation_flood_mask is not None:
            blend(vegetation_flood_mask, (57, 255, 20))  # Lime green, 47% opacity

        return Image.fromarray(np.clip(img_array, 0, 255).astype(np.uint8), mode='RGB')
    
    def _add_metadata(self, img: Image.Image, title: str) -> Image.Image:
        """Add title and metadata text to image."""
        
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Add semi-transparent background bar for text
        draw = ImageDraw.Draw(img)
        
        # Dark background for title bar
        draw.rectangle(
            [(0, 0), (self.width, 40)],
            fill=(20, 20, 20, 200)
        )
        
        # Try to add text (use default font if needed)
        try:
            # Use a reasonable default font size
            text = title
            # Draw text in white
            draw.text((10, 10), text, fill=(255, 255, 255))
        except Exception as e:
            # Font handling varies by platform
            print(f"Warning: Could not add text: {e}")
        
        return img
    
    def render_change_detection(self,
                                before_backscatter: np.ndarray,
                                after_backscatter: np.ndarray,
                                flood_threshold_db: float = -2.0) -> Tuple[Image.Image, float]:
        """
        Render change detection visualization showing flooded areas.
        
        Returns:
            Tuple of (visualization_image, flood_percentage)
        """
        
        # Calculate backscatter change
        delta_backscatter = after_backscatter - before_backscatter
        
        # Create binary mask where decrease indicates flooding
        # (negative change = water backscatter decreased = inundation)
        flood_mask = delta_backscatter < flood_threshold_db
        
        # Calculate flood percentage
        flood_percentage = np.mean(flood_mask) * 100
        
        # Render the after backscatter with flood overlay
        img = self.render_sar_backscatter(
            backscatter_db=after_backscatter,
            title="Post-Flood SAR Backscatter + Flood Detection",
            colormap="grayscale",
            inundation_mask=flood_mask.astype(np.float32)
        )
        
        return img, flood_percentage
    
    def to_base64_png(self, img: Image.Image) -> str:
        """Convert PIL image to base64-encoded PNG string."""
        
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        import base64
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return f"data:image/png;base64,{img_base64}"


# Large real AOIs can produce multi-thousand-pixel-per-side GeoTIFFs; the
# swipe-view PNG is a visual preview, not the analysis data (the real,
# full-resolution GeoTIFF remains available unmodified via
# /api/v2/analyze/{id}/layer/{name}.tif for export/GIS use) - rendering the
# preview at full resolution measured 80+ seconds and a 50+ MB PNG for one
# real 3000x3000 AOI (SAR speckle compresses poorly), which is far more
# detail than a browser swipe comparison needs or can usefully display.
MAX_DISPLAY_DIM = 1600


def _decimated_shape(height: int, width: int, max_dim: int = MAX_DISPLAY_DIM) -> Tuple[int, int]:
    """Target (height, width) for display, preserving aspect ratio, capped at max_dim on the longer side."""
    if max(height, width) <= max_dim:
        return height, width
    scale = max_dim / max(height, width)
    return max(1, round(height * scale)), max(1, round(width * scale))


def render_real_sar_layer(
    tif_path: str,
    title: str,
    colormap: str = "grayscale",
    inundation_mask_path: Optional[str] = None,
    vegetation_flood_mask_path: Optional[str] = None,
) -> str:
    """
    Render a REAL SAR backscatter GeoTIFF (produced by Phase 5's
    ChangeDetectionEngine/GeoTIFFExporter from an actual downloaded NISAR L2
    GCOV granule) as a base64 PNG for display, reusing the same colorization/
    overlay drawing code as the (now-removed) synthetic path - but fed with
    real pixel values read directly from disk. No synthetic data generation
    is involved anywhere in this function.
    """
    import rasterio
    from rasterio.enums import Resampling

    with rasterio.open(tif_path) as src:
        out_shape = _decimated_shape(src.height, src.width)
        backscatter_db = src.read(1, out_shape=out_shape, resampling=Resampling.average).astype(np.float64)

    # Masks are written from the same aligned grid as the backscatter layer,
    # so they share its native shape - reusing out_shape keeps all arrays
    # aligned for the overlay blend.
    inundation_mask = None
    if inundation_mask_path:
        with rasterio.open(inundation_mask_path) as src:
            inundation_mask = src.read(1, out_shape=out_shape, resampling=Resampling.average).astype(np.float32)

    vegetation_flood_mask = None
    if vegetation_flood_mask_path:
        with rasterio.open(vegetation_flood_mask_path) as src:
            vegetation_flood_mask = src.read(1, out_shape=out_shape, resampling=Resampling.average).astype(np.float32)

    renderer = SARBackscatterRenderer(width=backscatter_db.shape[1], height=backscatter_db.shape[0])
    img = renderer.render_sar_backscatter(
        backscatter_db=backscatter_db,
        title=title,
        colormap=colormap,
        inundation_mask=inundation_mask,
        vegetation_flood_mask=vegetation_flood_mask,
    )
    return renderer.to_base64_png(img)


def render_timeseries_frame(backscatter_db: np.ndarray, date_label: str) -> Image.Image:
    """
    Render one real acquisition's AOI subset as a single time-series
    animation frame (ASF OpenSARlab NISAR Cookbook section 7, "SAR Time
    Series Animation") - reuses the same real colorization code as the
    before/after swipe view, just titled with its real acquisition date
    instead of "Before"/"After". Downsamples large real frames (same
    MAX_DISPLAY_DIM cap as the swipe view) so a multi-frame animation/GIF
    stays a reasonable size - this is a display convenience only, the full-
    resolution per-date data (means, pixel counts) is computed before this
    downsampling happens, never from the downsampled frame.
    """
    renderer = SARBackscatterRenderer(width=backscatter_db.shape[1], height=backscatter_db.shape[0])
    img = renderer.render_sar_backscatter(
        backscatter_db=backscatter_db,
        title=date_label,
        colormap="grayscale",
    )
    if max(img.size) > MAX_DISPLAY_DIM:
        scale = MAX_DISPLAY_DIM / max(img.size)
        new_size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
        img = img.resize(new_size, Image.LANCZOS)
    return img


if __name__ == "__main__":
    # Test visualization
    renderer = SARBackscatterRenderer()
    
    # Create synthetic data
    before_data = renderer._generate_synthetic_nisar_data()
    after_data = before_data.copy()
    after_data[100:200, 100:200] -= 8  # Simulate flooding
    
    # Render visualizations
    before_img = renderer.render_sar_backscatter(before_data, "Pre-Flood")
    after_img = renderer.render_sar_backscatter(after_data, "Post-Flood")
    
    # Save test images
    before_img.save("test_before.png")
    after_img.save("test_after.png")
    
    print("Test images saved: test_before.png, test_after.png")
