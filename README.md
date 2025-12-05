# US Border Redistricting

Algorithmically redrawing US state borders using genetic algorithms and 2024 county-level voting data.

## Objective

Create 50 new states that are:
- **Politically homogeneous** - Counties with similar voting patterns grouped together
- **Roughly equal in population** - Balance population across all states
- **Geographically contiguous** - Each state forms a connected region

## Algorithm

Uses a genetic algorithm approach with:
- **Fitness function**: Combines political homogeneity, population balance, and geographic contiguity
- **Mutation**: Reassign border counties to adjacent states
- **Crossover**: Combine parent solutions to create offspring
- **Selection**: Tournament selection based on fitness
- **Elitism**: Preserve best solutions across generations

## Quick Start

### Web Interface (Recommended - Watch Borders Evolve in Real-Time!)

```bash
# Install dependencies
pip install -r requirements.txt

# Generate synthetic election data (if needed)
python fetch_election_data.py --synthetic

# Start the web server
python app.py

# Open your browser to http://localhost:5000
```

### Command Line Interface

```bash
# Install dependencies
pip install -r requirements.txt

# Run quick start script (includes demo)
python quick_start.py
```

## Manual Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Required packages:
- pandas (data manipulation)
- geopandas (geographic data)
- matplotlib (visualization)
- numpy (numerical computing)
- shapely (geometric operations)
- requests (data fetching)
- tqdm (progress bars)

### 2. Get Election Data

**Option A: Use real 2024 data (recommended)**

Create `data/election_2024.csv` with the following columns:
- `FIPS`: 5-digit county FIPS code (string)
- `dem_votes`: Democratic party votes (integer)
- `rep_votes`: Republican party votes (integer)
- `total_votes`: Total votes cast (integer)

Data sources:
- [MIT Election Lab](https://electionlab.mit.edu/data)
- [Harvard Dataverse](https://dataverse.harvard.edu/)
- State election offices

**Option B: Generate synthetic data (for testing)**

```bash
python fetch_election_data.py --synthetic
```

### 3. Run the Algorithm

```bash
# Basic run with default parameters
python main.py

# Custom parameters
python main.py --states 50 --population 100 --generations 500

# Quick test (faster but less optimal)
python main.py --population 50 --generations 100
```

## Command Line Options

```
--states N             Number of states to create (default: 50)
--population N         GA population size (default: 100)
--generations N        Number of generations (default: 500)
--mutation-rate RATE   Mutation probability (default: 0.1)
--data-dir PATH        Data directory (default: data)
--output-dir PATH      Output directory (default: output)
```

## Output Files

The algorithm generates the following files in the `output/` directory:

1. **new_borders.png** - Side-by-side comparison of original vs. new state borders
2. **state_comparison.png** - Statistical analysis of the new states
3. **fitness_history.png** - Evolution of fitness over generations
4. **new_states.geojson** - Geographic boundaries of new states (for GIS software)

## How It Works

### 1. Data Loading
- Fetches US county boundaries from Census Bureau
- Loads 2024 election results by county
- Computes county adjacency graph

### 2. Genetic Algorithm
- **Representation**: Each solution is an array mapping counties to states
- **Initial Population**: Random state assignments + current borders
- **Fitness Evaluation**:
  - Political homogeneity: Minimize variance of political lean within each state
  - Population balance: Minimize variance of population across states
  - Contiguity: Heavy penalty for disconnected states
- **Selection**: Tournament selection favors fitter solutions
- **Crossover**: Region-based crossover combines parent solutions
- **Mutation**: Reassigns border counties to neighboring states
- **Elitism**: Best solutions are preserved

### 3. Visualization
- Creates maps colored by political lean
- Generates statistical comparisons
- Exports results in multiple formats

## Project Structure

```
us-borders/
├── main.py                    # Main entry point
├── genetic_algorithm.py       # GA implementation
├── data_loader.py            # Data fetching and loading
├── visualizer.py             # Map generation and plotting
├── fetch_election_data.py    # Helper for election data
├── quick_start.py            # Quick setup script
├── requirements.txt          # Python dependencies
├── data/                     # Data files (auto-created)
│   ├── counties.geojson
│   ├── election_2024.csv
│   └── county_neighbors.json
└── output/                   # Results (auto-created)
    ├── new_borders.png
    ├── state_comparison.png
    ├── fitness_history.png
    └── new_states.geojson
```

## Performance Tips

- **Faster runs**: Use smaller population (50) and fewer generations (100-200)
- **Better results**: Use larger population (100-200) and more generations (500-1000)
- **Memory**: Continental US has ~3,000 counties - this fits easily in memory
- **Time**: Typical run takes 5-15 minutes depending on parameters

## Notes

- The algorithm optimizes for political homogeneity, which may not be desirable in practice
- Real-world redistricting involves many other factors (communities of interest, existing boundaries, etc.)
- This is a computational experiment, not a policy proposal

## Customization

You can modify the fitness function in `genetic_algorithm.py:calculate_fitness()` to:
- Weight different objectives (homogeneity vs. population balance)
- Add new constraints (e.g., respect existing state boundaries)
- Incorporate other data (economic, demographic, geographic features)

## Troubleshooting

**"No voting data found"**: Add 2024 election data to `data/election_2024.csv` or generate synthetic data

**"ModuleNotFoundError"**: Install dependencies with `pip install -r requirements.txt`

**Slow performance**: Reduce `--population` and `--generations` parameters

**Memory issues**: The algorithm should work on most modern computers, but if you encounter issues, try reducing population size
