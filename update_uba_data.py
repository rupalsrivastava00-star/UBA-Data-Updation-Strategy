import os
import time
import zipfile
import pandas as pd
import requests

# Verified UBA endpoint for annual balances
API_URL = "https://luftdaten.umweltbundesamt.de/api/air-data/v4/annualbalances/json"
TARGET_STATIONS = ["1613", "1647", "1665", "1670"]

# Query historical data from 2016 up through 2027
YEARS = range(2016, 2028)

# Official UBA component IDs mapping to pollutants
POLLUTANTS = {
    1: "PM10", 2: "CO", 3: "O3", 4: "SO2", 5: "NO2",
    6: "PB", 7: "BAP", 8: "BEN", 9: "PM2.5", 10: "AS", 11: "CD", 12: "NI"
}

def fetch_fail_safe_data(component_id, year):
    """
    Fetches raw annual balance data from the UBA API for a given pollutant and year,
    filtering specifically for our TARGET_STATIONS.
    """
    params = {"component": component_id, "year": year, "lang": "en"}
    extracted_rows = []
    try:
        response = requests.get(API_URL, params=params, timeout=20)
        if response.status_code != 200:
            return []
        
        payload = response.json()
        if isinstance(payload, dict) and "data" in payload:
            indices = payload.get("indices", [])
            data_block = payload.get("data", [])
            items = data_block.items() if isinstance(data_block, dict) else [(None, r) for r in data_block]
            
            for key, row in items:
                row_list = list(row)
                matched_station = None
                
                # Check if this row belongs to our target stations (using row key or internal values)
                if key and str(key) in TARGET_STATIONS:
                    matched_station = str(key)
                else:
                    for item in row_list:
                        if str(item) in TARGET_STATIONS:
                            matched_station = str(item)
                            break
                
                # If a station matches, align the columns using the API indices
                if matched_station:
                    row_dict = {
                        "Year": int(year),
                        "Station ID": int(matched_station)
                    }
                    if len(row_list) == len(indices) - 1 and key is not None:
                        row_dict[indices[0]] = key
                        for idx, val in enumerate(row_list):
                            if idx + 1 < len(indices):
                                row_dict[indices[idx + 1]] = val
                    else:
                        for idx, col_name in enumerate(indices):
                            if idx < len(row_list):
                                row_dict[col_name] = row_list[idx]
                    extracted_rows.append(row_dict)
        return extracted_rows
    except Exception as e:
        print(f"  -> Connection or parsing error: {e}")
        return []

def main():
    print("=== Starting UBA Air Quality Extraction ===")
    
    # Establish local data folder directory for output
    output_dir = "data"
    os.makedirs(output_dir, exist_ok=True)
    generated_files = []
    
    for comp_id, comp_code in POLLUTANTS.items():
        print(f"Scanning Pollutant: {comp_code}...")
        all_records = []
        for year in YEARS:
            records = fetch_fail_safe_data(comp_id, year)
            if records:
                print(f" -> Found data for year {year}")
            all_records.extend(records)
            time.sleep(0.1)  # Polite network spacing to avoid rate limits
            
        if all_records:
            df = pd.DataFrame(all_records)
            fixed_cols = ["Year", "Station ID"]
            other_cols = [c for c in df.columns if c not in fixed_cols]
            df = df[fixed_cols + other_cols]
            df.sort_values(by=["Station ID", "Year"], inplace=True)
            
            # Save files cleanly inside our data directory
            filename = os.path.join(output_dir, f"leipzig_raw_{comp_code}.csv")
            df.to_csv(filename, index=False, encoding="utf-8-sig")
            generated_files.append(filename)
            print(f" -> SUCCESS: Saved {filename} ({len(df)} total data rows)\n")
        else:
            print(f" -> No records found in database for {comp_code}\n")

    if generated_files:
        zip_filename = os.path.join(output_dir, "leipzig_complete_raw_data.zip")
        print(f"=== Bundling all sheets into final delivery archive: {zip_filename} ===")
        with zipfile.ZipFile(zip_filename, 'w') as archive:
            for file in generated_files:
                # Add file inside the zip without storing absolute folder paths
                archive.write(file, os.path.basename(file))
                os.remove(file)
        print("=== Complete! New data file compiled in 'data/' folder. ===")
    else:
        print("\nExtraction failed to capture data rows. Verify your target list and connection.")

if __name__ == "__main__":
    main()
