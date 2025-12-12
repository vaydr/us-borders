from sre_parse import State
import numpy as np
import time
import matplotlib.pyplot as plt
county_to_neighbors = {}
county_to_state = {}
state_to_counties = {}
state_to_bordering_counties = {}
county_to_partisan_lean = {}
county_to_population = {}
state_to_partisan_lean = {}
state_to_ev = {'AK': 3, 'AL': 9, 'AR': 6, 'AZ': 11, 'CA': 55, 'CO': 9, 'CT': 7, 'DC': 3, 'DE': 3, 'FL': 29, 'GA': 16, 'HI': 4, 'IA': 6, 'ID': 4, 'IL': 20, 'IN': 11, 'KS': 6, 'KY': 8, 'LA': 8, 'MA': 11, 'MD': 10, 'ME': 4, 'MI': 16, 'MN': 10, 'MO': 10, 'MS': 6, 'MT': 3, 'NC': 15, 'ND': 3, 'NE': 5, 'NH': 4, 'NJ': 14, 'NM': 5, 'NV': 6, 'NY': 29, 'OH': 18, 'OK': 7, 'OR': 7, 'PA': 20, 'RI': 4, 'SC': 9, 'SD': 3, 'TN': 11, 'TX': 38, 'UT': 6, 'VA': 13, 'VT': 3, 'WA': 12, 'WI': 10, 'WV': 5, 'WY': 3}
import csv
NUM_ITERATIONS = 25000
YEAR = 2020

for line in open('data/county_adjacency.txt'):
    #lines look like: County Name County, AB|69420|Other County, CD|69696|67676
    county_name_state, county_id, adjacent_county_name_state, adjacent_county_id, _ = line.split('|')

    state = county_name_state.split(', ')[1]
    if state in ['AK', 'HI']: # skip Alaska and Hawaii as they are not part of the contiguous US
        continue
    adjacent_state = adjacent_county_name_state.split(', ')[1]
    state_to_counties.setdefault(state, set()).add(county_id)
    county_to_state[county_id] = state

    # Add bidirectional neighbor relationship (fixes CT and other asymmetric border issues)
    county_to_neighbors.setdefault(county_id, set()).add(adjacent_county_id)
    # Only add reverse if adjacent county is not in AK/HI
    if adjacent_state not in ['AK', 'HI']:
        county_to_neighbors.setdefault(adjacent_county_id, set()).add(county_id)


def compute_state_to_bordering_counties():
    global state_to_bordering_counties
    state_to_bordering_counties = {}
    for state, counties in state_to_counties.items():
        for county in counties:
            if county in county_to_neighbors:
                for neighbor in county_to_neighbors[county]:
                    neighbor_state = county_to_state[neighbor]
                    if state != neighbor_state:
                        state_to_bordering_counties.setdefault(state, set()).add(neighbor)

def sample_state():
    # Compute state ranks based on county count (1 = least counties, 50 = most counties)
    state_county_counts = [(state, len(counties)) for state, counties in state_to_counties.items()]
    state_county_counts.sort(key=lambda x: x[1])  # Sort by county count
    state_ranks = {state: rank + 1 for rank, (state, _) in enumerate(state_county_counts)}

    state_weights = np.exp(np.array([1/(state_ranks[state] ** 2) for state in state_to_counties.keys()]))
    state_weights = state_weights / np.sum(state_weights)

    return np.random.choice(list(state_to_counties.keys()), p=state_weights)

#TODO weighted sampling of adjacent counties
def sample_adjacent_county(state):
    def _number_of_adjacent_states(county):
        return len(set(county_to_state[neighbor] for neighbor in county_to_neighbors[county]))
    county_logits = np.array([1/(_number_of_adjacent_states(county) ** 2) for county in state_to_bordering_counties[state]])
    county_weights = np.exp(county_logits) / np.sum(np.exp(county_logits))
    return np.random.choice(list(state_to_bordering_counties[state]), p=county_weights)
def iteration():
    state_to_grow = sample_state()

    #state eats a random adjacent county
    pivot_county = sample_adjacent_county(state_to_grow)
    state_to_shrink = county_to_state[pivot_county]
    #remove the adjacent county from the old state and add it to the sampled state
    state_to_counties[state_to_grow].add(pivot_county)
    state_to_counties[state_to_shrink].remove(pivot_county)
    county_to_state[pivot_county] = state_to_grow
    #recompute the state to bordering counties
    compute_state_to_bordering_counties()
    if not _is_state_contiguous(state_to_shrink):
        # Reverse the assignments we just made
        state_to_counties[state_to_grow].remove(pivot_county)
        state_to_counties[state_to_shrink].add(pivot_county)
        county_to_state[pivot_county] = state_to_shrink
        # Recompute the state to bordering counties again
        compute_state_to_bordering_counties()
        return
    return


def generate_initial_partisan_lean(year: int | None = None):
    
    global county_to_partisan_lean
    county_to_partisan_lean = {}
    global county_to_population
    county_to_population = {}
    if not year:
        for _, counties in state_to_counties.items():
            state_lean = np.random.uniform(-20, 20)
            for county in counties:
                county_to_partisan_lean[county] = np.random.normal(state_lean, np.abs(state_lean)+1)
                county_to_population[county] = np.random.randint(1000, 100000)
        return
    
    file = f'data/{year}_US_County_Level_Presidential_Results.csv'
    with open(file, 'r') as f:
        reader = csv.reader(f)
        next(reader)
        for state,county_fips,county_name,votes_gop,votes_dem,_,_,_,_,_ in reader:
            if state in ['Alaska', 'Hawaii']:
                continue
            votes_gop, votes_dem = int(votes_gop), int(votes_dem)
            total_votes = votes_gop + votes_dem
            if county_fips not in county_to_state:
                raise ValueError(f"County {county_fips} with name {county_name} not found")
            county_to_partisan_lean[county_fips] = (votes_gop - votes_dem) / total_votes
            county_to_population[county_fips] = total_votes
def _is_state_contiguous(state):
    counties = state_to_counties[state]
    if not counties:
        return False
    
    # Start BFS from any county in the state
    start_county = next(iter(counties))
    visited = set()
    queue = [start_county]
    visited.add(start_county)
    
    while queue:
        current_county = queue.pop(0)
        if current_county in county_to_neighbors:
            for neighbor in county_to_neighbors[current_county]:
                if neighbor in counties and neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
    
    return len(visited) == len(counties)

def compute_state_to_partisan_lean():
    global state_to_partisan_lean
    global state_to_ev
    state_to_partisan_lean = {}
    state_to_ev = {}
    temp = {}
    for state, counties in state_to_counties.items():
        if counties:
            avg_lean = sum(county_to_partisan_lean[county] * county_to_population[county] for county in counties) / sum(county_to_population[county] for county in counties)
            state_to_partisan_lean[state] = avg_lean
        temp[state] = sum(county_to_population[county] for county in counties)
    
    total_population = sum(temp.values())
    for state, population in temp.items():
        state_to_ev[state] = int(round(population * 538 / total_population))
    
def _reward_score(lean:float, tie_mode:bool = False):
    if tie_mode:
        return (-abs(lean))
    sign = 1 if lean > 0 else -1 if lean < 0 else 0
    return sign - lean

def get_configuration_score(winner: str):
    global state_to_partisan_lean, state_to_ev
    score = 0
    if winner != "Tie":
        multiplier = 1 if winner == "Republican" else -1
        for state, partisan_lean in state_to_partisan_lean.items():
            score += state_to_ev[state] * _reward_score(partisan_lean * multiplier, tie_mode=False)
    else:
        for state, partisan_lean in state_to_partisan_lean.items():
            score += state_to_ev[state] * _reward_score(partisan_lean, tie_mode=True)

    return score

# Track state for follow-the-leader mode
follow_the_leader_state = None
last_moved_county = None

# Track frontier for BFS/DFS modes
traversal_frontier = []  # list of counties to explore
traversal_visited = set()  # counties already taken

# Track rejected moves for smart exploration (max heap via negative scores)
import heapq
rejected_moves_heap = []  # list of (-score, pivot_county, state_to_grow, from_state)
iterations_since_exchange = 0


def reset_follow_the_leader():
    """Reset the leader state and traversal state."""
    global follow_the_leader_state, last_moved_county, traversal_frontier, traversal_visited
    global rejected_moves_heap, iterations_since_exchange
    follow_the_leader_state = None
    last_moved_county = None
    traversal_frontier = []
    traversal_visited = set()
    rejected_moves_heap = []
    iterations_since_exchange = 0


def _reset_rejected_tracking():
    """Reset rejected moves tracking after a successful exchange."""
    global rejected_moves_heap, iterations_since_exchange
    rejected_moves_heap = []
    iterations_since_exchange = 0


def _add_rejected_move(score, pivot_county, state_to_grow, from_state):
    """Add a rejected move to the heap and trim to max size."""
    global rejected_moves_heap, iterations_since_exchange
    heapq.heappush(rejected_moves_heap, (-score, pivot_county, state_to_grow, from_state))

    # Trim to keep only best `iterations_since_exchange` moves
    # Since we use negative scores, smallest = best. We want to remove worst (largest/least negative)
    if len(rejected_moves_heap) > iterations_since_exchange:
        # Convert to list, sort (best first = most negative), keep best N, re-heapify
        items = list(rejected_moves_heap)
        items.sort()  # Most negative (best) first
        rejected_moves_heap = items[:iterations_since_exchange]
        heapq.heapify(rejected_moves_heap)


def _try_execute_best_reject(target):
    """
    Try to execute the best rejected move that is still valid.
    Returns True if successful, False otherwise.
    """
    global rejected_moves_heap

    while rejected_moves_heap:
        neg_score, pivot_county, state_to_grow, from_state = heapq.heappop(rejected_moves_heap)

        # Check if this move is still valid:
        # 1. pivot_county still belongs to from_state
        if county_to_state.get(pivot_county) != from_state:
            continue  # County has moved, skip

        # 2. pivot_county is still adjacent to state_to_grow
        if pivot_county not in state_to_bordering_counties.get(state_to_grow, set()):
            continue  # No longer adjacent, skip

        # Try the move
        state_to_counties[from_state].remove(pivot_county)
        state_to_counties[state_to_grow].add(pivot_county)
        county_to_state[pivot_county] = state_to_grow

        # Check contiguity
        if not _is_state_contiguous(from_state):
            # Undo
            state_to_counties[state_to_grow].remove(pivot_county)
            state_to_counties[from_state].add(pivot_county)
            county_to_state[pivot_county] = from_state
            continue

        # Update state
        compute_state_to_bordering_counties()
        compute_state_to_partisan_lean()

        # Check population conditions
        if not _population_conditions_met():
            # Undo
            state_to_counties[state_to_grow].remove(pivot_county)
            state_to_counties[from_state].add(pivot_county)
            county_to_state[pivot_county] = from_state
            compute_state_to_bordering_counties()
            compute_state_to_partisan_lean()
            continue

        # Success! Move is executed and state is updated
        return True

    return False


def sample_adjacent_county_excluding(state, exclude_county):
    """Sample adjacent county but exclude a specific one to prevent ping-pong."""
    candidates = [c for c in state_to_bordering_counties[state] if c != exclude_county]
    if not candidates:
        return None

    def _number_of_adjacent_states(county):
        return len(set(county_to_state[neighbor] for neighbor in county_to_neighbors[county]))

    county_logits = np.array([1/(_number_of_adjacent_states(county) ** 2) for county in candidates])
    county_weights = np.exp(county_logits) / np.sum(np.exp(county_logits))
    return np.random.choice(candidates, p=county_weights)


def iteration_greedy(target='Republican', mode='standard', alpha=0.01):
    """
    Stochastic hill-climb with different traversal modes.
    target: 'Republican', 'Democratic', or 'Tie'
    mode: 'standard', 'follow_the_leader', 'bfs', or 'dfs'
    alpha: probability of selecting from best rejected moves instead of random exploration

    Returns: (success, heap_used, pivot_county)
        - success: whether the move was accepted
        - heap_used: whether a move from the rejected heap was used
        - pivot_county: the county that was considered (for rejected visualization), None if no county was considered
    """
    global follow_the_leader_state, last_moved_county, traversal_frontier, traversal_visited
    global iterations_since_exchange
    import random

    compute_state_to_partisan_lean()
    current_score = get_configuration_score(target)

    pivot_county = None
    state_to_grow = None

    if mode in ['bfs', 'dfs']:
        # BFS/DFS: traverse along borders
        # If frontier empty, pick a random starting state and seed frontier
        if not traversal_frontier:
            state_to_grow = sample_state()
            if state_to_grow in state_to_bordering_counties and state_to_bordering_counties[state_to_grow]:
                # Seed with all border counties of this state
                traversal_frontier = list(state_to_bordering_counties[state_to_grow])
                random.shuffle(traversal_frontier)
                traversal_visited = set()

        # Try to get next county from frontier
        while traversal_frontier:
            if mode == 'bfs':
                candidate = traversal_frontier.pop(0)  # FIFO for BFS
            else:  # dfs
                candidate = traversal_frontier.pop()  # LIFO for DFS

            # Skip if already taken or no longer a valid target
            if candidate in traversal_visited:
                continue
            candidate_state = county_to_state.get(candidate)
            if candidate_state is None:
                continue

            # Find a state that can take this county (one of its neighbors)
            for neighbor in county_to_neighbors.get(candidate, []):
                neighbor_state = county_to_state.get(neighbor)
                if neighbor_state and neighbor_state != candidate_state:
                    pivot_county = candidate
                    state_to_grow = neighbor_state
                    break

            if pivot_county:
                break

        if not pivot_county:
            # Frontier exhausted, reset for next time
            traversal_frontier = []
            traversal_visited = set()
            return False, False, None

    elif mode == 'follow_the_leader':
        # Follow-the-leader: loser becomes next grower
        if follow_the_leader_state is not None:
            state_to_grow = follow_the_leader_state
        else:
            state_to_grow = sample_state()

        if state_to_grow not in state_to_bordering_counties or not state_to_bordering_counties[state_to_grow]:
            follow_the_leader_state = None
            last_moved_county = None
            return False, False, None

        # Exclude the county that was just moved to prevent ping-pong
        if last_moved_county is not None:
            pivot_county = sample_adjacent_county_excluding(state_to_grow, last_moved_county)
            if pivot_county is None:
                follow_the_leader_state = None
                last_moved_county = None
                return False, False, None
        else:
            pivot_county = sample_adjacent_county(state_to_grow)

    else:  # standard mode
        state_to_grow = sample_state()
        if state_to_grow not in state_to_bordering_counties or not state_to_bordering_counties[state_to_grow]:
            return False, False, None
        pivot_county = sample_adjacent_county(state_to_grow)

    from_state = county_to_state[pivot_county]

    # Try the move
    state_to_counties[from_state].remove(pivot_county)
    state_to_counties[state_to_grow].add(pivot_county)
    county_to_state[pivot_county] = state_to_grow

    # Check contiguity
    if not _is_state_contiguous(from_state):
        # Undo invalid move
        state_to_counties[state_to_grow].remove(pivot_county)
        state_to_counties[from_state].add(pivot_county)
        county_to_state[pivot_county] = from_state
        return False, False, pivot_county  # Return pivot for rejected visualization

    # Compute new score
    compute_state_to_bordering_counties()
    compute_state_to_partisan_lean()
    new_score = get_configuration_score(target)

    # Check population conditions (with move applied)
    pop_ok = _population_conditions_met()

    # Accept if score improved AND population conditions met
    if new_score >= current_score and pop_ok:
        # Success! Reset rejected tracking
        _reset_rejected_tracking()
        # Mode-specific bookkeeping on success
        if mode == 'follow_the_leader':
            follow_the_leader_state = from_state
            last_moved_county = pivot_county
        elif mode in ['bfs', 'dfs']:
            traversal_visited.add(pivot_county)
            # Add neighbors of the taken county to frontier (expand the wave)
            for neighbor in county_to_neighbors.get(pivot_county, []):
                if neighbor not in traversal_visited and county_to_state.get(neighbor) != state_to_grow:
                    traversal_frontier.append(neighbor)
        return True, False, pivot_county  # (success, heap_used=False, pivot_county for accepted)

    # Move was worse or population conditions not met - undo it
    state_to_counties[state_to_grow].remove(pivot_county)
    state_to_counties[from_state].add(pivot_county)
    county_to_state[pivot_county] = from_state
    compute_state_to_bordering_counties()
    compute_state_to_partisan_lean()

    # If population was OK, this was a valid but worse move - track it for potential future use
    if pop_ok:
        iterations_since_exchange += 1
        _add_rejected_move(new_score, pivot_county, state_to_grow, from_state)

        # With probability alpha, try to execute the best rejected move from the heap
        if np.random.random() < alpha:
            if _try_execute_best_reject(target):
                _reset_rejected_tracking()
                # Mode-specific bookkeeping for heap-selected move
                # Note: We don't know which county was moved, so skip follow_the_leader/bfs/dfs bookkeeping
                return True, True, None  # (success, heap_used, pivot_county unknown for heap move)

    return False, False, pivot_county  # (rejected, heap_used=False, pivot_county for visualization)

def _population_conditions_met():
    global state_to_counties, county_to_population
    for _, counties in state_to_counties.items():
        if not counties:
            return False
        state_pop = sum(county_to_population[county] for county in counties)
        if state_pop < 100000:
            return False
        
    return True

def compute_election_winner():
    global state_to_partisan_lean
    r_win, d_win = 0, 0
    for state, partisan_lean in state_to_partisan_lean.items():
        if partisan_lean > 0:
            r_win += state_to_ev[state]
        else:
            d_win += state_to_ev[state]
    if r_win > d_win:
        return 'Republican', r_win, d_win
    elif d_win > r_win:
        return 'Democratic', d_win, r_win
    else:
        return 'Tie', r_win, d_win

def main():

    time_start = time.time()
    compute_state_to_bordering_counties(year = YEAR)
    print(f"Time taken to compute state to bordering counties: {time.time() - time_start} seconds")
    generate_initial_partisan_lean()
    print(f"Time taken to generate initial partisan lean: {time.time() - time_start} seconds")
    # Track average partisan lean and county count for each state over iterations
    state_names = list(state_to_counties.keys())
    partisan_lean_history = {state: [] for state in state_names}
    county_count_history = {state: [] for state in state_names}
    
    # Record initial values
    for state in state_names:
        counties = state_to_counties[state]
        county_count_history[state].append(len(counties))
        if counties:
            avg_lean = sum(county_to_partisan_lean[county] * county_to_population[county] for county in counties) / sum(county_to_population[county] for county in counties)
        partisan_lean_history[state].append(avg_lean)
    
    # Run simulation and record values after each iteration
    for _ in range(NUM_ITERATIONS):
        iteration()
        for state in state_names:
            counties = state_to_counties[state]
            county_count_history[state].append(len(counties))
            if counties:
                avg_lean = sum(county_to_partisan_lean[county] * county_to_population[county] for county in counties) / sum(county_to_population[county] for county in counties)
            else:
                avg_lean = 0
            partisan_lean_history[state].append(avg_lean)
    
    # Create the plots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 12))
    iterations = range(NUM_ITERATIONS + 1)  # +1 to include initial state
    
    # Plot 1: Number of counties per state
    for state in state_names:
        ax1.plot(iterations, county_count_history[state], label=state, alpha=0.7)
    
    ax1.set_xlabel('Iteration')
    ax1.set_ylabel('Number of Counties')
    ax1.set_title('Number of Counties per State Over Iterations')
    ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Average partisan lean per state
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