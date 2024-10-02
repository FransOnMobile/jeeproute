import pandas as pd
import geopandas as gpd
import folium
import networkx as nx
from shapely.geometry import Point, Polygon
from shapely import wkt
import osmnx as ox
import random

# Load geographical data
barangay_geo_data = pd.read_csv(r'C:\Users\roblo\DS PROJ\brgy_geography.csv')
barangay_geo_data = barangay_geo_data[['uuid', 'adm4_pcode', 'brgy_total_area', 'geometry']]
barangay_geo_data['geometry'] = barangay_geo_data['geometry'].apply(lambda x: wkt.loads(x) if isinstance(x, str) else None)

# Load population data
population_data = pd.read_csv(r'C:\Users\roblo\DS PROJ\barangay_population.csv', header=None)
population_data.columns = ['adm4_pcode', 'Population Percentage', 'Total Population']
population_data['Total Population'] = pd.to_numeric(population_data['Total Population'].str.replace(',', ''), errors='coerce')

# Merge geo and population data
barangay_data = barangay_geo_data.merge(population_data, how='left', on='adm4_pcode')

# Load OSM graph of Davao City
G = ox.graph_from_place('Davao City, Philippines', network_type='drive')

# Add population data to the graph nodes
for idx, row in barangay_data.iterrows():
    if isinstance(row['geometry'], (Polygon, Point)):
        centroid = row['geometry'].centroid
        nearest_node = ox.distance.nearest_nodes(G, X=centroid.x, Y=centroid.y)
        if nearest_node is not None:
            G.nodes[nearest_node]['population'] = row['Total Population']

# Define start and end coordinates for each route manually
routes_data = {
    'Route Number': list(range(1, 53)),
    'Start Coordinates': [
        (7.093152421272088, 125.49993428160754), 
        (7.060619061795135, 125.55517022884592), 
        (7.114490100767806, 125.623088685563), 
        (7.043871022343036, 125.53111744849649), 
        (7.0885050905200835, 125.61302628385484),
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None],  # Add exact coordinates here
    'End Coordinates': [
        (7.075384225629551, 125.61106155040653), 
        (7.0757997012759315, 125.62515495212945), 
        (7.074108526329221, 125.62087799211763),  
        (7.075326222792941, 125.61106284055438), 
        (7.0629728010666035, 125.61118030919188),
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None],  # Add exact coordinates here
}

# Convert routes data to a DataFrame
routes_df = pd.DataFrame(routes_data)

# Create a color map for routes
colors = ["blue", "green", "red", "purple", "orange", "darkred", "lightred", "beige", "darkblue", "darkgreen", "cadetblue", "pink"]
random.shuffle(colors)  # Shuffle colors for random assignment

# Initialize a combined map
combined_map = folium.Map(location=(7.0792, 125.6099), zoom_start=12)

# Set to track occupied edges
occupied_edges = set()

# Find the nearest nodes for the start and end coordinates of each route
for idx, row in routes_df.iterrows():
    start_coords = row['Start Coordinates']
    end_coords = row['End Coordinates']
    
    # Skip routes with missing coordinates
    if start_coords is None or end_coords is None:
        print(f"Skipping route {row['Route Number']} due to missing coordinates.")
        continue
    
    start_node = ox.distance.nearest_nodes(G, X=start_coords[1], Y=start_coords[0])
    end_node = ox.distance.nearest_nodes(G, X=end_coords[1], Y=end_coords[0])

    # Use a population-weighted shortest path if applicable
    try:
        path = nx.shortest_path(G, source=start_node, target=end_node, weight='length')
        path_coords = [(G.nodes[node]['y'], G.nodes[node]['x']) for node in path]

        # Select a color for the current route
        route_color = colors[(row['Route Number'] - 1) % len(colors)]

        # Mark edges as occupied
        path_edges = [(path[i], path[i + 1]) for i in range(len(path) - 1)]
        if any(edge in occupied_edges for edge in path_edges):
            print(f"Route {row['Route Number']} blocked, looking for an alternative path...")
            # Temporarily remove edges
            for edge in path_edges:
                if edge in occupied_edges:
                    G.remove_edge(*edge)  # Remove the edge from the graph
            
            # Attempt to find an alternative path
            try:
                alternative_path = nx.shortest_path(G, source=start_node, target=end_node, weight='length')
                path_coords = [(G.nodes[node]['y'], G.nodes[node]['x']) for node in alternative_path]
                print(f"Alternative path found for route {row['Route Number']}.")
            except nx.NetworkXNoPath:
                print(f"No alternative path found for route {row['Route Number']}.")
                continue
            finally:
                # Restore the edges back to the graph
                G.add_edges_from(path_edges)

        # Plot the route on the combined map
        folium.PolyLine(locations=path_coords, color=route_color, weight=5, opacity=0.7).add_to(combined_map)

        # Add markers along the route with route labels
        for node in path:
            folium.Marker(
                location=[G.nodes[node]['y'], G.nodes[node]['x']],
                popup=f"Route {row['Route Number']} (Population: {G.nodes[node].get('population', 'N/A')})",
                icon=folium.Icon(color=route_color),
            ).add_to(combined_map)

        # Mark edges as occupied
        occupied_edges.update(path_edges)

    except nx.NodeNotFound as e:
        print(f"Error: {e} for route {row['Route Number']}")

# Save the combined map for all routes in a specified location
output_path = r'C:\Users\roblo\DS PROJ\combined_jeepney_routes.html'
combined_map.save(output_path)
print(f"Combined map saved as '{output_path}'.")

# Save the routes data to CSV for reference
routes_df.to_csv('jeepney_routes_with_coordinates.csv', index=False)
