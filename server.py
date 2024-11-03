# server.py

import socket
import threading
import logging
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Game:
    def __init__(self, game_id, server):
        self.game_id = game_id
        self.server = server  # Reference to the Server instance
        self.players = []  # List of dictionaries: {'socket': ..., 'uuid': ..., 'username': ..., 'avatar': ..., 'symbol': ...}
        self.board = [['' for _ in range(3)] for _ in range(3)]
        self.current_player_index = 0
        self.winner = None

    def add_player(self, client_info):
        self.players.append(client_info)

    def make_move(self, player_uuid, position):
        player = self.players[self.current_player_index]
        if player['uuid'] != player_uuid:
            return {'status': 'failure', 'code': 'not_your_turn', 'message': 'It is not your turn.'}

        row, col = position
        if self.board[row][col]:
            return {'status': 'failure', 'code': 'invalid_move', 'message': 'Position already occupied.'}

        symbol = player['symbol']
        self.board[row][col] = symbol

        if self.check_winner(symbol):
            self.winner = player
        elif self.is_draw():
            self.winner = 'draw'
        else:
            self.current_player_index = (self.current_player_index + 1) % len(self.players)
        return {'status': 'success'}

    def check_winner(self, symbol):
        lines = []
        # Rows
        lines.extend(self.board)
        # Columns
        lines.extend([list(col) for col in zip(*self.board)])
        # Diagonals
        lines.append([self.board[i][i] for i in range(3)])
        lines.append([self.board[i][2 - i] for i in range(3)])
        for line in lines:
            if all(cell == symbol for cell in line):
                return True
        return False

    def is_draw(self):
        return all(cell for row in self.board for cell in row)

    def current_player_info(self):
        return self.players[self.current_player_index]

    def winner_username(self):
        if self.winner == 'draw':
            return 'draw'
        elif self.winner:
            return self.winner['username']
        else:
            return None

    def remove_player(self, player_uuid):
        self.players = [player for player in self.players if player['uuid'] != player_uuid]

class Server:
    def __init__(self, host='127.0.0.1', port=65432, max_workers=10):
        self.server_address = (host, port)
        self.is_running = True
        self.max_workers = max_workers
        self.setup_server_socket()
        self.clients = {}  # key: client_socket.fileno(), value: client_info dictionary
        self.games = {}    # key: game_id, value: Game instance
        self.waiting_client = None  # A client_info dictionary waiting for an opponent

    def setup_server_socket(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.server_socket.bind(self.server_address)
            self.server_socket.listen()
            logging.info(f"Server listening on {self.server_address[0]}:{self.server_address[1]}")
        except socket.error as e:
            logging.error(f"Socket error during server setup: {e}")
            self.server_socket.close()
            sys.exit(1)

    def send_message(self, client_socket, message):
        try:
            client_socket.sendall((json.dumps(message) + '\n').encode('utf-8'))
            logging.debug(f"Sent to {client_socket.getpeername()}: {message}")
        except socket.error as e:
            logging.error(f"Error sending message to {client_socket.getpeername()}: {e}")

    def send_error(self, client_socket, code, message):
        error_message = {
            "type": "error",
            "data": {
                "code": code,
                "message": message
            }
        }
        self.send_message(client_socket, error_message)

    def assign_to_game(self, client_info):
        if self.waiting_client:
            # Start a new game
            game_id = str(uuid.uuid4())
            new_game = Game(game_id, self)
            # Assign symbols
            client_info['symbol'] = 'O'
            self.waiting_client['symbol'] = 'X'

            new_game.add_player(self.waiting_client)
            new_game.add_player(client_info)
            self.games[game_id] = new_game

            # Update client info
            self.clients[self.waiting_client['socket'].fileno()]['game_id'] = game_id
            self.clients[client_info['socket'].fileno()]['game_id'] = game_id

            # Notify both players
            self.send_join_ack(self.waiting_client['socket'], game_id, self.waiting_client['symbol'], self.waiting_client['uuid'])
            self.send_join_ack(client_info['socket'], game_id, client_info['symbol'], client_info['uuid'])

            # Clear the waiting client
            logging.info(f"Game {game_id} started between {self.waiting_client['username']} and {client_info['username']}")
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

    def handle_join(self, client_socket, data):
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
        self.assign_to_game(client_info)

    def handle_move(self, client_socket, data):
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
            # If game is over, remove it from active games
            if game.winner:
                logging.info(f"Game {game_id} ended. Winner: {game.winner_username()}")
                self.games.pop(game_id, None)
        else:
            self.send_error(client_socket, result['code'], result['message'])

    def handle_chat(self, client_socket, data):
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
        logging.info(f"Game {game_id}: {sender_info['username']} says: {message}")

    def handle_quit(self, client_socket, data):
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

        logging.info(f"Game {game_id}: {player_info['username']} has quit the game.")

        # If no players left, remove the game
        if not game.players:
            self.games.pop(game_id, None)
            logging.info(f"Game {game_id} has been removed due to no remaining players.")

    def handle_client(self, client_socket, address):
        thread_name = threading.current_thread().name
        logging.info(f"[{thread_name}] Connection established with {address}")
        client_socket.settimeout(300)  # Set client socket timeout to 5 minutes
        try:
            while True:
                data = ''
                while '\n' not in data:
                    chunk = client_socket.recv(1024).decode('utf-8')
                    if not chunk:
                        break
                    data += chunk
                if not data:
                    break
                messages = data.strip().split('\n')
                for message in messages:
                    try:
                        message_data = json.loads(message)
                        message_type = message_data.get('type')
                        message_content = message_data.get('data')

                        if message_type == 'join':
                            self.handle_join(client_socket, message_content)
                        elif message_type == 'move':
                            self.handle_move(client_socket, message_content)
                        elif message_type == 'chat':
                            self.handle_chat(client_socket, message_content)
                        elif message_type == 'quit':
                            self.handle_quit(client_socket, message_content)
                        else:
                            self.send_error(client_socket, "unknown_type", "Unknown message type.")
                    except json.JSONDecodeError:
                        self.send_error(client_socket, "invalid_json", "Invalid JSON format.")
        except socket.timeout:
            logging.error(f"[{thread_name}] Socket timed out with {address}")
        except socket.error as e:
            logging.error(f"[{thread_name}] Socket error with {address}: {e}")
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
                                "type": "quit_ack",
                                "data": {
                                    "status": "success",
                                    "message": f"{client_info['username']} has left the game."
                                }
                            }
                            self.send_message(player['socket'], response)
                        if not game.players:
                            self.games.pop(game_id, None)
                            logging.info(f"Game {game_id} has been removed due to no remaining players.")
            client_socket.close()
            logging.info(f"[{thread_name}] Connection closed with {address}")

    def start(self):
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            while self.is_running:
                try:
                    client_socket, address = self.server_socket.accept()
                    executor.submit(self.handle_client, client_socket, address)
                except socket.timeout:
                    continue  # Continue accepting new connections
                except socket.error as e:
                    logging.error(f"Socket error during accept: {e}")
                    break
                except Exception as e:
                    logging.exception(f"Unexpected error: {e}")
                    break

    def stop(self):
        self.is_running = False
        self.server_socket.close()
        logging.info("Server has been stopped.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TCP Server")
    parser.add_argument('--host', default='127.0.0.1', help='Server host')
    parser.add_argument('--port', type=int, default=65432, help='Server port')
    parser.add_argument('--max-workers', type=int, default=10, help='Maximum number of worker threads')
    args = parser.parse_args()

    server = Server(host=args.host, port=args.port, max_workers=args.max_workers)

    # Register signal handler
    def signal_handler(sig, frame):
        logging.info("Server shutting down...")
        server.stop()
        sys.exit(0)

    import signal
    signal.signal(signal.SIGINT, signal_handler)

    server.start()
