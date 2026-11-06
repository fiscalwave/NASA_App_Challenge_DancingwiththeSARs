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
                               inundation_mask: Optional[np.ndarray] = None) -> Image.Image:
        """
        Render SAR backscatter as a visualization image.
        
        Args:
            backscatter_db: 2D array of backscatter values in dB (or None for synthetic)
            title: Title text to display
            colormap: Color scheme ('grayscale', 'radar', 'thermal')
            inundation_mask: Optional binary mask for flood areas
        
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
        
        # Add inundation overlay if provided
        if inundation_mask is not None:
            img = self._add_inundation_overlay(img, inundation_mask)
        
        # Add metadata and title
        img = self._add_metadata(img, title)
        
        return img
    
    def _generate_synthetic_nisar_data(self) -> np.ndarray:
        """Generate synthetic NISAR-like SAR backscatter data for visualization."""
        
        # Create base terrain with realistic SAR characteristics
        y, x = np.ogrid[:self.height, :self.width]
        
        # Natural terrain variation (typically -20 to -5 dB for vegetation)
        terrain_base = -15 + 5 * np.sin(y * 0.01) * np.cos(x * 0.01)
        
        # Add urban/built-up areas (typically -8 to -2 dB for buildings)
        urban_x, urban_y = self.width // 3, self.height // 3
        urban_dist = np.sqrt((x - urban_x)**2 + (y - urban_y)**2)
        urban_areas = np.where(urban_dist < 80, -5, 0)
        
        # Add water features (very low backscatter, typically -25 to -18 dB)
        water_x, water_y = 2 * self.width // 3, 2 * self.height // 3
        water_dist = np.sqrt((x - water_x)**2 + (y - water_y)**2)
        water_areas = np.where(water_dist < 60, -22, 0)
        
        # Combine layers
        backscatter = terrain_base + urban_areas + water_areas
        
        # Add speckle noise (SAR characteristic)
        speckle = np.random.normal(0, 1, (self.height, self.width))
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
                                inundation_mask: np.ndarray) -> Image.Image:
        """Add neon orange inundation overlay to detected flood areas."""
        
        # Convert grayscale to RGB if needed
        if img.mode == 'L':
            img = img.convert('RGB')
        
        # Create overlay
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        
        # Apply neon orange color (#FF6B00) with transparency to flood mask
        for i in range(self.height):
            for j in range(self.width):
                if inundation_mask[i, j] > 0.5:  # If pixel is marked as flooded
                    overlay.putpixel((j, i), (255, 107, 0, 120))  # Neon orange, 47% opacity
        
        # Composite overlay onto base image
        img = img.convert('RGBA')
        img = Image.alpha_composite(img, overlay)
        img = img.convert('RGB')
        
        return img
    
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


def create_sar_visualization(scene_id: str, scene_type: str = "post-flood") -> str:
    """
    Create a SAR backscatter visualization for a scene.
    
    Args:
        scene_id: Scene identifier
        scene_type: Type of scene ('pre-flood' or 'post-flood')
    
    Returns:
        Base64-encoded PNG data URL
    """
    
    renderer = SARBackscatterRenderer(width=512, height=512)
    
    # Generate synthetic NISAR backscatter
    backscatter = renderer._generate_synthetic_nisar_data()
    
    # Render visualization
    if scene_type == "pre-flood":
        title = f"Pre-Flood Baseline (Scene: {scene_id})"
        img = renderer.render_sar_backscatter(
            backscatter_db=backscatter,
            title=title,
            colormap="grayscale"
        )
    else:
        title = f"Post-Flood Crisis (Scene: {scene_id})"
        # Simulate some flood (lower backscatter in certain areas)
        flood_backscatter = backscatter.copy()
        flood_backscatter[150:250, 150:250] -= 8  # Simulate flood in central area
        flood_mask = (flood_backscatter < (backscatter - 3))
        
        img = renderer.render_sar_backscatter(
            backscatter_db=flood_backscatter,
            title=title,
            colormap="grayscale",
            inundation_mask=flood_mask.astype(np.float32)
        )
    
    # Convert to base64 data URL
    return renderer.to_base64_png(img)


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
