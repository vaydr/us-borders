"""
Visualization module for displaying redistricted state borders.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from matplotlib.colors import LinearSegmentedColormap


class MapVisualizer:
    """Creates visualizations of redistricted states."""

    def __init__(self, counties_gdf):
        self.counties = counties_gdf

    def plot_redistricting(self, solution_df, output_path="output/new_borders.png", show_stats=True):
        """
        Plot the new state borders with political coloring.

        Args:
            solution_df: GeoDataFrame with 'new_state' column
            output_path: Path to save the output image
            show_stats: Whether to show statistics on the plot
        """
        fig, axes = plt.subplots(1, 2, figsize=(20, 8))

        # Create colormap: blue (Democratic) to red (Republican)
        colors = ['#0015BC', '#9999FF', '#FFFFFF', '#FF9999', '#BC0000']
        n_bins = 100
        cmap = LinearSegmentedColormap.from_list('political', colors, N=n_bins)

        # Plot 1: Original states
        ax1 = axes[0]
        if 'STATEFP' in solution_df.columns and 'political_lean' in solution_df.columns:
            solution_df.plot(
                column='political_lean',
                cmap=cmap,
                vmin=-1,
                vmax=1,
                ax=ax1,
                edgecolor='black',
                linewidth=0.3,
                legend=False
            )
            ax1.set_title('Original State Borders\n(Colored by Political Lean)', fontsize=14, fontweight='bold')
        else:
            solution_df.plot(ax=ax1, edgecolor='black', linewidth=0.3, facecolor='lightgray')
            ax1.set_title('Original State Borders', fontsize=14, fontweight='bold')

        ax1.axis('off')

        # Plot 2: New states
        ax2 = axes[1]

        # Calculate average political lean for each new state
        state_avg_leans = solution_df.groupby('new_state')['political_lean'].mean()
        solution_df['new_state_lean'] = solution_df['new_state'].map(state_avg_leans)

        solution_df.plot(
            column='new_state_lean',
            cmap=cmap,
            vmin=-1,
            vmax=1,
            ax=ax2,
            edgecolor='black',
            linewidth=0.5,
            legend=False
        )
        ax2.set_title('Optimized State Borders\n(Colored by Average Political Lean)', fontsize=14, fontweight='bold')
        ax2.axis('off')

        # Add colorbar
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=-1, vmax=1))
        sm._A = []
        cbar = fig.colorbar(sm, ax=axes, orientation='horizontal', pad=0.05, aspect=50)
        cbar.set_label('Political Lean (Blue = Democratic, Red = Republican)', fontsize=12)

        # Add statistics if requested
        if show_stats:
            stats = self._calculate_statistics(solution_df)
            stats_text = (
                f"Statistics:\n"
                f"States: {stats['num_states']}\n"
                f"Avg Population: {stats['avg_population']:,.0f}\n"
                f"Population Std Dev: {stats['pop_std']:,.0f}\n"
                f"Political Homogeneity: {stats['homogeneity']:.3f}\n"
                f"Non-contiguous States: {stats['non_contiguous']}"
            )
            fig.text(0.5, 0.02, stats_text, ha='center', fontsize=10, family='monospace',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved map to {output_path}")
        plt.close()

    def plot_fitness_history(self, fitness_history, output_path="output/fitness_history.png"):
        """
        Plot the fitness evolution over generations.
        """
        fig, ax = plt.subplots(figsize=(10, 6))

        ax.plot(fitness_history, linewidth=2, color='#0066CC')
        ax.set_xlabel('Generation', fontsize=12)
        ax.set_ylabel('Best Fitness', fontsize=12)
        ax.set_title('Genetic Algorithm Fitness Evolution', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved fitness history to {output_path}")
        plt.close()

    def plot_state_comparison(self, solution_df, output_path="output/state_comparison.png"):
        """
        Create comparison plots showing state characteristics.
        """
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        # Calculate statistics by state
        new_state_stats = solution_df.groupby('new_state').agg({
            'POP': 'sum' if 'POP' in solution_df.columns else 'count',
            'political_lean': 'mean',
            'FIPS': 'count'  # Number of counties
        }).reset_index()

        # Plot 1: Population distribution
        ax1 = axes[0, 0]
        ax1.hist(new_state_stats['POP'], bins=30, color='skyblue', edgecolor='black')
        ax1.set_xlabel('Population', fontsize=10)
        ax1.set_ylabel('Number of States', fontsize=10)
        ax1.set_title('Population Distribution Across New States', fontsize=11, fontweight='bold')
        ax1.grid(True, alpha=0.3)

        # Plot 2: Political lean distribution
        ax2 = axes[0, 1]
        colors = ['blue' if x < 0 else 'red' for x in new_state_stats['political_lean']]
        ax2.bar(range(len(new_state_stats)), new_state_stats['political_lean'].sort_values(),
               color=colors, edgecolor='black', alpha=0.7)
        ax2.set_xlabel('State (sorted)', fontsize=10)
        ax2.set_ylabel('Average Political Lean', fontsize=10)
        ax2.set_title('Political Lean by State', fontsize=11, fontweight='bold')
        ax2.axhline(y=0, color='black', linestyle='--', linewidth=1)
        ax2.grid(True, alpha=0.3, axis='y')

        # Plot 3: Number of counties per state
        ax3 = axes[1, 0]
        ax3.hist(new_state_stats['FIPS'], bins=20, color='lightgreen', edgecolor='black')
        ax3.set_xlabel('Number of Counties', fontsize=10)
        ax3.set_ylabel('Number of States', fontsize=10)
        ax3.set_title('Counties per State Distribution', fontsize=11, fontweight='bold')
        ax3.grid(True, alpha=0.3)

        # Plot 4: Scatter plot of population vs political lean
        ax4 = axes[1, 1]
        scatter_colors = ['blue' if x < 0 else 'red' for x in new_state_stats['political_lean']]
        ax4.scatter(new_state_stats['POP'], new_state_stats['political_lean'],
                   c=scatter_colors, s=100, alpha=0.6, edgecolor='black')
        ax4.set_xlabel('Population', fontsize=10)
        ax4.set_ylabel('Political Lean', fontsize=10)
        ax4.set_title('Population vs Political Lean', fontsize=11, fontweight='bold')
        ax4.axhline(y=0, color='black', linestyle='--', linewidth=1)
        ax4.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved comparison plots to {output_path}")
        plt.close()

    def _calculate_statistics(self, solution_df):
        """Calculate statistics about the redistricting."""
        stats = {}

        # Number of states
        stats['num_states'] = solution_df['new_state'].nunique()

        # Population statistics
        if 'POP' in solution_df.columns:
            state_pops = solution_df.groupby('new_state')['POP'].sum()
            stats['avg_population'] = state_pops.mean()
            stats['pop_std'] = state_pops.std()
        else:
            stats['avg_population'] = 0
            stats['pop_std'] = 0

        # Political homogeneity (average within-state variance)
        state_variances = solution_df.groupby('new_state')['political_lean'].var()
        stats['homogeneity'] = 1 / (1 + state_variances.mean())  # Higher is more homogeneous

        # Non-contiguous states (simplified check)
        stats['non_contiguous'] = 0  # Would need proper contiguity check

        return stats

    def export_geojson(self, solution_df, output_path="output/new_states.geojson"):
        """
        Export the new state boundaries as GeoJSON.
        """
        # Dissolve counties into states, only keeping geometry
        # Use simple dissolve without aggregating other columns
        dissolved = solution_df[['new_state', 'geometry']].dissolve(by='new_state')
        dissolved.to_file(output_path, driver='GeoJSON')
        print(f"Exported new state boundaries to {output_path}")
