import csv
import json
from collections import defaultdict

# Inputs
INPUT_GEOJSON = "corridors.geojson"
INPUT_CSV = "icaos_in_boxes.csv"

# Output
OUTPUT_GEOJSON = "corridors_with_icao_points.geojson"

# Expected CSV columns (from your script)
BOX_COL = "box_name"
ICAO_COL = "icao_code"
LAT_COL = "latitude_deg"
LON_COL = "longitude_deg"


def safe_float(s):
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def main():
    # Load corridor polygons geojson
    with open(INPUT_GEOJSON, "r", encoding="utf-8") as f:
        gj = json.load(f)

    if gj.get("type") != "FeatureCollection" or "features" not in gj:
        raise ValueError("Input geojson must be a FeatureCollection with a 'features' array.")

    # Read ICAO points from CSV and dedupe by ICAO
    # Keep track of which boxes each ICAO belongs to
    icao_to_data = {}  # icao -> {"lat": .., "lon": .., "boxes": set()}
    rows_read = 0
    rows_used = 0

    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {BOX_COL, ICAO_COL, LAT_COL, LON_COL}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV missing required columns: {sorted(missing)}. Found: {reader.fieldnames}")

        for row in reader:
            rows_read += 1

            icao = (row.get(ICAO_COL) or "").strip().upper()
            box = (row.get(BOX_COL) or "").strip()

            lat = safe_float(row.get(LAT_COL))
            lon = safe_float(row.get(LON_COL))

            # Skip incomplete rows
            if not icao or not box or lat is None or lon is None:
                continue

            # Basic sanity bounds
            if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                continue

            if icao not in icao_to_data:
                icao_to_data[icao] = {"lat": lat, "lon": lon, "boxes": set()}
            else:
                # If the same ICAO shows slightly different coords across boxes, keep the first.
                pass

            icao_to_data[icao]["boxes"].add(box)
            rows_used += 1

    # Build Point features
    point_features = []
    for icao in sorted(icao_to_data.keys()):
        lat = icao_to_data[icao]["lat"]
        lon = icao_to_data[icao]["lon"]
        boxes = sorted(icao_to_data[icao]["boxes"])

        # GeoJSON coordinate order is [lon, lat]
        feat = {
            "type": "Feature",
            "id": f"ICAO_{icao}",
            "properties": {
                "type": "airport",
                "icao": icao,
                "boxes": boxes,
                "box_count": len(boxes),
            },
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat],
            },
        }
        point_features.append(feat)

    # Append points after polygons
    gj["features"].extend(point_features)

    with open(OUTPUT_GEOJSON, "w", encoding="utf-8") as f:
        json.dump(gj, f, ensure_ascii=False, indent=2)

    print(f"CSV rows read: {rows_read}")
    print(f"CSV rows used (box matches): {rows_used}")
    print(f"Unique ICAO points added: {len(point_features)}")
    print(f"Wrote: {OUTPUT_GEOJSON}")


if __name__ == "__main__":
    main()
