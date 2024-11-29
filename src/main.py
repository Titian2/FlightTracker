#!/usr/bin/env python3
import os
import sys
import json
from dotenv import load_dotenv
from postmarker.core import PostmarkClient
from jinja2 import Template
from api_utils import fetch_flight_data  # Importing from api_utils.py
from datetime import datetime, timedelta
from IPython.core.display import display, HTML


# Add the src directory to the Python path
project_dir = "/Users/simon/Dropbox/Python/WebScraping/Flights/project-root"
sys.path.append(os.path.join(project_dir, "src"))

# Load environment variables
load_dotenv(dotenv_path=os.path.join(project_dir, 'config/.env'))

# Retrieve API keys from environment
DUFFEL_API_TOKEN = os.getenv("DUFFEL_API_KEY")
POSTMARK_API_TOKEN = os.getenv("POSTMARK_API_TOKEN")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")

# Validate API keys
if not DUFFEL_API_TOKEN:
    raise ValueError("Duffel API key not found. Set it in the .env file.")
if not all([POSTMARK_API_TOKEN, SENDER_EMAIL, RECEIVER_EMAIL]):
    raise ValueError("Postmark API variables are missing. Ensure POSTMARK_API_TOKEN, SENDER_EMAIL, and RECEIVER_EMAIL are set.")

# Initialize Postmark client
postmark = PostmarkClient(server_token=POSTMARK_API_TOKEN)

def get_dates_within_next_month():
    """
    Generate a list of dates within the next 30 days for flight departure.
    """
    today = datetime.today()
    return [(today + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(1, 31)]


def check_flights_under_price(flights, max_price):
    """
    Filter flights that are under a specified price.
    """
    return [flight for flight in flights if float(flight['price']) < max_price]



def get_top_cheapest_flights(json_data, top_n=5):
    """
    Extracts and ranks the top N cheapest flights from the API response, including airline codes.
    """
    offers = json_data.get('data', {}).get('offers', [])
    if not offers:
        return []

    # Convert prices to float for sorting
    for offer in offers:
        try:
            offer['total_amount'] = float(offer.get('total_amount', float('inf')))
        except ValueError:
            offer['total_amount'] = float('inf')

    # Sort offers by price
    sorted_offers = sorted(offers, key=lambda x: x['total_amount'])

    # Extract top N cheapest offers
    results = []
    for idx, offer in enumerate(sorted_offers[:top_n], start=1):
        total_price = offer.get('total_amount', 'N/A')
        currency = offer.get('total_currency', 'USD')
        slices = offer.get('slices', [])

        for flight_slice in slices:
            origin = flight_slice.get('origin', {}).get('name', 'Unknown Origin')
            destination = flight_slice.get('destination', {}).get('name', 'Unknown Destination')

            segments = flight_slice.get('segments', [])
            segment_details = []
            for segment in segments:
                # Prioritize operating carrier for the flight code
                airline = segment.get('operating_carrier', {}).get('name', 'Unknown Airline')
                flight_code = f"{segment['operating_carrier']['iata_code']}{segment.get('operating_carrier_flight_number', '')}"
                segment_details.append({
                    "origin": segment.get('origin', {}).get('iata_code'),
                    "destination": segment.get('destination', {}).get('iata_code'),
                    "departure": segment.get('departing_at'),
                    "arrival": segment.get('arriving_at'),
                    "airline": airline,
                    "flight_code": flight_code
                })

            results.append({
                "rank": idx,
                "price": f"{currency} {total_price:.2f}",
                "origin": origin,
                "destination": destination,
                "segments": segment_details
            })
            


    return results


# Prepare flight data with connections
def prepare_flight_data(flights, max_results=5):
    placeholder_logo = "https://via.placeholder.com/100x30?text=No+Logo"
    seen_flights = set()
    parsed_flights = []

    for flight in flights:
        slice_info = flight["slices"][0]
        segments = slice_info["segments"]

        # Skip flights with "Duffel Airways" as a carrier
        if any(
            segment.get("operating_carrier", {}).get("name") == "Duffel Airways"
            or segment.get("marketing_carrier", {}).get("name") == "Duffel Airways"
            for segment in segments
        ):
            continue

        num_connections = len(segments) - 1

        connections = []
        for segment in segments:
            operating_carrier = segment.get("operating_carrier", {})
            marketing_carrier = segment.get("marketing_carrier", {})

            carrier_name = operating_carrier.get("name") or marketing_carrier.get("name", "Unknown Carrier")
            flight_code = (
                f"{operating_carrier.get('iata_code', '')}{segment.get('operating_carrier_flight_number', '')}"
                if operating_carrier.get("iata_code") and segment.get("operating_carrier_flight_number")
                else f"{marketing_carrier.get('iata_code', '')}{segment.get('marketing_carrier_flight_number', '')}"
            ).strip()

            connections.append({
                "origin": segment["origin"]["iata_code"],
                "destination": segment["destination"]["iata_code"],
                "departure": format_time(segment["departing_at"]),
                "arrival": format_time(segment["arriving_at"]),
                "carrier": carrier_name,
                "flight_code": flight_code or "N/A"
            })

        price = float(flight["total_amount"])
        departure_time = format_time(segments[0]["departing_at"])
        arrival_time = format_time(segments[-1]["arriving_at"])
        logo_url = (
            segments[0].get("operating_carrier", {}).get("logo_symbol_url")
            or segments[0].get("marketing_carrier", {}).get("logo_symbol_url")
            or placeholder_logo
        )
        airline_name = operating_carrier.get("name") or marketing_carrier.get("name", "Unknown Airline")

        unique_key = (price, departure_time, arrival_time, num_connections)
        if unique_key in seen_flights:
            continue
        seen_flights.add(unique_key)

        parsed_flights.append({
            "logo_url": logo_url,
            "airline_name": airline_name,
            "origin": slice_info["origin"]["name"],
            "origin_code": slice_info["origin"]["iata_code"],
            "destination": slice_info["destination"]["name"],
            "destination_code": slice_info["destination"]["iata_code"],
            "departure_time": departure_time,
            "arrival_time": arrival_time,
            "price": f"{price:.2f}",
            "num_connections": num_connections,
            "connections": connections
        })

        if len(parsed_flights) == max_results:
            break

    return parsed_flights


def send_email_with_template(flights, origin, destination):
    """
    Sends an email with flight details using a Jinja2 HTML template.
    """
    if not flights:
        print("No flights available to send.")
        return

    # Subject line
    subject = f"Top 5 Cheapest Flights from {origin} to {destination}"

    # Load email template
    template_path = os.path.join(project_dir, "email_template.html")
    with open(template_path) as template_file:
        template = Template(template_file.read())

    # Cheapest price
    cheapest_price = flights[0]['price'] if flights else "N/A"

    # Render HTML email body
    email_body = template.render(
        cheapest_price=cheapest_price,
        flights=flights,
        action_url="https://your-flight-tracker.com/details",
        unsubscribe_url="https://your-flight-tracker.com/unsubscribe"
    )

    # Send the email
    try:
        postmark.emails.send(
            From=SENDER_EMAIL,
            To=RECEIVER_EMAIL,
            Subject=subject,
            HtmlBody=email_body
        )
        print("Email alert sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")

json_file_path = os.path.join(project_dir, "data/duffel_response.json")

# Load JSON data from file or switch to API response
def load_flight_data(from_api=False, api_response=None):
    if from_api and api_response:
        return api_response  # Use API response if provided
    else:
        with open(json_file_path, "r") as file:
            return json.load(file)["data"]["offers"]

# Format departure and arrival times
def format_time(iso_time):
    try:
        return datetime.fromisoformat(iso_time).strftime("%Y-%m-%d %I:%M %p")
    except ValueError:
        return iso_time  # Return original if parsing fails



def main():
    # Define the flight search parameters
    origin = "LAX"
    destination = "GLA"
    max_price = 600  # Price threshold in USD
    offer_request = {
        "slices": [
            {"origin": origin, "destination": destination, "departure_date": "2024-12-01"},
            {"origin": destination, "destination": origin, "departure_date": "2024-12-08"}
        ],
        "passengers": [{"type": "adult"}],
        "cabin_class": "economy"
    }

    # Fetch flight data using src/api_utils.py
    print("Fetching flight data...")
    response = fetch_flight_data(DUFFEL_API_TOKEN, offer_request)

    # Check response validity
    if not response or 'data' not in response or 'offers' not in response['data']:
        print("Failed to fetch valid flight data.")
        return

    # Save the raw response to a file
    output_file = os.path.join(project_dir, "data/duffel_response.json")
    with open(output_file, "w") as f:
        json.dump(response, f, indent=4)
    print(f"Flight data saved to {output_file}")

    # Load flights and process
    flights = load_flight_data()
    parsed_flights = prepare_flight_data(flights)

    # Filter flights under the price threshold
    filtered_flights = [flight for flight in parsed_flights if float(flight["price"]) < max_price]
    if not filtered_flights:
        print(f"No flights found under ${max_price}.")
        return

    # Extract top 5 cheapest flights from filtered results
    top_cheapest_flights = sorted(filtered_flights, key=lambda x: float(x["price"]))[:5]

    # Send email with flight details
    send_email_with_template(top_cheapest_flights, origin, destination)
    print(f"Email sent with flights under ${max_price}.")


if __name__ == "__main__":
    main()