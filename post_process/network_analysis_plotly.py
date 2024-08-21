import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotter
from pathlib import Path

if __name__ == '__main__':
    outputs = Path("/home/gray/git/oedisi_dopf/outputs")
    branch_info, bus_info = plotter.extract_dataframes(outputs/"omoo_single_step/topology.json")

