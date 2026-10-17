"""Map panels: decide whether a dimension holds places, and match its values to boundaries.

A dimension gets a map only when its values are recognisably places: at least 85% of its records
name a country (or, for the countries in geo/states-50m.geojson, a state or province) and at least
three regions are matched (six when the column holds only codes like "CA", "TX"). Detection reads the
values, not column names, so "Region = North / South" or "City" stay plain breakdowns. Boundaries are Natural Earth (public domain), bundled in backend/geo/
so maps work offline in exported reports.
"""

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from model import dimensions
from profile import q

GEO_DIR = Path(__file__).parent / "geo"
WORLD = "world"
MIN_COVERAGE = 0.85
MIN_REGIONS = 3
MIN_CODE_REGIONS = 6

# common spellings that differ from the Natural Earth name; values are ISO 3166 alpha-3 codes
ALIASES = {
    "USA": "USA", "US": "USA", "U.S.": "USA", "U.S.A.": "USA", "United States": "USA",
    "United States of America": "USA", "UK": "GBR", "U.K.": "GBR", "United Kingdom": "GBR",
    "Great Britain": "GBR", "Britain": "GBR", "Russian Federation": "RUS", "South Korea": "KOR",
    "Republic of Korea": "KOR", "Korea South": "KOR", "North Korea": "PRK", "Korea North": "PRK",
    "DPRK": "PRK", "Viet Nam": "VNM", "Iran, Islamic Republic of": "IRN", "Lao PDR": "LAO",
    "Czech Republic": "CZE", "Ivory Coast": "CIV", "Côte d'Ivoire": "CIV", "DR Congo": "COD",
    "DRC": "COD", "Democratic Republic of the Congo": "COD", "Democratic Republic of Congo": "COD",
    "Congo, Democratic Republic": "COD", "Congo Kinshasa": "COD", "Republic of the Congo": "COG",
    "Congo Brazzaville": "COG", "United Republic of Tanzania": "TZA", "Macedonia": "MKD",
    "North Macedonia": "MKD", "Swaziland": "SWZ", "Eswatini": "SWZ", "Burma": "MMR", "Türkiye": "TUR",
    "Turkiye": "TUR", "The Bahamas": "BHS", "The Gambia": "GMB", "East Timor": "TLS",
    "Timor-Leste": "TLS", "State of Palestine": "PSE", "Palestine": "PSE", "Holland": "NLD",
    "The Netherlands": "NLD", "UAE": "ARE", "United Arab Emirates": "ARE", "Kyrgyz Republic": "KGZ",
    "Bosnia and Herzegovina": "BIH", "Trinidad and Tobago": "TTO", "Vatican": "VAT", "Holy See": "VAT",
}
# countries Natural Earth leaves without ISO codes ("-99")
MISSING_CODES = {"France": ("FR", "FRA"), "Norway": ("NO", "NOR"), "Kosovo": ("XK", "XKX")}


def norm(text: str) -> str:
    """Lower-case, accent-free, punctuation-free form used for name matching."""
    s = unicodedata.normalize("NFKD", str(text))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", s.lower().replace("&", " and ")).strip()


@lru_cache(maxsize=None)
def _countries() -> list[dict]:
    return json.loads((GEO_DIR / "countries-110m.geojson").read_text())["features"]


@lru_cache(maxsize=None)
def _states() -> list[dict]:
    return json.loads((GEO_DIR / "states-50m.geojson").read_text())["features"]


def keys() -> list[str]:
    """Boundary sets a map can use: the world, plus one per country with state/province boundaries."""
    return [WORLD] + [f"states-{iso}" for iso in sorted({f["properties"]["iso_a2"] for f in _states()})]


@lru_cache(maxsize=None)
def _index(key: str) -> tuple[dict, dict]:
    """(names, codes): normalised name -> region name, and upper-case code -> region name."""
    names: dict[str, str] = {}
    codes: dict[str, str] = {}
    if key == WORLD:
        for f in _countries():
            p = f["properties"]
            name = p["NAME"]
            for n in (p.get("NAME"), p.get("NAME_LONG"), p.get("ADMIN")):
                if n:
                    names.setdefault(norm(n), name)
            for c in (p.get("ISO_A2"), p.get("ISO_A3"), *MISSING_CODES.get(name, ())):
                if c and c != "-99":
                    codes.setdefault(c, name)
        for spelling, iso3 in ALIASES.items():
            if iso3 in codes:
                names.setdefault(norm(spelling), codes[iso3])
    else:
        iso2 = key.removeprefix("states-")
        for f in _states():
            p = f["properties"]
            if p["iso_a2"] != iso2:
                continue
            names.setdefault(norm(p["name"]), p["name"])
            codes.setdefault(p["iso_3166_2"].split("-")[-1], p["name"])
    return names, codes


def _lookup_via(key: str, label) -> tuple[str | None, str]:
    """(region, how): how is "name", "code2"/"code3" (matched as a code), or "" when unmatched."""
    names, codes = _index(key)
    text = str(label).strip()
    region = names.get(norm(text))
    if region:
        return region, "name"
    # codes only when written as codes ("IN", "USA"), so the word "in" doesn't become India
    if text.isupper() and 2 <= len(text) <= 3 and text in codes:
        return codes[text], f"code{len(text)}"
    return None, ""


def _lookup(key: str, label) -> str | None:
    return _lookup_via(key, label)[0]


def match(key: str, labels: list) -> tuple[dict, list]:
    """Map each label to a region name. Returns ({label: region}, [unmatched labels])."""
    matches, missing = {}, []
    for label in labels:
        region = _lookup(key, label)
        if region:
            matches[label] = region
        else:
            missing.append(label)
    return matches, missing


def _best_fit(rows: list) -> dict | None:
    total = sum(n for _, n in rows)
    best = None
    for key in keys():
        hit, regions, how = 0, set(), set()
        for label, n in rows:
            region, via = _lookup_via(key, label)
            if region:
                hit += n
                regions.add(region)
                how.add(via)
        coverage = hit / total if total else 0
        # short codes collide with ordinary abbreviations (HR, IT, FIN are also departments): a column of
        # codes only counts when it names enough regions
        need = MIN_REGIONS if "name" in how else MIN_CODE_REGIONS
        if coverage >= MIN_COVERAGE and len(regions) >= need and (best is None or coverage > best["coverage"]):
            best = {"geo": key, "coverage": round(coverage, 3), "regions": len(regions)}
    return best


def fit_dimension(ds, scope: dict, name: str) -> dict | None:
    """Which boundary set (if any) this dimension's values fit, with coverage and region count."""
    rows = ds.query(f"SELECT CAST({q(name)} AS VARCHAR), count(*) FROM {q(scope['view'])} "
                    f"WHERE {q(name)} IS NOT NULL GROUP BY 1")["rows"]
    return _best_fit(rows)


def detect(ds, scope: dict) -> list[dict]:
    """Dimensions of this scope whose values are places, best-covered first."""
    fits = []
    for d in dimensions(scope):
        fit = fit_dimension(ds, scope, d["name"])
        if fit:
            fits.append({"dim": d["name"], "label": d["label"], **fit})
    return sorted(fits, key=lambda f: -f["coverage"])


@lru_cache(maxsize=None)
def boundaries(key: str) -> dict:
    """GeoJSON for one boundary set, with a single `name` property the chart matches regions on."""
    if key not in keys():
        raise KeyError(key)
    if key == WORLD:
        src = [(f, f["properties"]["NAME"]) for f in _countries()]
    else:
        iso2 = key.removeprefix("states-")
        src = [(f, f["properties"]["name"]) for f in _states() if f["properties"]["iso_a2"] == iso2]
    return {"type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": {"name": name}, "geometry": f["geometry"]} for f, name in src]}


def used_boundaries(panels: dict) -> dict:
    """{key: GeoJSON} for every map panel in a dashboard — embedded in exports so they render offline."""
    out = {}
    for p in panels.values():
        key = (p.get("map") or {}).get("geo")
        if key and key not in out:
            out[key] = boundaries(key)
    return out
