# sports_api.py

import os
import requests
from requests import Session
from requests.exceptions import HTTPError
import difflib


class OddsAPI:
    """Client for The Odds API (v4), with cached sports and session-based requests."""
    def __init__(self, api_key=None, region="us"):
        self.api_key = api_key or os.getenv("ODDS_API_KEY")
        if not self.api_key:
            raise ValueError("Missing Odds API key")
        self.base_url = "https://api.the-odds-api.com/v4"
        self.session = Session()
        self.session.params = {'apiKey': self.api_key}
        self.region = region
        self._sports_cache = None

    def get_sports(self):
        if self._sports_cache is not None:
            return self._sports_cache
        try:
            resp = self.session.get(f"{self.base_url}/sports", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            self._sports_cache = data
            return data
        except HTTPError as http_err:
            print(f"[Error] Failed to fetch sports: {http_err}")
        except Exception as err:
            print(f"[Error] Unexpected error in get_sports: {err}")
        return []

    def find_sport_key(self, name):
        if not name:
            return None
        name = name.strip().lower()
        sports = self.get_sports()
        if not sports:
            return None
        keys = [s['key'].lower() for s in sports]
        titles = [s['title'].lower() for s in sports]
        options = keys + titles
        matches = difflib.get_close_matches(name, options, n=1, cutoff=0.6)
        if matches:
            best = matches[0]
            for sport in sports:
                if sport['key'].lower() == best or sport['title'].lower() == best:
                    return sport['key']
        # Substring heuristics (e.g. "football" -> NFL)
        if "football" in name and "soccer" not in name:
            return "americanfootball_nfl"
        if "soccer" in name or ("football" in name and "soccer" in name):
            return "soccer_epl"
        if "basketball" in name or "nba" in name:
            return "basketball_nba"
        if "baseball" in name or "mlb" in name:
            return "baseball_mlb"
        if "cricket" in name:
            for sport in sports:
                if sport['key'].startswith("cricket_"):
                    return sport['key']
        if "hockey" in name or "nhl" in name:
            return "icehockey_nhl"
        if "tennis" in name:
            for sport in sports:
                if sport['key'].startswith("tennis_"):
                    return sport['key']
        return None

    def list_events(self, sport_key):
        if not sport_key:
            return []
        try:
            url = f"{self.base_url}/sports/{sport_key}/events"
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except HTTPError as http_err:
            print(f"[Error] /events failed for {sport_key}: {http_err}")
        except Exception as err:
            print(f"[Error] Unexpected error in list_events: {err}")
        return []

    def get_scores(self, sport_key, days_from=1):
        if not sport_key:
            return []
        try:
            params = {'daysFrom': days_from}
            url = f"{self.base_url}/sports/{sport_key}/scores"
            resp = self.session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except HTTPError as http_err:
            print(f"[Error] /scores failed for {sport_key}: {http_err}")
        except Exception as err:
            print(f"[Error] Unexpected error in get_scores: {err}")
        return []

    def get_odds(self, sport_key, region=None, markets=None):
        if not sport_key:
            return []
        try:
            params = {}
            if region:
                params['regions'] = region
            if markets:
                params['markets'] = markets
            url = f"{self.base_url}/sports/{sport_key}/odds"
            resp = self.session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except HTTPError as http_err:
            print(f"[Error] /odds failed for {sport_key}: {http_err}")
        except Exception as err:
            print(f"[Error] Unexpected error in get_odds: {err}")
        return []