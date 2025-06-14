# tools.py
import os
import requests
import logging
import json
from datetime import datetime, timedelta
from langchain.tools import Tool
from dotenv import load_dotenv
from difflib import get_close_matches


load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OddsAPIClient:
    BASE_URL = "https://api.the-odds-api.com/v4"
    
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("ODDS_API_KEY")
        if not self.api_key:
            raise ValueError("Missing ODDS_API_KEY environment variable.")
        self._sports_cache = None
        self._sports_cache_time = datetime.min
        self.sport_key_map = {}   # title/description → key mapping
        self._load_sport_names()

    def _request(self, path, params=None):
        url = f"{self.BASE_URL}{path}"
        params = {**(params or {}), "apiKey": self.api_key}
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.HTTPError as e:
            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            return {"error": f"HTTP error: {e.response.status_code} - {e.response.text}"}
        except requests.RequestException as e:
            logger.error(f"Request exception: {str(e)}")
            return {"error": str(e)}

    def list_sports(self, all_sports=False):
        if (datetime.now() - self._sports_cache_time) < timedelta(hours=1) and self._sports_cache:
            logger.info("Returning cached sports data")
            return self._sports_cache
        params = {"all": "true"} if all_sports else {}
        data = self._request("/sports", params)
        if isinstance(data, dict) and "error" in data:
            logger.error(f"Error in list_sports: {data['error']}")
            return data
        elif isinstance(data, list):
            self._sports_cache = data
            self._sports_cache_time = datetime.now()
            logger.info(f"Cached {len(data)} sports")
            return data
        else:
            logger.warning("Unexpected response format in list_sports")
            return {"error": "Unexpected response format"}
        
    def _load_sport_names(self):
        logger.info("Loading sports metadata into memory...")
        sports = self.list_sports(all_sports=True)
        if isinstance(sports, list):
            for sport in sports:
                title = sport["title"].lower()
                desc = sport.get("description", "").lower()
                key = sport["key"]
                # Map both title and description to key
                self.sport_key_map[title] = key
                if desc:
                    self.sport_key_map[desc] = key
        logger.info(f"Loaded {len(self.sport_key_map)} sport name aliases.")


    def resolve_sport_key(self, user_input):
        """Resolve sport key using fuzzy matching with improved matching"""
        user_input = user_input.strip().lower()
        
        # First check exact matches
        if user_input in self.sport_key_map:
            return self.sport_key_map[user_input]
        
        # Try close matches with lower cutoff
        close_matches = get_close_matches(
            user_input, 
            self.sport_key_map.keys(), 
            n=1, 
            cutoff=0.5  # Lower threshold for better matching
        )
        
        if close_matches:
            return self.sport_key_map[close_matches[0]]
        
        # Try matching without underscores
        normalized_input = user_input.replace(' ', '_')
        if normalized_input in self.sport_key_map:
            return self.sport_key_map[normalized_input]
        
        logger.warning(f"No sport match found for: {user_input}")
        return None


    def list_odds(self, sport, regions=None, markets=None):
        assert sport, "Missing 'sport'. Try action=list_sports first."
        params = {}
        if regions:
            params["regions"] = regions
        if markets:
            params["markets"] = markets
        data = self._request(f"/sports/{sport}/odds", params)
        if isinstance(data, dict) and "error" in data:
            logger.error(f"Error in list_odds: {data['error']}")
            return data
        elif isinstance(data, list):
            return data
        else:
            logger.warning("Unexpected response format in list_odds")
            return {"error": "Unexpected response format"}

    def list_events(self, sport):
        assert sport, "Missing 'sport'."
        data = self._request(f"/sports/{sport}/events")
        if isinstance(data, dict) and "error" in data:
            logger.error(f"Error in list_events: {data['error']}")
            return data
        elif isinstance(data, list):
            return data
        else:
            logger.warning("Unexpected response format in list_events")
            return {"error": "Unexpected response format"}

    def get_event_odds(self, sport, event_id, markets=None):
        assert sport and event_id, "'sport' and 'event_id' required."
        params = {"markets": markets} if markets else {}
        data = self._request(f"/sports/{sport}/events/{event_id}/odds", params)
        if isinstance(data, dict) and "error" in data:
            logger.error(f"Error in get_event_odds: {data['error']}")
            return data
        elif isinstance(data, dict):
            return data
        else:
            logger.warning("Unexpected response format in get_event_odds")
            return {"error": "Unexpected response format"}

    def get_scores(self, sport, days_from=1):
        if not sport:
            return {"error": "Missing sport parameter"}
        # Add sport key resolution
        sport_key = self.resolve_sport_key(sport)
        if not sport_key:
            return {"error": f"Invalid sport: {sport}"}
        
        params = {"daysFrom": days_from}
        return self._request(f"/sports/{sport_key}/scores", params)
        
    # Update in OddsAPIClient class
# def get_scores(self, sport, days_from=1):
#     assert sport, "Missing 'sport'."
#     params = {"daysFrom": days_from}  # Changed to camelCase
#     return self._request(f"/sports/{sport}/scores", params)

# # Add this new method for event details
# def get_event_details(self, event_id):
#     assert event_id, "Missing 'event_id'."
#     return self._request(f"/events/{event_id}")

    def list_historical_odds(self, sport, date_iso, regions=None, markets=None):
        assert sport and date_iso, "'sport' and 'date_iso' required."
        params = {"date": date_iso}
        if regions:
            params["regions"] = regions
        if markets:
            params["markets"] = markets
        data = self._request(f"/historical/sports/{sport}/odds", params)
        if isinstance(data, dict) and "error" in data:
            logger.error(f"Error in list_historical_odds: {data['error']}")
            return data
        elif isinstance(data, list):
            return data
        else:
            logger.warning("Unexpected response format in list_historical_odds")
            return {"error": "Unexpected response format"}

odds_client = OddsAPIClient()

def odds_api_tool_func(query: str) -> str:
    logger.info(f"Processing query: {query}")
    try:
        # if not query.startswith("action="):
        #     return "Please provide a query in the format: action=<method>;param1:value1;param2:value2"
        # parts = query.split(";")
        # action = parts[0].split("=", 1)[1]
        # params = {}
        # for p in parts[1:]:
        #     if ":" in p:
        #         k, v = p.split(":", 1)
        #         params[k] = v
        
        # Handle both formats: with and without "action=" prefix
        if query.startswith("action="):
            parts = query.split(";")
            action = parts[0].split("=", 1)[1]
            params = {}
            for p in parts[1:]:
                if ":" in p:
                    k, v = p.split(":", 1)
                    params[k] = v
        else:
            # Handle format without "action=" prefix
            parts = query.split(";")
            action = parts[0]
            params = {}
            for p in parts[1:]:
                if ":" in p:
                    k, v = p.split(":", 1)
                    params[k] = v
                    
        # Convert expected types
        if 'days_from' in params:
            params['days_from'] = int(params['days_from'])
        if 'all_sports' in params:
            params['all_sports'] = params['all_sports'].lower() == 'true'
        # Call the method
        method = getattr(odds_client, action, None)
        if method is None:
            logger.error(f"Invalid action: {action}")
            return f"Invalid action: {action}. Available actions: list_sports, list_odds, list_events, get_event_odds, get_scores, list_historical_odds, etc."
        result = method(**params)
        logger.info(f"Method {action} returned type: {type(result)}")
        # Handle the result
        if isinstance(result, dict) and "error" in result:
            return f"Oops! {result['error']}"
        elif isinstance(result, list):
            summary = f"Found {len(result)} items. Here are the first 5:\n"
            summary += "\n---\n".join(json.dumps(i, indent=2) for i in result[:5])
            return summary
        elif isinstance(result, dict):
            return json.dumps(result, indent=2)
        else:
            logger.warning(f"Unexpected result type: {type(result)}")
            return "Unexpected result type"
    except Exception as e:
        logger.error(f"Error in odds_api_tool_func: {str(e)}")
        return f"Error: {str(e)}"

odds_api_tool = Tool(
    name="odds_api",
    func=odds_api_tool_func,
    description="Interact with the Odds API. Format: 'action;param1:value1;param2:value2' OR 'action=method;param1:value1'. Use list_sports to discover sports."
)