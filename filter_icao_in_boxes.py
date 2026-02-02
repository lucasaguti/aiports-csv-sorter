import csv
import json
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional


LAT_COL = "latitude_deg"
LON_COL = "longitude_deg"
ICAO_COL = "icao_code"
EXTRA_COLS = ["ident", "name"]  # keep or remove as you like


@dataclass(frozen=True)
class Box:
    name: str
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float

    def contains(self, lat: float, lon: float) -> bool:
        if not (self.min_lat <= lat <= self.max_lat):
            return False

        # handle normal vs dateline-crossing boxes
        if self.min_lon <= self.max_lon:
            return self.min_lon <= lon <= self.max_lon
        else:
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

        boxes.append(Box(name, min_lat, max_lat, min_lon, max_lon))

    # ensure unique names
    names = [b.name for b in boxes]
    if len(names) != len(set(names)):
        raise ValueError("Box names must be unique.")

    return boxes


def main():
    if len(sys.argv) < 3:
        print("Usage: python filter_icao_in_boxes.py <airports.csv> <boxes.json> [out.csv]")
        sys.exit(1)

    csv_path = sys.argv[1]
    boxes_path = sys.argv[2]
    out_csv = sys.argv[3] if len(sys.argv) >= 4 else "icaos_in_boxes.csv"

    boxes = load_boxes(boxes_path)

    # output rows + per-box counts
    rows: List[Dict[str, str]] = []
    per_box_seen = {b.name: set() for b in boxes}
    per_box_count = {b.name: 0 for b in boxes}

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        required = {LAT_COL, LON_COL, ICAO_COL}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV missing required columns: {sorted(missing)}. Found: {reader.fieldnames}")

        for row in reader:
            icao = (row.get(ICAO_COL) or "").strip().upper()
            if not icao:
                continue

            lat = safe_float(row.get(LAT_COL))
            lon = safe_float(row.get(LON_COL))
            if lat is None or lon is None:
                continue

            for b in boxes:
                if b.contains(lat, lon):
                    if icao in per_box_seen[b.name]:
                        continue
                    per_box_seen[b.name].add(icao)
                    per_box_count[b.name] += 1

                    out = {
                        "box_name": b.name,
                        "icao_code": icao,
                        "latitude_deg": f"{lat}",
                        "longitude_deg": f"{lon}",
                    }
                    for c in EXTRA_COLS:
                        out[c] = (row.get(c) or "").strip()
                    rows.append(out)

    # sort nicely for Excel
    rows.sort(key=lambda r: (r["box_name"], r["icao_code"]))

    fieldnames = ["box_name", "icao_code", "latitude_deg", "longitude_deg"] + EXTRA_COLS
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    total = sum(per_box_count.values())
    print(f"Done. Matched {total} ICAO codes across {len(boxes)} boxes.")
    for b in boxes:
        print(f"  {b.name}: {per_box_count[b.name]} ICAOs")
    print(f"Wrote: {out_csv}")


if __name__ == "__main__":
    main()
