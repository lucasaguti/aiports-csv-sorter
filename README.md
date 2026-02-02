1) Generate icaos_in_boxes.csv from airports.csv + boxes.json

Inputs: airports.csv, boxes.json
Output: icaos_in_boxes.csv

python filter_icao_in_boxes.py airports.csv boxes.json

Open in Excel:

start icaos_in_boxes.csv

2) Generate corridors_with_icao_points.geojson from corridors.geojson + icaos_in_boxes.csv

Inputs: corridors.geojson, icaos_in_boxes.csv
Output: corridors_with_icao_points.geojson

python add_icao_points_from_csv_to_geojson.py


Open in Notepad (for copy/paste into geojson.io):

notepad corridors_with_icao_points.geojson


Or copy GeoJSON straight to clipboard:

cat corridors_with_icao_points.geojson | clip

3) Typical end-to-end run (copy/paste)
cd ~/projects/airports-csv-sorter
python filter_icao_in_boxes.py airports.csv boxes.json
python add_icao_points_from_csv_to_geojson.py
start icaos_in_boxes.csv
cat corridors_with_icao_points.geojson | clip
