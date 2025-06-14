# chatbot.py

import os
import json
from datetime import datetime
from sports_api import OddsAPI
import openai
from dotenv import load_dotenv

load_dotenv()

# ─────────────── Environment & Initialization ───────────────
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    print("[Error] Missing OPENAI_API_KEY in environment")
    exit(1)

odds_api = OddsAPI(api_key=os.getenv("ODDS_API_KEY"), region="us")
if not odds_api.api_key:
    print("[Error] Missing ODDS_API_KEY in environment")
    exit(1)

# Where we’ll persist chat history between runs:
CHAT_HISTORY_FILE = "chat_history.json"


def load_chat_history():
    """
    Load chat history from disk if it exists; otherwise return an empty list.
    We store each turn as {"role": "user"/"assistant", "content": "...", "timestamp": "..."}.
    """
    if os.path.isfile(CHAT_HISTORY_FILE):
        try:
            with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return []


def save_chat_history(history):
    """Save the list of message dicts back to CHAT_HISTORY_FILE."""
    try:
        with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Warning] Failed to save chat history: {e}")


def append_to_history(history, role, content):
    """Helper to append a single message (with timestamp) to the in-memory list."""
    entry = {
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    history.append(entry)
    save_chat_history(history)


# ─────────────── Intent + Sport Detection ───────────────
def detect_intent_and_sport(user_text):
    text = user_text.lower().strip()

    greetings = ["hi", "hello", "hey", "good morning", "good evening", "good afternoon"]
    if text in greetings:
        return "greeting", None

    sports = odds_api.get_sports()
    sport_map = {s['title'].lower(): s['key'] for s in sports}
    key_map = {s['key'].lower(): s['key'] for s in sports}

    candidates = []
    for title_lower, key in sport_map.items():
        if title_lower in text:
            candidates.append((len(title_lower), key))
    for key_lower, key in key_map.items():
        if key_lower in text:
            candidates.append((len(key_lower), key))

    if candidates:
        _, sport_key = max(candidates, key=lambda x: x[0])
    else:
        sport_key = odds_api.find_sport_key(text)

    if "score" in text or "scores" in text:
        intent = "scores"
    elif "odds" in text or "bet" in text:
        intent = "odds"
    elif "home team" in text or "home-team" in text:
        intent = "home_team"
    elif any(w in text for w in ["next", "upcoming", "when is", "who is playing"]):
        intent = "next_event"
    else:
        intent = "next_event"

    return intent, sport_key


# ─────────────── Formatting Answer via GPT ───────────────
def format_answer_with_gpt(chat_history, data, user_query):
    system_prompt = (
        "You are a friendly, concise sports assistant. You have access to structured data "
        "about upcoming matches, scores, and betting odds. You also have broad sports knowledge. "
        "When the user asks a question, use the information provided below to give a helpful answer in natural language. "
        "Do not just dump JSON; interpret the data or answer from general knowledge if no data is available."
    )

    messages = [{"role": "system", "content": system_prompt}]

    # Trim history to last few turns to avoid token overflow
    max_turns = 6
    trimmed = chat_history[-max_turns:] if len(chat_history) > max_turns else chat_history
    for entry in trimmed:
        messages.append({"role": entry["role"], "content": entry["content"]})

    prompt_data = json.dumps(data, default=str, indent=2)
    combined = (
        f"User asked: \"{user_query}\"\n"
        f"Here is the data (JSON):\n{prompt_data}\n"
        "Based on this data or your knowledge, please give a helpful answer."
    )
    messages.append({"role": "user", "content": combined})

    try:
        resp = openai.chat.completions.create(
            # model="gpt-3.5-turbo", # o4-mini
            # model="o4-mini",
            
            model="gpt-4.1-nano",
            
            messages=messages,
            max_completion_tokens=4000,
            # max_tokens=4000,
            # temperature=0.3
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[Error] OpenAI API call failed: {e}")
        return str(data)


# ─────────────── Main Handler ───────────────
def handle_query(chat_history, user_input):
    intent, sport_key = detect_intent_and_sport(user_input)

    if intent == "greeting":
        return "Hey there! I can tell you about scores, upcoming matches, betting odds, or general sports info. What would you like to know?"

    # General query if no sport_key
    if not sport_key:
        api_data = {}  # no structured data
        return format_answer_with_gpt(chat_history, api_data, user_input)

    if intent == "scores":
        api_data = {"scores": odds_api.get_scores(sport_key, days_from=1)}
        if not api_data["scores"]:
            return "I don’t see any recent scores for that sport."
    elif intent == "odds":
        api_data = {"odds": odds_api.get_odds(sport_key, region=odds_api.region, markets="h2h")}  # noqa: E501
        if not api_data["odds"]:
            return "I don’t see any odds for that sport right now."
    elif intent == "home_team":
        events = odds_api.list_events(sport_key)
        if not events:
            return "I don’t see any upcoming games for that sport."
        next_game = sorted(events, key=lambda e: e.get("commence_time", ""))[0]
        api_data = {
            "home_team": next_game.get("home_team"),
            "away_team": next_game.get("away_team"),
            "commence_time": next_game.get("commence_time")
        }
    else:  # next_event
        events = odds_api.list_events(sport_key)
        if not events:
            return "I don’t see any upcoming games for that sport."
        api_data = {"next_games": sorted(events, key=lambda e: e.get("commence_time", ""))[:3]}

    return format_answer_with_gpt(chat_history, api_data, user_input)


# ─────────────── Interactive Loop ───────────────
if __name__ == "__main__":
    print("SportsBot is ready! (type 'exit' or 'quit' to stop)")
    chat_history = load_chat_history()

    while True:
        try:
            user_input = input("\nYou: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                print("Bot: Goodbye! 👋")
                break

            append_to_history(chat_history, "user", user_input)
            response = handle_query(chat_history, user_input)
            print(f"Bot: {response}")
            append_to_history(chat_history, "assistant", response)
        except KeyboardInterrupt:
            print("\nBot: Goodbye! 👋")
            break
        except Exception as err:
            print(f"[Error] Unexpected error in main loop: {err}")
            break

