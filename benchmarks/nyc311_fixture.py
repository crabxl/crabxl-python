"""Build the NYC 311 read benchmark file.

The file has the same shape as the sample in the calamine README: 1,000,000
service requests with the 41 columns of the original export. The script takes
the first 100,000 requests of January in each year 2010 to 2019 from the NYC
Open Data dataset "311 Service Requests from 2010 to 2019" (76ig-c548), ordered
by creation time and unique key. A query over a full year times out on the
server, so the script reads only January.

XlsxWriter writes the file in its default mode, so text is in a shared string
table, as in files that Excel saves. This needs several GiB of memory.

Usage:
    python benchmarks/nyc311_fixture.py --cache /tmp/nyc311 --output nyc311-1m.xlsx
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import http.client
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

DATASET = "https://data.cityofnewyork.us/resource/76ig-c548.csv"
YEARS = range(2010, 2020)
ROWS_PER_YEAR = 100_000
PAGE_ROWS = 25_000

COLUMNS = [
    "unique_key", "created_date", "closed_date", "agency", "agency_name", "complaint_type",
    "descriptor", "location_type", "incident_zip", "incident_address", "street_name",
    "cross_street_1", "cross_street_2", "intersection_street_1", "intersection_street_2",
    "address_type", "city", "landmark", "facility_type", "status", "due_date",
    "resolution_description", "resolution_action_updated_date", "community_board", "bbl",
    "borough", "x_coordinate_state_plane", "y_coordinate_state_plane", "open_data_channel_type",
    "park_facility_name", "park_borough", "vehicle_type", "taxi_company_borough",
    "taxi_pick_up_location", "bridge_highway_name", "bridge_highway_direction", "road_ramp",
    "bridge_highway_segment", "latitude", "longitude", "location",
]  # fmt: skip

DATES = {"created_date", "closed_date", "due_date", "resolution_action_updated_date"}
INTEGERS = {
    "unique_key",
    "incident_zip",
    "bbl",
    "x_coordinate_state_plane",
    "y_coordinate_state_plane",
}
FLOATS = {"latitude", "longitude"}


def fetch(year: int, offset: int, limit: int) -> bytes:
    query = urllib.parse.urlencode(
        {
            "$select": ",".join(COLUMNS),
            "$where": f"created_date between '{year}-01-01' and '{year}-01-31T23:59:59'",
            "$order": "created_date,unique_key",
            "$limit": limit,
            "$offset": offset,
        }
    )
    for attempt in range(5):
        try:
            with urllib.request.urlopen(f"{DATASET}?{query}", timeout=600) as response:
                return response.read()
        except (OSError, http.client.HTTPException) as error:
            print(f"retry {year} at {offset}: {error}", file=sys.stderr, flush=True)
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"cannot download {year} at offset {offset}")


def download(cache: Path) -> list[Path]:
    """Download each year in pages. The server closes large requests."""
    cache.mkdir(parents=True, exist_ok=True)
    paths = []
    for year in YEARS:
        path = cache / f"{year}.csv"
        if not path.exists():
            print(f"downloading {year}", file=sys.stderr, flush=True)
            parts = []
            for offset in range(0, ROWS_PER_YEAR, PAGE_ROWS):
                page = fetch(year, offset, PAGE_ROWS).decode("utf-8")
                header, _, body = page.partition("\n")
                if not parts:
                    parts.append(header + "\n")
                parts.append(body)
            text = "".join(parts)
            rows = sum(1 for _ in csv.reader(text.splitlines(keepends=True))) - 1
            if rows != ROWS_PER_YEAR:
                raise RuntimeError(f"{year} has {rows} rows, not {ROWS_PER_YEAR}")
            path.write_text(text, encoding="utf-8")
        paths.append(path)
    return paths


def convert(name: str, text: str):
    """Return the typed value for one CSV field, or None for an empty field."""
    if text == "":
        return None
    if name in DATES:
        return dt.datetime.fromisoformat(text)
    if name in INTEGERS and text.isdigit():
        return int(text)
    if name in FLOATS:
        try:
            return float(text)
        except ValueError:
            return text
    return text


def build(paths: list[Path], output: Path) -> dict:
    import xlsxwriter

    book = xlsxwriter.Workbook(str(output))
    sheet = book.add_worksheet("NYC_311_SR_2010-2019-sample-1M")
    date_format = book.add_format({"num_format": "yyyy-mm-dd hh:mm:ss"})
    sheet.write_row(0, 0, COLUMNS)
    values = len(COLUMNS)
    row_index = 1
    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            header = next(reader)
            if header != COLUMNS:
                raise RuntimeError(f"unexpected columns in {path}")
            for record in reader:
                for column, (name, text) in enumerate(zip(COLUMNS, record)):
                    value = convert(name, text)
                    if value is None:
                        continue
                    if isinstance(value, dt.datetime):
                        sheet.write_datetime(row_index, column, value, date_format)
                    elif isinstance(value, str):
                        sheet.write_string(row_index, column, value)
                    else:
                        sheet.write_number(row_index, column, value)
                    values += 1
                row_index += 1
    book.close()
    return {"rows": row_index, "columns": len(COLUMNS), "values": values}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--cache", required=True, help="directory for the downloaded CSV files"
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    summary = build(download(Path(args.cache)), Path(args.output))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
