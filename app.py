"""
Flask web application for real-time US border redistricting visualization.
"""

from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import threading
import time
import numpy as np

from data_loader import DataLoader
from simple_algorithm import SimpleRedistrictingAlgorithm
from realtime_visualizer import RealtimeVisualizer

app = Flask(__name__)
app.config['SECRET_KEY'] = 'us-borders-secret-key'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Global state
data_loader = None
counties_data = None
neighbors = None
visualizer = None
ga_thread = None
is_running = False


def initialize_data():
    """Load data on startup."""
    global data_loader, counties_data, neighbors, visualizer

    print("Loading data...")
    data_loader = DataLoader()
    counties_data = data_loader.load_county_data()

    # FORCE REGENERATE political lean data with new N(X, abs(X)+1) distribution
    if True:  # Always regenerate for testing
        print("Generating synthetic political data with state-based variation...")
        import numpy as np
        np.random.seed(42)

        # Generate base lean X ~ Uniform(-20, 20) for each state (R to D)
        # Then sample each county from N(X, abs(X)+1)
        if 'STATEFP' in counties_data.columns:
            state_base_leans = {}
            for state in counties_data['STATEFP'].unique():
                state_base_leans[state] = np.random.uniform(-20, 20)

            # For each county, sample from N(X, abs(X)+1) where X is the state's base lean
            political_leans = []
            for idx in counties_data.index:
                state = counties_data.loc[idx, 'STATEFP']
                X = state_base_leans[state]
                sigma = abs(X) + 1
                county_lean = np.random.normal(X, sigma)
                political_leans.append(county_lean)

            counties_data['political_lean'] = political_leans
            print(f"Generated political leans: state base leans range from {min(state_base_leans.values()):.2f} to {max(state_base_leans.values()):.2f}")

            # DIAGNOSTIC: Show sample of leans to verify variation
            import pandas as pd
            sample_states = list(state_base_leans.keys())[:3]
            for state_fp in sample_states:
                state_counties = counties_data[counties_data['STATEFP'] == state_fp]
                state_leans = state_counties['political_lean'].values
                print(f"  State {state_fp}: base={state_base_leans[state_fp]:.2f}, counties range [{state_leans.min():.2f}, {state_leans.max():.2f}], mean={state_leans.mean():.2f}, std={state_leans.std():.2f}")
        else:
            # Fallback if no state data
            counties_data['political_lean'] = np.random.randn(len(counties_data)) * 0.3

    if 'POP' not in counties_data.columns:
        counties_data['POP'] = 100000

    neighbors = data_loader.compute_county_neighbors(counties_data)
    visualizer = RealtimeVisualizer(counties_data, neighbors)  # Pass neighbors dict!

    print(f"Loaded {len(counties_data)} counties")


@app.route('/')
def index():
    """Serve the main page."""
    return render_template('index.html')


@app.route('/api/initial-map')
def get_initial_map():
    """Get the initial state borders map."""
    if visualizer is None:
        return jsonify({'error': 'Data not loaded'}), 500

    img_base64 = visualizer.generate_initial_frame()
    return jsonify({'image': img_base64})


@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    print('Client connected')
    emit('status', {'message': 'Connected to server'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    print('Client disconnected')


@socketio.on('start_algorithm')
def handle_start_algorithm(data):
    """Start the genetic algorithm with specified parameters."""
    global ga_thread, is_running

    if is_running:
        emit('error', {'message': 'Algorithm already running'})
        return

    # Get parameters from client
    iterations = data.get('generations', 500)  # Use 'generations' param as iterations

    print(f"Starting simple iterative algorithm: {iterations} iterations")

    # Run algorithm in background thread
    def run_algorithm():
        global is_running
        is_running = True

        try:
            # Create simple algorithm instance
            algo = SimpleRedistrictingAlgorithm(
                counties_data=counties_data,
                neighbors=neighbors,
                num_states=50
            )

            iteration_count = [0]

            # Define callback for updates
            def update_callback(iteration, solution):
                global is_running
                import time

                # Stop if requested
                if not is_running:
                    return False  # Signal to stop

                try:
                    callback_start = time.time()
                    iteration_count[0] = iteration

                    # Update EVERY iteration for smooth animation
                    # Calculate fitness for display (just for stats)
                    stats_start = time.time()
                    state_pops, state_leans = algo.get_state_stats()
                    pop_variance = np.var(state_pops)
                    fitness = -pop_variance / 1e9  # Negative variance (higher is better)
                    stats_time = time.time() - stats_start

                    # Generate visualization
                    viz_start = time.time()
                    img_base64 = visualizer.generate_frame(solution, iteration, fitness)
                    viz_time = time.time() - viz_start

                    # Send update to client
                    emit_start = time.time()
                    socketio.emit('generation_update', {
                        'generation': iteration,
                        'fitness': float(fitness),
                        'total_generations': iterations,
                        'image': img_base64
                    })
                    emit_time = time.time() - emit_start

                    callback_time = time.time() - callback_start

                    # Log timing every 10 iterations
                    if iteration % 10 == 0:
                        print(f"Iter {iteration}: callback={callback_time:.3f}s (stats={stats_time:.3f}s, viz={viz_time:.3f}s, emit={emit_time:.3f}s)")

                    return True  # Continue

                except Exception as e:
                    print(f"Error in callback: {e}")
                    import traceback
                    traceback.print_exc()
                    return False  # Stop on error

            # Run algorithm with callback
            algo.run(iterations, callback=update_callback)

            # Send completion
            socketio.emit('algorithm_complete', {
                'final_fitness': 0.0,
                'generations': iterations
            })

        except Exception as e:
            print(f"Error running algorithm: {e}")
            import traceback
            traceback.print_exc()
            socketio.emit('error', {'message': str(e)})

        finally:
            is_running = False

    ga_thread = threading.Thread(target=run_algorithm)
    ga_thread.daemon = True
    ga_thread.start()

    emit('algorithm_started', {
        'iterations': iterations
    })


@socketio.on('stop_algorithm')
def handle_stop_algorithm():
    """Stop the currently running algorithm."""
    global is_running
    is_running = False
    emit('algorithm_stopped', {'message': 'Algorithm stopped'})


if __name__ == '__main__':
    # Initialize data on startup
    initialize_data()

    # Run Flask app
    print("\n" + "=" * 60)
    print("US Border Redistricting - Web Interface")
    print("=" * 60)
    print("\nServer starting on http://localhost:5000")
    print("Open your browser and navigate to http://localhost:5000")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 60 + "\n")

    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
