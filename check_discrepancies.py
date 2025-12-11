"""
Script to find discrepancies between:
1. county_adjacency.txt (FIPS codes)
2. 2024 election data (FIPS codes)
3. counties.geojson (GEOID)
"""

import json
import csv

# 1. Load FIPS from county_adjacency.txt
adjacency_fips = set()
for line in open('data/county_adjacency.txt'):
    parts = line.split('|')
    county_id = parts[1]
    adjacent_id = parts[3]

    # Extract state from county name
    county_state = parts[0].split(', ')[1] if ', ' in parts[0] else ''
    adjacent_state = parts[2].split(', ')[1] if ', ' in parts[2] else ''

    # Skip Alaska and Hawaii
    if county_state not in ['AK', 'HI']:
        adjacency_fips.add(county_id)
    if adjacent_state not in ['AK', 'HI']:
        adjacency_fips.add(adjacent_id)

print(f"County adjacency: {len(adjacency_fips)} unique FIPS codes (excluding AK/HI)")

# 2. Load FIPS from 2024 election data
election_fips = set()
election_data = {}
with open('data/2024_US_County_Level_Presidential_Results.csv', 'r') as f:
    reader = csv.reader(f)
    next(reader)  # skip header
    for row in reader:
        state_name, county_fips, county_name = row[0], row[1], row[2]
        # Skip Alaska and Hawaii
        if state_name not in ['Alaska', 'Hawaii']:
            election_fips.add(county_fips)
            election_data[county_fips] = (state_name, county_name)

print(f"2024 Election data: {len(election_fips)} unique FIPS codes (excluding AK/HI)")

# 3. Load GEOID from counties.geojson
with open('data/counties.geojson', 'r') as f:
    geojson = json.load(f)

geojson_geoids = set()
geojson_data = {}
for feature in geojson['features']:
    geoid = feature['properties']['GEOID']
    name = feature['properties'].get('NAME', 'Unknown')
    state_fp = feature['properties'].get('STATEFP', '')
    # Skip Alaska (02) and Hawaii (15)
    if state_fp not in ['02', '15']:
        geojson_geoids.add(geoid)
        geojson_data[geoid] = (name, state_fp)

print(f"GeoJSON: {len(geojson_geoids)} unique GEOIDs (excluding AK/HI)")

print("\n" + "="*60)
print("DISCREPANCIES")
print("="*60)

# In adjacency but NOT in election
adj_not_election = adjacency_fips - election_fips
if adj_not_election:
    print(f"\n[1] In adjacency but NOT in 2024 election ({len(adj_not_election)}):")
    for fips in sorted(adj_not_election)[:20]:
        print(f"    {fips}")
    if len(adj_not_election) > 20:
        print(f"    ... and {len(adj_not_election) - 20} more")

# In election but NOT in adjacency
election_not_adj = election_fips - adjacency_fips
if election_not_adj:
    print(f"\n[2] In 2024 election but NOT in adjacency ({len(election_not_adj)}):")
    for fips in sorted(election_not_adj)[:20]:
        info = election_data.get(fips, ('?', '?'))
        print(f"    {fips}: {info[1]}, {info[0]}")
    if len(election_not_adj) > 20:
        print(f"    ... and {len(election_not_adj) - 20} more")

# In adjacency but NOT in geojson
adj_not_geojson = adjacency_fips - geojson_geoids
if adj_not_geojson:
    print(f"\n[3] In adjacency but NOT in GeoJSON ({len(adj_not_geojson)}):")
    for fips in sorted(adj_not_geojson)[:20]:
        print(f"    {fips}")
    if len(adj_not_geojson) > 20:
        print(f"    ... and {len(adj_not_geojson) - 20} more")

# In geojson but NOT in adjacency
geojson_not_adj = geojson_geoids - adjacency_fips
if geojson_not_adj:
    print(f"\n[4] In GeoJSON but NOT in adjacency ({len(geojson_not_adj)}):")
    for geoid in sorted(geojson_not_adj)[:20]:
        info = geojson_data.get(geoid, ('?', '?'))
        print(f"    {geoid}: {info[0]} (state {info[1]})")
    if len(geojson_not_adj) > 20:
        print(f"    ... and {len(geojson_not_adj) - 20} more")

# In election but NOT in geojson
election_not_geojson = election_fips - geojson_geoids
if election_not_geojson:
    print(f"\n[5] In 2024 election but NOT in GeoJSON ({len(election_not_geojson)}):")
    for fips in sorted(election_not_geojson)[:20]:
        info = election_data.get(fips, ('?', '?'))
        print(f"    {fips}: {info[1]}, {info[0]}")
    if len(election_not_geojson) > 20:
        print(f"    ... and {len(election_not_geojson) - 20} more")

# In geojson but NOT in election
geojson_not_election = geojson_geoids - election_fips
if geojson_not_election:
    print(f"\n[6] In GeoJSON but NOT in 2024 election ({len(geojson_not_election)}):")
    for geoid in sorted(geojson_not_election)[:20]:
        info = geojson_data.get(geoid, ('?', '?'))
        print(f"    {geoid}: {info[0]} (state {info[1]})")
    if len(geojson_not_election) > 20:
        print(f"    ... and {len(geojson_not_election) - 20} more")

# Summary
print("\n" + "="*60)
print("SUMMARY")
print("="*60)
all_three = adjacency_fips & election_fips & geojson_geoids
print(f"Counties in ALL THREE sources: {len(all_three)}")
print(f"Adjacency only: {len(adjacency_fips - election_fips - geojson_geoids)}")
print(f"Election only: {len(election_fips - adjacency_fips - geojson_geoids)}")
print(f"GeoJSON only: {len(geojson_geoids - adjacency_fips - election_fips)}")
