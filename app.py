# app.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from chatbot import handle_query, append_to_history
import uvicorn

app = FastAPI(title="GPTBETS AI Service")

class ChatPayload(BaseModel):
    user_id: str
    new_message: str
    history: list  # list of {"role":..., "content":..., "timestamp":...}

class ChatResponse(BaseModel):
    response: str
    updated_history: list

@app.post("/chatbot", response_model=ChatResponse)
def chat_endpoint(payload: ChatPayload):
    # validate
    if not payload.new_message or not isinstance(payload.history, list):
        raise HTTPException(400, "Invalid payload")
    # append user
    history = payload.history.copy()
    append_to_history(history, "user", payload.new_message)
    # get bot reply
    reply = handle_query(history, payload.new_message)
    # append assistant
    append_to_history(history, "assistant", reply)
    return ChatResponse(response=reply, updated_history=history)

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
