import os
import requests
from dotenv import load_dotenv

load_dotenv()

client_id = os.getenv("HYBLOCK_CLIENT_ID")
client_secret = os.getenv("HYBLOCK_CLIENT_SECRET")
api_key = os.getenv("HYBLOCK_API_KEY")

AUTH_URL = "https://auth-api.hyblockcapital.com/oauth2/token"
BASE_URL = "https://api1.hyblockcapital.com/v1"

def update_access_token():
    auth_data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.post(AUTH_URL, data=auth_data, headers=headers)
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        raise Exception(f"Failed to get access token: {response.text}")

def get_hyblock_data(endpoint: str, query: dict):
    access_token = update_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "x-api-key": api_key
    }
    url = BASE_URL + endpoint
    response = requests.get(url, headers=headers, params=query)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to fetch data from Hyblock: {response.text}")
