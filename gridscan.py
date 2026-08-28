#!/usr/bin/env python3
"""
===============================================================================
OMNIA GRIDSCAN - Geographic Entity Discovery for Formal Verification Corpus
===============================================================================

PURPOSE:
This tool supports OMNIA, a corpus of machine-checked Coq formalizations across
all domains of human knowledge.

This scanner queries Wolfram's geographic database to discover entities within
specified regions. It supports both single-point queries and systematic global
scanning with guaranteed complete spheroid coverage.

MODES:
1. POINT QUERY: Scan a single location with specified radius
2. GLOBAL SCAN: Systematic pole-to-pole scan with complete coverage

GLOBAL SCAN COVERAGE:
- Earth modeled as WGS84 oblate spheroid
- Latitude bands with variable cell counts (fewer at poles, more at equator)
- Cell radii calculated to ensure overlap (no gaps)
- Coverage formula guarantees ratio >= 1.0 (complete coverage)

GRANULARITY LEVELS (for Wolfram entity queries):
- minimal:  Cities, countries, continents only (fast, ~6 types)
- standard: Above + universities, museums, historical sites (~15 types)
- detailed: Above + all infrastructure, natural features (~39 types)
- full:     Every geographic entity type Wolfram supports (~59 types, slow)

IMPORTANT NOTES FOR LLMS:
- Only entities WITHIN the specified radius are returned
- If 0 entities returned, that region is genuinely sparse in Wolfram's data
- Geographic coordinates peg and bound a region for investigation. The
  question is not primarily "what geographic features exist here?" but
  "what rule-systems, institutions, historical events, legal frameworks,
  scientific phenomena, or human practices are associated with this region?"

  A scan returning "University of Bologna" is not an invitation to formalize
  the university's architecture. It is a prompt to consider: what emerged
  from Bologna that has formalizable structure? (The medieval ius commune,
  the oldest university statutes, the Bologna Process for European higher
  education.) The entity is a pointer to a region of human activity.

  Geographic features themselves may also be formalization targets. A
  mountain may have climbing grades, erosion dynamics, jurisdictional
  boundaries. A reef may encode navigation hazards or legal protections.
  But these are instances of the general pattern, not the primary focus.

  The question is: what structure--rules, constraints, classifications,
  processes, decision procedures, state transitions, logical dependencies,
  invariants--exists in or originated from this region?

- Regarding geography: do not claim an entity exists within a scanned region
  unless Wolfram reported it. Research beyond Wolfram to understand what
  an entity involves, but trust Wolfram for what is where.
- This tool is a work in progress - contributions welcome

USAGE:
    # Single point query
    python gridscan.py point <lat> <lon> [radius_km] [granularity]

    # Grid statistics and coverage verification
    python gridscan.py grid [cell_size_deg]

    # Preview scan cells
    python gridscan.py preview [cell_size_deg] [pattern] [limit]

    # Full global scan (outputs JSON per cell)
    python gridscan.py scan [cell_size_deg] [pattern] [granularity]

PATTERNS:
- north_cw:  North pole to south, clockwise (east) longitude progression
- north_ccw: North pole to south, counter-clockwise (west) progression
- south_cw:  South pole to north, clockwise progression
- south_ccw: South pole to north, counter-clockwise progression

EXAMPLES:
    python gridscan.py point 51.51 -0.13 30            # London, 30km
    python gridscan.py point 35.68 139.69 40           # Tokyo, 40km
    python gridscan.py point 40.77 -73.12 50           # Bohemia NY, 50km
    python gridscan.py point 42.44 -76.50 35           # Ithaca NY, 35km
    python gridscan.py point 43.08 -73.79 25           # Saratoga Springs NY, 25km
    python gridscan.py point 37.97 23.73 25 detailed   # Athens, detailed
    python gridscan.py point 36.74 -119.79 40          # Fresno CA, 40km
    python gridscan.py point 34.20 -119.18 30          # Oxnard CA, 30km
    python gridscan.py point 40.59 -122.39 35          # Redding CA, 35km
    python gridscan.py point 29.65 -82.32 30           # Gainesville FL, 30km
    python gridscan.py point 30.42 -87.22 25           # Pensacola FL, 25km
    python gridscan.py point 26.64 -81.87 40           # Fort Myers FL, 40km
    python gridscan.py point -33.87 151.21 35          # Sydney, 35km
    python gridscan.py point 55.75 37.62 20 minimal    # Moscow, minimal
    python gridscan.py point -22.91 -43.17 30 full     # Rio de Janeiro, full
    python gridscan.py grid 10                          # Show 10deg grid stats
    python gridscan.py preview 10 north_cw 5           # Preview first 5 cells
    python gridscan.py scan 10 north_cw minimal        # Full scan, minimal entities

Author: Charles C. Norton
Repository: https://github.com/CharlesCNorton/omnia
License: MIT
Status: WORK IN PROGRESS - much to be done
===============================================================================
"""

import subprocess
import sys
import json
import math
import time
from typing import Generator, Dict, List, Any, Optional

# =============================================================================
# CONSTANTS
# =============================================================================

VALID_PATTERNS = {"north_cw", "north_ccw", "south_cw", "south_ccw"}
"""Set[str]: Valid scan pattern identifiers."""

MIN_CELL_SIZE_DEG = 1.0
MAX_CELL_SIZE_DEG = 90.0
"""float: Bounds for cell size parameter to prevent degenerate grids."""

# WGS84 ellipsoid parameters (standard Earth model)
# Reference: National Geospatial-Intelligence Agency, WGS84 specification
EARTH_EQUATORIAL_RADIUS_KM = 6378.137
"""float: Earth's radius at equator in kilometers (WGS84 semi-major axis)."""

EARTH_POLAR_RADIUS_KM = 6356.752
"""float: Earth's radius at poles in kilometers (WGS84 semi-minor axis)."""

EARTH_MEAN_RADIUS_KM = 6371.0
"""float: Earth's mean radius in kilometers (volumetric mean)."""

# =============================================================================
# LOGGING
# =============================================================================

VERBOSE = False
"""bool: Global verbose output flag."""


def log(msg: str) -> None:
    """
    Print a message to stderr if verbose mode is enabled.

    Args:
        msg: Message to print.
    """
    if VERBOSE:
        print(f"[gridscan] {msg}", file=sys.stderr)


def log_always(msg: str) -> None:
    """
    Print a message to stderr unconditionally.

    Args:
        msg: Message to print.
    """
    print(f"[gridscan] {msg}", file=sys.stderr)


def set_verbose(enabled: bool) -> None:
    """
    Enable or disable verbose output.

    Args:
        enabled: Whether to enable verbose mode.
    """
    global VERBOSE
    VERBOSE = enabled


# =============================================================================
# VALIDATION
# =============================================================================


def validate_coordinates(lat: float, lon: float) -> None:
    """
    Validate latitude and longitude bounds.

    Args:
        lat: Latitude in degrees.
        lon: Longitude in degrees.

    Raises:
        ValueError: If coordinates are out of valid range.
    """
    if not -90 <= lat <= 90:
        raise ValueError(f"Latitude must be between -90 and 90, got {lat}")
    if not -180 <= lon <= 180:
        raise ValueError(f"Longitude must be between -180 and 180, got {lon}")


def validate_cell_size(cell_size_deg: float) -> None:
    """
    Validate cell size is within reasonable bounds.

    Args:
        cell_size_deg: Cell size in degrees.

    Raises:
        ValueError: If cell size is out of valid range.
    """
    if not MIN_CELL_SIZE_DEG <= cell_size_deg <= MAX_CELL_SIZE_DEG:
        raise ValueError(
            f"Cell size must be between {MIN_CELL_SIZE_DEG} and {MAX_CELL_SIZE_DEG}, "
            f"got {cell_size_deg}"
        )


def validate_pattern(pattern: str) -> None:
    """
    Validate scan pattern identifier.

    Args:
        pattern: Pattern string to validate.

    Raises:
        ValueError: If pattern is not recognized.
    """
    if pattern not in VALID_PATTERNS:
        raise ValueError(
            f"Invalid pattern '{pattern}'. Valid patterns: {sorted(VALID_PATTERNS)}"
        )


def validate_radius(radius_km: float) -> None:
    """
    Validate search radius is positive and reasonable.

    Args:
        radius_km: Radius in kilometers.

    Raises:
        ValueError: If radius is invalid.
    """
    if radius_km <= 0:
        raise ValueError(f"Radius must be positive, got {radius_km}")
    if radius_km > EARTH_MEAN_RADIUS_KM * math.pi:
        raise ValueError(f"Radius {radius_km}km exceeds half Earth circumference")


# Entity types organized by query granularity level
# Each level includes all types from previous levels plus additional types
ENTITY_LEVELS: Dict[str, List[str]] = {
    "minimal": [
        "City", "Town", "Village", "Country", "Island", "Ocean"
    ],
    "standard": [
        "City", "Town", "Village", "Country", "Island", "Ocean",
        "AdministrativeDivision", "University", "Museum", "HistoricalSite",
        "ArchaeologicalSite", "HistoricalCountry", "Mountain", "Lake", "River"
    ],
    "detailed": [
        "City", "Town", "Village", "Country", "Island", "Ocean",
        "AdministrativeDivision", "University", "Museum", "HistoricalSite",
        "ArchaeologicalSite", "HistoricalCountry", "Mountain", "Lake", "River",
        "Airport", "Bridge", "Building", "Canal", "Castle", "Cave", "Cemetery",
        "Dam", "Desert", "Forest", "Glacier", "Hospital", "Library",
        "MilitaryBase", "Mine", "Park", "Prison", "Railroad", "Reef",
        "Shipwreck", "Stadium", "Tunnel", "Volcano", "Waterfall"
    ],
    "full": [
        "City", "Town", "Village", "Country", "Island", "Ocean",
        "AdministrativeDivision", "University", "Museum", "HistoricalSite",
        "ArchaeologicalSite", "HistoricalCountry", "Mountain", "Lake", "River",
        "Airport", "AmusementPark", "AstronomicalObservatory", "Beach", "Bridge",
        "BroadcastStation", "Building", "Canal", "Castle", "Cave", "Cemetery",
        "Dam", "Desert", "EarthImpact", "Forest", "GeographicRegion",
        "GeologicalFormation", "Glacier", "Hospital", "Library",
        "MetropolitanArea", "MilitaryBase", "MilitaryConflict", "Mine",
        "Neighborhood", "NuclearExplosion", "NuclearReactor", "NuclearTestSite",
        "OilField", "Park", "ParticleAccelerator", "Prison", "Railroad", "Reef",
        "ReserveLand", "RocketLaunchSite", "Shipwreck", "Stadium", "TideStation",
        "Tunnel", "UnderseaFeature", "Volcano", "Waterfall", "WeatherStation"
    ]
}
"""Dict[str, List[str]]: Wolfram entity types organized by granularity level.

The granularity levels control how many entity types are queried:
- minimal: Fast queries, basic geographic features only
- standard: Balanced queries, includes cultural/historical features
- detailed: Comprehensive queries, includes infrastructure
- full: Exhaustive queries, all supported Wolfram geographic entity types
"""

# =============================================================================
# GRID GENERATION
# =============================================================================
# These functions implement spheroid-aware grid generation that guarantees
# complete Earth surface coverage. The key insight is that longitude lines
# converge at the poles, so fewer cells are needed at high latitudes.


def lat_circumference_km(lat_deg: float) -> float:
    """
    Calculate the circumference of Earth at a given latitude.

    At the equator, this equals the full equatorial circumference.
    At the poles, this approaches zero as longitude lines converge.
    Uses WGS84 oblate spheroid model.

    Args:
        lat_deg: Latitude in degrees (-90 to 90).

    Returns:
        Circumference in kilometers at the specified latitude.

    Example:
        >>> lat_circumference_km(0)    # Equator
        40075.017  # km (approximately)
        >>> lat_circumference_km(60)   # 60degN
        20037.508  # km (approximately half)
        >>> lat_circumference_km(90)   # Pole
        0.0
    """
    lat_rad = math.radians(lat_deg)
    r = EARTH_EQUATORIAL_RADIUS_KM * math.cos(lat_rad)
    return 2 * math.pi * r


def cells_per_band(lat_deg: float, cell_size_deg: float) -> int:
    """
    Calculate the number of longitude cells needed at a given latitude.

    This function ensures approximately equal-area cells across the globe
    by scaling the number of cells proportionally to the circumference
    at each latitude. Near the poles, fewer cells are needed because
    longitude lines converge.

    Args:
        lat_deg: Center latitude of the band in degrees (-90 to 90).
        cell_size_deg: Size of latitude bands in degrees.

    Returns:
        Number of longitude cells needed for this latitude band.
        Minimum is 1 (for polar caps).

    Example:
        >>> cells_per_band(0, 10)    # Equator, 10deg cells
        36
        >>> cells_per_band(60, 10)   # 60degN, 10deg cells
        18
        >>> cells_per_band(85, 10)   # Near pole, 10deg cells
        1
    """
    # Polar caps get a single cell
    if abs(lat_deg) >= 90 - cell_size_deg / 2:
        return 1

    # Scale number of cells by ratio of circumferences
    equator_circumference = lat_circumference_km(0)
    lat_circumference = lat_circumference_km(lat_deg)
    equator_cells = 360 / cell_size_deg
    scaled_cells = equator_cells * (lat_circumference / equator_circumference)

    return max(1, int(round(scaled_cells)))


def cell_radius_km(lat_deg: float, cell_size_deg: float, num_cells: int) -> float:
    """
    Calculate the radius in kilometers needed to cover a grid cell.

    The radius is computed from the cell center to its corner (half the
    diagonal), with a 10% margin added to ensure overlap between adjacent
    cells and prevent gaps in coverage.

    Args:
        lat_deg: Center latitude of the cell in degrees.
        cell_size_deg: Height of the cell in degrees (latitude span).
        num_cells: Number of cells in this latitude band (determines width).

    Returns:
        Radius in kilometers that fully covers the cell with margin.

    Note:
        The 10% margin (1.1 multiplier) ensures complete coverage even
        with floating-point imprecision and edge effects. This results
        in approximately 90% overlap between adjacent cells.
    """
    # Latitude span in km (constant regardless of longitude)
    lat_span_km = (cell_size_deg / 360) * (2 * math.pi * EARTH_MEAN_RADIUS_KM)

    # Longitude span in km (varies with latitude)
    lon_span_deg = 360 / num_cells
    lon_span_km = (lon_span_deg / 360) * lat_circumference_km(lat_deg)

    # Radius = half diagonal, plus 10% margin for overlap
    diagonal = math.sqrt(lat_span_km ** 2 + lon_span_km ** 2)
    return diagonal / 2 * 1.1


def generate_grid(
    cell_size_deg: float = 10,
    pattern: str = "north_cw"
) -> Generator[Dict[str, Any], None, None]:
    """
    Generate grid cells for complete Earth surface coverage.

    Yields cells in a systematic order based on the specified pattern,
    starting from one pole and progressing to the other. The grid
    automatically adjusts cell count per latitude band to maintain
    approximately equal-area cells.

    Args:
        cell_size_deg: Size of latitude bands in degrees. Smaller values
            give finer resolution but more cells. Default 10deg.
        pattern: Scan pattern determining traversal order:
            - "north_cw": Start at North Pole, move south, clockwise longitude
            - "north_ccw": Start at North Pole, move south, counter-clockwise
            - "south_cw": Start at South Pole, move north, clockwise longitude
            - "south_ccw": Start at South Pole, move north, counter-clockwise

    Yields:
        Dict containing cell information:
            - center_lat: Latitude of cell center in degrees
            - center_lon: Longitude of cell center in degrees
            - radius_km: Radius in km that covers this cell
            - band: Latitude band index (0 = starting pole)
            - cell: Cell index within this band
            - total_cells_in_band: Number of cells in this latitude band

    Example:
        >>> for cell in generate_grid(10, "north_cw"):
        ...     print(f"({cell['center_lat']}, {cell['center_lon']})")
        ...     if cell['band'] > 0:  # Just show first two bands
        ...         break
        (85.0, 0.0)
        (75.0, -160.0)
        ...
    """
    validate_cell_size(cell_size_deg)
    validate_pattern(pattern)

    log(f"Generating grid: cell_size={cell_size_deg}deg, pattern={pattern}")

    # Determine latitude traversal direction based on pattern
    if pattern.startswith("north"):
        lat_start = 90 - cell_size_deg / 2
        lat_end = -90 + cell_size_deg / 2
        lat_step = -cell_size_deg
    else:
        lat_start = -90 + cell_size_deg / 2
        lat_end = 90 - cell_size_deg / 2
        lat_step = cell_size_deg

    # Determine longitude traversal direction
    clockwise = pattern.endswith("cw")

    band_idx = 0
    lat = lat_start

    # Iterate through latitude bands
    while (lat_step > 0 and lat <= lat_end) or (lat_step < 0 and lat >= lat_end):
        num_cells = cells_per_band(lat, cell_size_deg)
        lon_step = 360 / num_cells
        radius = cell_radius_km(lat, cell_size_deg, num_cells)

        # Generate longitude positions for this band
        if clockwise:
            lons = [i * lon_step - 180 + lon_step / 2 for i in range(num_cells)]
        else:
            lons = [180 - i * lon_step - lon_step / 2 for i in range(num_cells)]

        # Yield each cell in this latitude band
        for cell_idx, lon in enumerate(lons):
            # Normalize longitude to [-180, 180]
            while lon > 180:
                lon -= 360
            while lon < -180:
                lon += 360

            yield {
                "center_lat": round(lat, 6),
                "center_lon": round(lon, 6),
                "radius_km": round(radius, 2),
                "band": band_idx,
                "cell": cell_idx,
                "total_cells_in_band": num_cells
            }

        band_idx += 1
        lat += lat_step


def grid_stats(cell_size_deg: float = 10) -> Dict[str, Any]:
    """
    Calculate comprehensive statistics for a grid configuration.

    This function analyzes a grid configuration and verifies that it
    provides complete Earth surface coverage. It's used to validate
    grid parameters before running a full scan.

    Args:
        cell_size_deg: Size of latitude bands in degrees.

    Returns:
        Dict containing:
            - cell_size_deg: The input cell size
            - total_bands: Number of latitude bands
            - total_cells: Total number of cells in the grid
            - earth_surface_km2: Earth's surface area in km2
            - covered_area_km2: Total area covered by all cells
            - coverage_ratio: covered_area / earth_surface (should be >= 1.0)
            - complete_coverage: Boolean, True if coverage_ratio >= 1.0
            - bands: List of dicts with per-band statistics

    Example:
        >>> stats = grid_stats(10)
        >>> print(f"Total cells: {stats['total_cells']}")
        Total cells: 408
        >>> print(f"Coverage: {stats['coverage_ratio']}")
        Coverage: 1.927
    """
    validate_cell_size(cell_size_deg)

    log(f"Computing grid statistics for cell_size={cell_size_deg}deg")

    total_cells = 0
    bands = []

    # Calculate statistics for each latitude band
    lat = 90 - cell_size_deg / 2
    while lat >= -90 + cell_size_deg / 2:
        num_cells = cells_per_band(lat, cell_size_deg)
        radius = cell_radius_km(lat, cell_size_deg, num_cells)
        bands.append({
            "lat": round(lat, 1),
            "cells": num_cells,
            "radius_km": round(radius, 1)
        })
        total_cells += num_cells
        lat -= cell_size_deg

    # Calculate coverage verification
    earth_surface_km2 = 4 * math.pi * EARTH_MEAN_RADIUS_KM ** 2
    covered_area = sum(math.pi * b["radius_km"] ** 2 * b["cells"] for b in bands)
    coverage_ratio = covered_area / earth_surface_km2

    log(f"Grid has {total_cells} cells across {len(bands)} bands")
    log(f"Coverage ratio: {coverage_ratio:.3f}")

    return {
        "cell_size_deg": cell_size_deg,
        "total_bands": len(bands),
        "total_cells": total_cells,
        "earth_surface_km2": round(earth_surface_km2, 0),
        "covered_area_km2": round(covered_area, 0),
        "coverage_ratio": round(coverage_ratio, 3),
        "complete_coverage": coverage_ratio >= 1.0,
        "bands": bands
    }


# =============================================================================
# WOLFRAM QUERY
# =============================================================================
# These functions handle communication with Wolfram Language via wolframscript.
# The Wolfram code queries geographic entities and filters them by distance.


def build_wolfram_code(
    lat: float,
    lon: float,
    radius: float,
    entity_types: List[str]
) -> str:
    """
    Build Wolfram Language code for geographic entity query.

    Generates Wolfram code that:
    1. Defines the query position
    2. Queries each entity type using GeoNearest
    3. Filters results to only include entities within the radius
    4. Returns JSON-formatted results

    Args:
        lat: Latitude of query center in degrees.
        lon: Longitude of query center in degrees.
        radius: Search radius in kilometers.
        entity_types: List of Wolfram entity type strings to query.

    Returns:
        String containing valid Wolfram Language code.

    Note:
        The generated code uses Quiet and Check to handle missing data
        gracefully, returning empty results rather than errors.
    """
    types_str = "{" + ", ".join(f'"{t}"' for t in entity_types) + "}"

    log(f"Building Wolfram query for ({lat}, {lon}) radius={radius}km, {len(entity_types)} types")

    return f'''
lat = {lat};
lon = {lon};
radiusKm = {radius};
pos = GeoPosition[{{lat, lon}}];

withinRadius[list_, maxDist_] := Select[list,
  Quiet[Check[QuantityMagnitude[GeoDistance[pos, #], "Kilometers"], Infinity]] <= maxDist &
];

safeName[e_] := Quiet[Check[Module[{{n = CommonName[e]}}, If[StringQ[n], n, None]], None]];
safeNames[list_] := DeleteCases[safeName /@ list, None | Nothing | Null];
safeNearest[type_, n_] := Quiet[Check[GeoNearest[type, pos, n], {{}}]];

entityTypes = {types_str};

results = Association[];
totalCount = 0;

Do[
  entities = withinRadius[safeNearest[etype, 20], radiusKm];
  names = safeNames[entities];
  If[Length[names] > 0,
    results[etype] = names;
    totalCount += Length[names];
  ];
, {{etype, entityTypes}}];

continents = Quiet[Check[GeoNearest["Continent", pos, 1], {{}}]];
continent = If[Length[continents] > 0, safeName[First[continents]], None];

output = <|
  "coordinates" -> <|"lat" -> lat, "lon" -> lon|>,
  "radius_km" -> radiusKm,
  "total_entities" -> totalCount,
  "continent" -> continent,
  "entities" -> results
|>;

Print[ExportString[Select[output, # =!= None &], "JSON", "Compact" -> False]]
'''


def query_point(
    lat: float,
    lon: float,
    radius_km: float = 100,
    granularity: str = "standard"
) -> Dict[str, Any]:
    """
    Query Wolfram for geographic entities within radius of a point.

    Executes a Wolfram Language query via wolframscript to find all
    entities of the specified granularity level within the given radius.
    Only entities actually within the radius are returned (not nearest).

    Args:
        lat: Latitude of query center in degrees (-90 to 90).
        lon: Longitude of query center in degrees (-180 to 180).
        radius_km: Search radius in kilometers. Default 100.
        granularity: Entity type granularity level. One of:
            "minimal", "standard", "detailed", "full". Default "standard".

    Returns:
        Dict containing:
            - coordinates: {lat, lon} of query center
            - radius_km: Search radius used
            - total_entities: Count of entities found
            - continent: Nearest continent name
            - entities: Dict mapping entity types to lists of entity names
            - granularity: Granularity level used
            - entity_types_queried: Number of entity types queried

        On error, returns dict with "error" key containing error message.

    Examples:
        >>> result = query_point(51.51, -0.13, 30, "minimal")
        >>> print(f"Found {result['total_entities']} entities")
        Found 8 entities
        >>> print(result['entities'].get('City', []))
        ['London', 'Westminster', 'Camden']

        >>> result = query_point(35.68, 139.69, 40, "minimal")
        >>> print(result['entities'].get('City', []))
        ['Tokyo', 'Shibuya', 'Shinjuku']

        >>> result = query_point(36.74, -119.79, 40, "minimal")
        >>> print(result['entities'].get('City', []))
        ['Fresno', 'Clovis', 'Sanger']

        >>> result = query_point(34.20, -119.18, 30, "minimal")
        >>> print(result['entities'].get('City', []))
        ['Oxnard', 'Ventura', 'Camarillo']

        >>> result = query_point(40.59, -122.39, 35, "minimal")
        >>> print(result['entities'].get('City', []))
        ['Redding', 'Anderson', 'Shasta Lake']

        >>> result = query_point(40.77, -73.12, 50, "minimal")
        >>> print(result['entities'].get('City', []))
        ['Bohemia', 'Sayville', 'Oakdale']

        >>> result = query_point(29.65, -82.32, 30, "minimal")
        >>> print(result['entities'].get('City', []))
        ['Gainesville', 'Alachua', 'Newberry']

        >>> result = query_point(30.42, -87.22, 25, "minimal")
        >>> print(result['entities'].get('City', []))
        ['Pensacola', 'Gulf Breeze', 'Milton']

        >>> result = query_point(26.64, -81.87, 40, "minimal")
        >>> print(result['entities'].get('City', []))
        ['Fort Myers', 'Cape Coral', 'Lehigh Acres']

        >>> result = query_point(-33.87, 151.21, 35, "minimal")
        >>> print(result['entities'].get('City', []))
        ['Sydney', 'Parramatta', 'Manly']

    Note:
        Timeout scales with granularity: minimal=60s, standard=120s,
        detailed=180s, full=300s.
    """
    validate_coordinates(lat, lon)
    validate_radius(radius_km)

    log(f"Querying point ({lat}, {lon}) radius={radius_km}km granularity={granularity}")

    # Validate granularity level
    if granularity not in ENTITY_LEVELS:
        return {"error": f"Invalid granularity. Choose: {list(ENTITY_LEVELS.keys())}"}

    entity_types = ENTITY_LEVELS[granularity]
    code = build_wolfram_code(lat, lon, radius_km, entity_types)

    # Timeout scales with query complexity
    timeouts = {"minimal": 60, "standard": 120, "detailed": 180, "full": 300}
    timeout = timeouts.get(granularity, 120)

    log(f"Executing wolframscript with timeout={timeout}s")
    start_time = time.time()

    try:
        result = subprocess.run(
            ["wolframscript", "-code", code],
            capture_output=True,
            timeout=timeout,
            encoding='utf-8',
            errors='replace'
        )

        elapsed = time.time() - start_time
        log(f"Wolfram query completed in {elapsed:.2f}s")

        if result.returncode == 0 and result.stdout and result.stdout.strip():
            output = result.stdout.strip()
            # Remove trailing "Null" if present (Wolfram artifact)
            if output.endswith("Null"):
                output = output[:-4].strip()
            if output:
                data = json.loads(output)
                log(f"Found {data.get('total_entities', 0)} entities")
                data["granularity"] = granularity
                data["entity_types_queried"] = len(entity_types)
                return data

        # No results found - return empty structure
        return {
            "coordinates": {"lat": lat, "lon": lon},
            "radius_km": radius_km,
            "granularity": granularity,
            "total_entities": 0,
            "entities": {}
        }

    except subprocess.TimeoutExpired:
        return {
            "error": f"Query timed out ({timeout}s)",
            "coordinates": {"lat": lat, "lon": lon}
        }
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse error: {e}"}
    except FileNotFoundError:
        return {
            "error": "wolframscript not found. Install Wolfram Engine or Mathematica.",
            "coordinates": {"lat": lat, "lon": lon}
        }
    except Exception as e:
        return {
            "error": str(e),
            "coordinates": {"lat": lat, "lon": lon}
        }


# =============================================================================
# CLI
# =============================================================================
# Command-line interface for the gridscan tool.


def print_help() -> None:
    """
    Print help message including module docstring and granularity levels.
    """
    print(__doc__)
    print("Granularity levels:")
    for level, types in ENTITY_LEVELS.items():
        print(f"  {level}: {len(types)} entity types")
    print("\nUse -v or --verbose for detailed output.")


def cmd_point(args: List[str]) -> None:
    """
    Handle the 'point' command for single-location queries.

    Args:
        args: Command-line arguments after 'point'.
              Expected: <lat> <lon> [radius_km] [granularity]
    """
    if len(args) < 2:
        print("Usage: python gridscan.py point <lat> <lon> [radius_km] [granularity]")
        sys.exit(1)

    try:
        lat = float(args[0])
        lon = float(args[1])
    except ValueError as e:
        print(f"Error: Invalid coordinate format: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        validate_coordinates(lat, lon)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        radius = float(args[2]) if len(args) > 2 else 100
    except ValueError as e:
        print(f"Error: Invalid radius format: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        validate_radius(radius)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    granularity = args[3] if len(args) > 3 else "standard"

    if granularity not in ENTITY_LEVELS:
        print(f"Error: Invalid granularity '{granularity}'", file=sys.stderr)
        print(f"Valid options: {list(ENTITY_LEVELS.keys())}", file=sys.stderr)
        sys.exit(1)

    log_always(f"Querying ({lat}, {lon}) radius {radius}km [{granularity}]")
    result = query_point(lat, lon, radius, granularity)
    print(json.dumps(result, indent=2))


def cmd_grid(args: List[str]) -> None:
    """
    Handle the 'grid' command for displaying grid statistics.

    Args:
        args: Command-line arguments after 'grid'.
              Expected: [cell_size_deg]
    """
    try:
        size = float(args[0]) if args else 10
    except ValueError as e:
        print(f"Error: Invalid cell size: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        validate_cell_size(size)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    stats = grid_stats(size)
    print(json.dumps(stats, indent=2))


def cmd_preview(args: List[str]) -> None:
    """
    Handle the 'preview' command for showing sample grid cells.

    Args:
        args: Command-line arguments after 'preview'.
              Expected: [cell_size_deg] [pattern] [limit]
    """
    try:
        size = float(args[0]) if args else 10
    except ValueError as e:
        print(f"Error: Invalid cell size: {e}", file=sys.stderr)
        sys.exit(1)

    pattern = args[1] if len(args) > 1 else "north_cw"

    try:
        limit = int(args[2]) if len(args) > 2 else 10
    except ValueError as e:
        print(f"Error: Invalid limit: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        validate_pattern(pattern)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    log_always(f"First {limit} cells of {size}deg grid [{pattern}]")
    for i, cell in enumerate(generate_grid(size, pattern)):
        if i >= limit:
            break
        print(json.dumps(cell))


def cmd_scan(args: List[str]) -> None:
    """
    Handle the 'scan' command for full global scanning.

    Validates coverage before scanning and refuses to run if
    coverage_ratio < 1.0 (gaps would exist).

    Args:
        args: Command-line arguments after 'scan'.
              Expected: [cell_size_deg] [pattern] [granularity]
    """
    try:
        size = float(args[0]) if args else 10
    except ValueError as e:
        print(f"Error: Invalid cell size: {e}", file=sys.stderr)
        sys.exit(1)

    pattern = args[1] if len(args) > 1 else "north_cw"
    granularity = args[2] if len(args) > 2 else "minimal"

    try:
        validate_cell_size(size)
        validate_pattern(pattern)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if granularity not in ENTITY_LEVELS:
        print(f"Error: Invalid granularity '{granularity}'", file=sys.stderr)
        print(f"Valid options: {list(ENTITY_LEVELS.keys())}", file=sys.stderr)
        sys.exit(1)

    # Validate coverage before scanning
    stats = grid_stats(size)
    if not stats["complete_coverage"]:
        print(
            f"ERROR: {size}deg grid has coverage ratio {stats['coverage_ratio']} < 1.0",
            file=sys.stderr
        )
        print("Gaps may exist. Use smaller cell size.", file=sys.stderr)
        sys.exit(1)

    log_always(f"Scanning {stats['total_cells']} cells, {size}deg grid [{pattern}] [{granularity}]")
    log(f"Coverage ratio: {stats['coverage_ratio']:.3f}")

    scanned = 0
    total_entities = 0
    start_time = time.time()

    # Execute scan, outputting one JSON object per cell
    for cell in generate_grid(size, pattern):
        result = query_point(
            cell["center_lat"],
            cell["center_lon"],
            cell["radius_km"],
            granularity
        )
        result["grid_cell"] = cell
        print(json.dumps(result))
        sys.stdout.flush()  # Ensure immediate output for piping

        scanned += 1
        total_entities += result.get("total_entities", 0)

        if scanned % 10 == 0:
            elapsed = time.time() - start_time
            rate = scanned / elapsed * 60 if elapsed > 0 else 0
            log(f"Progress: {scanned}/{stats['total_cells']} cells, {total_entities} entities, {rate:.1f} cells/min")

    elapsed = time.time() - start_time
    log_always(f"Scan complete: {scanned} cells, {total_entities} entities in {elapsed:.1f}s")


if __name__ == "__main__":
    # Check for verbose flag
    if "-v" in sys.argv or "--verbose" in sys.argv:
        set_verbose(True)
        sys.argv = [a for a in sys.argv if a not in ("-v", "--verbose")]

    if len(sys.argv) < 2:
        print_help()
        sys.exit(0)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == "point":
        cmd_point(args)
    elif cmd == "grid":
        cmd_grid(args)
    elif cmd == "preview":
        cmd_preview(args)
    elif cmd == "scan":
        cmd_scan(args)
    elif cmd in ("help", "-h", "--help"):
        print_help()
    else:
        print(f"Unknown command: {cmd}")
        print("Commands: point, grid, preview, scan, help")
        sys.exit(1)
