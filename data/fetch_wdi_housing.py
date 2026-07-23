#!/usr/bin/env python3
"""Download and assemble a public World Bank housing-services panel for Africa."""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

OUTPUT_DIR = Path(__file__).parent
BASE_URL = "https://api.worldbank.org/v2"
INDICATORS = {
    "water_access_pct": "SH.H2O.BASW.ZS",
    "sanitation_access_pct": "SH.STA.BASS.ZS",
    "electricity_access_pct": "EG.ELC.ACCS.ZS",
    "gdp_per_capita_constant_usd": "NY.GDP.PCAP.KD",
    "urban_population_pct": "SP.URB.TOTL.IN.ZS",
    "population_density": "EN.POP.DNST",
    "population_total": "SP.POP.TOTL",
}
AFRICA_CODES = {
    "AGO", "BEN", "BWA", "BFA", "BDI", "CMR", "CPV", "CAF", "TCD", "COM", "COG", "COD", "CIV", "DJI", "EGY", "GNQ", "ERI", "SWZ", "ETH", "GAB", "GMB", "GHA", "GIN", "GNB", "KEN", "LSO", "LBR", "LBY", "MDG", "MWI", "MLI", "MRT", "MUS", "MAR", "MOZ", "NAM", "NER", "NGA", "RWA", "STP", "SEN", "SYC", "SLE", "SOM", "ZAF", "SSD", "SDN", "TZA", "TGO", "TUN", "UGA", "ZMB", "ZWE",
}


def get_json(url: str):
    request = Request(url, headers={"User-Agent": "QM640-capstone-research/1.0"})
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def fetch_indicator(code: str) -> list[dict]:
    url = f"{BASE_URL}/country/all/indicator/{code}?format=json&per_page=20000"
    payload = get_json(url)
    return payload[1]


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    values: dict[tuple[str, int], dict[str, object]] = {}
    indicator_meta: dict[str, object] = {}

    for name, code in INDICATORS.items():
        rows = fetch_indicator(code)
        indicator_meta[name] = {"code": code, "rows_received": len(rows)}
        for row in rows:
            country_code = row.get("countryiso3code")
            year_value = row.get("date")
            value = row.get("value")
            if country_code not in AFRICA_CODES or value is None or not str(year_value).isdigit():
                continue
            year = int(year_value)
            if not 2000 <= year <= 2024:
                continue
            key = (country_code, year)
            record = values.setdefault(key, {"country_code": country_code, "year": year})
            record[name] = value
            record["country_name"] = row["country"]["value"]

    fields = ["country_code", "country_name", "year", *INDICATORS.keys(), "housing_service_deprivation_pct"]
    output_rows: list[dict[str, object]] = []
    for record in values.values():
        required = [record.get(name) for name in ("water_access_pct", "sanitation_access_pct", "electricity_access_pct")]
        if all(value is not None for value in required):
            record["housing_service_deprivation_pct"] = round(sum(100 - float(value) for value in required) / 3, 4)
        else:
            record["housing_service_deprivation_pct"] = None
        output_rows.append(record)

    output_rows.sort(key=lambda row: (str(row["country_name"]), int(row["year"])))
    csv_path = OUTPUT_DIR / "africa_housing_services_panel.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)

    complete_target = [row for row in output_rows if row["housing_service_deprivation_pct"] is not None]
    complete_all = [row for row in complete_target if all(row.get(name) is not None for name in INDICATORS)]
    audit = {
        "download_date": date.today().isoformat(),
        "source": "World Bank World Development Indicators API",
        "source_url": "https://data.worldbank.org/",
        "license": "CC BY-4.0",
        "indicator_metadata": indicator_meta,
        "african_country_codes": sorted(AFRICA_CODES),
        "rows_written": len(output_rows),
        "target_complete_rows": len(complete_target),
        "complete_model_rows": len(complete_all),
        "country_count": len({row["country_code"] for row in output_rows}),
        "year_min": min(row["year"] for row in output_rows),
        "year_max": max(row["year"] for row in output_rows),
        "target_definition": "Mean of 100 minus basic drinking-water, basic sanitation, and electricity access percentages.",
        "target_caveat": "This is a country-year service-deprivation index, not a household-level deprivation measure.",
    }
    (OUTPUT_DIR / "dataset_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
