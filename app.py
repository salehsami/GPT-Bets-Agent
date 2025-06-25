import os
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import chatbot  # your chatbot module

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret')
socketio = SocketIO(app, cors_allowed_origins="*")

# Load chat history once at startup
chat_history = chatbot.load_chat_history()

@socketio.on('connect')
def on_connect():
    emit('chat_response', {'msg': 'Welcome to GPT Bets Ai Assistant, How can I help you?.'})
    # Save greeting to history
    chatbot.append_to_history(chat_history, 'assistant', 'Welcome! Ask me about sports.')

@socketio.on('user_message')
def handle_user_message(data):
    user_text = data.get('msg', '')
    # Append user message to history
    chatbot.append_to_history(chat_history, 'user', user_text)

    # Get bot response
    response = chatbot.handle_query(chat_history, user_text)

    # Append bot response to history
    chatbot.append_to_history(chat_history, 'assistant', response)

    emit('chat_response', {'msg': response})

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
