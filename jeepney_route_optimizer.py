import pandas as pd
import geopandas as gpd
import folium
import networkx as nx
from shapely.geometry import Point, Polygon
from shapely import wkt
import osmnx as ox
from scipy.spatial.distance import euclidean
from shapely.ops import transform
from pyproj import Transformer
import random

# Load geographical data for barangays
barangay_geo_data = pd.read_csv(r'C:\Users\roblo\DS PROJ\brgy_geography.csv')
barangay_geo_data = barangay_geo_data[['uuid', 'adm4_pcode', 'geometry']]
barangay_geo_data['geometry'] = barangay_geo_data['geometry'].apply(lambda x: wkt.loads(x) if isinstance(x, str) else None)

# Load population data
population_data = pd.read_csv(r'C:\Users\roblo\DS PROJ\barangay_population.csv', header=None)
population_data.columns = ['adm4_pcode', 'Population Percentage', 'Total Population']
population_data['Total Population'] = pd.to_numeric(population_data['Total Population'].str.replace(',', ''), errors='coerce')

# Function to calculate barangay area
def calculate_area(polygon):
    transformer = Transformer.from_crs("epsg:4326", "epsg:32651", always_xy=True)  # UTM zone 51N for Davao
    if isinstance(polygon, Polygon):
        projected_polygon = transform(transformer.transform, polygon)
        return projected_polygon.area
    return None

# Add calculated areas to the geo data
barangay_geo_data['brgy_total_area'] = barangay_geo_data['geometry'].apply(calculate_area)

# Merge geo and population data
barangay_data = barangay_geo_data.merge(population_data, how='left', on='adm4_pcode')

# Load old jeepney routes
old_routes_df = pd.read_csv(r'C:\Users\roblo\DS PROJ\old_jeepney_routes.csv')

# Load OSM graph of Davao City
G = ox.graph_from_place('Davao City, Philippines', network_type='drive')

# Add population data to the graph nodes
for idx, row in barangay_data.iterrows():
    if isinstance(row['geometry'], Polygon):
        centroid = row['geometry'].centroid
        nearest_node = ox.distance.nearest_nodes(G, X=centroid.x, Y=centroid.y)
        if nearest_node is not None:
            G.nodes[nearest_node]['population'] = row['Total Population']

# Function to assign population density to edges, accounting for multi-graph edges
def assign_population_density_to_edges(G, barangay_data):
    for index, row in barangay_data.iterrows():
        if row['brgy_total_area'] > 0:  # Ensure valid area
            density = row['Total Population'] / row['brgy_total_area']
            for u, v, k, data in G.edges(keys=True, data=True):  # Unpack multi-graph edge with key
                # Assign population density to the edge if it's part of a barangay
                G.edges[u, v, k]['population_density'] = density

assign_population_density_to_edges(G, barangay_data)

# Custom weight function
def compute_weight(u, v, data):
    length = data.get('length', 1)
    population_density = data.get('population_density', 1)
    return length / population_density

# Max routes per edge
occupied_edges = {}
MAX_ROUTES_PER_EDGE = 10

# Optimize single route
def optimize_route(start_coords, end_coords, route_id, route_name):
    start_node = ox.distance.nearest_nodes(G, X=start_coords[1], Y=start_coords[0])
    end_node = ox.distance.nearest_nodes(G, X=end_coords[1], Y=end_coords[0])

    try:
        # Optimize to end
        path_to_end = nx.shortest_path(G, source=start_node, target=end_node, weight=compute_weight)
        path_edges = [(path_to_end[i], path_to_end[i + 1]) for i in range(len(path_to_end) - 1)]

        for edge in path_edges:
            occupied_edges[edge] = occupied_edges.get(edge, 0) + 1
            if occupied_edges[edge] > MAX_ROUTES_PER_EDGE:
                print(f"Edge {edge} blocked for route {route_name}, finding alternative...")
                G.remove_edge(*edge)
                path_to_end = nx.shortest_path(G, source=start_node, target=end_node, weight=compute_weight)
                G.add_edges_from([edge])  # Restore edge

        # Complete loop back to start
        path_to_start = nx.shortest_path(G, source=end_node, target=start_node, weight=compute_weight)
        full_path = path_to_end + path_to_start[1:]

        return [(G.nodes[node]['y'], G.nodes[node]['x']) for node in full_path]

    except (nx.NodeNotFound, nx.NetworkXNoPath) as e:
        print(f"Route {route_name} error: {e}")
        return []

# Furthest points on a route
def find_furthest_points(geometry):
    if geometry:
        coords = list(geometry.coords)
        max_distance = 0
        furthest_pair = (coords[0], coords[0])
        for i in range(len(coords)):
            for j in range(i + 1, len(coords)):
                distance = euclidean(coords[i], coords[j])
                if distance > max_distance:
                    max_distance = distance
                    furthest_pair = (coords[i], coords[j])
        return furthest_pair
    return None, None

# Generate a random color
def generate_random_color():
    return f'#{random.randint(0, 0xFFFFFF):06x}'

# Optimize all routes
combined_map = folium.Map(location=[7.1907, 125.4553], zoom_start=12)
for idx, row in old_routes_df.iterrows():
    route_name = row['name']  # Get the jeepney route name
    route_geom = wkt.loads(row['geometry'])
    start_coords, end_coords = find_furthest_points(route_geom)

    if start_coords and end_coords:
        start_coords = (start_coords[1], start_coords[0])
        end_coords = (end_coords[1], end_coords[0])
        print(f"Optimizing route {route_name} from {start_coords} to {end_coords}...")
        path_coords = optimize_route(start_coords, end_coords, idx, route_name)

        if path_coords:
            route_feature_group = folium.FeatureGroup(name=f'{route_name}')
            color = generate_random_color()  # Assign a random color to each route
            folium.PolyLine(
                locations=path_coords, 
                color=color, 
                weight=5, 
                opacity=0.7, 
                tooltip=f'Route: {route_name}'
            ).add_to(route_feature_group)
            route_feature_group.add_to(combined_map)

# Add Layer Control and Save Map
folium.LayerControl().add_to(combined_map)
output_path = r'C:\Users\roblo\DS PROJ\combined_jeepney_routes.html'
combined_map.save(output_path)
print(f"Map saved to {output_path}")