"""
Ultra-optimized Flask app that visualizes my_sim.py
Client-side rendering - server only sends color mappings
"""
from flask import Flask, render_template, jsonify, send_file
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import threading
import time
import json

# Import TwoWayAlgorithm class
from my_sim import TwoWayAlgorithm

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Global data - use threading.Event for thread-safe stop signaling
stop_event = threading.Event()
is_running = False

# The algorithm instance - this holds all simulation state
algorithm = None

# State for pause/resume
paused_state = {
    'iteration': 0,
    'total_iterations': 0,
    'target': 'Republican',
    'mode': 'standard',
    'render_every': 10
}

# Best state tracking (snapshot when best score achieved)
best_state = {
    'score': float('-inf'),
    'iteration': 0,
    'snapshot': None  # Will store get_state_snapshot() result
}

# Saved initial state for reset
initial_snapshot = None

# 49 maximally distinguishable colors
PALETTE = [
    "#c5003a", "#01d97a", "#c00a9d", "#66d248", "#7d4fd6",
    "#b1e03b", "#2c50d5", "#b1c300", "#a936bc", "#ccff6c",
    "#d979ff", "#f5ca1e", "#0054c4", "#ffdd59", "#418cff",
    "#fffb81", "#7638a4", "#86ffa8", "#ff2f90", "#1d7200",
    "#f78dff", "#587a00", "#b990ff", "#ad8500", "#007dda",
    "#ff9e35", "#69509a", "#b1ffb4", "#bd0067", "#00eedd",
    "#f72a58", "#01b887", "#ff7bcb", "#417833", "#e29eff",
    "#cd8100", "#816fbd", "#f76926", "#a390e1", "#9e4900",
    "#922c7d", "#7a9746", "#ac1621", "#e1c571", "#9c2c4a",
    "#ff9f63", "#e47799", "#b17d3a", "#973725",
]

# state_id -> palette index (fixed at startup)
state_color_idx = {}


def generate_state_colors():
    """Assign each state a unique color index."""
    global state_color_idx
    state_color_idx = {}

    states = sorted([str(s) for s in algorithm.state_to_counties.keys()])
    for i, state in enumerate(states):
        state_color_idx[state] = i % len(PALETTE)


def get_county_colors():
    """Get county_id -> color_index mapping."""
    return {str(geoid): state_color_idx.get(str(state), 0)
            for geoid, state in algorithm.county_to_state.items()}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/geojson')
def get_geojson():
    """Serve the counties GeoJSON file."""
    return send_file('data/counties.geojson', mimetype='application/json')


def get_state_partisan_leans():
    """Calculate population-weighted average partisan lean for each state."""
    state_leans = {}
    for state, counties in algorithm.state_to_counties.items():
        if counties:
            total_pop = sum(algorithm.county_to_population.get(c, 0) for c in counties)
            if total_pop > 0:
                avg_lean = sum(
                    algorithm.county_to_partisan_lean.get(c, 0) * algorithm.county_to_population.get(c, 0)
                    for c in counties
                ) / total_pop
                state_leans[str(state)] = avg_lean
            else:
                state_leans[str(state)] = 0
        else:
            state_leans[str(state)] = 0
    return state_leans


def get_election_results():
    """Compute election winner using algorithm's logic."""
    algorithm.compute_state_to_partisan_lean()
    winner, winner_ev, loser_ev = algorithm.compute_election_winner()

    # Determine side1 and side2 EVs based on winner
    if winner == algorithm.side1:
        side1_ev, side2_ev = winner_ev, loser_ev
    elif winner == algorithm.side2:
        side1_ev, side2_ev = loser_ev, winner_ev
    else:  # Tie
        side1_ev, side2_ev = winner_ev, loser_ev

    return {
        'winner': winner,
        'side1': algorithm.side1,
        'side2': algorithm.side2,
        'side1_ev': side1_ev,
        'side2_ev': side2_ev,
        'side1_color': algorithm.color1,
        'side2_color': algorithm.color2,
        # Backwards compatible keys
        'r_ev': side1_ev,
        'd_ev': side2_ev
    }


@app.route('/api/init')
def init_data():
    """Get initial state: palette, county colors, neighbor data, and partisan lean."""
    # Build neighbors dict with string keys
    neighbors = {}
    for geoid, neighbor_list in algorithm.county_to_neighbors.items():
        neighbors[str(geoid)] = [str(n) for n in neighbor_list]

    # Build partisan lean dict with string keys
    partisan_lean = {str(geoid): lean for geoid, lean in algorithm.county_to_partisan_lean.items()}

    # Build population dict with string keys
    population = {str(geoid): pop for geoid, pop in algorithm.county_to_population.items()}

    # Build county to state mapping
    county_to_state_map = {str(geoid): str(state) for geoid, state in algorithm.county_to_state.items()}

    # Build state EVs and populations
    state_evs = dict(algorithm.state_to_ev)
    state_populations = {}
    for state, counties in algorithm.state_to_counties.items():
        state_populations[state] = sum(algorithm.county_to_population.get(c, 0) for c in counties)

    return jsonify({
        'palette': PALETTE,
        'colors': get_county_colors(),
        'neighbors': neighbors,
        'partisanLean': partisan_lean,
        'population': population,
        'stateLeans': get_state_partisan_leans(),
        'countyToState': county_to_state_map,
        'stateEVs': state_evs,
        'statePopulations': state_populations,
        'election': get_election_results(),
        # Include side configuration
        'sideConfig': {
            'side1': algorithm.side1,
            'side1_color': algorithm.color1,
            'side1_abbrev': getattr(algorithm, 'abbrev1', algorithm.side1[:3].upper()),
            'side2': algorithm.side2,
            'side2_color': algorithm.color2,
            'side2_abbrev': getattr(algorithm, 'abbrev2', algorithm.side2[:3].upper())
        }
    })


@socketio.on('connect')
def on_connect():
    print('Client connected')
    emit('status', {'message': 'Connected'})


@socketio.on('disconnect')
def on_disconnect():
    print('Client disconnected')


def get_current_score(target):
    """Get current configuration score for the given target."""
    algorithm.compute_state_to_partisan_lean()
    return algorithm.get_configuration_score(target)


@socketio.on('start_algorithm')
def start_algorithm(data):
    """Run simulation - sends only color updates, not images."""
    global is_running, paused_state, stop_event, best_state

    if is_running:
        emit('error', {'message': 'Already running'})
        return

    # Check if resuming from pause
    resume = data.get('resume', False)

    if resume and paused_state['iteration'] > 0:
        # Resume from where we left off
        start_iteration = paused_state['iteration']
        iterations = paused_state['total_iterations']
        render_every = paused_state['render_every']
        target = paused_state['target']
        mode = paused_state['mode']
        print(f"Resuming from iteration {start_iteration}/{iterations}, target: {target}, mode: {mode}")
    else:
        # Fresh start
        start_iteration = 0
        iterations = data.get('generations', 25000)
        render_every = data.get('render_every', 50)
        target = data.get('target', algorithm.side1)  # Default to algorithm's side1
        mode = data.get('mode', 'standard')
        print(f"Starting {iterations} iterations, updating every {render_every}, target: {target}, mode: {mode}")
        # Reset follow-the-leader state only on fresh start
        algorithm.reset_follow_the_leader()
        # Reset best state tracking on fresh start
        best_state = {
            'score': float('-inf'),
            'iteration': 0,
            'snapshot': None
        }

    # Clear stop event
    stop_event.clear()

    def run():
        global is_running, paused_state, best_state
        is_running = True
        heap_used_this_batch = False
        rejected_counties_batch = set()  # Track rejected counties between updates

        try:
            for i in range(start_iteration, iterations):
                # Check stop event (thread-safe)
                if stop_event.is_set():
                    # Save state for resume
                    paused_state = {
                        'iteration': i,
                        'total_iterations': iterations,
                        'target': target,
                        'mode': mode,
                        'render_every': render_every
                    }
                    socketio.emit('algorithm_paused', {
                        'generation': i,
                        'total': iterations,
                        'message': 'Paused - click play to resume'
                    })
                    break

                success, heap_used, pivot_county = algorithm.iteration_greedy(target, mode)
                if heap_used:
                    heap_used_this_batch = True

                # Track rejected counties (not accepted and has a pivot)
                if not success and pivot_county is not None:
                    rejected_counties_batch.add(str(pivot_county))

                # Send color update every N iterations
                if (i + 1) % render_every == 0 or (i + 1) == iterations:
                    if heap_used_this_batch:
                        socketio.emit('thinking')
                        heap_used_this_batch = False

                    score = get_current_score(target)
                    current_iter = i + 1

                    # Track best and save snapshot
                    if score > best_state['score']:
                        best_state = {
                            'score': score,
                            'iteration': current_iter,
                            'snapshot': algorithm.get_state_snapshot()
                        }

                    socketio.emit('color_update', {
                        'generation': current_iter,
                        'total': iterations,
                        'colors': get_county_colors(),
                        'stateLeans': get_state_partisan_leans(),
                        'countyToState': {str(geoid): str(state) for geoid, state in algorithm.county_to_state.items()},
                        'election': get_election_results(),
                        'score': score,
                        'bestScore': best_state['score'],
                        'bestIteration': best_state['iteration'],
                        'rejectedCounties': list(rejected_counties_batch)
                    })

                    # Clear rejected counties for next batch
                    rejected_counties_batch.clear()
            else:
                # Loop completed without break (not paused)
                paused_state['iteration'] = 0  # Clear pause state
                socketio.emit('algorithm_complete', {'generations': iterations})

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            socketio.emit('error', {'message': str(e)})

        finally:
            is_running = False

    thread = threading.Thread(target=run)
    thread.daemon = True
    thread.start()

    emit('algorithm_started', {'iterations': iterations, 'target': target, 'resumed': resume})


@socketio.on('stop_algorithm')
def stop_algorithm():
    global stop_event
    stop_event.set()  # Signal the thread to stop
    emit('algorithm_stopping', {'message': 'Stopping...'})


@socketio.on('reset_algorithm')
def reset_algorithm():
    global is_running, paused_state, stop_event, best_state, initial_snapshot
    stop_event.set()  # Stop any running algorithm
    is_running = False

    # Clear pause and best state
    paused_state = {
        'iteration': 0,
        'total_iterations': 0,
        'target': algorithm.side1,
        'mode': 'standard',
        'render_every': 10
    }
    best_state = {
        'score': float('-inf'),
        'iteration': 0,
        'snapshot': None
    }

    # Restore initial state from saved snapshot
    if initial_snapshot:
        algorithm.restore_state_snapshot(initial_snapshot)
    
    algorithm.reset_follow_the_leader()

    print("Algorithm reset to initial state")
    emit('reset_complete', {
        'colors': get_county_colors(),
        'stateLeans': get_state_partisan_leans(),
        'countyToState': {str(geoid): str(state) for geoid, state in algorithm.county_to_state.items()},
        'election': get_election_results()
    })


@socketio.on('restore_best')
def restore_best():
    """Restore to the best scoring state and set up to resume from there."""
    global is_running, paused_state, stop_event, best_state

    if best_state['iteration'] == 0 or best_state['snapshot'] is None:
        emit('error', {'message': 'No best state saved yet'})
        return

    # Stop if running
    stop_event.set()
    is_running = False

    # Restore state from best snapshot
    algorithm.restore_state_snapshot(best_state['snapshot'])

    # Set up paused_state to resume from best iteration
    paused_state = {
        'iteration': best_state['iteration'],
        'total_iterations': paused_state.get('total_iterations', 100000),
        'target': paused_state.get('target', algorithm.side1),
        'mode': paused_state.get('mode', 'standard'),
        'render_every': paused_state.get('render_every', 10)
    }

    print(f"Restored to best state at iteration {best_state['iteration']} with score {best_state['score']:.2f}")
    emit('best_restored', {
        'colors': get_county_colors(),
        'stateLeans': get_state_partisan_leans(),
        'countyToState': {str(geoid): str(state) for geoid, state in algorithm.county_to_state.items()},
        'election': get_election_results(),
        'score': best_state['score'],
        'iteration': best_state['iteration']
    })


if __name__ == '__main__':
    print("="*60)
    print("Initializing...")
    print("="*60)

    # Create algorithm instance with configurable sides
    # You can change these to customize the simulation
    algorithm = TwoWayAlgorithm(
        side1="Republican",
        color1="red",
        side2="Democrat",
        color2="blue"
    )
    # Custom abbreviations (optional - defaults to first 3 chars uppercased)
    algorithm.abbrev1 = "GOP"
    algorithm.abbrev2 = "DEM"
    
    # Initialize algorithm
    algorithm.compute_state_to_bordering_counties()
    algorithm.generate_initial_partisan_lean(2020)
    print(f"Initialized: {len(algorithm.state_to_counties)} states, {len(algorithm.county_to_state)} counties")

    # Save initial state for reset functionality
    initial_snapshot = algorithm.get_state_snapshot()
    print("Saved initial state for reset")

    # Generate initial state colors
    generate_state_colors()
    print(f"Generated colors for {len(state_color_idx)} states")

    print("="*60)
    print(f"Simulation configured for: {algorithm.side1} vs {algorithm.side2}")
    print("Server starting on http://localhost:5000")
    print("="*60)

    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
