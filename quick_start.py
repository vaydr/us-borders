"""
Quick start script to set up and run the redistricting algorithm.
This script will:
1. Check if dependencies are installed
2. Generate synthetic election data if needed
3. Run a small test of the genetic algorithm
"""

import sys
import subprocess
from pathlib import Path

def setup_data():
    """Set up data directories and generate synthetic data if needed."""
    print("\nSetting up data...")

    data_dir = Path('data')
    data_dir.mkdir(exist_ok=True)

    output_dir = Path('output')
    output_dir.mkdir(exist_ok=True)

    # Check if election data exists
    election_file = data_dir / 'election_2024.csv'

    if not election_file.exists():
        print("\nElection data not found. Generating synthetic data...")
        print("(For real results, add actual 2024 data to data/election_2024.csv)")

        try:
            subprocess.run([sys.executable, 'fetch_election_data.py', '--synthetic'],
                         check=True)
        except subprocess.CalledProcessError:
            print("Error generating synthetic data")
            return False

    print("Data setup complete!")
    return True


def run_demo():
    """Run a quick demo with reduced parameters."""
    print("\n" + "=" * 60)
    print("Running quick demo...")
    print("(Using reduced parameters for faster execution)")
    print("=" * 60)

    try:
        subprocess.run([
            sys.executable, 'main.py',
            '--states', '50',
            '--population', '50',      # Smaller population
            '--generations', '100',    # Fewer generations
            '--mutation-rate', '0.15'
        ], check=True)

        print("\n" + "=" * 60)
        print("Demo complete! Check the output/ directory for results.")
        print("=" * 60)
        print("\nTo run with full parameters:")
        print("  python main.py --population 100 --generations 500")

    except subprocess.CalledProcessError:
        print("Error running demo")
        return False

    return True


def main():
    print("=" * 60)
    print("US BORDER REDISTRICTING - QUICK START")
    print("=" * 60)


    # Step 2: Setup data
    if not setup_data():
        print("\nData setup failed.")
        sys.exit(1)

    # Step 3: Ask if user wants to run demo
    print("\n" + "=" * 60)
    response = input("Run quick demo? (y/n): ").strip().lower()

    if response == 'y':
        run_demo()
    else:
        print("\nSetup complete! You can now run:")
        print("  python main.py")


if __name__ == "__main__":
    main()
