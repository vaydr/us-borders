"""
Real-time visualization for the Flask web app.
FAST rendering with consistent scale and smooth transitions.
"""

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for threading
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
import io
import base64


class RealtimeVisualizer:
    """Creates real-time visualizations for the web interface."""

    def __init__(self, counties_gdf, neighbors_dict=None):
        self.counties = counties_gdf

        # Pre-compute fixed map extent for consistent scale
        bounds = counties_gdf.total_bounds
        self.xlim = (bounds[0], bounds[2])
        self.ylim = (bounds[1], bounds[3])

        # Use provided neighbor dict (already computed!) - MUCH faster than geometry.touches()
        self.county_neighbors = {}
        if neighbors_dict:
            fips_to_idx = {fips: idx for idx, fips in enumerate(counties_gdf['FIPS'].tolist())}
            for fips, neighbor_fips_list in neighbors_dict.items():
                if fips in fips_to_idx:
                    idx = fips_to_idx[fips]
                    self.county_neighbors[idx] = set([
                        fips_to_idx[n] for n in neighbor_fips_list if n in fips_to_idx
                    ])

        # Create colormap
        colors = ['#0015BC', '#6B6BFF', '#FFFFFF', '#FF6B6B', '#BC0000']
        self.cmap = LinearSegmentedColormap.from_list('political', colors, N=100)

        # Cache for initial map
        self._initial_map_cache = None

        # CRITICAL OPTIMIZATION: Precompute ALL possible border edges at initialization
        print(f"Precomputing border edges for {len(counties_gdf)} counties...")
        self.border_edges = {}  # {(idx1, idx2): geometry}
        for idx in counties_gdf.index:
            county_geom = counties_gdf.loc[idx, 'geometry']
            for neighbor_idx in self.county_neighbors.get(idx, set()):
                if neighbor_idx > idx:  # Only process each pair once
                    neighbor_geom = counties_gdf.loc[neighbor_idx, 'geometry']
                    shared = county_geom.intersection(neighbor_geom)
                    if not shared.is_empty:
                        self.border_edges[(idx, neighbor_idx)] = shared

        print(f"Visualizer initialized with {len(counties_gdf)} counties, {len(self.border_edges)} border edges")

    def generate_frame(self, solution: np.ndarray, generation: int = 0, fitness: float = 0.0):
        """
        Generate a single frame showing current state borders.
        Shows thick state borders with county colors.

        Args:
            solution: Array mapping counties to states (MUST have exactly 50 states)
            generation: Current generation number
            fitness: Current fitness value

        Returns:
            Base64 encoded PNG image
        """
        import time
        frame_start = time.time()

        # CRITICAL: Verify state count
        num_states = len(np.unique(solution))
        assert num_states == 50, f"Solution has {num_states} states, expected 50!"

        setup_start = time.time()
        fig, ax = plt.subplots(1, 1, figsize=(14, 9), dpi=65)
        setup_time = time.time() - setup_start

        # Create index mapping: dataframe index -> array position
        idx_to_pos = {idx: pos for pos, idx in enumerate(self.counties.index)}

        # CRITICAL FIX: Color each county by its OWN lean, not state average!
        # This shows the variation within states
        color_start = time.time()
        county_colors = self.counties['political_lean'].values
        color_time = time.time() - color_start

        # Plot counties with thin edges (scale for -20 to +20 range)
        plot_start = time.time()
        self.counties.plot(
            ax=ax,
            color=[self.cmap((lean + 20.0) / 40.0) for lean in county_colors],
            edgecolor='#666666',
            linewidth=0.3,
            alpha=1.0
        )
        plot_time = time.time() - plot_start

        # Now draw thick state borders - use PRECOMPUTED edges!
        from shapely.geometry import LineString

        # Just check which precomputed edges cross state boundaries
        border_start = time.time()
        border_lines = []
        for (idx1, idx2), geom in self.border_edges.items():
            # Check if these two counties are in different states
            if idx1 in idx_to_pos and idx2 in idx_to_pos:
                state1 = solution[idx_to_pos[idx1]]
                state2 = solution[idx_to_pos[idx2]]
                if state1 != state2:
                    border_lines.append(geom)
        border_find_time = time.time() - border_start

        # Draw all state borders
        draw_start = time.time()
        for geom in border_lines:
            if geom.geom_type == 'LineString':
                x, y = geom.xy
                ax.plot(x, y, color='black', linewidth=2.5, solid_capstyle='round', zorder=10)
            elif geom.geom_type == 'MultiLineString':
                for line in geom.geoms:
                    x, y = line.xy
                    ax.plot(x, y, color='black', linewidth=2.5, solid_capstyle='round', zorder=10)
        draw_time = time.time() - draw_start

        # Set fixed extent
        ax.set_xlim(self.xlim)
        ax.set_ylim(self.ylim)
        ax.set_aspect('equal')

        ax.set_title(
            f'Iteration {generation}',
            fontsize=16,
            fontweight='bold',
            pad=15
        )
        ax.axis('off')

        # Convert to base64
        save_start = time.time()
        buf = io.BytesIO()
        plt.tight_layout(pad=0.5)
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=65, facecolor='white')
        plt.close(fig)
        buf.seek(0)

        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        save_time = time.time() - save_start

        total_time = time.time() - frame_start

        # Log timing every 10 frames
        if generation % 10 == 0:
            print(f"  VIZ BREAKDOWN: setup={setup_time:.3f}s, color={color_time:.3f}s, plot={plot_time:.3f}s, borders_find={border_find_time:.3f}s, borders_draw={draw_time:.3f}s, save={save_time:.3f}s, TOTAL={total_time:.3f}s")

        return img_base64

    def generate_initial_frame(self):
        """
        Generate the initial frame showing original state borders.
        CACHED: Only generates once, then reuses.

        Returns:
            Base64 encoded PNG image
        """
        # Return cached version if available
        if self._initial_map_cache is not None:
            return self._initial_map_cache

        fig, ax = plt.subplots(1, 1, figsize=(14, 9), dpi=65)

        if 'STATEFP' in self.counties.columns:
            # Color each county by its OWN lean (shows variation within states)
            county_colors = self.counties['political_lean'].values

            # Plot counties with thin edges
            self.counties.plot(
                ax=ax,
                color=[self.cmap((lean + 20.0) / 40.0) for lean in county_colors],  # Scale for -20 to +20 range
                edgecolor='#666666',
                linewidth=0.3,
                alpha=1.0
            )

            # Draw thick state borders - use PRECOMPUTED edges!
            from shapely.geometry import LineString
            border_lines = []

            for (idx1, idx2), geom in self.border_edges.items():
                state1 = self.counties.loc[idx1, 'STATEFP']
                state2 = self.counties.loc[idx2, 'STATEFP']
                if state1 != state2:
                    border_lines.append(geom)

            # Draw state borders
            for geom in border_lines:
                if geom.geom_type == 'LineString':
                    x, y = geom.xy
                    ax.plot(x, y, color='black', linewidth=2.5, solid_capstyle='round', zorder=10)
                elif geom.geom_type == 'MultiLineString':
                    for line in geom.geoms:
                        x, y = line.xy
                        ax.plot(x, y, color='black', linewidth=2.5, solid_capstyle='round', zorder=10)
        else:
            # No state info
            self.counties.plot(
                ax=ax,
                edgecolor='gray',
                linewidth=0.3,
                facecolor='lightgray'
            )

        # Set fixed extent
        ax.set_xlim(self.xlim)
        ax.set_ylim(self.ylim)
        ax.set_aspect('equal')

        ax.set_title(
            'Original US State Borders',
            fontsize=16,
            fontweight='bold',
            pad=15
        )
        ax.axis('off')

        # Convert to base64
        buf = io.BytesIO()
        plt.tight_layout(pad=0.5)
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=65, facecolor='white')
        plt.close(fig)
        buf.seek(0)

        img_base64 = base64.b64encode(buf.read()).decode('utf-8')

        # Cache it!
        self._initial_map_cache = img_base64
        return img_base64
