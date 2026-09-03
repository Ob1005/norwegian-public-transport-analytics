import os

import requests
from dotenv import load_dotenv

BASE_URL = "https://api.entur.io/journey-planner/v3/graphql"

DEPARTURES_QUERY = """
query GetDepartures($stopPlaceId: String!, $numberOfDepartures: Int!) {
  stopPlace(id: $stopPlaceId) {
    name
    estimatedCalls(numberOfDepartures: $numberOfDepartures) {
      realtime
      aimedDepartureTime
      expectedDepartureTime
      destinationDisplay {
        frontText
      }
      serviceJourney {
        journeyPattern {
          line {
            publicCode
            name
            transportMode
          }
        }
      }
    }
  }
}
"""


def get_departures(stop_place_id: str, number_of_departures: int = 5) -> dict:
    """Retrieve scheduled and real-time departures for an Entur stop."""
    load_dotenv()

    client_name = os.getenv("ENTUR_CLIENT_NAME")
    if not client_name:
        raise ValueError("ENTUR_CLIENT_NAME is missing from the .env file")

    response = requests.post(
        BASE_URL,
        headers={
            "ET-Client-Name": client_name,
            "Content-Type": "application/json",
        },
        json={
            "query": DEPARTURES_QUERY,
            "variables": {
                "stopPlaceId": stop_place_id,
                "numberOfDepartures": number_of_departures,
            },
        },
        timeout=30,
    )
    response.raise_for_status()

    result = response.json()
    if result.get("errors"):
        raise RuntimeError(f"Entur GraphQL error: {result['errors']}")

    return result["data"]


def main() -> None:
    """Display the next departures from Oslo S."""
    data = get_departures("NSR:StopPlace:59872")
    stop = data["stopPlace"]

    print(f"Next departures from {stop['name']}:")

    for call in stop["estimatedCalls"]:
        line = call["serviceJourney"]["journeyPattern"]["line"]
        destination = call["destinationDisplay"]["frontText"]

        print(
            f"- {line['transportMode']} {line['publicCode']} to {destination}: "
            f"{call['expectedDepartureTime']}"
        )


if __name__ == "__main__":
    main()