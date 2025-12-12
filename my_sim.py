import numpy as np
import time
import matplotlib.pyplot as plt
import csv
import heapq
import random

# Default electoral votes (2020)
DEFAULT_STATE_TO_EV = {
    'AK': 3, 'AL': 9, 'AR': 6, 'AZ': 11, 'CA': 55, 'CO': 9, 'CT': 7, 'DC': 3,
    'DE': 3, 'FL': 29, 'GA': 16, 'HI': 4, 'IA': 6, 'ID': 4, 'IL': 20, 'IN': 11,
    'KS': 6, 'KY': 8, 'LA': 8, 'MA': 11, 'MD': 10, 'ME': 4, 'MI': 16, 'MN': 10,
    'MO': 10, 'MS': 6, 'MT': 3, 'NC': 15, 'ND': 3, 'NE': 5, 'NH': 4, 'NJ': 14,
    'NM': 5, 'NV': 6, 'NY': 29, 'OH': 18, 'OK': 7, 'OR': 7, 'PA': 20, 'RI': 4,
    'SC': 9, 'SD': 3, 'TN': 11, 'TX': 38, 'UT': 6, 'VA': 13, 'VT': 3, 'WA': 12,
    'WI': 10, 'WV': 5, 'WY': 3
}

NUM_ITERATIONS = 25000
YEAR = 2020


class TwoWayAlgorithm:
    """
    Encapsulates all state and logic for the two-way partisan redistricting simulation.

    Parameters:
        side1: Name of the first side (e.g., "Republican")
        color1: Color for the first side (e.g., "red")
        side2: Name of the second side (e.g., "Democrat")
        color2: Color for the second side (e.g., "blue")
        augment: Optional dict of {county_fips: {'side1': votes, 'side2': votes}}
                 If provided, uses this data for partisan lean calculation instead of
                 real election data. Vote proportions are scaled by actual county
                 population from the base election year.

                 Generate augment data using the generator module:
                     from generator import generate_from_real_shifted
                     augment = generate_from_real_shifted(2020, shift=0.05)
    """

    def __init__(self, side1="Republican", color1="red", side2="Democrat", color2="blue", augment=None):
        # Side configuration
        self.side1 = side1
        self.color1 = color1
        self.side2 = side2
        self.color2 = color2

        # Augment data for synthetic elections
        self.augment = augment

        # Core data structures
        self.county_to_neighbors = {}
        self.county_to_state = {}
        self.state_to_counties = {}
        self.state_to_bordering_counties = {}
        self.county_to_partisan_lean = {}
        self.county_to_population = {}
        self.state_to_partisan_lean = {}
        self.state_to_ev = DEFAULT_STATE_TO_EV.copy()

        # Follow-the-leader / traversal state
        self.follow_the_leader_state = None
        self.last_moved_county = None
        self.traversal_frontier = []
        self.traversal_visited = set()

        # Rejected moves tracking
        self.rejected_moves_heap = []
        self.iterations_since_exchange = 0

        # Load county adjacency data
        self._load_county_adjacency_data()
    
    def _load_county_adjacency_data(self):
        """Load county adjacency data from file and populate data structures."""
        with open('data/county_adjacency.txt', 'r') as file:
            for line in file:
                # Parse line format: County Name, AB|01001|Other County, CD|01021|52283
                parts = line.strip().split('|')
                if len(parts) < 4:
                    continue
                
                county_name_state, county_id, adjacent_county_name_state, adjacent_county_id = parts[:4]
                
                # Extract state codes - handle cases where the split fails
                county_parts = county_name_state.split(', ')
                adjacent_parts = adjacent_county_name_state.split(', ')
                
                if len(county_parts) < 2 or len(adjacent_parts) < 2:
                    continue
                
                state = county_parts[-1].strip()
                adjacent_state = adjacent_parts[-1].strip()
                
                # Skip Alaska and Hawaii (not contiguous US)
                if state in ['AK', 'HI']:
                    continue
                
                # Add county to state mapping
                self.state_to_counties.setdefault(state, set()).add(county_id)
                self.county_to_state[county_id] = state
                
                # Add bidirectional neighbor relationships
                self.county_to_neighbors.setdefault(county_id, set()).add(adjacent_county_id)
                
                # Only add reverse relationship if adjacent county is not in AK/HI
                if adjacent_state not in ['AK', 'HI']:
                    self.county_to_neighbors.setdefault(adjacent_county_id, set()).add(county_id)
    
    def compute_state_to_bordering_counties(self):
        """Compute which counties border each state."""
        self.state_to_bordering_counties = {}
        for state, counties in self.state_to_counties.items():
            for county in counties:
                if county in self.county_to_neighbors:
                    for neighbor in self.county_to_neighbors[county]:
                        neighbor_state = self.county_to_state.get(neighbor)
                        if neighbor_state and state != neighbor_state:
                            self.state_to_bordering_counties.setdefault(state, set()).add(neighbor)
    
    def sample_state(self):
        """Sample a state weighted by inverse square of county count rank."""
        state_county_counts = [(state, len(counties)) for state, counties in self.state_to_counties.items()]
        state_county_counts.sort(key=lambda x: x[1])
        state_ranks = {state: rank + 1 for rank, (state, _) in enumerate(state_county_counts)}
        
        state_weights = np.exp(np.array([1/(state_ranks[state] ** 2) for state in self.state_to_counties.keys()]))
        state_weights = state_weights / np.sum(state_weights)
        
        return np.random.choice(list(self.state_to_counties.keys()), p=state_weights)
    
    def sample_adjacent_county(self, state):
        """Sample an adjacent county weighted by inverse square of adjacent states count."""
        if state not in self.state_to_bordering_counties or not self.state_to_bordering_counties[state]:
            return None
        
        def _number_of_adjacent_states(county):
            return len(set(self.county_to_state.get(neighbor) for neighbor in self.county_to_neighbors.get(county, [])))
        
        candidates = list(self.state_to_bordering_counties[state])
        county_logits = np.array([1/(_number_of_adjacent_states(county) ** 2) for county in candidates])
        county_weights = np.exp(county_logits) / np.sum(np.exp(county_logits))
        return np.random.choice(candidates, p=county_weights)
    
    def sample_adjacent_county_excluding(self, state, exclude_county):
        """Sample adjacent county but exclude a specific one to prevent ping-pong."""
        if state not in self.state_to_bordering_counties:
            return None
        
        candidates = [c for c in self.state_to_bordering_counties[state] if c != exclude_county]
        if not candidates:
            return None
        
        def _number_of_adjacent_states(county):
            return len(set(self.county_to_state.get(neighbor) for neighbor in self.county_to_neighbors.get(county, [])))
        
        county_logits = np.array([1/(_number_of_adjacent_states(county) ** 2) for county in candidates])
        county_weights = np.exp(county_logits) / np.sum(np.exp(county_logits))
        return np.random.choice(candidates, p=county_weights)
    
    def is_state_contiguous(self, state):
        """Check if a state's counties form a contiguous region."""
        counties = self.state_to_counties.get(state, set())
        if not counties:
            return False
        
        start_county = next(iter(counties))
        visited = set()
        queue = [start_county]
        visited.add(start_county)
        
        while queue:
            current_county = queue.pop(0)
            if current_county in self.county_to_neighbors:
                for neighbor in self.county_to_neighbors[current_county]:
                    if neighbor in counties and neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
        
        return len(visited) == len(counties)
    
    def generate_initial_partisan_lean(self, year=None):
        """
        Generate partisan lean data from election results, augment data, or random.

        If self.augment is provided, uses augment proportions for partisan lean
        and real election data (from year) for population scaling.

        Args:
            year: Election year for population data (default: 2020 if augment, None for random)
        """
        self.county_to_partisan_lean = {}
        self.county_to_population = {}

        # If augment data is provided, use it for lean calculation
        if self.augment is not None:
            # Default to 2020 for population data if no year specified
            pop_year = year if year else 2020
            self._generate_from_augment(pop_year)
            return

        if not year:
            # Random generation
            for _, counties in self.state_to_counties.items():
                state_lean = np.random.uniform(-20, 20)
                for county in counties:
                    self.county_to_partisan_lean[county] = np.random.normal(state_lean, np.abs(state_lean)+1)
                    self.county_to_population[county] = np.random.randint(1000, 100000)
            return

        # Load from real election data
        file = f'data/{year}_US_County_Level_Presidential_Results.csv'
        with open(file, 'r') as f:
            reader = csv.reader(f)
            next(reader)
            for state_name, county_fips, county_name, votes_gop, votes_dem, *_ in reader:
                if state_name in ['Alaska', 'Hawaii']:
                    continue
                votes_gop, votes_dem = int(votes_gop), int(votes_dem)
                total_votes = votes_gop + votes_dem
                if county_fips not in self.county_to_state:
                    raise ValueError(f"County {county_fips} with name {county_name} not found")
                self.county_to_partisan_lean[county_fips] = (votes_gop - votes_dem) / total_votes
                self.county_to_population[county_fips] = total_votes

    def _generate_from_augment(self, pop_year):
        """
        Generate partisan lean from augment data with real population scaling.

        Uses augment data for vote proportions (lean calculation) and real
        election data for county populations.

        Args:
            pop_year: Year to use for population data
        """
        # First, load population data from real election
        population_data = {}
        file = f'data/{pop_year}_US_County_Level_Presidential_Results.csv'
        with open(file, 'r') as f:
            reader = csv.reader(f)
            next(reader)
            for state_name, county_fips, county_name, votes_gop, votes_dem, *_ in reader:
                if state_name in ['Alaska', 'Hawaii']:
                    continue
                total_votes = int(votes_gop) + int(votes_dem)
                population_data[county_fips] = total_votes

        # Now apply augment data for partisan lean
        for county_fips in self.county_to_state:
            # Get population from real data
            pop = population_data.get(county_fips, 10000)  # Default if missing
            self.county_to_population[county_fips] = pop

            # Get lean from augment data
            if county_fips in self.augment:
                aug = self.augment[county_fips]
                side1_votes = aug.get('side1', 0)
                side2_votes = aug.get('side2', 0)
                total = side1_votes + side2_votes
                if total > 0:
                    # Lean: positive = side1, negative = side2
                    self.county_to_partisan_lean[county_fips] = (side1_votes - side2_votes) / total
                else:
                    self.county_to_partisan_lean[county_fips] = 0.0
            else:
                # County not in augment data - default to neutral
                self.county_to_partisan_lean[county_fips] = 0.0
    
    def compute_state_to_partisan_lean(self):
        """Compute population-weighted partisan lean for each state."""
        self.state_to_partisan_lean = {}
        self.state_to_ev = {}
        temp = {}
        
        for state, counties in self.state_to_counties.items():
            if counties:
                total_pop = sum(self.county_to_population.get(county, 0) for county in counties)
                if total_pop > 0:
                    avg_lean = sum(
                        self.county_to_partisan_lean.get(county, 0) * self.county_to_population.get(county, 0)
                        for county in counties
                    ) / total_pop
                    self.state_to_partisan_lean[state] = avg_lean
                else:
                    self.state_to_partisan_lean[state] = 0
                temp[state] = total_pop
            else:
                temp[state] = 0
        
        total_population = sum(temp.values())
        if total_population > 0:
            for state, population in temp.items():
                self.state_to_ev[state] = int(round(population * 538 / total_population))
    
    def _reward_score(self, lean, tie_mode=False):
        """Compute reward score for a given lean value."""
        if tie_mode:
            return -abs(lean)
        sign = 1 if lean > 0 else -1 if lean < 0 else 0
        return sign - lean
    
    def get_configuration_score(self, target):
        """
        Get the configuration score for the current state.
        
        target: self.side1, self.side2, or 'Tie'
        """
        score = 0
        if target != "Tie":
            # Positive lean favors side1, negative favors side2
            multiplier = 1 if target == self.side1 else -1
            for state, partisan_lean in self.state_to_partisan_lean.items():
                score += self.state_to_ev.get(state, 0) * self._reward_score(partisan_lean * multiplier, tie_mode=False)
        else:
            for state, partisan_lean in self.state_to_partisan_lean.items():
                score += self.state_to_ev.get(state, 0) * self._reward_score(partisan_lean, tie_mode=True)
        
        return score
    
    def compute_election_winner(self):
        """Compute who wins the election based on current state leans."""
        side1_ev, side2_ev = 0, 0
        for state, partisan_lean in self.state_to_partisan_lean.items():
            if partisan_lean > 0:
                side1_ev += self.state_to_ev.get(state, 0)
            else:
                side2_ev += self.state_to_ev.get(state, 0)
        
        if side1_ev > side2_ev:
            return self.side1, side1_ev, side2_ev
        elif side2_ev > side1_ev:
            return self.side2, side2_ev, side1_ev
        else:
            return 'Tie', side1_ev, side2_ev
    
    def population_conditions_met(self):
        """Check if all states meet minimum population requirements."""
        for _, counties in self.state_to_counties.items():
            if not counties:
                return False
            state_pop = sum(self.county_to_population.get(county, 0) for county in counties)
            if state_pop < 100000:
                return False
        return True
    
    def reset_follow_the_leader(self):
        """Reset the leader state and traversal state."""
        self.follow_the_leader_state = None
        self.last_moved_county = None
        self.traversal_frontier = []
        self.traversal_visited = set()
        self.rejected_moves_heap = []
        self.iterations_since_exchange = 0
    
    def _reset_rejected_tracking(self):
        """Reset rejected moves tracking after a successful exchange."""
        self.rejected_moves_heap = []
        self.iterations_since_exchange = 0
    
    def _add_rejected_move(self, score, pivot_county, state_to_grow, from_state):
        """Add a rejected move to the heap and trim to max size."""
        heapq.heappush(self.rejected_moves_heap, (-score, pivot_county, state_to_grow, from_state))
        
        # Trim to keep only best N moves
        if len(self.rejected_moves_heap) > self.iterations_since_exchange:
            items = list(self.rejected_moves_heap)
            items.sort()
            self.rejected_moves_heap = items[:self.iterations_since_exchange]
            heapq.heapify(self.rejected_moves_heap)
    
    def _try_execute_best_reject(self, target):
        """Try to execute the best rejected move that is still valid."""
        while self.rejected_moves_heap:
            neg_score, pivot_county, state_to_grow, from_state = heapq.heappop(self.rejected_moves_heap)
            
            # Check if move is still valid
            if self.county_to_state.get(pivot_county) != from_state:
                continue
            if pivot_county not in self.state_to_bordering_counties.get(state_to_grow, set()):
                continue
            
            # Try the move
            self.state_to_counties[from_state].remove(pivot_county)
            self.state_to_counties[state_to_grow].add(pivot_county)
            self.county_to_state[pivot_county] = state_to_grow
            
            # Check contiguity
            if not self.is_state_contiguous(from_state):
                self.state_to_counties[state_to_grow].remove(pivot_county)
                self.state_to_counties[from_state].add(pivot_county)
                self.county_to_state[pivot_county] = from_state
                continue
            
            # Update state
            self.compute_state_to_bordering_counties()
            self.compute_state_to_partisan_lean()
            
            # Check population conditions
            if not self.population_conditions_met():
                self.state_to_counties[state_to_grow].remove(pivot_county)
                self.state_to_counties[from_state].add(pivot_county)
                self.county_to_state[pivot_county] = from_state
                self.compute_state_to_bordering_counties()
                self.compute_state_to_partisan_lean()
                continue
            
            return True
        
        return False
    
    def iteration_greedy(self, target=None, mode='standard', alpha=0.01):
        """
        Stochastic hill-climb with different traversal modes.
        
        target: self.side1, self.side2, or 'Tie' (defaults to self.side1)
        mode: 'standard', 'follow_the_leader', 'bfs', or 'dfs'
        alpha: probability of selecting from best rejected moves
        
        Returns: (success, heap_used, pivot_county)
        """
        if target is None:
            target = self.side1
        
        self.compute_state_to_partisan_lean()
        current_score = self.get_configuration_score(target)
        
        pivot_county = None
        state_to_grow = None
        
        if mode in ['bfs', 'dfs']:
            # BFS/DFS traversal along borders
            if not self.traversal_frontier:
                state_to_grow = self.sample_state()
                if state_to_grow in self.state_to_bordering_counties and self.state_to_bordering_counties[state_to_grow]:
                    self.traversal_frontier = list(self.state_to_bordering_counties[state_to_grow])
                    random.shuffle(self.traversal_frontier)
                    self.traversal_visited = set()
            
            while self.traversal_frontier:
                if mode == 'bfs':
                    candidate = self.traversal_frontier.pop(0)
                else:
                    candidate = self.traversal_frontier.pop()
                
                if candidate in self.traversal_visited:
                    continue
                candidate_state = self.county_to_state.get(candidate)
                if candidate_state is None:
                    continue
                
                for neighbor in self.county_to_neighbors.get(candidate, []):
                    neighbor_state = self.county_to_state.get(neighbor)
                    if neighbor_state and neighbor_state != candidate_state:
                        pivot_county = candidate
                        state_to_grow = neighbor_state
                        break
                
                if pivot_county:
                    break
            
            if not pivot_county:
                self.traversal_frontier = []
                self.traversal_visited = set()
                return False, False, None
        
        elif mode == 'follow_the_leader':
            if self.follow_the_leader_state is not None:
                state_to_grow = self.follow_the_leader_state
            else:
                state_to_grow = self.sample_state()
            
            if state_to_grow not in self.state_to_bordering_counties or not self.state_to_bordering_counties[state_to_grow]:
                self.follow_the_leader_state = None
                self.last_moved_county = None
                return False, False, None
            
            if self.last_moved_county is not None:
                pivot_county = self.sample_adjacent_county_excluding(state_to_grow, self.last_moved_county)
                if pivot_county is None:
                    self.follow_the_leader_state = None
                    self.last_moved_county = None
                    return False, False, None
            else:
                pivot_county = self.sample_adjacent_county(state_to_grow)
        
        else:  # standard mode
            state_to_grow = self.sample_state()
            if state_to_grow not in self.state_to_bordering_counties or not self.state_to_bordering_counties[state_to_grow]:
                return False, False, None
            pivot_county = self.sample_adjacent_county(state_to_grow)
        
        if pivot_county is None:
            return False, False, None
        
        from_state = self.county_to_state[pivot_county]
        
        # Try the move
        self.state_to_counties[from_state].remove(pivot_county)
        self.state_to_counties[state_to_grow].add(pivot_county)
        self.county_to_state[pivot_county] = state_to_grow
        
        # Check contiguity
        if not self.is_state_contiguous(from_state):
            self.state_to_counties[state_to_grow].remove(pivot_county)
            self.state_to_counties[from_state].add(pivot_county)
            self.county_to_state[pivot_county] = from_state
            return False, False, pivot_county
        
        # Compute new score
        self.compute_state_to_bordering_counties()
        self.compute_state_to_partisan_lean()
        new_score = self.get_configuration_score(target)
        
        # Check population conditions
        pop_ok = self.population_conditions_met()
        
        # Accept if score improved AND population conditions met
        if new_score >= current_score and pop_ok:
            self._reset_rejected_tracking()
            if mode == 'follow_the_leader':
                self.follow_the_leader_state = from_state
                self.last_moved_county = pivot_county
            elif mode in ['bfs', 'dfs']:
                self.traversal_visited.add(pivot_county)
                for neighbor in self.county_to_neighbors.get(pivot_county, []):
                    if neighbor not in self.traversal_visited and self.county_to_state.get(neighbor) != state_to_grow:
                        self.traversal_frontier.append(neighbor)
            return True, False, pivot_county
        
        # Move was worse or population conditions not met - undo
        self.state_to_counties[state_to_grow].remove(pivot_county)
        self.state_to_counties[from_state].add(pivot_county)
        self.county_to_state[pivot_county] = from_state
        self.compute_state_to_bordering_counties()
        self.compute_state_to_partisan_lean()
        
        if pop_ok:
            self.iterations_since_exchange += 1
            self._add_rejected_move(new_score, pivot_county, state_to_grow, from_state)
            
            if np.random.random() < alpha:
                if self._try_execute_best_reject(target):
                    self._reset_rejected_tracking()
                    return True, True, None
        
        return False, False, pivot_county
    
    def iteration(self):
        """Run a single random iteration (non-greedy)."""
        state_to_grow = self.sample_state()
        pivot_county = self.sample_adjacent_county(state_to_grow)
        
        if pivot_county is None:
            return
        
        state_to_shrink = self.county_to_state[pivot_county]
        
        self.state_to_counties[state_to_grow].add(pivot_county)
        self.state_to_counties[state_to_shrink].remove(pivot_county)
        self.county_to_state[pivot_county] = state_to_grow
        
        self.compute_state_to_bordering_counties()
        
        if not self.is_state_contiguous(state_to_shrink):
            self.state_to_counties[state_to_grow].remove(pivot_county)
            self.state_to_counties[state_to_shrink].add(pivot_county)
            self.county_to_state[pivot_county] = state_to_shrink
            self.compute_state_to_bordering_counties()
    
    def get_state_snapshot(self):
        """Get a snapshot of current state for saving/restoring."""
        return {
            'county_to_state': dict(self.county_to_state),
            'state_to_counties': {s: set(c) for s, c in self.state_to_counties.items()}
        }
    
    def restore_state_snapshot(self, snapshot):
        """Restore state from a snapshot."""
        self.county_to_state.clear()
        self.county_to_state.update(snapshot['county_to_state'])
        
        self.state_to_counties.clear()
        for state, counties in snapshot['state_to_counties'].items():
            self.state_to_counties[state] = set(counties)
        
        self.compute_state_to_bordering_counties()


# ==============================================================================
# BACKWARDS COMPATIBILITY LAYER
# These global variables and functions are provided for backwards compatibility
# with existing code that uses the module-level API.
# ==============================================================================

# Create a default global instance
_default_algorithm = None

def _get_default_algorithm():
    """Get or create the default algorithm instance."""
    global _default_algorithm
    if _default_algorithm is None:
        _default_algorithm = TwoWayAlgorithm()
    return _default_algorithm

# Expose instance attributes as module-level for backwards compatibility
@property
def county_to_neighbors():
    return _get_default_algorithm().county_to_neighbors

@property  
def county_to_state():
    return _get_default_algorithm().county_to_state

@property
def state_to_counties():
    return _get_default_algorithm().state_to_counties

@property
def state_to_bordering_counties():
    return _get_default_algorithm().state_to_bordering_counties

@property
def county_to_partisan_lean():
    return _get_default_algorithm().county_to_partisan_lean

@property
def county_to_population():
    return _get_default_algorithm().county_to_population

@property
def state_to_partisan_lean():
    return _get_default_algorithm().state_to_partisan_lean

@property
def state_to_ev():
    return _get_default_algorithm().state_to_ev


# Create a module wrapper for property access
class _ModuleWrapper:
    """Wrapper to expose algorithm instance attributes as module attributes."""
    
    def __init__(self, module):
        self._module = module
    
    def __getattr__(self, name):
        # First check if it's a real module attribute
        if name.startswith('_') or name in ('TwoWayAlgorithm', 'DEFAULT_STATE_TO_EV', 
                                              'NUM_ITERATIONS', 'YEAR'):
            return getattr(self._module, name)
        
        # Check if it's an algorithm instance attribute
        algo = _get_default_algorithm()
        if hasattr(algo, name):
            return getattr(algo, name)
        
        # Fall back to module
        return getattr(self._module, name)
    
    def __setattr__(self, name, value):
        if name == '_module':
            object.__setattr__(self, name, value)
        else:
            # Try to set on algorithm instance first
            algo = _get_default_algorithm()
            if hasattr(algo, name):
                setattr(algo, name, value)
            else:
                setattr(self._module, name, value)


# Backwards compatible global functions that delegate to the default instance
def compute_state_to_bordering_counties():
    """Backwards compatible function."""
    _get_default_algorithm().compute_state_to_bordering_counties()

def generate_initial_partisan_lean(year=None):
    """Backwards compatible function."""
    _get_default_algorithm().generate_initial_partisan_lean(year)

def compute_state_to_partisan_lean():
    """Backwards compatible function."""
    _get_default_algorithm().compute_state_to_partisan_lean()

def get_configuration_score(target):
    """Backwards compatible function."""
    return _get_default_algorithm().get_configuration_score(target)

def compute_election_winner():
    """Backwards compatible function."""
    return _get_default_algorithm().compute_election_winner()

def reset_follow_the_leader():
    """Backwards compatible function."""
    _get_default_algorithm().reset_follow_the_leader()

def iteration_greedy(target='Republican', mode='standard', alpha=0.01):
    """Backwards compatible function."""
    return _get_default_algorithm().iteration_greedy(target, mode, alpha)

def iteration():
    """Backwards compatible function."""
    _get_default_algorithm().iteration()


def main():
    """Main function for standalone testing."""
    algo = TwoWayAlgorithm()
    
    time_start = time.time()
    algo.compute_state_to_bordering_counties()
    print(f"Time taken to compute state to bordering counties: {time.time() - time_start} seconds")
    algo.generate_initial_partisan_lean(YEAR)
    print(f"Time taken to generate initial partisan lean: {time.time() - time_start} seconds")
    
    state_names = list(algo.state_to_counties.keys())
    partisan_lean_history = {state: [] for state in state_names}
    county_count_history = {state: [] for state in state_names}
    
    for state in state_names:
        counties = algo.state_to_counties[state]
        county_count_history[state].append(len(counties))
        if counties:
            total_pop = sum(algo.county_to_population.get(c, 0) for c in counties)
            if total_pop > 0:
                avg_lean = sum(algo.county_to_partisan_lean.get(c, 0) * algo.county_to_population.get(c, 0) for c in counties) / total_pop
            else:
                avg_lean = 0
        else:
            avg_lean = 0
        partisan_lean_history[state].append(avg_lean)
    
    for _ in range(NUM_ITERATIONS):
        algo.iteration()
        for state in state_names:
            counties = algo.state_to_counties[state]
            county_count_history[state].append(len(counties))
            if counties:
                total_pop = sum(algo.county_to_population.get(c, 0) for c in counties)
                if total_pop > 0:
                    avg_lean = sum(algo.county_to_partisan_lean.get(c, 0) * algo.county_to_population.get(c, 0) for c in counties) / total_pop
                else:
                    avg_lean = 0
            else:
                avg_lean = 0
            partisan_lean_history[state].append(avg_lean)
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 12))
    iterations = range(NUM_ITERATIONS + 1)
    
    for state in state_names:
        ax1.plot(iterations, county_count_history[state], label=state, alpha=0.7)
    
    ax1.set_xlabel('Iteration')
    ax1.set_ylabel('Number of Counties')
    ax1.set_title('Number of Counties per State Over Iterations')
    ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax1.grid(True, alpha=0.3)
    
    for state in state_names:
        ax2.plot(iterations, partisan_lean_history[state], label=state, alpha=0.7)
    
    ax2.set_xlabel('Iteration')
    ax2.set_ylabel('Average Partisan Lean')
    ax2.set_title('Average Partisan Lean per State Over Iterations')
    ax2.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
