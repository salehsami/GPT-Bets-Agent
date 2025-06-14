from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import chatbot  # import your chatbot logic here
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret')
socketio = SocketIO(app, cors_allowed_origins="*")

@socketio.on('connect')
def on_connect():
    emit('chat_response', {'msg': 'Welcome to GPT Bets Ai'})

@socketio.on('user_message')
def handle_user_message(data):
    user_text = data.get('msg', '')
    reply = chatbot.handle_query(chatbot.load_chat_history(), user_text)
    emit('chat_response', {'msg': reply})

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    socketio.run(app)
