import pandas as pd
import geopandas as gpd
import folium
import networkx as nx
from shapely.geometry import Point, Polygon
from shapely import wkt
import osmnx as ox

# Load the Project CCHAIN geographical data from a CSV
barangay_geo_data = pd.read_csv(r'C:\Users\roblo\DS PROJ\brgy_geography.csv')  # Adjust path

# Filter necessary columns from the CCHAIN data
barangay_geo_data = barangay_geo_data[['uuid', 'adm4_pcode', 'brgy_total_area', 'geometry']]

# Convert 'geometry' column to a shapely Polygon or Point
barangay_geo_data['geometry'] = barangay_geo_data['geometry'].apply(lambda x: wkt.loads(x) if isinstance(x, str) else None)

# Load population data from barangay_population.csv (no header)
population_data = pd.read_csv(r'C:\Users\roblo\DS PROJ\barangay_population.csv', header=None)  # No header
population_data.columns = ['adm4_pcode', 'Population Percentage', 'Total Population']

# Convert 'Total Population' to numeric, forcing errors to NaN
population_data['Total Population'] = pd.to_numeric(population_data['Total Population'].str.replace(',', ''), errors='coerce')

# Merge the population data with geo data based on 'adm4_pcode'
barangay_data = barangay_geo_data.merge(population_data, how='left', on='adm4_pcode')

# Create a graph from the OSM road network
G = ox.graph_from_place('Davao City, Philippines', network_type='drive')

# Add population data to the nodes in the graph
for idx, row in barangay_data.iterrows():
    if isinstance(row['geometry'], (Polygon, Point)):
        centroid = row['geometry'].centroid
        nearest_node = ox.distance.nearest_nodes(G, X=centroid.x, Y=centroid.y)
        if nearest_node is not None:
            G.nodes[nearest_node]['population'] = row['Total Population']  # Store population data in the node

# Define starting and ending barangays using their adm4_pcode (e.g., Mintal and Roxas)
start_barangay = 'PH1102402126'  # Replace with correct adm4_pcode
end_barangay = 'PH1102402137'  # Replace with correct adm4_pcode

# Strip any leading or trailing spaces
start_barangay = start_barangay.strip()
end_barangay = end_barangay.strip()

# Find the nearest nodes for the start and end barangays
start_node = None
end_node = None

for idx, row in barangay_data.iterrows():
    if row['adm4_pcode'] == start_barangay and isinstance(row['geometry'], (Polygon, Point)):
        centroid = row['geometry'].centroid
        start_node = ox.distance.nearest_nodes(G, X=centroid.x, Y=centroid.y)
    elif row['adm4_pcode'] == end_barangay and isinstance(row['geometry'], (Polygon, Point)):
        centroid = row['geometry'].centroid
        end_node = ox.distance.nearest_nodes(G, X=centroid.x, Y=centroid.y)

# Debugging: Print start and end nodes
print("Start node:", start_node)
print("End node:", end_node)

# Use Dijkstra's algorithm to find the shortest path
try:
    path = nx.shortest_path(G, source=start_node, target=end_node, weight='length')  # Use 'length' as the weight
    print("Path found:", path)
except nx.NodeNotFound as e:
    print(f"Error: {e}")

# Get the geographical coordinates for each barangay along the path
path_coords = [(G.nodes[node]['y'], G.nodes[node]['x']) for node in path]

# Initialize a map centered around the path
route_map = folium.Map(location=path_coords[0], zoom_start=13)

# Plot the route on the map
folium.PolyLine(locations=path_coords, color='blue', weight=5).add_to(route_map)

# Add markers for each barangay along the path
for node in path:
    folium.Marker(
        location=[G.nodes[node]['y'], G.nodes[node]['x']],
        popup=f"{node} (Population: {G.nodes[node].get('population', 'N/A')})",
    ).add_to(route_map)

# Save and display the map
route_map.save('optimized_jeepney_route.html')
route_map
