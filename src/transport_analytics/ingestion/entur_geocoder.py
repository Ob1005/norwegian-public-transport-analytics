import argparse
import os

import requests
from dotenv import load_dotenv

BASE_URL = "https://api.entur.io/geocoder/v1/autocomplete"


def search_stops(query: str, size: int = 5) -> dict:
    """Search Entur for public transport stops matching a text query."""
    load_dotenv()

    client_name = os.getenv("ENTUR_CLIENT_NAME")
    if not client_name:
        raise ValueError("ENTUR_CLIENT_NAME is missing from the .env file")

    response = requests.get(
        BASE_URL,
        headers={"ET-Client-Name": client_name},
        params={
            "text": query,
            "lang": "no",
            "size": size,
            "layers": "venue",
        },
        timeout=30,
    )
    response.raise_for_status()

    return response.json()


def main() -> None:
    """Search for stops using a terminal argument."""
    parser = argparse.ArgumentParser(
        description="Search Entur for Norwegian public transport stops."
    )
    parser.add_argument(
        "query",
        nargs="?",
        default="Oslo S",
        help="Stop name to search for. Defaults to Oslo S.",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=5,
        help="Maximum number of results. Defaults to 5.",
    )
    arguments = parser.parse_args()

    results = search_stops(arguments.query, arguments.size)

    print(f"Matching stops for '{arguments.query}':")

    for feature in results.get("features", []):
        properties = feature.get("properties", {})
        name = properties.get("name", "Unknown stop")
        stop_id = properties.get("id", feature.get("id", "Unknown ID"))
        print(f"- {name} ({stop_id})")


if __name__ == "__main__":
    main()