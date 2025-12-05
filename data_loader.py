"""
Data loading module for county-level voting data and geographic boundaries.
"""

import pandas as pd
import geopandas as gpd
import requests
from pathlib import Path
import json


class DataLoader:
    """Handles fetching and loading county-level data."""

    def __init__(self, data_dir="data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

    def fetch_county_boundaries(self):
        """
        Fetch US county boundaries from Census Bureau.
        Returns GeoDataFrame with county geometries.
        """
        shapefile_path = self.data_dir / "counties.geojson"

        if shapefile_path.exists():
            print("Loading cached county boundaries...")
            return gpd.read_file(shapefile_path)

        print("Downloading county boundaries from Census Bureau...")
        # Using 2020 Census county boundaries (5m resolution for faster processing)
        url = "https://www2.census.gov/geo/tiger/GENZ2020/shp/cb_2020_us_county_5m.zip"

        gdf = gpd.read_file(url)

        # Filter to continental US (exclude Alaska, Hawaii, territories)
        continental_fips = gdf[
            ~gdf['STATEFP'].isin(['02', '15', '60', '66', '69', '72', '78'])
        ]

        # Save for future use
        continental_fips.to_file(shapefile_path, driver='GeoJSON')
        print(f"Saved county boundaries to {shapefile_path}")

        return continental_fips

    def fetch_2024_election_data(self):
        """
        Fetch 2024 presidential election results by county.
        Returns DataFrame with county FIPS codes and vote shares.
        """
        csv_path = self.data_dir / "election_2024.csv"

        if csv_path.exists():
            print("Loading cached election data...")
            return pd.read_csv(csv_path)

        print("Fetching 2024 election data...")
        # We'll try to get data from a reliable source
        # MIT Election Lab typically publishes county-level data
        # For now, we'll provide a structure and users can add data

        # NOTE: As of December 2024, full certified county results may still be coming in
        # This is a placeholder that will need real data
        print("WARNING: 2024 county-level data needs to be manually added")
        print(f"Please place CSV file with columns [FIPS, dem_votes, rep_votes, total_votes] at {csv_path}")

        # Create a placeholder structure
        df = pd.DataFrame(columns=[
            'FIPS',          # 5-digit county FIPS code
            'dem_votes',     # Democratic votes
            'rep_votes',     # Republican votes
            'total_votes'    # Total votes cast
        ])

        return df

    def load_county_data(self):
        """
        Load and merge all county data.
        Returns GeoDataFrame with geometries, voting data, and populations.
        """
        # Get geographic boundaries
        counties_geo = self.fetch_county_boundaries()

        # Get election data
        election_data = self.fetch_2024_election_data()

        # Merge on FIPS code
        counties_geo['FIPS'] = counties_geo['STATEFP'] + counties_geo['COUNTYFP']

        if not election_data.empty:
            # Ensure FIPS codes are strings and properly zero-padded
            election_data['FIPS'] = election_data['FIPS'].astype(str).str.zfill(5)

            counties = counties_geo.merge(
                election_data,
                left_on='FIPS',
                right_on='FIPS',
                how='left'
            )

            # Calculate vote share (but NOT political_lean - that's generated in app.py)
            counties['dem_share'] = counties['dem_votes'] / counties['total_votes']
            counties['rep_share'] = counties['rep_votes'] / counties['total_votes']
            # REMOVED: counties['political_lean'] - app.py generates this with N(X, abs(X)+1)
        else:
            counties = counties_geo
            print("WARNING: No election data loaded")

        return counties

    def compute_county_neighbors(self, counties_gdf):
        """
        Compute which counties are adjacent to each other.
        Returns dictionary: {county_fips: [neighbor_fips, ...]}
        """
        neighbors_path = self.data_dir / "county_neighbors.json"

        if neighbors_path.exists():
            print("Loading cached neighbor data...")
            with open(neighbors_path) as f:
                return json.load(f)

        print("Computing county neighbors (this may take a moment)...")
        neighbors = {}

        for idx, county in counties_gdf.iterrows():
            fips = county['FIPS']
            # Find all counties that touch this one
            touching = counties_gdf[
                counties_gdf.geometry.touches(county.geometry)
            ]['FIPS'].tolist()
            neighbors[fips] = touching

        # Save for future use
        with open(neighbors_path, 'w') as f:
            json.dump(neighbors, f)

        print(f"Saved neighbor data to {neighbors_path}")
        return neighbors


if __name__ == "__main__":
    # Test data loading
    loader = DataLoader()
    counties = loader.load_county_data()
    print(f"\nLoaded {len(counties)} counties")
    print(f"Columns: {counties.columns.tolist()}")

    neighbors = loader.compute_county_neighbors(counties)
    print(f"\nComputed neighbors for {len(neighbors)} counties")
