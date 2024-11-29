import requests

def fetch_flight_data(access_token, offer_request):
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Duffel-Version': 'v2',
        'Content-Type': 'application/json'
    }
    response = requests.post(
        'https://api.duffel.com/air/offer_requests',
        headers=headers,
        json={"data": offer_request}
    )
    return response.json()