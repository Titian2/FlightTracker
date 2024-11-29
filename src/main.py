from dotenv import load_dotenv
import os
from api_utils import fetch_flight_data


project_dir = "/Users/simon/Dropbox/Python/WebScraping/Flights/project-root"



print('$$$$')
load_dotenv(dotenv_path=os.path.join(project_dir,'config/.env'))

# Retrieve the API key from the environment
access_token = os.getenv("DUFFEL_API_KEY")
if not access_token:
    raise ValueError("Duffel API key not found. Set it in the .env file.")

# Define the flight search parameters
offer_request = {
    "slices": [
        {"origin": "LAX", "destination": "GLA", "departure_date": "2024-12-01"},
        {"origin": "GLA", "destination": "LAX", "departure_date": "2024-12-08"}
    ],
    "passengers": [{"type": "adult"}],
    "cabin_class": "economy"
}

# Fetch flight data
response = fetch_flight_data(access_token, offer_request)

# Save the response to a file
print(os.getcwd()) 


output_file = os.path.join(project_dir,"data/duffel_response.json")
with open(output_file, "w") as f:
    import json
    json.dump(response, f, indent=4)

print("Flight data saved to", output_file)
        