
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.collections import LineCollection
from matplotlib.patches import Circle
from matplotlib.animation import FFMpegWriter
from scipy.spatial import cKDTree
import subprocess

# --- config ---
rows, cols = 64, 64
timesteps = 100
FPS = 5
video_no_audio = '../assets/synthetic_crystal_growth_final_gravityfade.mp4'
background_music_path = '../assets/background_music_crystal_growth.mp3'
final_output = '../assets/synthetic_crystal_growth_final_gravityfade_with_music.mp4'
seed_points = [(rows // 2, cols // 2)]
grow_chance = 0.5
tail_length = 8
padding = 4
bh_count = 3000
figsize = (10, 10)
gravity_threshold = 0.08

# --- initialize ---
bh_positions = np.random.randint(0, rows, size=(bh_count, 2))
bh_stuck = np.full(bh_count, False, dtype=bool)
bh_latch_frame = np.full(bh_count, -1, dtype=int)

grid_history = []
gravity_map_history = []
active = np.zeros((rows, cols), dtype=bool)
gravity_seed = np.random.rand(rows, cols) * 0.08  # mock gravity_well

for r, c in seed_points:
    active[r, c] = True

for t in range(timesteps):
    new_active = active.copy()
    new_gravity = gravity_seed.copy()
    for r in range(rows):
        for c in range(cols):
            if not active[r, c]:
                neighbors = 0
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        if dr == 0 and dc == 0:
                            continue
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < rows and 0 <= nc < cols and active[nr, nc]:
                            neighbors += 1
                if 1 <= neighbors <= 3 and np.random.rand() < grow_chance:
                    new_active[r, c] = True
            if new_active[r, c]:
                new_gravity[r, c] += 0.01
    grid_history.append(new_active.copy())
    gravity_map_history.append(new_gravity.copy())
    active = new_active

plt.style.use('dark_background')
fig, ax = plt.subplots(figsize=figsize)
ax.set_facecolor('black')

def update(frame):
    global bh_positions, bh_stuck, bh_latch_frame
    ax.clear()
    ax.set_xlim(0 - padding, cols + padding)
    ax.set_ylim(0 - padding, rows + padding)
    ax.set_facecolor('black')
    ax.set_title(f'Timestep {frame}')

    grid = grid_history[frame]
    gravity_map = gravity_map_history[frame]
    lines = []
    alphas = []

    for age in range(tail_length):
        idx = frame - age
        if idx < 0:
            continue
        g = grid_history[idx]
        for r in range(rows):
            for c in range(cols):
                if g[r, c]:
                    for dr in [-1, 0, 1]:
                        for dc in [-1, 0, 1]:
                            if dr == 0 and dc == 0:
                                continue
                            nr, nc = r + dr, c + dc
                            if 0 <= nr < rows and 0 <= nc < cols and g[nr, nc]:
                                line = [(c, r), (nc, nr)]
                                lines.append(line)
                                alphas.append(1.0 - age / tail_length)

    filament_cells = np.argwhere(grid)
    latched_positions = []
    if len(filament_cells) > 0:
        tip_tree = cKDTree(filament_cells)
        for i, (r, c) in enumerate(bh_positions):
            if bh_stuck[i]:
                continue
            _, idx = tip_tree.query([r, c], k=1)
            tr, tc = filament_cells[idx]
            dr, dc = np.sign(tr - r), np.sign(tc - c)
            new_r, new_c = r + dr, c + dc
            if 0 <= new_r < rows and 0 <= new_c < cols:
                bh_positions[i] = [new_r, new_c]
                if grid[new_r, new_c]:
                    bh_stuck[i] = True
                    bh_latch_frame[i] = frame

    latched_positions = {tuple(p) for i, p in enumerate(bh_positions) if bh_stuck[i]}

    if lines:
        line_strengths = []
        for (x1, y1), (x2, y2) in lines:
            r1, c1 = int(y1), int(x1)
            r2, c2 = int(y2), int(x2)
            g1 = gravity_map[r1, c1] if 0 <= r1 < rows and 0 <= c1 < cols else 0
            g2 = gravity_map[r2, c2] if 0 <= r2 < rows and 0 <= c2 < cols else 0
            near_bh1 = any(abs(r1 - br) <= 1 and abs(c1 - bc) <= 1 for br, bc in latched_positions)
            near_bh2 = any(abs(r2 - br) <= 1 and abs(c2 - bc) <= 1 for br, bc in latched_positions)
            if (near_bh1 or near_bh2) or (g1 > gravity_threshold or g2 > gravity_threshold):
                line_strengths.append(1.0)
            else:
                line_strengths.append(0.1)

        base_colors = np.ones((len(lines), 4)) * np.array([0.5, 0.8, 1.0, 0.3])  # light blue with alpha
        base_colors[:, -1] *= line_strengths
        lc = LineCollection(lines, colors=base_colors, linewidths=2.5)
        ax.add_collection(lc)

        strong_lines = [line for i, line in enumerate(lines) if line_strengths[i] >= 1.0]
        if strong_lines:
            crisp = LineCollection(strong_lines, colors='white', linewidths=0.4, alpha=1.0)
            ax.add_collection(crisp)

    for i, (r, c) in enumerate(bh_positions):
        if bh_stuck[i]:
            pulse = 0.1 + 0.05 * np.sin(0.3 * (frame - bh_latch_frame[i]))
            ax.scatter(c, r, s=10, c='lime', alpha=0.9, marker='o', zorder=10)
            ax.scatter(c, r, s=120, c='lime', alpha=pulse, marker='o', zorder=9)
        else:
            ax.scatter(c, r, s=10, c='aqua', alpha=0.4, marker='o', zorder=8)

    # --- draw legend ---
    legend_x, legend_y = 2, rows + 2
    legend_items = [
        ("Filaments", 'white'),
        ("Free Black Holes", 'aqua'),
        ("Latched Black Holes", 'lime'),
    ]
    for i, (label, color) in enumerate(legend_items):
        ax.scatter(legend_x, legend_y - i * 2, s=20, color=color)
        ax.text(legend_x + 2, legend_y - i * 2, label, color='white', fontsize=8, va='center')

    return []

print("Rendering animation...")
writer = FFMpegWriter(fps=FPS, metadata=dict(artist='RipCrystal'), bitrate=1800)
ani = animation.FuncAnimation(fig, update, frames=timesteps, blit=True)
ani.save(video_no_audio, writer=writer)

print("Merging background music...")
subprocess.run([
    "ffmpeg", "-y",
    "-i", video_no_audio,
    "-i", background_music_path,
    "-c:v", "copy",
    "-c:a", "aac",
    "-map", "0:v", "-map", "1:a",
    "-shortest",
    final_output
], check=True)

print(f"Final video saved: {final_output}")
