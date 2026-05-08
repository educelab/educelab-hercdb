import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

# ── Node groups ──────────────────────────────────────────────────────────────
PHYSICAL   = ["PHerc", "Cornice", "Pezzo"]
IDENTITY   = ["EduceLabID"]
METADATA   = ["Author", "Language", "Unroller", "UnrollingMethod",
               "OsloMethod", "CavalloScribalStyle", "CustodialInstitution",
               "CustodialLocation", "ObjectFormat", "MaterialType", "Disegni"]
DATASETS   = ["FlatbedScanDataset", "PGSRaw", "SpectralRaw"]
PIPELINE   = ["Pipeline", "Process", "PGSProcessed", "SpectralProcessed",
               "Registered", "WebProcessed"]

ALL_NODES  = PHYSICAL + IDENTITY + METADATA + DATASETS + PIPELINE

COLOR_MAP = {
    "physical":  "#4e9af1",
    "identity":  "#f1c84e",
    "metadata":  "#6fcf97",
    "datasets":  "#eb5757",
    "pipeline":  "#bb6bd9",
}

def node_color(n):
    if n in PHYSICAL:  return COLOR_MAP["physical"]
    if n in IDENTITY:  return COLOR_MAP["identity"]
    if n in METADATA:  return COLOR_MAP["metadata"]
    if n in DATASETS:  return COLOR_MAP["datasets"]
    if n in PIPELINE:  return COLOR_MAP["pipeline"]
    return "#cccccc"

# ── Edges (source, target, label) ────────────────────────────────────────────
EDGES = [
    # Physical hierarchy
    ("PHerc",     "Cornice",     "HAS"),
    ("PHerc",     "Pezzo",       "HAS"),
    ("Cornice",   "Pezzo",       "HAS"),
    # Identity
    ("EduceLabID","PHerc",       "ASSIGNED_TO"),
    ("EduceLabID","Cornice",     "ASSIGNED_TO"),
    ("EduceLabID","Pezzo",       "ASSIGNED_TO"),
    ("EduceLabID","EduceLabID",  "REPLACES"),
    # Disegni
    ("Disegni",   "PHerc",       "DEPICTS"),
    # Custodial
    ("PHerc",     "CustodialInstitution", "STORED_AT"),
    ("CustodialInstitution", "CustodialLocation", "LOCATED_AT"),
    # Metadata attachments (shown once from PHerc, implied for Cornice/Pezzo/Disegni)
    ("PHerc",     "ObjectFormat",       "HAS_OBJECT_FORMAT"),
    ("PHerc",     "MaterialType",       "HAS_MATERIAL_TYPE"),
    ("PHerc",     "Language",           "HAS_LANGUAGE"),
    ("PHerc",     "Unroller",           "UNROLLED_BY"),
    ("PHerc",     "UnrollingMethod",    "UNROLLED_BY_METHOD"),
    ("PHerc",     "OsloMethod",         "METHOD"),
    ("PHerc",     "Author",             "AUTHORED_BY"),
    ("PHerc",     "CavalloScribalStyle","STYLE"),
    # Datasets → EduceLabID
    ("FlatbedScanDataset", "EduceLabID", "BELONGS_TO"),
    ("PGSRaw",             "EduceLabID", "BELONGS_TO"),
    ("SpectralRaw",        "EduceLabID", "BELONGS_TO"),
    # Pipeline
    ("PGSRaw",           "Process",           "INPUT"),
    ("SpectralRaw",      "Process",           "INPUT"),
    ("Process",          "PGSProcessed",      "OUTPUT"),
    ("Process",          "SpectralProcessed", "OUTPUT"),
    ("PGSProcessed",     "Process",           "INPUT"),
    ("SpectralProcessed","Process",           "INPUT"),
    ("Process",          "Registered",        "OUTPUT"),
    ("Registered",       "Process",           "INPUT"),
    ("Process",          "WebProcessed",      "OUTPUT"),
    ("Process",          "Pipeline",          "STAGE_OF"),
]

G = nx.DiGraph()
G.add_nodes_from(ALL_NODES)
for src, dst, lbl in EDGES:
    G.add_edge(src, dst, label=lbl)

# ── Manual positions (grouped layout) ────────────────────────────────────────
pos = {
    # Physical – centre
    "PHerc":    (0, 0),
    "Cornice":  (-1.2, -1.2),
    "Pezzo":    (0,    -2.2),

    # Identity – just left of physical
    "EduceLabID": (-2.5, 0),

    # Disegni – above PHerc
    "Disegni": (0, 1.5),

    # Custodial – right of PHerc
    "CustodialInstitution": (2.2, 1.2),
    "CustodialLocation":    (3.8, 1.2),

    # Metadata – spread right/lower-right
    "Author":             (2.2, 0),
    "Language":           (3.5, 0),
    "Unroller":           (2.2, -1.2),
    "UnrollingMethod":    (3.5, -1.2),
    "OsloMethod":         (2.2, -2.4),
    "CavalloScribalStyle":(3.5, -2.4),
    "ObjectFormat":       (2.2, -3.6),
    "MaterialType":       (3.5, -3.6),

    # Datasets – left side
    "FlatbedScanDataset": (-4.0, -1.0),
    "PGSRaw":             (-4.0, -2.2),
    "SpectralRaw":        (-4.0, -3.4),

    # Pipeline – bottom
    "Pipeline":           (-1.0, -5.2),
    "Process":            (-2.5, -4.0),
    "PGSProcessed":       (-4.5, -5.0),
    "SpectralProcessed":  (-3.0, -5.8),
    "Registered":         (-1.5, -6.6),
    "WebProcessed":       (0.0,  -7.4),
}

fig, ax = plt.subplots(figsize=(22, 18))
ax.set_facecolor("#1a1a2e")
fig.patch.set_facecolor("#1a1a2e")

colors = [node_color(n) for n in G.nodes()]

nx.draw_networkx_nodes(G, pos, ax=ax, node_color=colors,
                       node_size=2200, alpha=0.9)
nx.draw_networkx_labels(G, pos, ax=ax,
                        font_size=7.5, font_color="white", font_weight="bold")

# Draw edges with curved arrows so bidirectional edges are visible
nx.draw_networkx_edges(G, pos, ax=ax,
                       edge_color="#aaaaaa", arrows=True,
                       arrowsize=15, width=1.2,
                       connectionstyle="arc3,rad=0.08",
                       node_size=2200, min_source_margin=18, min_target_margin=18)

# Edge labels – skip self-loops to avoid clutter
edge_labels = {(s, d): lbl for s, d, lbl in EDGES if s != d}
nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, ax=ax,
                              font_size=5.5, font_color="#ffdd88",
                              bbox=dict(boxstyle="round,pad=0.1", fc="#1a1a2e", alpha=0.6))

# Legend
patches = [
    mpatches.Patch(color=COLOR_MAP["physical"],  label="Physical object"),
    mpatches.Patch(color=COLOR_MAP["identity"],  label="Identity / UUID"),
    mpatches.Patch(color=COLOR_MAP["metadata"],  label="Metadata"),
    mpatches.Patch(color=COLOR_MAP["datasets"],  label="Raw datasets"),
    mpatches.Patch(color=COLOR_MAP["pipeline"],  label="Pipeline / processing"),
]
ax.legend(handles=patches, loc="upper right", fontsize=9,
          facecolor="#2a2a4e", labelcolor="white", edgecolor="#555555")

ax.set_title("hercdb – Neo4j graph schema (loader-derived)",
             color="white", fontsize=13, pad=12)
ax.axis("off")

out = Path(__file__).parent / "hercdb_schema.png"
fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
print(f"Saved → {out}")
