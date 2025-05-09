import pandas as pd
import plotly.graph_objects as go
import gzip
import py7zr
from pathlib import Path

# Load structure data
with gzip.open("../data/inflation.csv.gz", "rt") as f:
    df = pd.read_csv(f)

#df = df.iloc[::2]  # Keep every 2nd row
df = df.sample(frac=0.1, random_state=42)  # Keep 10% of rows

# Prepare 3D volume data
x = df["col"]
y = df["row"]
z = df["layer"]
value = df["curvature"]

# Identify black hole points
bh_df = df[df["is_black_hole"] == True]

# Build 3D plot with volume and black holes
fig = go.Figure()

# Curvature volume
fig.add_trace(go.Volume(
    x=x, y=y, z=z, value=value,
    isomin=0.01, isomax=value.max(),
    opacity=0.1, surface_count=20,
    colorscale="Plasma",
    caps=dict(x_show=False, y_show=False, z_show=False)
))

# Black hole scatter
fig.add_trace(go.Scatter3d(
    x=bh_df["col"],
    y=bh_df["row"],
    z=bh_df["layer"],
    mode="markers",
    marker=dict(size=4, color="red", symbol="circle"),
    name="Black Holes"
))

fig.update_layout(
    scene=dict(
        xaxis_title="col",
        yaxis_title="row",
        zaxis_title="layer"
    ),
    title="3D Curvature Field with Black Holes"
)

base_path = Path(__file__).resolve().parent
assets_path = base_path.parent / "assets"
html_file = assets_path / "curvature_3d_plot.html"
zip_file = assets_path / "curvature_3d_plot.7z"

fig.write_html(html_file, auto_open=False)

with py7zr.SevenZipFile(zip_file, 'w') as archive:
    archive.write(html_file)

print(f"Created {zip_file}")
