from pymongo.server_api import ServerApi
from pymongo.mongo_client import MongoClient
from flask import Flask, render_template, request, redirect, url_for, Response, jsonify, session
from flask_socketio import join_room, SocketIO, emit
import time
import json


app = Flask(__name__)
app.secret_key = 'Wcit2007'

uri = "mongodb+srv://FanaticalRoute:Wcit2007@funproject.cnmatnh.mongodb.net/?retryWrites=true&w=majority"
client = MongoClient(uri, server_api=ServerApi('1'))
db = client["MostLikelyGame"]
question = db["questions"]
lobbies = db["lobbies"]

# Initialize Flask-SocketIO
socketio = SocketIO(app)


@socketio.on('join')
def on_join(lobby_code):
    join_room(lobby_code)
    emit('update_lobby', room=lobby_code)  # Emit update_lobby event


@app.route('/')
def index():
    return render_template('index.html')

# Home Page


@app.route('/process', methods=['POST'])
def process():
    display_name = request.form.get('display_name')
    session['display_name'] = display_name
    create_code = request.form.get('create_code')
    join_code = request.form.get('join_code')

    if create_code and join_code:
        # User has done both: creating and joining a lobby
        return "Error: You cannot create and join a lobby at the same time."
    if create_code:
        # User is creating a lobby and is the host
        new_lobby = {"lobby_code": create_code, "host": display_name, "users": [
            display_name], "game_state": "waiting", "questions": []}
        lobbies.insert_one(new_lobby)
        # Redirect to the lobby page
        return redirect(url_for('lobby', code=create_code))
    if join_code:
        # User is joining an existing lobby
        lobby = lobbies.find_one({"lobby_code": join_code})
        if lobby is None:
            return "Error: The lobby you are trying to join does not exist."

        if display_name in lobby['users']:
            return "Error: A user with this display name already exists in the lobby."

        if lobby:
            lobbies.update_one({"lobby_code": join_code}, {
                               "$push": {"users": display_name}})
            # Emit update_lobby event with updated users
            updated_lobby = lobbies.find_one({"lobby_code": join_code})
            socketio.emit('update_lobby', {
                          'users': updated_lobby['users']}, room=join_code)
            # Redirect to the lobby page
            return redirect(url_for('lobby', code=join_code))
        else:
            return "Error: The lobby you are trying to join does not exist."
    else:
        return "Error: Please either create a new lobby or join an existing one."

# Lobby page


@app.route('/lobby/<code>')
def lobby(code):
    lobby = lobbies.find_one({"lobby_code": code})
    display_name = session.get('display_name')

    return render_template('lobby.html', lobby=lobby, display_name=display_name)


@app.route('/stream/<code>')
def stream(code):
    def event_stream():
        while True:
            lobby = lobbies.find_one({"lobby_code": code})
            yield f"data: {json.dumps(lobby['users'])}\n\n"
            time.sleep(1)  # Sleep for 1 second before checking again
    return Response(event_stream(), mimetype="text/event-stream")


@app.route('/quit_lobby', methods=['POST'])
def quit_lobby():
    data = request.get_json()
    display_name = session.get('display_name')
    lobby_code = data['lobby_code']

    # Remove the user from the lobby
    result = lobbies.update_one({"lobby_code": lobby_code}, {
        "$pull": {"users": display_name}})

    # Retrieve the updated lobby
    updated_lobby = lobbies.find_one({"lobby_code": lobby_code})

    # Emit a custom event with the updated player list
    socketio.emit('update_players', {
                  'players': updated_lobby['users']}, room=lobby_code)

    # Emit 'update_lobby' event
    socketio.emit('update_lobby', room=lobby_code)

    return '', 200


@app.route('/start_game', methods=['POST'])
def start_game():
    lobby_code = request.get_json().get('lobby_code')

    # Update the game_state of the lobby to 'started'
    lobbies.update_one({"lobby_code": lobby_code}, {
                       "$set": {"game_state": "started"}})

    game_url = url_for('game', code=lobby_code)
    return jsonify({'status': 'success', 'game_url': game_url}), 200


@app.route('/game/<code>')
def game():
    # Get a random question from the database
    question = db.question.aggregate([{"$sample": {"size": 1}}])
    # Get the correct lobby based on the code
    lobby = db.lobby.find_one({"lobby_code": code})

    return render_template('game.html', question=question, lobby=lobby)


'''
# Game
questions = [
    {"id": 21, "question": "Who's most likely to fall asleep during a movie?"},
    {"id": 22, "question": "Who's most likely to laugh at the wrong moment?"},
    {"id": 23, "question": "Who's most likely to actually be a spy?"},
    {"id": 24, "question": "Who's most likely to spend all their money on something stupid?"},
]

question.insert_many(questions)
'''


if __name__ == '__main__':
    try:
        client.admin.command('ping')
        print("Pinged your deployment. You successfully connected to MongoDB!")
    except Exception as e:
        print(e)

    app.run(debug=True)
