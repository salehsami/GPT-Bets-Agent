import os
import requests
from datetime import datetime
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from langchain.tools import Tool
from tavily import TavilyClient
import logging
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_VERSIONS = {
    "football": "https://v3.football.api-sports.io",
    "basketball": "https://v1.basketball.api-sports.io",
    "formula-1": "https://v1.formula-1.api-sports.io",
    "baseball": "https://v1.baseball.api-sports.io",
}

SPORT_KEYS_CACHE = None

def tavily_search(query: str) -> str:
    try:
        client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        results = client.search(query, max_results=5)
        snippets = [result.get("content", "No content available") for result in results.get("results", [])]
        return "\n".join(snippets) if snippets else "No results found."
    except Exception as e:
        logger.error(f"Tavily search error: {e}")
        return f"Error performing search: {str(e)}"

search_tool = Tool(
    name="tavily_search",
    func=tavily_search,
    description="Search the web using Tavily Search for recent information, including live sports scores, odds, or performance data when APIs are unavailable."
)

wiki_api_wrapper = WikipediaAPIWrapper(top_k_results=1, doc_content_chars_max=200)
wiki_tool = WikipediaQueryRun(api_wrapper=wiki_api_wrapper)

def save_to_txt(data: str, filename: str = "research_output.txt") -> str:
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_text = f"--- Research Output ---\nTimestamp: {timestamp}\n\n{data}\n\n"
        with open(filename, "a", encoding="utf-8") as f:
            f.write(formatted_text)
        return f"Data successfully saved to {filename}"
    except Exception as e:
        logger.error(f"Error saving to file: {e}")
        return f"Error saving data: {str(e)}"

save_tool = Tool(
    name="save_text_to_file",
    func=save_to_txt,
    description="Saves text data to a file with a timestamp. Use for storing research, odds, or API results."
)

# API-Sports data tool
def get_apisports_data(input_str: str) -> str:
    try:
        # Parse input: sport=<sport>;data_type=<endpoint>;params=<key1:value1,key2:value2>
        params_dict = {}
        for part in input_str.split(";"):
            if "=" in part:
                key, value = part.split("=", 1)
                params_dict[key.strip()] = value.strip()
        
        sport = params_dict.get("sport")
        data_type = params_dict.get("data_type")
        params_str = params_dict.get("params", "")
        
        if not sport or not data_type:
            return "Error: 'sport' and 'data_type' are required."
        
        if sport.lower() not in API_VERSIONS:
            return f"Error: Unsupported sport '{sport}'. Available: {list(API_VERSIONS.keys())}"
        
        # Parse additional parameters
        query_params = {}
        if params_str:
            for param in params_str.split(","):
                if ":" in param:
                    key, value = param.split(":", 1)
                    query_params[key.strip()] = value.strip()
        
        # Construct API URL
        base_url = API_VERSIONS[sport.lower()]
        endpoint = data_type.lower()  # e.g., leagues, fixtures, odds, statistics
        url = f"{base_url}/{endpoint}"
        
        # Make API request
        headers = {"x-apisports-key": os.getenv("APISPORTS_API_KEY")}
        response = requests.get(url, headers=headers, params=query_params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        if not data.get("response"):
            logger.warning(f"No data in API-Sports response: {data}")
            if "errors" in data and "access" in data["errors"]:
                return f"Error: API-Sports account issue - {data['errors']['access']}"
            return "No data available for this request."
        return str(data.get("response"))
    
    except requests.HTTPError as e:
        logger.error(f"API-Sports HTTP error: {e}")
        if e.response.status_code == 401:
            return "Error: Invalid or unauthorized API-Sports key."
        elif e.response.status_code == 429:
            return "Error: API-Sports rate limit exceeded."
        return f"Error fetching API-Sports data: {str(e)}"
    except requests.RequestException as e:
        logger.error(f"API-Sports request error: {e}")
        return f"Error fetching API-Sports data: {str(e)}"
    except Exception as e:
        logger.error(f"API-Sports processing error: {e}")
        return f"Error processing API-Sports request: {str(e)}"

apisports_tool = Tool(
    name="apisports_data",
    func=get_apisports_data,
    description="""
        Fetches sports data from api-sports.io, including leagues, fixtures, odds, and statistics.
        Input format: sport=<sport>;data_type=<endpoint>;params=<key1:value1,key2:value2>.
        Available sports: football, basketball, formula-1, baseball.
        Endpoints: leagues, fixtures, odds, statistics, players.
        Example: sport=football;data_type=fixtures;params=league:39,season:2024,live:all
    """
)

# The Odds API data tool
def get_theoddsapi_data(input_str: str) -> str:
    global SPORT_KEYS_CACHE
    
    try:
        # Parse input: data_type=<type>;sport=<sport>;params=<key1:value1,key2:value2>
        params_dict = {}
        for part in input_str.split(";"):
            if "=" in part:
                key, value = part.split("=", 1)
                params_dict[key.strip()] = value.strip()
        
        data_type = params_dict.get("data_type")
        sport = params_dict.get("sport", "")
        params_str = params_dict.get("params", "")
        
        if not data_type:
            return "Error: 'data_type' is required."
        
        # Fetch sport keys if cache is empty
        if SPORT_KEYS_CACHE is None:
            try:
                response = requests.get(
                    "https://api.the-odds-api.com/v4/sports",
                    params={"apiKey": os.getenv("ODDS_API_KEY")},
                    timeout=10
                )
                response.raise_for_status()
                SPORT_KEYS_CACHE = {sport["key"]: sport for sport in response.json() if sport["active"]}
                logger.info("Fetched and cached sport keys from The Odds API.")
            except requests.RequestException as e:
                logger.error(f"Failed to fetch sport keys: {e}")
                return "Error: Unable to fetch valid sport keys from The Odds API."
        
        # Map generic sport to specific key
        if data_type.lower() != "sports" and sport:
            # Handle common sport aliases
            sport_mappings = {
                "soccer": ["soccer_usa_mls", "soccer_epl", "soccer_spain_la_liga"],
                "baseball": ["baseball_mlb"],
                "basketball": ["basketball_nba"],
                "football": ["americanfootball_nfl", "americanfootball_ufl"],
            }
            if sport.lower() in sport_mappings:
                # Select the first matching key that's active
                for key in sport_mappings[sport.lower()]:
                    if key in SPORT_KEYS_CACHE:
                        sport = key
                        break
                else:
                    return f"Error: No active sport key found for '{sport}'. Try 'soccer_usa_mls' or 'baseball_mlb'."
            elif sport not in SPORT_KEYS_CACHE:
                return f"Error: Invalid sport key '{sport}'. Available keys: {list(SPORT_KEYS_CACHE.keys())}"
        
        # Parse additional parameters
        query_params = {"apiKey": os.getenv("ODDS_API_KEY")}
        if params_str:
            for param in params_str.split(","):
                if ":" in param:
                    key, value = param.split(":", 1)
                    query_params[key.strip()] = value.strip()
        
        # Construct API URL
        base_url = "https://api.the-odds-api.com/v4"
        if data_type.lower() == "sports":
            url = f"{base_url}/sports"
        elif data_type.lower() in ["odds", "scores"]:
            if not sport:
                return "Error: 'sport' is required for odds or scores."
            url = f"{base_url}/sports/{sport}/{data_type}"
        else:
            return f"Error: Unsupported data_type '{data_type}'. Use: sports, odds, scores."
        
        # Make API request
        response = requests.get(url, params=query_params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        if not data:
            logger.warning(f"No data in The Odds API response: {data}")
            return "No data available for this request."
        return json.dumps(data, indent=2)
    
    except requests.HTTPError as e:
        logger.error(f"The Odds API HTTP error: {e}")
        if e.response.status_code == 401:
            return "Error: Invalid or unauthorized The Odds API key."
        elif e.response.status_code == 429:
            return "Error: The Odds API rate limit exceeded."
        elif e.response.status_code == 404:
            return f"Error: Invalid sport key or endpoint for The Odds API. Check sport key (e.g., soccer_usa_mls)."
        return f"Error fetching The Odds API data: {str(e)}"
    except requests.RequestException as e:
        logger.error(f"The Odds API request error: {e}")
        return f"Error fetching The Odds API data: {str(e)}"
    except Exception as e:
        logger.error(f"The Odds API processing error: {e}")
        return f"Error processing The Odds API request: {str(e)}"

theoddsapi_tool = Tool(
    name="theoddsapi_data",
    func=get_theoddsapi_data,
    description="""
        Fetches live odds or scores from the-odds-api.com. Input format: data_type=<type>;sport=<sport>;params=<key1:value1,key2:value2>.
        Data types: sports (list sports), odds, scores. Sport required for odds/scores (e.g., soccer_usa_mls, soccer_epl, baseball_mlb).
        Example: data_type=scores;sport=soccer_usa_mls;params=daysFrom:3,regions:us
    """
)

# Robust Odds API tool with direct key and enhanced features
def robust_oddsapi_query(input_str: str) -> str:
    """
    Query The Odds API with robust error handling and flexible input.
    Input format: data_type=<type>;sport=<sport>;params=<key1:value1,key2:value2>
    Example: data_type=odds;sport=soccer_epl;params=regions:us,markets:h2h
    """
    API_KEY = "02fe6e8734f74f7547654e87da0ac7e4"  # Provided key
    BASE_URL = "https://api.the-odds-api.com/v4"
    try:
        # Parse input
        params_dict = {}
        for part in input_str.split(";"):
            if "=" in part:
                key, value = part.split("=", 1)
                params_dict[key.strip()] = value.strip()
        data_type = params_dict.get("data_type", "odds")
        sport = params_dict.get("sport", "")
        params_str = params_dict.get("params", "")

        # Build query params
        query_params = {"apiKey": API_KEY}
        if params_str:
            for param in params_str.split(","):
                if ":" in param:
                    k, v = param.split(":", 1)
                    query_params[k.strip()] = v.strip()

        # Build endpoint
        if data_type == "sports":
            url = f"{BASE_URL}/sports"
        elif data_type in ["odds", "scores"]:
            if not sport:
                return "Error: 'sport' is required for odds or scores. Try e.g. sport=soccer_epl."
            url = f"{BASE_URL}/sports/{sport}/{data_type}"
        elif data_type == "bookmakers":
            url = f"{BASE_URL}/bookmakers"
        elif data_type == "regions":
            url = f"{BASE_URL}/regions"
        elif data_type == "markets":
            url = f"{BASE_URL}/markets"
        else:
            return f"Error: Unsupported data_type '{data_type}'. Use: sports, odds, scores, bookmakers, regions, markets."

        # Make request
        resp = requests.get(url, params=query_params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return "No data available for this request."
        # Summarize for conversational output
        if isinstance(data, list):
            if len(data) > 5:
                summary = f"Showing {len(data)} results. Here are the first 3:\n"
                for item in data[:3]:
                    summary += json.dumps(item, indent=2) + "\n---\n"
                return summary
            else:
                return json.dumps(data, indent=2)
        elif isinstance(data, dict):
            return json.dumps(data, indent=2)
        else:
            return str(data)
    except requests.HTTPError as e:
        if e.response.status_code == 401:
            return "Error: Invalid or unauthorized Odds API key."
        elif e.response.status_code == 429:
            return "Error: Odds API rate limit exceeded."
        elif e.response.status_code == 404:
            return "Error: Invalid sport key or endpoint. Check your sport key (e.g., soccer_epl)."
        return f"HTTP error: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"

robust_oddsapi_tool = Tool(
    name="robust_oddsapi_data",
    func=robust_oddsapi_query,
    description="""
        Robust tool for The Odds API (v4). Supports endpoints: sports, odds, scores, bookmakers, regions, markets.\n
        Input: data_type=<type>;sport=<sport>;params=<key1:value1,key2:value2>\n
        Examples:\n
        - List sports: data_type=sports\n
        - Odds for EPL: data_type=odds;sport=soccer_epl;params=regions:us,markets:h2h\n
        - Scores for NBA: data_type=scores;sport=basketball_nba;params=daysFrom:1\n
        - List bookmakers: data_type=bookmakers\n
        - List regions: data_type=regions\n
        - List markets: data_type=markets\n    """
)