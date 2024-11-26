# server.py

import socket
import threading
import logging
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
import uuid
import signal
import time

# Configure logging to write to a file and console with detailed debug information
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG for more detailed logs
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("server.log"),
        logging.StreamHandler(sys.stdout)
    ]
)


class Game:
    """
    Represents a Tic-Tac-Toe game between two players.
    Manages the game state, player turns, and game logic.
    """

    def __init__(self, game_id, server):
        """
        Initializes a new game with a unique game_id and a reference to the server.
        """
        self.game_id = game_id
        self.server = server  # Reference to the Server instance
        self.players = []  # List of player dictionaries
        self.board = [['' for _ in range(3)] for _ in range(3)]  # 3x3 Tic-Tac-Toe board
        self.current_player_index = 0  # Index of the current player in self.players
        self.winner = None  # Stores the winner's information or 'draw'
        self.lock = threading.Lock()  # Ensures thread-safe operations
        self.new_game_requests = set()  # Tracks players requesting a new game
        self.new_game_timer = None  # Timer for new game requests

    def add_player(self, client_info):
        """
        Adds a player to the game.
        """
        self.players.append(client_info)

    def make_move(self, player_uuid, position):
        """
        Processes a player's move.
        :param player_uuid: Unique identifier of the player making the move.
        :param position: Tuple (row, col) indicating the move's position.
        :return: Dictionary indicating the result of the move.
        """
        with self.lock:
            if self.winner:
                return {'status': 'failure', 'code': 'game_over', 'message': 'The game has already ended.'}

            player = next((p for p in self.players if p['uuid'] == player_uuid), None)
            if not player:
                return {'status': 'failure', 'code': 'invalid_player', 'message': 'Player not found in the game.'}

            current_player = self.players[self.current_player_index]
            if current_player['uuid'] != player_uuid:
                return {'status': 'failure', 'code': 'not_your_turn', 'message': 'It is not your turn.'}

            row, col = position
            if not (0 <= row <= 2 and 0 <= col <= 2):
                return {'status': 'failure', 'code': 'invalid_position', 'message': 'Position out of bounds.'}
            if self.board[row][col]:
                return {'status': 'failure', 'code': 'invalid_move', 'message': 'Position already occupied.'}

            # Make the move
            self.board[row][col] = player['symbol']
            logging.info(f"Game {self.game_id}: {player['username']} placed '{player['symbol']}' at position ({row}, {col}).")

            # Check for a winner
            if self.check_winner(player['symbol']):
                self.winner = player
                logging.info(f"Game {self.game_id}: {player['username']} has won the game.")
            elif self.is_draw():
                self.winner = 'draw'
                logging.info(f"Game {self.game_id}: The game ended in a draw.")
            else:
                # Switch to the next player's turn
                self.current_player_index = (self.current_player_index + 1) % len(self.players)
                logging.info(f"Game {self.game_id}: It is now {self.players[self.current_player_index]['username']}'s turn.")

            return {'status': 'success'}

    def check_winner(self, symbol):
        """
        Checks if the given symbol has won the game.
        :param symbol: 'X' or 'O'
        :return: True if the symbol has a winning combination, False otherwise.
        """
        # Rows, columns, and diagonals to check
        lines = self.board.copy()
        lines += [list(col) for col in zip(*self.board)]  # Add columns
        lines += [[self.board[i][i] for i in range(3)], [self.board[i][2 - i] for i in range(3)]]  # Add diagonals

        # Check each line for a win
        for line in lines:
            if all(cell == symbol for cell in line):
                return True
        return False

    def is_draw(self):
        """
        Checks if the game has ended in a draw.
        :return: True if all cells are occupied and there is no winner, False otherwise.
        """
        return all(cell for row in self.board for cell in row)

    def current_player_info(self):
        """
        Retrieves information about the current player.
        :return: Player dictionary of the current player.
        """
        return self.players[self.current_player_index]

    def winner_username(self):
        """
        Retrieves the username of the winner or 'draw'.
        :return: Winner's username, 'draw', or None.
        """
        if self.winner == 'draw':
            return 'draw'
        elif self.winner:
            return self.winner['username']
        else:
            return None

    def remove_player(self, player_uuid):
        """
        Removes a player from the game based on their UUID.
        :param player_uuid: Unique identifier of the player to remove.
        """
        self.players = [p for p in self.players if p['uuid'] != player_uuid]

    def handle_new_game_request(self, player_uuid):
        """
        Handles a player's request to start a new game.
        :param player_uuid: UUID of the player requesting a new game.
        """
        with self.lock:
            self.new_game_requests.add(player_uuid)
            logging.debug(f"Game {self.game_id}: Received new game request from {player_uuid}.")

            if len(self.new_game_requests) == len(self.players):
                # All players have requested a new game
                self.reset_game()
                self.new_game_requests.clear()
                if self.new_game_timer:
                    self.new_game_timer.cancel()
                    self.new_game_timer = None
                logging.info(f"Game {self.game_id}: All players have requested a new game.")
            else:
                # Start a timer to wait for other players
                if not self.new_game_timer:
                    self.new_game_timer = threading.Timer(30.0, self.check_new_game_requests)
                    self.new_game_timer.start()
                    logging.debug(f"Game {self.game_id}: Started new game timer.")

    def check_new_game_requests(self):
        """
        Checks if all players have requested a new game after a timeout.
        """
        with self.lock:
            if len(self.new_game_requests) < len(self.players):
                # Notify players who haven't responded
                missing_players = [p for p in self.players if p['uuid'] not in self.new_game_requests]
                for player in missing_players:
                    notification = {
                        "type": "new_game_timeout",
                        "data": {
                            "message": "Not all players requested a new game. The game will continue waiting."
                        }
                    }
                    self.server.send_message(player['socket'], notification)
                    logging.debug(f"Game {self.game_id}: Sent new_game_timeout to {player['username']}.")

                # Optionally, decide to reset or keep waiting
                # Here, we choose to reset with available players
                if len(self.new_game_requests) >= 1:
                    self.reset_game()
                    self.new_game_requests.clear()
                    logging.info(f"Game {self.game_id}: Proceeding to reset the game with available players after timeout.")
            self.new_game_timer = None

    def reset_game(self):
        """
        Resets the game state for a new round.
        """
        self.board = [['' for _ in range(3)] for _ in range(3)]
        self.current_player_index = (self.current_player_index + 1) % len(self.players)  # Toggle to the next player
        self.winner = None
        logging.info(f"Game {self.game_id} has been reset for a new round.")

        # Notify all players about the new game
        for player in self.players:
            response = {
                "type": "new_game",
                "data": {
                    "status": "success",
                    "game_state": self.board,
                    "next_player_uuid": self.players[self.current_player_index]['uuid'],
                    "next_player_username": self.players[self.current_player_index]['username']
                }
            }
            self.server.send_message(player['socket'], response)
            logging.debug(f"Game {self.game_id}: Sent new_game to {player['username']}: {response}")


class Server:
    """
    Represents the Tic-Tac-Toe server.
    Manages client connections, game assignments, and message handling.
    """

    def __init__(self, host='0.0.0.0', port=65432, max_workers=10):
        """
        Initializes the server with the given host, port, and thread pool settings.
        """
        self.server_address = (host, port)
        self.is_running = True
        self.max_workers = max_workers
        self.setup_server_socket()
        self.clients = {}  # key: client_socket.fileno(), value: client_info dictionary
        self.games = {}    # key: game_id, value: Game instance
        self.waiting_client = None  # A client_info dictionary waiting for an opponent
        self.lock = threading.Lock()  # Ensures thread-safe operations

    def setup_server_socket(self):
        """
        Sets up the server socket to listen for incoming connections.
        """
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.server_socket.bind(self.server_address)
            self.server_socket.listen()
            self.server_socket.settimeout(1.0)  # Set timeout to allow graceful shutdown
            logging.info(f"Server listening on {self.server_address[0]}:{self.server_address[1]}")
        except socket.error as e:
            logging.error(f"Socket error during server setup: {e}")
            self.server_socket.close()
            sys.exit(1)

    def send_message(self, client_socket, message):
        """
        Sends a JSON-formatted message to a client.
        :param client_socket: Socket object of the client.
        :param message: Dictionary representing the message.
        """
        try:
            serialized_message = json.dumps(message) + '\n'
            client_socket.sendall(serialized_message.encode('utf-8'))
            logging.debug(f"Sent to {client_socket.getpeername()}: {message}")
        except socket.error as e:
            logging.error(f"Error sending message to {client_socket.getpeername()}: {e}")

    def send_error(self, client_socket, code, message):
        """
        Sends an error message to a client.
        :param client_socket: Socket object of the client.
        :param code: Error code.
        :param message: Error message.
        """
        error_message = {
            "type": "error",
            "data": {
                "code": code,
                "message": message
            }
        }
        self.send_message(client_socket, error_message)

    def assign_to_game(self, client_info):
        """
        Assigns a client to a game. If there is a waiting client, starts a new game.
        Otherwise, sets the client as waiting for an opponent.
        :param client_info: Dictionary containing client information.
        """
        with self.lock:
            logging.debug(f"Assigning {client_info['username']} to a game.")
            if self.waiting_client:
                # Start a new game
                game_id = str(uuid.uuid4())
                new_game = Game(game_id, self)

                # Assign symbols
                self.waiting_client['symbol'] = 'X'  # First player is 'X'
                client_info['symbol'] = 'O'  # Second player is 'O'

                # Add players to the game
                new_game.add_player(self.waiting_client)
                new_game.add_player(client_info)
                self.games[game_id] = new_game

                # Update client info with game ID
                self.clients[self.waiting_client['socket'].fileno()]['game_id'] = game_id
                self.clients[client_info['socket'].fileno()]['game_id'] = game_id

                # Notify both players
                self.send_join_ack(self.waiting_client['socket'], game_id, self.waiting_client['symbol'], self.waiting_client['uuid'])
                self.send_join_ack(client_info['socket'], game_id, client_info['symbol'], client_info['uuid'])

                # Notify the server
                logging.info(f"Game {game_id} started between {self.waiting_client['username']} and {client_info['username']}")

                # Clear the waiting client
                self.waiting_client = None
            else:
                # Wait for another player
                self.waiting_client = client_info
                # Notify the client that they are waiting
                response = {
                    "type": "join_ack",
                    "data": {
                        "status": "waiting",
                        "message": "Waiting for an opponent...",
                        "uuid": client_info['uuid']
                    }
                }
                self.send_message(client_info['socket'], response)
                logging.info(f"{client_info['username']} is waiting for an opponent.")

    def send_join_ack(self, client_socket, game_id, symbol, player_uuid):
        """
        Sends a join acknowledgment to a client, indicating successful game assignment.
        :param client_socket: Socket object of the client.
        :param game_id: Unique identifier of the game.
        :param symbol: Player's symbol ('X' or 'O').
        :param player_uuid: Unique identifier of the player.
        """
        response = {
            "type": "join_ack",
            "data": {
                "status": "success",
                "game_id": game_id,
                "player_symbol": symbol,
                "uuid": player_uuid
            }
        }
        self.send_message(client_socket, response)
        logging.debug(f"Sent join_ack to {client_socket.getpeername()}: {response}")

    def handle_join(self, client_socket, data):
        """
        Handles a join request from a client.
        :param client_socket: Socket object of the client.
        :param data: Dictionary containing join data.
        """
        username = data.get('username') or f"Player_{uuid.uuid4().hex[:6]}"
        avatar = data.get('avatar', '')
        player_uuid = str(uuid.uuid4())

        client_info = {
            'socket': client_socket,
            'username': username,
            'avatar': avatar,
            'uuid': player_uuid,
            'game_id': None,
            'symbol': None
        }
        self.clients[client_socket.fileno()] = client_info
        logging.info(f"{username} with UUID {player_uuid} has joined the server.")
        self.assign_to_game(client_info)

    def handle_move(self, client_socket, data):
        """
        Handles a move request from a client.
        :param client_socket: Socket object of the client.
        :param data: Dictionary containing move data.
        """
        logging.debug(f"Handling move: {data}")
        game_id = data.get('game_id')
        position = data.get('position')
        player_uuid = data.get('uuid')

        if not game_id or position is None or not player_uuid:
            self.send_error(client_socket, "missing_data", "Game ID, position, and UUID are required.")
            return

        game = self.games.get(game_id)
        if not game:
            self.send_error(client_socket, "invalid_game", "Game not found.")
            return

        # Process the move
        result = game.make_move(player_uuid, position)
        logging.debug(f"Move result: {result}")

        if result['status'] == 'success':
            # Broadcast the updated game state to all players
            for player in game.players:
                response = {
                    "type": "move_ack",
                    "data": {
                        "status": "success",
                        "game_state": game.board,
                        "next_player_uuid": game.current_player_info()['uuid'],
                        "next_player_username": game.current_player_info()['username'],
                        "winner": game.winner_username()
                    }
                }
                self.send_message(player['socket'], response)
                logging.debug(f"Sent move_ack to {player['username']}: {response}")

            # If game is over, notify players
            if game.winner:
                logging.info(f"Game {game.game_id} ended. Winner: {game.winner_username()}")
                for player in game.players:
                    response = {
                        "type": "game_over",
                        "data": {
                            "winner": game.winner_username(),
                            "game_id": game.game_id
                        }
                    }
                    self.send_message(player['socket'], response)
                    logging.debug(f"Sent game_over to {player['username']}: {response}")
        else:
            # Handle move errors
            self.send_error(client_socket, result['code'], result['message'])

    def handle_chat(self, client_socket, data):
        """
        Handles a chat message from a client.
        :param client_socket: Socket object of the client.
        :param data: Dictionary containing chat data.
        """
        game_id = data.get('game_id')
        message = data.get('message')
        player_uuid = data.get('uuid')

        if not game_id or not message or not player_uuid:
            self.send_error(client_socket, "missing_data", "Game ID, message, and UUID are required.")
            return

        game = self.games.get(game_id)
        if not game:
            self.send_error(client_socket, "invalid_game", "Game not found.")
            return

        # Broadcast the chat message to all players
        sender_info = next((p for p in game.players if p['uuid'] == player_uuid), None)
        if not sender_info:
            self.send_error(client_socket, "invalid_player", "Player not found in the game.")
            return

        broadcast = {
            "type": "chat_broadcast",
            "data": {
                "username": sender_info['username'],
                "message": message
            }
        }
        for player in game.players:
            self.send_message(player['socket'], broadcast)
        logging.info(f"Game {game.game_id}: {sender_info['username']} says: {message}")

    def handle_quit(self, client_socket, data):
        """
        Handles a quit request from a client.
        :param client_socket: Socket object of the client.
        :param data: Dictionary containing quit data.
        """
        game_id = data.get('game_id')
        player_uuid = data.get('uuid')

        if not game_id or not player_uuid:
            self.send_error(client_socket, "missing_data", "Game ID and UUID are required.")
            return

        game = self.games.get(game_id)
        if not game:
            self.send_error(client_socket, "invalid_game", "Game not found.")
            return

        # Remove the player from the game
        player_info = self.clients.get(client_socket.fileno())
        if not player_info:
            return

        game.remove_player(player_uuid)
        self.clients.pop(client_socket.fileno(), None)

        # Notify the other players
        for player in game.players:
            response = {
                "type": "quit_ack",
                "data": {
                    "status": "success",
                    "message": f"{player_info['username']} has left the game."
                }
            }
            self.send_message(player['socket'], response)
            logging.debug(f"Sent quit_ack to {player['username']}: {response}")

        logging.info(f"Game {game.game_id}: {player_info['username']} has quit the game.")

        # If no players left, remove the game
        if not game.players:
            self.games.pop(game.game_id, None)
            logging.info(f"Game {game.game_id} has been removed due to no remaining players.")

    def handle_new_game_response(self, client_socket, data):
        """
        Handles a new game response from a client, indicating whether to start a new game or quit.
        :param client_socket: Socket object of the client.
        :param data: Dictionary containing new game response data.
        """
        game_id = data.get('game_id')
        player_uuid = data.get('uuid')
        response = data.get('response')  # 'start' or 'quit'

        if not game_id or not player_uuid or response not in ['start', 'quit']:
            self.send_error(client_socket, "invalid_data", "Invalid game_id, uuid, or response.")
            return

        game = self.games.get(game_id)
        if not game:
            self.send_error(client_socket, "invalid_game", "Game not found.")
            return

        if response == 'start':
            game.handle_new_game_request(player_uuid)
        elif response == 'quit':
            self.handle_quit(client_socket, data)

    def handle_client(self, client_socket, address):
        """
        Handles communication with a connected client.
        :param client_socket: Socket object of the client.
        :param address: Address tuple of the client.
        """
        thread_name = threading.current_thread().name
        logging.info(f"[{thread_name}] Connection established with {address}")
        client_socket.settimeout(600)  # Set client socket timeout to 10 minutes
        try:
            buffer = ''
            while self.is_running:
                try:
                    data = client_socket.recv(1024).decode('utf-8')
                    if not data:
                        break  # Client disconnected
                    buffer += data
                    while '\n' in buffer:
                        message_str, buffer = buffer.split('\n', 1)
                        if message_str:
                            try:
                                message_data = json.loads(message_str)
                                message_type = message_data.get('type')
                                message_content = message_data.get('data')

                                # Route message to appropriate handler
                                if message_type == 'join':
                                    self.handle_join(client_socket, message_content)
                                elif message_type == 'move':
                                    self.handle_move(client_socket, message_content)
                                elif message_type == 'chat':
                                    self.handle_chat(client_socket, message_content)
                                elif message_type == 'quit':
                                    self.handle_quit(client_socket, message_content)
                                elif message_type == 'new_game_response':
                                    self.handle_new_game_response(client_socket, message_content)
                                else:
                                    self.send_error(client_socket, "unknown_type", "Unknown message type.")
                            except json.JSONDecodeError:
                                self.send_error(client_socket, "invalid_json", "Invalid JSON format.")
                except socket.timeout:
                    logging.error(f"[{thread_name}] Socket timed out with {address}")
                    break
                except socket.error as e:
                    logging.error(f"[{thread_name}] Socket error with {address}: {e}")
                    break
        except Exception as e:
            logging.exception(f"[{thread_name}] Unexpected error with {address}: {e}")
        finally:
            # Clean up on client disconnect
            client_info = self.clients.pop(client_socket.fileno(), None)
            if client_info:
                game_id = client_info.get('game_id')
                if game_id:
                    game = self.games.get(game_id)
                    if game:
                        game.remove_player(client_info['uuid'])
                        # Notify remaining players
                        for player in game.players:
                            response = {
                                "type": "opponent_disconnected",
                                "data": {
                                    "message": f"{client_info['username']} has disconnected.",
                                    "game_over": True
                                }
                            }
                            self.send_message(player['socket'], response)
                            logging.debug(f"Sent opponent_disconnected to {player['username']}: {response}")
                        if not game.players:
                            self.games.pop(game_id, None)
                            logging.info(f"Game {game_id} has been removed due to no remaining players.")
            client_socket.close()
            logging.info(f"[{thread_name}] Connection closed with {address}")

    def start(self):
        """
        Starts the server to accept incoming connections and handle clients.
        Utilizes a thread pool executor for managing client threads.
        """
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            while self.is_running:
                try:
                    client_socket, address = self.server_socket.accept()
                    executor.submit(self.handle_client, client_socket, address)
                except socket.timeout:
                    continue  # Continue accepting new connections
                except socket.error as e:
                    if self.is_running:
                        logging.error(f"Socket error during accept: {e}")
                    break
                except Exception as e:
                    logging.exception(f"Unexpected error: {e}")
                    break

    def stop(self):
        """
        Stops the server gracefully by closing the server socket and terminating all connections.
        """
        self.is_running = False
        self.server_socket.close()
        logging.info("Server has been stopped.")


def main():
    """
    Entry point of the server application.
    Parses command-line arguments, configures logging, and starts the server.
    """
    parser = argparse.ArgumentParser(description="Tic-Tac-Toe TCP Server")
    parser.add_argument('-p', '--port', type=int, required=True, help='Server port')
    args = parser.parse_args()

    # Initialize the server with listening IP set to 0.0.0.0
    server = Server(host='0.0.0.0', port=args.port, max_workers=20)

    # Register signal handler for graceful shutdown
    def signal_handler(sig, frame):
        logging.info("Server shutting down...")
        server.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start the server
    server.start()


if __name__ == "__main__":
    main()
