import socket
import threading
import logging
import argparse
import json
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Client:
    def __init__(self, host='127.0.0.1', port=65432, username='Player'):
        self.server_address = (host, port)
        self.username = username
        self.client_socket = None
        self.game_id = None
        self.player_symbol = None
        self.game_state = [['' for _ in range(3)] for _ in range(3)]
        self.connected = False
        self.receive_thread = None
        self.game_over = False
        self.winner = None
        self.last_error = None
        self.last_error_code = None
        self.chat_messages = []

    def connect(self):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.client_socket.connect(self.server_address)
            logging.info(f"Connected to server at {self.server_address}")
            self.connected = True
            # Start a thread to receive messages from the server
            self.receive_thread = threading.Thread(target=self.receive_messages)
            self.receive_thread.daemon = True
            self.receive_thread.start()
            # Send join request
            self.send_join_request()
            return True
        except socket.error as e:
            logging.error(f"Socket error during connection: {e}")
            return False

    def disconnect(self):
        if self.connected:
            self.connected = False
            self.client_socket.close()
            logging.info("Disconnected from server")

    def send_message(self, message):
        try:
            self.client_socket.sendall(json.dumps(message).encode('utf-8'))
        except socket.error as e:
            logging.error(f"Error sending message: {e}")

    def receive_messages(self):
        try:
            while self.connected:
                response = self.client_socket.recv(1024).decode('utf-8')
                if not response:
                    break
                try:
                    data = json.loads(response)
                    self.handle_server_response(data)
                except json.JSONDecodeError:
                    logging.error("Received invalid JSON from server")
        except socket.error as e:
            logging.error(f"Socket error: {e}")
        finally:
            self.disconnect()

    def send_join_request(self):
        message = {
            "type": "join",
            "data": {
                "username": self.username
            }
        }
        self.send_message(message)

    def send_move(self, position):
        if not self.game_id:
            print("You are not in a game yet.")
            return
        message = {
            "type": "move",
            "data": {
                "game_id": self.game_id,
                "position": position
            }
        }
        self.send_message(message)

    def send_chat(self, chat_message):
        if not self.game_id:
            print("You are not in a game yet.")
            return
        message = {
            "type": "chat",
            "data": {
                "game_id": self.game_id,
                "message": chat_message
            }
        }
        self.send_message(message)

    def send_quit(self):
        if self.game_id:
            message = {
                "type": "quit",
                "data": {
                    "game_id": self.game_id
                }
            }
            self.send_message(message)
        self.disconnect()

    def handle_server_response(self, data):
        message_type = data.get('type')
        message_data = data.get('data')

        if message_type == 'join_ack':
            self.handle_join_ack(message_data)
        elif message_type == 'move_ack':
            self.handle_move_ack(message_data)
        elif message_type == 'chat_broadcast':
            self.handle_chat_broadcast(message_data)
        elif message_type == 'quit_ack':
            self.handle_quit_ack(message_data)
        elif message_type == 'error':
            self.handle_error(message_data)
        else:
            logging.warning(f"Unknown message type received: {message_type}")

    def handle_join_ack(self, data):
        status = data.get('status')
        if status == 'success':
            self.game_id = data.get('game_id')
            self.player_symbol = data.get('player_symbol')
            logging.info(f"Joined game {self.game_id} as '{self.player_symbol}'")
            print(f"Game started! You are '{self.player_symbol}'.")
        elif status == 'waiting':
            message = data.get('message')
            logging.info(message)
            print(message)
        else:
            logging.error("Failed to join game.")

    def handle_move_ack(self, data):
        status = data.get('status')
        if status == 'success':
            self.game_state = data.get('game_state')
            next_player = data.get('next_player')
            winner = data.get('winner')
            self.display_game_state()
            if winner:
                self.game_over = True
                if winner == 'draw':
                    print("The game is a draw!")
                    self.winner = 'draw'
                elif winner == self.username:
                    print("Congratulations, you won!")
                    self.winner = self.username
                else:
                    print(f"{winner} has won the game.")
                    self.winner = winner
                self.connected = False  # End the game
            else:
                print(f"It's {next_player}'s turn.")
        else:
            logging.error("Failed to process move.")
            self.last_error = data.get('message')
            self.last_error_code = data.get('code')
            print(f"Error: {self.last_error}")

    def handle_chat_broadcast(self, data):
        username = data.get('username')
        message = data.get('message')
        self.chat_messages.append(message)
        print(f"[{username}]: {message}")

    def handle_quit_ack(self, data):
        status = data.get('status')
        message = data.get('message')
        if status == 'success':
            print(message)
            self.game_over = True
            self.connected = False
            self.disconnect()

    def handle_error(self, data):
        self.last_error_code = data.get('code')
        self.last_error = data.get('message')
        logging.error(f"Error from server [{self.last_error_code}]: {self.last_error}")
        print(f"Error: {self.last_error}")

    def display_game_state(self):
        print("\nCurrent Game Board:")
        for row in self.game_state:
            print(" | ".join(cell if cell else " " for cell in row))
            print("-" * 9)

    def start_game_loop(self):
        try:
            while self.connected and not self.game_over:
                command = input("Enter your move (row,col), 'chat', or 'quit': ")
                if command.lower() == 'quit':
                    self.send_quit()
                    break
                elif command.lower() == 'chat':
                    chat_message = input("Enter your chat message: ")
                    self.send_chat(chat_message)
                else:
                    try:
                        position = [int(x.strip()) for x in command.split(',')]
                        if len(position) == 2 and all(0 <= x <= 2 for x in position):
                            if self.game_state[position[0]][position[1]] == '':
                                self.send_move(position)
                            else:
                                print("That position is already occupied. Choose another one.")
                        else:
                            print("Invalid move. Enter row and column numbers between 0 and 2.")
                    except ValueError:
                        print("Invalid input. Please enter your move as 'row,col'.")
        except KeyboardInterrupt:
            self.send_quit()

def main():
    parser = argparse.ArgumentParser(description="TCP Client")
    parser.add_argument('--host', default='127.0.0.1', help='Server host')
    parser.add_argument('--port', type=int, default=65432, help='Server port')
    parser.add_argument('--username', default='Player', help='Your username')
    args = parser.parse_args()

    client = Client(host=args.host, port=args.port, username=args.username)
    if client.connect():
        client.start_game_loop()
    else:
        print("Failed to connect to the server.")

if __name__ == '__main__':
    main()
