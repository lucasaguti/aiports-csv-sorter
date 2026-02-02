import csv
import json
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


# ---- Your CSV columns (based on what you provided) ----
LAT_COL = "latitude_deg"
LON_COL = "longitude_deg"
ICAO_COL = "icao_code"

# Optional columns to carry through to output
EXTRA_COLS = ["ident", "name"]


@dataclass(frozen=True)
class Box:
    name: str
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float

    def contains(self, lat: float, lon: float) -> bool:
        # Latitude is always straightforward
        if not (self.min_lat <= lat <= self.max_lat):
            return False

        # Longitude may cross dateline
        if self.min_lon <= self.max_lon:
            return self.min_lon <= lon <= self.max_lon
        else:
            # crosses dateline: accept lon >= min_lon OR lon <= max_lon
            return lon >= self.min_lon or lon <= self.max_lon


def safe_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    s = value.strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def load_boxes(path: str) -> List[Box]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "boxes" not in data or not isinstance(data["boxes"], list):
        raise ValueError("boxes.json must contain a top-level key 'boxes' which is a list.")

    boxes: List[Box] = []
    for i, b in enumerate(data["boxes"]):
        try:
            name = str(b["name"]).strip()
            min_lat = float(b["min_lat"])
            max_lat = float(b["max_lat"])
            min_lon = float(b["min_lon"])
            max_lon = float(b["max_lon"])
        except Exception as e:
            raise ValueError(f"Invalid box entry at index {i}: {b}. Error: {e}")

        if not name:
            raise ValueError(f"Box at index {i} has an empty name.")

        if min_lat > max_lat:
            raise ValueError(f"Box '{name}' has min_lat > max_lat.")

        if not (-90.0 <= min_lat <= 90.0 and -90.0 <= max_lat <= 90.0):
            raise ValueError(f"Box '{name}' has latitude outside [-90, 90].")

        if not (-180.0 <= min_lon <= 180.0 and -180.0 <= max_lon <= 180.0):
            raise ValueError(f"Box '{name}' has longitude outside [-180, 180].")

        boxes.append(Box(name=name, min_lat=min_lat, max_lat=max_lat, min_lon=min_lon, max_lon=max_lon))

    # Ensure box names are unique
    names = [b.name for b in boxes]
    if len(names) != len(set(names)):
        raise ValueError("Box names must be unique.")

    return boxes


def filter_csv(csv_path: str, boxes: List[Box]) -> Tuple[List[Dict[str, str]], Dict[str, List[str]]]:
    """
    Returns:
      - combined_rows: list of rows for output CSV
      - per_box_icaos: dict box_name -> list of ICAO codes
    """
    combined_rows: List[Dict[str, str]] = []
    per_box_icaos: Dict[str, List[str]] = {b.name: [] for b in boxes}

    # For quick de-dup per box (some datasets have repeats)
    per_box_seen: Dict[str, set] = {b.name: set() for b in boxes}

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        # Basic header validation
        required = {LAT_COL, LON_COL, ICAO_COL}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV is missing required columns: {sorted(missing)}. Found: {reader.fieldnames}")

        for row in reader:
            icao = (row.get(ICAO_COL) or "").strip().upper()
            if not icao:
                # Skip rows with empty ICAO
                continue

            lat = safe_float(row.get(LAT_COL))
            lon = safe_float(row.get(LON_COL))
            if lat is None or lon is None:
                # Skip rows with missing/bad coordinates
                continue

            # Check each box
            for b in boxes:
                if b.contains(lat, lon):
                    # Deduplicate per box
                    if icao in per_box_seen[b.name]:
                        continue
                    per_box_seen[b.name].add(icao)
                    per_box_icaos[b.name].append(icao)

                    out = {
                        "box_name": b.name,
                        "icao_code": icao,
                        "latitude_deg": f"{lat}",
                        "longitude_deg": f"{lon}",
                    }
                    for c in EXTRA_COLS:
                        out[c] = (row.get(c) or "").strip()
                    combined_rows.append(out)

    return combined_rows, per_box_icaos


def write_combined_csv(path: str, rows: List[Dict[str, str]]) -> None:
    fieldnames = ["box_name", "icao_code", "latitude_deg", "longitude_deg"] + EXTRA_COLS
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_per_box_json(path: str, per_box: Dict[str, List[str]]) -> None:
    # Sorted lists make diffs/reviews nicer
    per_box_sorted = {k: sorted(v) for k, v in per_box.items()}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(per_box_sorted, f, indent=2)


def main():
    if len(sys.argv) < 3:
        print("Usage: python filter_icao_in_boxes.py <airports.csv> <boxes.json> [out_combined.csv] [out_per_box.json]")
        sys.exit(1)

    csv_path = sys.argv[1]
    boxes_path = sys.argv[2]
    out_csv = sys.argv[3] if len(sys.argv) >= 4 else "icaos_in_boxes.csv"
    out_json = sys.argv[4] if len(sys.argv) >= 5 else "icaos_by_box.json"

    boxes = load_boxes(boxes_path)
    rows, per_box = filter_csv(csv_path, boxes)

    write_combined_csv(out_csv, rows)
    write_per_box_json(out_json, per_box)

    # Summary
    total = sum(len(v) for v in per_box.values())
    print(f"Done. Matched {total} ICAO codes across {len(boxes)} boxes.")
    for b in boxes:
        print(f"  {b.name}: {len(per_box[b.name])} ICAOs")
    print(f"Wrote: {out_csv}")
    print(f"Wrote: {out_json}")


if __name__ == "__main__":
    main()
