The chatbot is up and runnign at

http://192.34.60.87:8000/chatbot

Do a post request


json body

{
    "user_id": "test123",
    "new_message": "What are some sharp indicators for today’s MLB slate?",
    "history": [
      { "role":"assistant", "content":"What’s your favorite sport?","timestamp":"2025-06-26T09:55:00Z" },
      { "role":"user",      "content":"I like basketball.",         "timestamp":"2025-06-26T09:56:00Z" },
      { "role":"assistant", "content":"Got it—NBA questions only!", "timestamp":"2025-06-26T09:57:00Z" },
      ]
}


Testing questions:
What are some sharp indicators for today’s MLB slate?
Lakers vs. Warriors at 7pm.
Who’s playing tonight?
I like basketball
