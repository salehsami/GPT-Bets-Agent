# main.py
import os
import logging
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain.memory import ConversationBufferMemory

from tools import odds_api_tool

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()
if not os.getenv("OPENAI_API_KEY") or not os.getenv("ODDS_API_KEY"):
    logger.error("Missing API keys in .env")
    exit(1)

# Initialize the LLM
llm = ChatOpenAI(model="gpt-4", api_key=os.getenv("OPENAI_API_KEY"), temperature=0.3)

# Build the prompt template
prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """
Hey champ! 🏆 I'm your odds buddy. Ask me for sports, odds, events, scores, history—I'll fetch it swiftly.
Use either format:
Format 1: action=<method>;param1:value1;param2:value2
Format 2: action;param1:value1;param2:value2

Examples:
- list_sports
- list_odds;sport:soccer_epl;regions:us
- get_scores;sport:basketball_nba;days_from:1
""",
    ),
    ("placeholder", "{chat_history}"),
    ("human", "{query}"),
    ("placeholder", "{agent_scratchpad}"),
])

# Create tool-calling agent
agent = create_tool_calling_agent(llm=llm, prompt=prompt, tools=[odds_api_tool])

if __name__ == "__main__":
    # Set up conversation memory to return BaseMessage list
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=[odds_api_tool],
        memory=memory,
        verbose=True
    )

    # Simple cache for repeated user queries
    cache = {}

    print("Type 'exit' to quit.")
    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() == "exit":
            break

        key = user_input.lower()
        # If we've answered this exact question before, return cached response
        if key in cache:
            print(f"Assistant (cached): {cache[key]}\n")
            continue

        # Otherwise, invoke the agent
        result = agent_executor.invoke({"query": user_input})
        assistant_reply = result.get("output", "I'm sorry, something went wrong.")
        print(f"Assistant: {assistant_reply}\n")

        # Store in cache
        cache[key] = assistant_reply


