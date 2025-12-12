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
