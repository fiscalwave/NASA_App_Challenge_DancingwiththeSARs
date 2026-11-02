from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

import asf_search as asf
import folium
import h5py
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import rasterio
import streamlit as st
from matplotlib.colors import TwoSlopeNorm
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.io import MemoryFile
from rasterio.transform import array_bounds, from_origin
from rasterio.warp import calculate_default_transform, reproject
from streamlit_folium import st_folium


st.set_page_config(
    page_title="NISAR | Flood & Wetland Monitor",
    page_icon=":material/satellite_alt:",
    layout="wide",
)

DATA_DIR = Path("data/scenes")
SEARCH_PATTERN = r"^(?!.*QA_STATS).*"
DEFAULT_BOUNDS = (41.30, 12.70, 41.35, 12.75)
POLARIZATIONS = ("HHHH", "HVHV", "VVVV", "HHHV", "VHVH", "VVVH")
MAX_SUBSET_PIXELS = 15_000_000


def bounds_to_wkt(bounds: tuple[float, float, float, float]) -> str:
    west, south, east, north = bounds
    return (
        f"POLYGON(({west} {south},{east} {south},{east} {north},"
        f"{west} {north},{west} {south}))"
    )


def search_gcov(
    username: str,
    password: str,
    bounds: tuple[float, float, float, float],
    start: date,
    end: date,
) -> list[str]:
    session = asf.ASFSession()
    session.auth_with_creds(username, password)
    options = asf.ASFSearchOptions(
        maxResults=250,
        intersectsWith=bounds_to_wkt(bounds),
        start=datetime.combine(start, datetime.min.time()),
        end=datetime.combine(end, datetime.max.time()),
        processingLevel=["GCOV"],
        dataset=["NISAR"],
        productionConfiguration=["PR"],
        dataMaturity="PROVISIONAL",
        session=session,
    )
    results = asf.search(opts=options)
    return list(
        dict.fromkeys(
            results.find_urls(
                extension=".h5",
                pattern=SEARCH_PATTERN,
                directAccess=False,
            )
        )
    )


def download_gcov(url: str, username: str, password: str) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    session = asf.ASFSession()
    session.auth_with_creds(username, password)
    asf.download_url(url, DATA_DIR, session=session)
    filename = Path(urlparse(url).path).name
    local_path = DATA_DIR / filename
    if not local_path.is_file() or local_path.stat().st_size == 0:
        raise FileNotFoundError(f"ASF did not create the expected file: {local_path}")
    return local_path


def find_frequency_group(h5_file: h5py.File) -> h5py.Group:
    groups: list[h5py.Group] = []

    def collect(name: str, item: h5py.Group | h5py.Dataset) -> None:
        if (
            isinstance(item, h5py.Group)
            and name.rsplit("/", 1)[-1].startswith("frequency")
            and "xCoordinates" in item
            and "yCoordinates" in item
            and "projection" in item
        ):
            groups.append(item)

    h5_file.visititems(collect)
    if not groups:
        raise ValueError("No GCOV frequency grid with coordinates was found in this HDF5 file.")
    return groups[0]


def list_polarizations(path: Path) -> list[str]:
    with h5py.File(path, "r") as h5_file:
        group = find_frequency_group(h5_file)
        return [
            polarization
            for polarization in POLARIZATIONS
            if polarization in group
            and isinstance(group[polarization], h5py.Dataset)
            and group[polarization].ndim == 2
        ]


def _scalar(value: object) -> int:
    return int(np.asarray(value).item())


def load_gcov_subset(
    path: Path,
    polarization: str,
    bounds: tuple[float, float, float, float],
) -> dict[str, object]:
    with h5py.File(path, "r") as h5_file:
        group = find_frequency_group(h5_file)
        if polarization not in group or not isinstance(group[polarization], h5py.Dataset):
            available = ", ".join(list_polarizations(path)) or "none"
            raise ValueError(
                f"{path.name} does not contain {polarization}. Available channels: {available}."
            )

        dataset = group[polarization]
        x_coordinates = np.asarray(group["xCoordinates"][:], dtype=np.float64)
        y_coordinates = np.asarray(group["yCoordinates"][:], dtype=np.float64)
        if dataset.shape != (y_coordinates.size, x_coordinates.size):
            raise ValueError(
                f"{polarization} dimensions do not match the grid coordinates in {path.name}."
            )

        projection = _scalar(group["projection"][()])
        transformer = Transformer.from_crs(
            "EPSG:4326",
            f"EPSG:{projection}",
            always_xy=True,
        )
        west, south, east, north = bounds
        projected_bounds = transformer.transform_bounds(
            west,
            south,
            east,
            north,
            densify_pts=21,
        )
        projected_west, projected_south, projected_east, projected_north = projected_bounds
        x_indices = np.flatnonzero(
            (x_coordinates >= projected_west) & (x_coordinates <= projected_east)
        )
        y_indices = np.flatnonzero(
            (y_coordinates >= projected_south) & (y_coordinates <= projected_north)
        )
        if x_indices.size == 0 or y_indices.size == 0:
            raise ValueError(f"The selected study area does not overlap {path.name}.")

        x_slice = slice(int(x_indices.min()), int(x_indices.max()) + 1)
        y_slice = slice(int(y_indices.min()), int(y_indices.max()) + 1)
        subset_shape = (y_slice.stop - y_slice.start, x_slice.stop - x_slice.start)
        if subset_shape[0] * subset_shape[1] > MAX_SUBSET_PIXELS:
            raise ValueError(
                "The selected area is too large to process safely in one run. "
                "Reduce the study-area bounds and try again."
            )

        raw_values = np.asarray(dataset[y_slice, x_slice])
        if np.iscomplexobj(raw_values):
            raw_values = raw_values.real
        raw_values = raw_values.astype(np.float32, copy=False)
        x_coordinates = x_coordinates[x_slice]
        y_coordinates = y_coordinates[y_slice]
        units = str(dataset.attrs.get("units", "")).lower()
        fill_value = dataset.attrs.get("_FillValue", dataset.attrs.get("fillValue"))

    valid = np.isfinite(raw_values)
    if fill_value is not None:
        valid &= raw_values != float(np.asarray(fill_value).item())
    if "db" in units or "decibel" in units:
        backscatter_db = raw_values
    else:
        valid &= raw_values > 0
        backscatter_db = np.full(raw_values.shape, np.nan, dtype=np.float32)
        backscatter_db[valid] = 10.0 * np.log10(raw_values[valid])
    backscatter_db[~valid] = np.nan

    if x_coordinates.size < 2 or y_coordinates.size < 2:
        raise ValueError(f"Not enough grid coordinates remain in {path.name} to map the data.")
    x_step = float(np.median(np.abs(np.diff(x_coordinates))))
    y_step = float(np.median(np.abs(np.diff(y_coordinates))))
    if x_coordinates[0] > x_coordinates[-1]:
        x_coordinates = x_coordinates[::-1]
        backscatter_db = backscatter_db[:, ::-1]
    if y_coordinates[0] < y_coordinates[-1]:
        y_coordinates = y_coordinates[::-1]
        backscatter_db = backscatter_db[::-1, :]

    transform = from_origin(
        float(x_coordinates[0]) - x_step / 2,
        float(y_coordinates[0]) + y_step / 2,
        x_step,
        y_step,
    )
    return {
        "data": backscatter_db,
        "transform": transform,
        "crs": f"EPSG:{projection}",
        "pixel_area_km2": (x_step * y_step) / 1_000_000,
    }


def compare_scenes(
    before: dict[str, object],
    after: dict[str, object],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    before_data = np.asarray(before["data"], dtype=np.float32)
    after_data = np.asarray(after["data"], dtype=np.float32)
    aligned_before = np.full(after_data.shape, np.nan, dtype=np.float32)
    reproject(
        source=before_data,
        destination=aligned_before,
        src_transform=before["transform"],
        src_crs=before["crs"],
        src_nodata=np.nan,
        dst_transform=after["transform"],
        dst_crs=after["crs"],
        dst_nodata=np.nan,
        resampling=Resampling.bilinear,
    )
    valid = np.isfinite(aligned_before) & np.isfinite(after_data)
    aligned_before[~valid] = np.nan
    aligned_after = after_data.copy()
    aligned_after[~valid] = np.nan
    change = np.full(after_data.shape, np.nan, dtype=np.float32)
    change[valid] = aligned_after[valid] - aligned_before[valid]
    return change, aligned_before, aligned_after, float(after["pixel_area_km2"])


def render_scene_comparison(
    before: np.ndarray,
    after: np.ndarray,
) -> bytes:
    valid_values = np.concatenate((before[np.isfinite(before)], after[np.isfinite(after)]))
    if valid_values.size:
        vmin, vmax = np.nanpercentile(valid_values, [2, 98])
        if vmin == vmax:
            vmin, vmax = float(vmin) - 1, float(vmax) + 1
    else:
        vmin, vmax = -1, 1

    color_map = matplotlib.colormaps["viridis"].copy()
    color_map.set_bad((0, 0, 0, 0))
    figure, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    image = None
    for axis, data, title in zip(axes, (before, after), ("Before (dB)", "After (dB)")):
        image = axis.imshow(
            np.ma.masked_invalid(data),
            cmap=color_map,
            vmin=vmin,
            vmax=vmax,
        )
        axis.set_title(title)
        axis.set_axis_off()
    figure.colorbar(image, ax=axes, label="Backscatter (dB)", shrink=0.8)
    from io import BytesIO

    image_buffer = BytesIO()
    figure.savefig(image_buffer, format="png", dpi=160)
    plt.close(figure)
    return image_buffer.getvalue()


def geotiff_bytes(
    data: np.ndarray,
    transform: rasterio.Affine,
    crs: str,
) -> bytes:
    height, width = data.shape
    with MemoryFile() as memory_file:
        with memory_file.open(
            driver="GTiff",
            height=height,
            width=width,
            count=1,
            dtype="float32",
            crs=crs,
            transform=transform,
            nodata=np.nan,
            compress="deflate",
        ) as dataset:
            dataset.write(data.astype(np.float32, copy=False), 1)
        return memory_file.read()


def create_sar_screening_masks(
    before: np.ndarray,
    after: np.ndarray,
    change: np.ndarray,
    flood_change_threshold_db: float,
    low_backscatter_threshold_db: float,
    pixel_area_km2: float,
) -> tuple[np.ndarray, np.ndarray, dict[str, float]]:
    valid = np.isfinite(before) & np.isfinite(after) & np.isfinite(change)
    possible_flood = np.full(change.shape, np.nan, dtype=np.float32)
    persistent_low_backscatter = np.full(change.shape, np.nan, dtype=np.float32)
    possible_flood[valid] = (
        (change[valid] <= -flood_change_threshold_db)
        & (after[valid] <= low_backscatter_threshold_db)
    ).astype(np.float32)
    persistent_low_backscatter[valid] = (
        (before[valid] <= low_backscatter_threshold_db)
        & (after[valid] <= low_backscatter_threshold_db)
    ).astype(np.float32)
    valid_pixels = int(valid.sum())
    return (
        possible_flood,
        persistent_low_backscatter,
        {
            "possible_flood_pixels": float(np.nansum(possible_flood)),
            "persistent_low_backscatter_pixels": float(
                np.nansum(persistent_low_backscatter)
            ),
            "possible_flood_area_km2": float(np.nansum(possible_flood)) * pixel_area_km2,
            "persistent_low_backscatter_area_km2": (
                float(np.nansum(persistent_low_backscatter)) * pixel_area_km2
            ),
            "valid_pixels": float(valid_pixels),
        },
    )


def render_sar_screening_map(
    possible_flood: np.ndarray,
    persistent_low_backscatter: np.ndarray,
    transform: rasterio.Affine,
    crs: str,
    bounds: tuple[float, float, float, float],
) -> tuple[folium.Map, bytes]:
    height, width = possible_flood.shape
    west, south, east, north = array_bounds(height, width, transform)
    scale = min(1.0, 1200 / max(width, height))
    map_transform, map_width, map_height = calculate_default_transform(
        crs,
        "EPSG:4326",
        width,
        height,
        west,
        south,
        east,
        north,
        dst_width=max(1, round(width * scale)),
        dst_height=max(1, round(height * scale)),
    )
    mapped_masks = []
    for mask in (possible_flood, persistent_low_backscatter):
        mapped = np.full((map_height, map_width), np.nan, dtype=np.float32)
        reproject(
            source=mask,
            destination=mapped,
            src_transform=transform,
            src_crs=crs,
            src_nodata=np.nan,
            dst_transform=map_transform,
            dst_crs="EPSG:4326",
            dst_nodata=np.nan,
            resampling=Resampling.nearest,
        )
        mapped_masks.append(mapped)

    map_west, map_south, map_east, map_north = array_bounds(
        map_height,
        map_width,
        map_transform,
    )
    overlay_bounds = [[map_south, map_west], [map_north, map_east]]
    map_center = [(map_south + map_north) / 2, (map_west + map_east) / 2]
    map_view = folium.Map(location=map_center, zoom_start=8, control_scale=True)
    overlays = (
        (mapped_masks[0], (232, 64, 64), "Possible new inundation candidates"),
        (
            mapped_masks[1],
            (30, 144, 255),
            "Persistent low-backscatter areas (water-like proxy)",
        ),
    )
    for mask, color, name in overlays:
        rgba = np.zeros((map_height, map_width, 4), dtype=np.uint8)
        visible = np.isfinite(mask) & (mask >= 0.5)
        rgba[visible, :3] = color
        rgba[visible, 3] = 190
        folium.raster_layers.ImageOverlay(
            image=rgba,
            bounds=overlay_bounds,
            name=name,
            interactive=True,
            cross_origin=False,
            zindex=2,
        ).add_to(map_view)
    folium.Rectangle(
        bounds=[[bounds[1], bounds[0]], [bounds[3], bounds[2]]],
        color="#f5a623",
        weight=2,
        fill=False,
        tooltip="Selected study area",
        name="Study area",
    ).add_to(map_view)
    folium.LayerControl().add_to(map_view)
    map_view.fit_bounds(overlay_bounds)

    from io import BytesIO

    figure, axes = plt.subplots(1, 2, figsize=(10, 5), constrained_layout=True)
    for axis, mask, title, color in zip(
        axes,
        (possible_flood, persistent_low_backscatter),
        (
            "Possible new inundation candidates",
            "Persistent low-backscatter proxy",
        ),
        ("#e84040", "#1e90ff"),
    ):
        rgba = np.zeros((*mask.shape, 4), dtype=np.float32)
        selected = np.isfinite(mask) & (mask >= 0.5)
        rgba[selected, :3] = matplotlib.colors.to_rgb(color)
        rgba[selected, 3] = 1
        axis.imshow(rgba)
        axis.set_title(title)
        axis.set_axis_off()
    image_buffer = BytesIO()
    figure.savefig(image_buffer, format="png", dpi=160)
    plt.close(figure)
    return map_view, image_buffer.getvalue()


def render_change_map(
    change: np.ndarray,
    transform: rasterio.Affine,
    crs: str,
    threshold_db: float,
    bounds: tuple[float, float, float, float],
) -> tuple[folium.Map, bytes, bytes, dict[str, float]]:
    height, width = change.shape
    west, south, east, north = array_bounds(height, width, transform)
    scale = min(1.0, 1200 / max(width, height))
    map_transform, map_width, map_height = calculate_default_transform(
        crs,
        "EPSG:4326",
        width,
        height,
        west,
        south,
        east,
        north,
        dst_width=max(1, round(width * scale)),
        dst_height=max(1, round(height * scale)),
    )
    mapped = np.full((map_height, map_width), np.nan, dtype=np.float32)
    candidate_change = np.where(
        np.abs(change) >= threshold_db,
        change,
        np.nan,
    )
    reproject(
        source=candidate_change,
        destination=mapped,
        src_transform=transform,
        src_crs=crs,
        src_nodata=np.nan,
        dst_transform=map_transform,
        dst_crs="EPSG:4326",
        dst_nodata=np.nan,
        resampling=Resampling.bilinear,
    )
    map_west, map_south, map_east, map_north = array_bounds(
        map_height,
        map_width,
        map_transform,
    )

    valid = np.isfinite(change)
    changed = valid & (np.abs(change) >= threshold_db)
    valid_count = int(valid.sum())
    candidate_area_km2 = float(changed.sum()) * float(
        np.nanmedian(np.abs(transform.a * transform.e))
    ) / 1_000_000
    stats = {
        "valid_pixels": float(valid_count),
        "candidate_pixels": float(changed.sum()),
        "candidate_area_km2": candidate_area_km2,
        "mean_change_db": float(np.nanmean(change)) if valid_count else float("nan"),
    }

    finite_values = np.abs(change[valid])
    limit = max(threshold_db, float(np.nanpercentile(finite_values, 98))) if valid_count else 1
    color_map = matplotlib.colormaps["RdBu_r"].copy()
    color_map.set_bad((0, 0, 0, 0))
    color_norm = TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit)
    rgba = color_map(
        color_norm(np.ma.masked_invalid(mapped)),
        bytes=True,
    )

    map_center = [(map_south + map_north) / 2, (map_west + map_east) / 2]
    map_view = folium.Map(location=map_center, zoom_start=8, control_scale=True)
    folium.raster_layers.ImageOverlay(
        image=rgba,
        bounds=[[map_south, map_west], [map_north, map_east]],
        opacity=0.78,
        name="Backscatter change (dB)",
        interactive=True,
        cross_origin=False,
        zindex=2,
    ).add_to(map_view)
    folium.Rectangle(
        bounds=[[bounds[1], bounds[0]], [bounds[3], bounds[2]]],
        color="#f5a623",
        weight=2,
        fill=False,
        tooltip="Selected study area",
        name="Study area",
    ).add_to(map_view)
    folium.LayerControl().add_to(map_view)
    map_view.fit_bounds([[map_south, map_west], [map_north, map_east]])

    from io import BytesIO

    image_buffer = BytesIO()
    figure = plt.figure(figsize=(8, 1.1))
    axis = figure.add_axes([0.08, 0.5, 0.84, 0.3])
    scalar_mappable = matplotlib.cm.ScalarMappable(
        norm=color_norm,
        cmap=color_map,
    )
    figure.colorbar(scalar_mappable, cax=axis, orientation="horizontal", label="Change in backscatter (dB)")
    figure.savefig(image_buffer, format="png", dpi=150, bbox_inches="tight", transparent=True)
    plt.close(figure)

    map_image_buffer = BytesIO()
    map_figure, map_axis = plt.subplots(figsize=(10, 8))
    map_plot = map_axis.imshow(
        np.ma.masked_invalid(candidate_change),
        cmap=color_map,
        norm=color_norm,
    )
    map_figure.colorbar(map_plot, ax=map_axis, label="Change in backscatter (dB)")
    map_axis.set_title(
        f"Potential surface change in NISAR GCOV backscatter (|change| >= {threshold_db:.1f} dB)"
    )
    map_axis.set_xlabel("Grid column")
    map_axis.set_ylabel("Grid row")
    map_figure.tight_layout()
    map_figure.savefig(map_image_buffer, format="png", dpi=160)
    plt.close(map_figure)
    return map_view, image_buffer.getvalue(), map_image_buffer.getvalue(), stats


def _search_tab(bounds: tuple[float, float, float, float]) -> None:
    st.subheader("Find before-and-after NISAR GCOV scenes")
    st.caption(
        "Search ASF for provisional NISAR GCOV products. Credentials are entered into "
        "this local Streamlit app, used for ASF requests, and not written to project files. "
        "Do not enter them into a publicly hosted or untrusted copy."
    )
    username = st.text_input("Earthdata Login username", key="earthdata_username")
    password = st.text_input(
        "Earthdata Login password",
        type="password",
        key="earthdata_password",
    )

    columns = st.columns(2)
    with columns[0]:
        st.markdown("**Before event**")
        before_start = st.date_input(
            "Start date",
            value=date(2025, 11, 22),
            key="before_start",
        )
        before_end = st.date_input(
            "End date",
            value=date(2025, 11, 23),
            key="before_end",
        )
    with columns[1]:
        st.markdown("**After event**")
        after_start = st.date_input(
            "Start date",
            value=date(2025, 12, 3),
            key="after_start",
        )
        after_end = st.date_input(
            "End date",
            value=date(2025, 12, 5),
            key="after_end",
        )

    if st.button("Search ASF for both periods", type="primary"):
        if not username.strip() or not password:
            st.error("Enter your Earthdata Login username and password to search ASF.")
            return
        if before_start > before_end or after_start > after_end:
            st.error("Each search period must start on or before its end date.")
            return
        try:
            with st.spinner("Searching ASF for NISAR GCOV scenes..."):
                before_urls = search_gcov(
                    username, password, bounds, before_start, before_end
                )
                after_urls = search_gcov(
                    username, password, bounds, after_start, after_end
                )
            st.session_state["gcov_search_results"] = {
                "before": before_urls,
                "after": after_urls,
            }
        except (asf.ASFError, ValueError, OSError) as error:
            st.error(f"ASF search could not be completed: {error}")
            return

    search_results = st.session_state.get("gcov_search_results")
    if not search_results:
        return
    before_urls = search_results["before"]
    after_urls = search_results["after"]
    left, right = st.columns(2)
    with left:
        st.markdown(f"**Before scenes: {len(before_urls)}**")
        st.write([Path(urlparse(url).path).name for url in before_urls] or "No scenes found.")
    with right:
        st.markdown(f"**After scenes: {len(after_urls)}**")
        st.write([Path(urlparse(url).path).name for url in after_urls] or "No scenes found.")

    if not before_urls or not after_urls:
        st.info("Try wider date windows or adjust the study-area bounds.")
        return

    before_url = st.selectbox(
        "Choose a before-event scene",
        before_urls,
        format_func=lambda url: Path(urlparse(url).path).name,
        key="before_scene_url",
    )
    after_url = st.selectbox(
        "Choose an after-event scene",
        after_urls,
        format_func=lambda url: Path(urlparse(url).path).name,
        key="after_scene_url",
    )
    if st.button("Download selected pair", type="primary"):
        if not username.strip() or not password:
            st.error("Enter your Earthdata credentials again to download the selected pair.")
            return
        try:
            with st.spinner("Downloading selected GCOV scenes..."):
                before_path = download_gcov(before_url, username, password)
                after_path = download_gcov(after_url, username, password)
            st.session_state["downloaded_scene_paths"] = [
                str(before_path),
                str(after_path),
            ]
            st.success(f"Downloaded both scenes to `{DATA_DIR.resolve()}`.")
            st.info("Open the Analyze tab to compare the downloaded pair.")
        except (asf.ASFError, FileNotFoundError, OSError, ValueError) as error:
            st.error(f"Download failed: {error}")


def _analyze_tab(
    bounds: tuple[float, float, float, float],
    threshold_db: float,
    low_backscatter_threshold_db: float,
) -> None:
    st.subheader("Compare local GCOV HDF5 scenes")
    st.caption(
        "Choose HDF5 scenes already downloaded by this app, or place your files in "
        "`data/scenes` and refresh."
    )
    folder = Path(st.text_input("Folder containing GCOV .h5 files", str(DATA_DIR)))
    if not folder.is_dir():
        st.warning(f"Folder not found: {folder}")
        return
    scene_paths = sorted(folder.glob("*.h5"))
    if len(scene_paths) < 2:
        st.info("Add at least two `.h5` GCOV files to this folder, or use the Search ASF tab.")
        return

    labels = {str(path): path.name for path in scene_paths}
    before_path_text = st.selectbox(
        "Before-event HDF5 file",
        [str(path) for path in scene_paths],
        format_func=lambda value: labels[value],
        key="local_before_scene",
    )
    after_options = [str(path) for path in scene_paths if str(path) != before_path_text]
    after_path_text = st.selectbox(
        "After-event HDF5 file",
        after_options,
        format_func=lambda value: labels[value],
        key="local_after_scene",
    )

    try:
        before_polarizations = list_polarizations(Path(before_path_text))
        after_polarizations = list_polarizations(Path(after_path_text))
    except (OSError, ValueError) as error:
        st.error(f"Could not inspect the selected HDF5 files: {error}")
        return
    common_polarizations = [
        channel for channel in before_polarizations if channel in after_polarizations
    ]
    if not common_polarizations:
        st.error("The selected scenes have no matching two-dimensional polarization channels.")
        return
    polarization = st.selectbox("Polarization channel", common_polarizations)

    if st.button("Analyze potential change", type="primary"):
        try:
            with st.spinner("Reading the GCOV subsets and comparing backscatter..."):
                before = load_gcov_subset(
                    Path(before_path_text),
                    polarization,
                    bounds,
                )
                after = load_gcov_subset(
                    Path(after_path_text),
                    polarization,
                    bounds,
                )
                change, aligned_before, aligned_after, pixel_area_km2 = compare_scenes(
                    before,
                    after,
                )
                before_after_png = render_scene_comparison(aligned_before, aligned_after)
                possible_flood, persistent_low_backscatter, screening_stats = (
                    create_sar_screening_masks(
                        aligned_before,
                        aligned_after,
                        change,
                        threshold_db,
                        low_backscatter_threshold_db,
                        pixel_area_km2,
                    )
                )
                screening_map, screening_png = render_sar_screening_map(
                    possible_flood,
                    persistent_low_backscatter,
                    after["transform"],
                    after["crs"],
                    bounds,
                )
                map_view, legend_png, map_png, stats = render_change_map(
                    change,
                    after["transform"],
                    after["crs"],
                    threshold_db,
                    bounds,
                )
                before_tiff = geotiff_bytes(
                    aligned_before,
                    after["transform"],
                    after["crs"],
                )
                after_tiff = geotiff_bytes(
                    aligned_after,
                    after["transform"],
                    after["crs"],
                )
                change_tiff = geotiff_bytes(
                    change,
                    after["transform"],
                    after["crs"],
                )
                possible_flood_tiff = geotiff_bytes(
                    possible_flood,
                    after["transform"],
                    after["crs"],
                )
                persistent_low_backscatter_tiff = geotiff_bytes(
                    persistent_low_backscatter,
                    after["transform"],
                    after["crs"],
                )
            st.session_state["analysis_result"] = {
                "change": change,
                "before_after_png": before_after_png,
                "screening_map": screening_map,
                "screening_png": screening_png,
                "screening_stats": screening_stats,
                "screening_threshold_db": threshold_db,
                "low_backscatter_threshold_db": low_backscatter_threshold_db,
                "possible_flood_tiff": possible_flood_tiff,
                "persistent_low_backscatter_tiff": persistent_low_backscatter_tiff,
                "before_tiff": before_tiff,
                "after_tiff": after_tiff,
                "change_tiff": change_tiff,
                "transform": after["transform"],
                "crs": after["crs"],
                "pixel_area_km2": pixel_area_km2,
                "stats": stats,
                "before": Path(before_path_text).name,
                "after": Path(after_path_text).name,
                "polarization": polarization,
                "threshold_db": threshold_db,
                "map_view": map_view,
                "legend_png": legend_png,
                "map_png": map_png,
            }
        except (OSError, ValueError, rasterio.errors.RasterioError) as error:
            st.error(f"Analysis could not be completed: {error}")
            return

    result = st.session_state.get("analysis_result")
    if not result:
        return
    required_result_fields = {
        "stats",
        "before_after_png",
        "before_tiff",
        "after_tiff",
        "change_tiff",
        "map_view",
        "legend_png",
        "map_png",
        "screening_map",
        "screening_png",
        "screening_stats",
        "screening_threshold_db",
        "low_backscatter_threshold_db",
        "possible_flood_tiff",
        "persistent_low_backscatter_tiff",
    }
    if not required_result_fields.issubset(result):
        st.session_state.pop("analysis_result", None)
        st.info("The saved analysis is outdated. Click **Analyze potential change** to refresh it.")
        return
    stats = result["stats"]
    metrics = st.columns(3)
    metrics[0].metric("Candidate-change area", f"{stats['candidate_area_km2']:.2f} km²")
    metrics[1].metric("Candidate pixels", f"{int(stats['candidate_pixels']):,}")
    metrics[2].metric("Mean backscatter change", f"{stats['mean_change_db']:.2f} dB")
    st.warning(
        "This map highlights potential backscatter surface change only. It is not a "
        "confirmed flood boundary or damage assessment; validate with independent data."
    )
    screening_stats = result["screening_stats"]
    st.subheader("Exploratory flood and wetland screening")
    st.caption(
        "Red marks new low-backscatter areas that may be consistent with open-water "
        "inundation. Blue marks areas with low backscatter in both scenes. The blue "
        "layer is only a persistent water-like proxy, not a wetland classification."
    )
    st.warning(
        "SAR-only thresholds cannot reliably distinguish wetlands from open water, "
        "shadows, or other dark surfaces, and flooding can also increase backscatter. "
        "Treat these layers as screening candidates and validate them independently.",
        title="Exploratory results, not confirmed flood or wetland data",
    )
    screening_metrics = st.columns(2)
    screening_metrics[0].metric(
        "Possible new inundation",
        f"{screening_stats['possible_flood_area_km2']:.2f} km²",
    )
    screening_metrics[1].metric(
        "Persistent low-backscatter proxy",
        f"{screening_stats['persistent_low_backscatter_area_km2']:.2f} km²",
    )
    st_folium(result["screening_map"], height=500, use_container_width=True)
    st.image(
        result["screening_png"],
        width="stretch",
        alt="Possible inundation and persistent low-backscatter screening masks",
    )
    screening_downloads = st.columns(2)
    with screening_downloads[0]:
        st.download_button(
            "Download possible inundation mask",
            data=result["possible_flood_tiff"],
            file_name="nisar_possible_inundation_candidates.tif",
            mime="image/tiff",
        )
    with screening_downloads[1]:
        st.download_button(
            "Download low-backscatter proxy mask",
            data=result["persistent_low_backscatter_tiff"],
            file_name="nisar_persistent_low_backscatter_proxy.tif",
            mime="image/tiff",
        )
    st.caption(
        f"Screening used a low-backscatter cutoff of "
        f"{result['low_backscatter_threshold_db']:.1f} dB and a decrease threshold "
        f"of {result['screening_threshold_db']:.1f} dB."
    )
    st.subheader("Before and after backscatter")
    st.image(
        result["before_after_png"],
        width="stretch",
        alt="Before and after backscatter comparison",
    )
    st.subheader("Color-coded potential change")
    st_folium(result["map_view"], height=600, use_container_width=True)
    st.image(result["legend_png"], width=600)
    downloads = st.columns(3)
    with downloads[0]:
        st.download_button(
            "Download before GeoTIFF",
            data=result["before_tiff"],
            file_name="nisar_before_backscatter_db.tif",
            mime="image/tiff",
        )
    with downloads[1]:
        st.download_button(
            "Download after GeoTIFF",
            data=result["after_tiff"],
            file_name="nisar_after_backscatter_db.tif",
            mime="image/tiff",
        )
    with downloads[2]:
        st.download_button(
            "Download change GeoTIFF",
            data=result["change_tiff"],
            file_name="nisar_backscatter_change_db.tif",
            mime="image/tiff",
        )
    st.download_button(
        "Download change map (PNG)",
        data=result["map_png"],
        file_name="nisar_potential_surface_change.png",
        mime="image/png",
    )

    summary = (
        "Flood & Wetland Change Map - analysis summary\n"
        f"Before scene: {result['before']}\n"
        f"After scene: {result['after']}\n"
        f"Polarization: {result['polarization']}\n"
        f"Candidate threshold: +/-{result['threshold_db']:.1f} dB\n"
        f"Potential-change area: {stats['candidate_area_km2']:.2f} km2\n"
        f"Mean backscatter change: {stats['mean_change_db']:.2f} dB\n"
        f"Possible new inundation candidates: "
        f"{screening_stats['possible_flood_area_km2']:.2f} km2\n"
        f"Persistent low-backscatter proxy: "
        f"{screening_stats['persistent_low_backscatter_area_km2']:.2f} km2\n"
        "Interpretation: exploratory SAR screening only; not confirmed flood or "
        "wetland classification.\n"
    )
    st.download_button(
        "Download analysis summary",
        data=summary,
        file_name="nisar_change_summary.txt",
        mime="text/plain",
    )


st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"] {
        background:
            radial-gradient(ellipse at 82% 12%, rgba(35, 54, 72, .18), transparent 34%),
            #07090d;
    }
    [data-testid="stHeader"] {
        background: rgba(7, 9, 13, .92);
    }
    [data-testid="stSidebar"] {
        border-right: 1px solid #252b34;
    }
    [data-testid="stSidebar"] > div:first-child {
        background: #0c1016;
    }
    .main .block-container {
        max-width: 1540px;
        padding-top: 0;
    }
    .mission-topbar {
        align-items: center;
        border-bottom: 1px solid #20252d;
        color: #e8ebef;
        display: flex;
        font-size: .78rem;
        justify-content: space-between;
        letter-spacing: .12em;
        min-height: 52px;
        text-transform: uppercase;
    }
    .mission-wordmark {
        font-weight: 800;
        letter-spacing: .16em;
    }
    .mission-wordmark span {
        color: #f04438;
        padding: 0 .45rem;
    }
    .mission-live {
        color: #aeb7c2;
        font-size: .68rem;
        letter-spacing: .18em;
    }
    .mission-live i {
        background: #41d98a;
        border-radius: 50%;
        display: inline-block;
        height: 7px;
        margin-right: 9px;
        vertical-align: 1px;
        width: 7px;
    }
    .mission-nav {
        border-bottom: 1px solid #252a32;
        color: #d3d8df;
        display: flex;
        flex-wrap: wrap;
        gap: 2rem;
        letter-spacing: .04em;
        padding: 15px 0;
    }
    .mission-nav b {
        color: #fff;
        font-weight: 600;
    }
    .mission-hero {
        align-items: center;
        background:
            linear-gradient(90deg, rgba(5, 7, 10, .96) 0%, rgba(5, 7, 10, .76) 44%, rgba(5, 7, 10, .18) 100%),
            radial-gradient(ellipse at 76% 88%, rgba(46, 81, 92, .58), transparent 37%),
            radial-gradient(ellipse at 69% 63%, rgba(110, 93, 65, .42), transparent 46%),
            linear-gradient(165deg, #121923 5%, #080b10 65%);
        border-bottom: 1px solid #353b44;
        display: flex;
        justify-content: space-between;
        margin: 0 -1rem 2.4rem;
        min-height: 365px;
        overflow: hidden;
        padding: 3.6rem clamp(1.5rem, 7vw, 7rem);
        position: relative;
    }
    .mission-hero:before {
        background: radial-gradient(ellipse at 50% 100%, transparent 36%, rgba(0, 0, 0, .9) 71%);
        border: 1px solid rgba(200, 220, 230, .26);
        border-radius: 50%;
        content: "";
        height: 420px;
        left: 47%;
        position: absolute;
        top: 60%;
        transform: rotate(-9deg);
        width: 900px;
    }
    .mission-hero:after {
        background-image: radial-gradient(rgba(255,255,255,.62) .7px, transparent .9px);
        background-position: 0 0;
        background-size: 47px 43px;
        content: "";
        inset: 0;
        opacity: .2;
        pointer-events: none;
        position: absolute;
    }
    .mission-copy {
        max-width: 680px;
        position: relative;
        z-index: 1;
    }
    .mission-eyebrow, .section-kicker {
        color: #c5ccd4;
        font-size: .68rem;
        font-weight: 700;
        letter-spacing: .28em;
        text-transform: uppercase;
    }
    .mission-title {
        color: #fff;
        font-size: clamp(4rem, 8vw, 7.3rem);
        font-weight: 800;
        letter-spacing: -.065em;
        line-height: .96;
        margin: 1.1rem 0 1.25rem;
    }
    .mission-subtitle {
        color: #e0e5eb;
        font-size: clamp(1rem, 1.6vw, 1.35rem);
        line-height: 1.55;
        margin-bottom: 1.4rem;
        max-width: 590px;
    }
    .mission-pills {
        color: #c8d0d8;
        display: flex;
        flex-wrap: wrap;
        font-size: .72rem;
        gap: 1.35rem;
        letter-spacing: .12em;
        text-transform: uppercase;
    }
    .mission-pills strong {
        color: #fff;
        font-weight: 650;
    }
    .mission-satellite {
        color: #dce5eb;
        filter: drop-shadow(0 10px 24px rgba(0,0,0,.4));
        margin-right: 1vw;
        opacity: .8;
        position: relative;
        width: min(32vw, 380px);
        z-index: 1;
    }
    .workspace-heading {
        align-items: end;
        display: flex;
        justify-content: space-between;
        margin: 0 0 1rem;
    }
    .workspace-heading h2 {
        color: #f4f6f8;
        font-size: clamp(1.35rem, 2.3vw, 2rem);
        letter-spacing: -.025em;
        margin: .35rem 0 0;
    }
    .workspace-note {
        color: #9da7b2;
        font-size: .8rem;
        letter-spacing: .08em;
        text-transform: uppercase;
    }
    [data-testid="stTabs"] [role="tablist"] {
        border-bottom: 1px solid #282e37;
        gap: 1.5rem;
    }
    [data-testid="stTabs"] button[role="tab"] {
        color: #aab3be;
        font-size: .9rem;
        padding: .8rem .25rem;
    }
    [data-testid="stTabs"] button[aria-selected="true"] {
        color: #fff;
    }
    div[data-testid="stMetric"] {
        background: #11161e;
        border: 1px solid #29313b;
        border-radius: 5px;
        padding: 1rem 1.1rem;
    }
    @media (max-width: 760px) {
        .mission-hero {
            min-height: 330px;
            padding: 2.4rem 1.4rem;
        }
        .mission-satellite {
            opacity: .22;
            position: absolute;
            right: -2rem;
            width: 60vw;
        }
        .mission-hero:before {
            left: 20%;
        }
        .workspace-heading {
            align-items: flex-start;
            flex-direction: column;
            gap: .5rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    """
    <div class="mission-topbar">
      <div class="mission-wordmark">NASA <span>/</span> EARTH OBSERVATION</div>
      <div class="mission-live"><i></i> Mission data console</div>
    </div>
    <div class="mission-nav">
      <b>Explore</b><span>NISAR</span><span>Earth science</span>
      <span>Societal benefits</span><span>Data &amp; tools</span>
      <span>Mission resources</span>
    </div>
    <section class="mission-hero">
      <div class="mission-copy">
        <div class="mission-eyebrow">NASA–ISRO Synthetic Aperture Radar</div>
        <div class="mission-title">NISAR</div>
        <div class="mission-subtitle">
          Observe a changing planet. Explore radar imagery for potential flood
          and wetland surface change.
        </div>
        <div class="mission-pills">
          <span><strong>● Active mission</strong></span>
          <span>L-band + S-band radar</span>
          <span>Earth science</span>
        </div>
      </div>
      <svg class="mission-satellite" viewBox="0 0 360 260" role="img"
           aria-label="Illustration of a radar satellite above Earth">
        <defs>
          <linearGradient id="earth" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0" stop-color="#8e8d77"/>
            <stop offset=".52" stop-color="#425a56"/>
            <stop offset="1" stop-color="#182833"/>
          </linearGradient>
          <linearGradient id="panel" x1="0" x2="1">
            <stop stop-color="#31506b"/>
            <stop offset="1" stop-color="#111e2a"/>
          </linearGradient>
        </defs>
        <path d="M-25 225 Q170 145 390 216 L390 290 L-25 290Z" fill="url(#earth)" opacity=".78"/>
        <path d="M-20 223 Q175 141 390 213" fill="none" stroke="#d1d9d4" stroke-opacity=".52" stroke-width="2"/>
        <g transform="translate(176 125) rotate(-17)">
          <path d="M-122 -22h75v44h-75zM48 -22h75v44H48z" fill="url(#panel)" stroke="#a9bbc4" stroke-opacity=".7"/>
          <path d="M-97 -22v44m25-44v44m25-44v44M73-22v44m25-44v44" stroke="#9bb0ba" stroke-opacity=".58"/>
          <path d="M-47 -9h95v18h-95z" fill="#c6a15f" stroke="#f1d29a" stroke-opacity=".8"/>
          <path d="M0-9V-54m-16-2q16-22 32 0m-42-9q26-34 52 0" fill="none" stroke="#e1e6e5" stroke-width="2"/>
          <circle cy="-54" r="3" fill="#f04438"/>
        </g>
      </svg>
    </section>
    <div class="workspace-heading">
      <div>
        <div class="section-kicker">Mission operations</div>
        <h2>Explore NISAR data</h2>
      </div>
      <div class="workspace-note">Flood &amp; wetland change workspace</div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption(
    "Potential backscatter changes are screening results—not confirmed flood "
    "boundaries or wetland classifications. Validate findings independently."
)

with st.sidebar:
    st.header("Study area")
    st.caption("Example bounds from the NISAR Cookbook. Change them for your event.")
    west = st.number_input("West longitude", value=DEFAULT_BOUNDS[0], format="%.4f")
    south = st.number_input("South latitude", value=DEFAULT_BOUNDS[1], format="%.4f")
    east = st.number_input("East longitude", value=DEFAULT_BOUNDS[2], format="%.4f")
    north = st.number_input("North latitude", value=DEFAULT_BOUNDS[3], format="%.4f")
    threshold_db = st.slider(
        "Potential-change threshold (dB)",
        min_value=0.5,
        max_value=6.0,
        value=1.5,
        step=0.5,
    )
    low_backscatter_threshold_db = st.slider(
        "Low-backscatter cutoff (dB)",
        min_value=-30.0,
        max_value=0.0,
        value=-15.0,
        step=0.5,
        help=(
            "Exploratory cutoff used for water-like screening only. GCOV values and "
            "land-cover conditions vary; adjust this and validate independently."
        ),
    )

bounds = (west, south, east, north)
if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
    st.error("Enter valid bounds: west < east and south < north, within longitude/latitude limits.")
    st.stop()

search_tab, analyze_tab = st.tabs(["Search & download from ASF", "Analyze local scenes"])
with search_tab:
    _search_tab(bounds)
with analyze_tab:
    _analyze_tab(bounds, threshold_db, low_backscatter_threshold_db)
