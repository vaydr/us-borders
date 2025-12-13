"""
Election data generators for creating synthetic/hypothetical election scenarios.

Each generator returns a dictionary: {county_fips: {'side1': votes, 'side2': votes}}
The votes are relative (proportional) and will be scaled by actual county population
when used with TwoWayAlgorithm's augment parameter.

Usage:
    from generator import generate_uniform_random, generate_from_real_shifted

    # Generate a hypothetical election shifted +5% toward side1
    augment = generate_from_real_shifted(2020, shift=0.05)

    algorithm = TwoWayAlgorithm(
        side1="Republican", color1="red",
        side2="Democrat", color2="blue",
        augment=augment
    )
"""

import random
import csv
import os


def get_all_counties(year=2020):
    """Get list of all county FIPS codes from election data."""
    counties = []
    filepath = f'data/{year}_US_County_Level_Presidential_Results.csv'
    with open(filepath, 'r') as f:
        reader = csv.reader(f)
        next(reader)  # Skip header
        for row in reader:
            state_name, county_fips = row[0], row[1]
            if state_name not in ['Alaska', 'Hawaii']:
                counties.append(county_fips)
    return counties


def generate_uniform_random(counties=None, bias=0.0, std=0.3, seed=None):
    """
    Generate uniformly random election results.

    Args:
        counties: list of county FIPS codes (if None, loads from 2020 data)
        bias: -1 to 1, shifts all results (positive = side1, negative = side2)
        std: standard deviation of the random lean
        seed: random seed for reproducibility

    Returns:
        dict of {county_fips: {'side1': votes, 'side2': votes}}
    """
    if seed is not None:
        random.seed(seed)

    if counties is None:
        counties = get_all_counties()

    results = {}
    for county in counties:
        lean = bias + random.gauss(0, std)
        lean = max(-1, min(1, lean))  # Clamp to [-1, 1]

        # Convert lean to vote proportions
        side1_pct = (1 + lean) / 2
        side2_pct = 1 - side1_pct

        # Use 1000 as base (will be scaled by actual population)
        results[county] = {
            'side1': int(1000 * side1_pct),
            'side2': int(1000 * side2_pct)
        }

    return results


def generate_from_csv(filepath):
    """
    Load election data from a custom CSV file.

    Expected format (with header):
        county,side1,side2
        01001,5432,4568
        01003,12000,8000
        ...

    Args:
        filepath: path to CSV file

    Returns:
        dict of {county_fips: {'side1': votes, 'side2': votes}}
    """
    results = {}
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            results[row['county']] = {
                'side1': int(row['side1']),
                'side2': int(row['side2'])
            }
    return results


def generate_from_real(year=2020):
    """
    Load actual election results as augment data.

    This essentially replicates real election data in the augment format.
    Useful as a base for modifications.

    Args:
        year: election year (2020, 2016, etc.)

    Returns:
        dict of {county_fips: {'side1': votes, 'side2': votes}}
    """
    results = {}
    filepath = f'data/{year}_US_County_Level_Presidential_Results.csv'

    with open(filepath, 'r') as f:
        reader = csv.reader(f)
        next(reader)  # Skip header
        for row in reader:
            state_name, county_fips, county_name, votes_gop, votes_dem = row[:5]
            if state_name in ['Alaska', 'Hawaii']:
                continue

            results[county_fips] = {
                'side1': int(votes_gop),
                'side2': int(votes_dem)
            }

    return results


def generate_from_real_shifted(year=2020, shift=0.0):
    """
    Load real election data and apply a uniform shift to all counties.

    Args:
        year: election year
        shift: -1 to 1, amount to shift all results
               positive = toward side1, negative = toward side2

    Returns:
        dict of {county_fips: {'side1': votes, 'side2': votes}}
    """
    base = generate_from_real(year)
    return apply_shift(base, shift)


def apply_shift(data, shift):
    """
    Apply a uniform shift to election data.

    Args:
        data: dict from another generator
        shift: -1 to 1, amount to shift

    Returns:
        dict with shifted results
    """
    results = {}
    for county, votes in data.items():
        total = votes['side1'] + votes['side2']
        if total == 0:
            results[county] = votes
            continue

        lean = (votes['side1'] - votes['side2']) / total
        lean += shift
        lean = max(-0.999, min(0.999, lean))  # Clamp

        side1_pct = (1 + lean) / 2
        results[county] = {
            'side1': int(total * side1_pct),
            'side2': int(total * (1 - side1_pct))
        }

    return results


def generate_swing_modified(base_data, swing_counties, swing_shift=0.1):
    """
    Take base election data and shift specific counties.

    Args:
        base_data: dict from another generator
        swing_counties: list of county FIPS codes to shift
        swing_shift: how much to shift those counties (-1 to 1)

    Returns:
        dict with modified results
    """
    results = {}
    swing_set = set(swing_counties)

    for county, votes in base_data.items():
        total = votes['side1'] + votes['side2']
        if total == 0:
            results[county] = votes
            continue

        lean = (votes['side1'] - votes['side2']) / total

        if county in swing_set:
            lean += swing_shift
            lean = max(-0.999, min(0.999, lean))

        side1_pct = (1 + lean) / 2
        results[county] = {
            'side1': int(total * side1_pct),
            'side2': int(total * (1 - side1_pct))
        }

    return results


def generate_landslide(counties=None, winner='side1', margin=0.2, std=0.15, seed=None):
    """
    Generate a landslide election for one side.

    Args:
        counties: list of county FIPS (if None, loads from 2020)
        winner: 'side1' or 'side2'
        margin: average winning margin (0 to 1)
        std: variation between counties
        seed: random seed

    Returns:
        dict of election results
    """
    bias = margin if winner == 'side1' else -margin
    return generate_uniform_random(counties, bias=bias, std=std, seed=seed)


def generate_close_election(counties=None, std=0.2, seed=None):
    """
    Generate a very close/competitive election (no bias).

    Args:
        counties: list of county FIPS
        std: variation between counties
        seed: random seed

    Returns:
        dict of election results
    """
    return generate_uniform_random(counties, bias=0.0, std=std, seed=seed)


def generate_flipped(year=2020):
    """
    Generate election with all results flipped (side1 <-> side2).

    Args:
        year: base year to flip

    Returns:
        dict with flipped results
    """
    base = generate_from_real(year)
    results = {}

    for county, votes in base.items():
        results[county] = {
            'side1': votes['side2'],
            'side2': votes['side1']
        }

    return results


def generate_state_flipped(year=2020, states_to_flip=None):
    """
    Flip specific states while keeping others the same.

    Args:
        year: base election year
        states_to_flip: list of state abbreviations to flip (e.g., ['GA', 'AZ', 'PA'])

    Returns:
        dict with selectively flipped results
    """
    if states_to_flip is None:
        states_to_flip = []

    flip_set = set(states_to_flip)

    # Load county to state mapping
    county_to_state = {}
    with open('data/county_adjacency.txt', 'r') as f:
        for line in f:
            parts = line.strip().split('|')
            if len(parts) >= 2:
                county_parts = parts[0].split(', ')
                if len(county_parts) >= 2:
                    state = county_parts[-1].strip()
                    county_id = parts[1]
                    county_to_state[county_id] = state

    base = generate_from_real(year)
    results = {}

    for county, votes in base.items():
        state = county_to_state.get(county)
        if state in flip_set:
            results[county] = {
                'side1': votes['side2'],
                'side2': votes['side1']
            }
        else:
            results[county] = votes

    return results


def generate_from_google_trends(search_term_1, search_term_2, timeframe='today 12-m', cache_dir='data/trends_cache'):
    """
    Generate election data from Google Trends search interest.
    
    Fetches state-level Google Trends data for two search terms and converts
    the relative interest into synthetic election results. Counties inherit
    their state's trend ratio.
    
    Args:
        search_term_1: Search term representing side1 (e.g., "Republican", "Trump")
        search_term_2: Search term representing side2 (e.g., "Democrat", "Biden")
        timeframe: Google Trends timeframe (default: 'today 12-m' for past year)
                   Options: 'now 1-d', 'now 7-d', 'today 1-m', 'today 3-m', 'today 12-m', 'today 5-y'
        cache_dir: Directory to cache trend results (avoids rate limits)
    
    Returns:
        dict of {county_fips: {'side1': votes, 'side2': votes}}
    
    Note:
        Requires pytrends library: pip install pytrends
        Google Trends has rate limits; results are cached to avoid repeated API calls.
    """
    try:
        from pytrends.request import TrendReq
    except ImportError:
        raise ImportError("pytrends is required for Google Trends data. Install with: pip install pytrends")
    
    import hashlib
    import json
    import time as time_module
    
    # Create cache directory if needed
    os.makedirs(cache_dir, exist_ok=True)
    
    # Generate cache key from search terms and timeframe
    cache_key = hashlib.md5(f"{search_term_1}|{search_term_2}|{timeframe}".encode()).hexdigest()
    cache_file = os.path.join(cache_dir, f"trends_{cache_key}.json")
    
    # Try to load from cache
    state_ratios = None
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                cached = json.load(f)
                # Check if cache is less than 24 hours old
                if time_module.time() - cached.get('timestamp', 0) < 86400:
                    state_ratios = cached.get('data')
                    print(f"Loaded Google Trends data from cache")
        except (json.JSONDecodeError, KeyError):
            pass
    
    # Fetch from Google Trends if not cached
    if state_ratios is None:
        print(f"Fetching Google Trends data for '{search_term_1}' vs '{search_term_2}'...")
        state_ratios = _fetch_google_trends_by_state(search_term_1, search_term_2, timeframe)
        
        # Cache the results
        with open(cache_file, 'w') as f:
            json.dump({'timestamp': time_module.time(), 'data': state_ratios}, f)
        print(f"Cached Google Trends data to {cache_file}")
    
    # Load county to state mapping
    county_to_state = _get_county_to_state_mapping()
    
    # Generate results for each county based on their state's ratio
    results = {}
    counties = get_all_counties()
    
    for county in counties:
        state = county_to_state.get(county, 'TX')  # Default to TX if unknown
        
        # Get the state's trend ratio (default to 50-50 if no data)
        ratio = state_ratios.get(state, {'side1': 50, 'side2': 50})
        
        side1_interest = ratio['side1']
        side2_interest = ratio['side2']
        total = side1_interest + side2_interest
        
        if total > 0:
            side1_pct = side1_interest / total
            side2_pct = side2_interest / total
        else:
            side1_pct = side2_pct = 0.5
        
        # Convert to vote counts (1000 base, scaled by population later)
        results[county] = {
            'side1': int(1000 * side1_pct),
            'side2': int(1000 * side2_pct)
        }
    
    return results


def _fetch_google_trends_by_state(search_term_1, search_term_2, timeframe):
    """
    Fetch Google Trends interest by state for two search terms.
    
    Returns:
        dict of {state_abbrev: {'side1': interest, 'side2': interest}}
    """
    from pytrends.request import TrendReq
    import time as time_module
    
    # State abbreviation to full name mapping (for Google Trends geo codes)
    state_codes = {
        'AL': 'US-AL', 'AZ': 'US-AZ', 'AR': 'US-AR', 'CA': 'US-CA', 'CO': 'US-CO',
        'CT': 'US-CT', 'DE': 'US-DE', 'DC': 'US-DC', 'FL': 'US-FL', 'GA': 'US-GA',
        'ID': 'US-ID', 'IL': 'US-IL', 'IN': 'US-IN', 'IA': 'US-IA', 'KS': 'US-KS',
        'KY': 'US-KY', 'LA': 'US-LA', 'ME': 'US-ME', 'MD': 'US-MD', 'MA': 'US-MA',
        'MI': 'US-MI', 'MN': 'US-MN', 'MS': 'US-MS', 'MO': 'US-MO', 'MT': 'US-MT',
        'NE': 'US-NE', 'NV': 'US-NV', 'NH': 'US-NH', 'NJ': 'US-NJ', 'NM': 'US-NM',
        'NY': 'US-NY', 'NC': 'US-NC', 'ND': 'US-ND', 'OH': 'US-OH', 'OK': 'US-OK',
        'OR': 'US-OR', 'PA': 'US-PA', 'RI': 'US-RI', 'SC': 'US-SC', 'SD': 'US-SD',
        'TN': 'US-TN', 'TX': 'US-TX', 'UT': 'US-UT', 'VT': 'US-VT', 'VA': 'US-VA',
        'WA': 'US-WA', 'WV': 'US-WV', 'WI': 'US-WI', 'WY': 'US-WY'
    }
    
    # Initialize pytrends
    pytrends = TrendReq(hl='en-US', tz=360)
    
    state_ratios = {}
    
    # Fetch US-wide data first to get regional breakdown
    try:
        pytrends.build_payload([search_term_1, search_term_2], cat=0, timeframe=timeframe, geo='US')
        
        # Get interest by region (state-level)
        region_df = pytrends.interest_by_region(resolution='REGION', inc_low_vol=True, inc_geo_code=True)
        
        if not region_df.empty:
            for geo_code in region_df.index:
                # Extract state abbreviation from geo code (e.g., "US-TX" -> "TX")
                if geo_code.startswith('US-'):
                    state_abbrev = geo_code[3:]
                    if state_abbrev in state_codes:
                        side1_val = region_df.loc[geo_code, search_term_1] if search_term_1 in region_df.columns else 50
                        side2_val = region_df.loc[geo_code, search_term_2] if search_term_2 in region_df.columns else 50
                        
                        # Handle NaN and zero values
                        if not isinstance(side1_val, (int, float)) or side1_val != side1_val:  # NaN check
                            side1_val = 50
                        if not isinstance(side2_val, (int, float)) or side2_val != side2_val:
                            side2_val = 50
                        
                        state_ratios[state_abbrev] = {
                            'side1': max(1, int(side1_val)),
                            'side2': max(1, int(side2_val))
                        }
            
            print(f"Fetched trends data for {len(state_ratios)} states")
    
    except Exception as e:
        print(f"Warning: Could not fetch Google Trends data: {e}")
        print("Using neutral 50-50 fallback for all states")
    
    # Fill in any missing states with neutral data
    for state in state_codes:
        if state not in state_ratios:
            state_ratios[state] = {'side1': 50, 'side2': 50}
    
    return state_ratios


def _get_county_to_state_mapping():
    """Load county FIPS to state abbreviation mapping."""
    county_to_state = {}
    with open('data/county_adjacency.txt', 'r') as f:
        for line in f:
            parts = line.strip().split('|')
            if len(parts) >= 2:
                county_parts = parts[0].split(', ')
                if len(county_parts) >= 2:
                    state = county_parts[-1].strip()
                    county_id = parts[1]
                    county_to_state[county_id] = state
    return county_to_state




def save_to_csv(data, filepath):
    """
    Save augment data to a CSV file for reuse.

    Args:
        data: dict from a generator
        filepath: output file path
    """
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['county', 'side1', 'side2'])
        for county, votes in sorted(data.items()):
            writer.writerow([county, votes['side1'], votes['side2']])


# Example usage and testing
if __name__ == '__main__':
    print("Testing generators...")

    # Test uniform random
    random_data = generate_uniform_random(seed=42)
    print(f"Generated {len(random_data)} counties with random data")

    # Test real data
    real_data = generate_from_real(2020)
    print(f"Loaded {len(real_data)} counties from 2020 election")

    # Test shifted
    shifted = generate_from_real_shifted(2020, shift=0.05)
    print(f"Generated shifted data (+5% side1)")

    # Test flipped
    flipped = generate_flipped(2020)
    print(f"Generated flipped data")

    # Show sample
    sample_county = list(real_data.keys())[0]
    print(f"\nSample county {sample_county}:")
    print(f"  Real:    side1={real_data[sample_county]['side1']}, side2={real_data[sample_county]['side2']}")
    print(f"  Shifted: side1={shifted[sample_county]['side1']}, side2={shifted[sample_county]['side2']}")
    print(f"  Flipped: side1={flipped[sample_county]['side1']}, side2={flipped[sample_county]['side2']}")

    # Test Google Trends (optional - requires pytrends and internet)
    print("\n--- Google Trends Test ---")
    try:
        trends_data = generate_from_google_trends("coffee", "tea")
        print(f"Generated {len(trends_data)} counties from Google Trends")
        sample = list(trends_data.keys())[0]
        print(f"  Sample {sample}: side1={trends_data[sample]['side1']}, side2={trends_data[sample]['side2']}")
    except ImportError as e:
        print(f"Skipping Google Trends test: {e}")
    except Exception as e:
        print(f"Google Trends test failed: {e}")
