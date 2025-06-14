import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage
from langchain.agents import create_tool_calling_agent, AgentExecutor
from tools import search_tool, wiki_tool, save_tool, apisports_tool, theoddsapi_tool
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
try:
    load_dotenv()
except Exception as e:
    logger.error(f"Failed to load .env file: {e}")
    exit(1)

# Validate API keys
required_keys = ["OPENAI_API_KEY", "APISPORTS_API_KEY", "ODDS_API_KEY", "TAVILY_API_KEY"]
for key in required_keys:
    if not os.getenv(key):
        logger.error(f"Missing environment variable: {key}")
        exit(1)

# Initialize OpenAI model
try:
    llm = ChatOpenAI(
        model="gpt-4o",
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=0.4
    )
except Exception as e:
    logger.error(f"Failed to initialize OpenAI model: {e}")
    exit(1)

# Define prompt template
prompt = ChatPromptTemplate.from_messages([
    ("system", """
        You are a helpful assistant specializing in live sports data. Use theoddsapi_data for live odds and scores, ensuring correct sport keys (e.g., soccer_epl, baseball_mlb).
        Use apisports_data for detailed sports data (leagues, fixtures, stats) if available, or tavily_search as a fallback for live scores, odds, or stats if APIs fail.
        Maintain conversational context, provide concise responses, and clearly explain any data retrieval issues.
    """),
    ("placeholder", "{chat_history}"),
    ("human", "{query}"),
    ("placeholder", "{agent_scratchpad}"),
])

# Initialize tools
tools = [search_tool, wiki_tool, save_tool, apisports_tool, theoddsapi_tool]

# Create agent
try:
    agent = create_tool_calling_agent(llm=llm, prompt=prompt, tools=tools)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
except Exception as e:
    logger.error(f"Failed to create agent: {e}")
    exit(1)

# Main interaction loop
def main():
    chat_history = []
    logger.info("Starting conversational agent. Type 'exit' to quit.")
    
    while True:
        try:
            query = input("You: ")
            if query.lower() == "exit":
                logger.info("Exiting program.")
                break
            
            # Invoke agent with query and chat history
            response = agent_executor.invoke({
                "query": query,
                "chat_history": chat_history
            })
            
            # Extract and display response
            assistant_response = response.get("output", "Sorry, I couldn't process that request.")
            print("Assistant:", assistant_response)
            
            # Update chat history
            chat_history.append(HumanMessage(content=query))
            chat_history.append(AIMessage(content=assistant_response))
            
        except KeyboardInterrupt:
            logger.info("Program interrupted by user.")
            break
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            print("Assistant: An error occurred. Please try again.")
            continue

if __name__ == "__main__":
    main()