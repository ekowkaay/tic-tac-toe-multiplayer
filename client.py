# client.py

import socket
import threading
import argparse
import json
import logging
import sys
import time
import queue

class Client:
    def __init__(self, host='127.0.0.1', port=65432, username='Player'):
        self.server_address = (host, port)
        self.username = username
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connected = False
        self.game_id = None
        self.player_symbol = None
        self.game_state = [['' for _ in range(3)] for _ in range(3)]
        self.my_turn = False
        self.game_over = False
        self.message_queue = queue.Queue()  # Queue to store incoming messages

    def connect(self):
        try:
            self.socket.connect(self.server_address)
            logging.info(f"Connected to server at {self.server_address}")
            self.connected = True
            # Start the receiver thread
            threading.Thread(target=self.receive_messages, daemon=True).start()
            # Send join request
            self.send_join_request()
            return True
        except socket.error as e:
            logging.error(f"Connection error: {e}")
            return False

    def disconnect(self):
        if self.connected:
            try:
                self.socket.close()
            except Exception as e:
                logging.error(f"Error closing socket: {e}")
            self.connected = False
            logging.info("Disconnected from server")

    def send_message(self, message):
        try:
            self.socket.sendall((json.dumps(message) + '\n').encode('utf-8'))
        except socket.error as e:
            logging.error(f"Send error: {e}")
            self.connected = False

    def send_join_request(self):
        message = {
            "type": "join",
            "data": {
                "username": self.username
            }
        }
        self.send_message(message)

    def send_move(self, position):
        message = {
            "type": "move",
            "data": {
                "game_id": self.game_id,
                "position": position
            }
        }
        self.send_message(message)

    def send_chat(self, message_text):
        message = {
            "type": "chat",
            "data": {
                "game_id": self.game_id,
                "message": message_text
            }
        }
        self.send_message(message)

    def send_quit(self):
        message = {
            "type": "quit",
            "data": {
                "game_id": self.game_id
            }
        }
        self.send_message(message)

    def receive_messages(self):
        buffer = ''
        while self.connected and not self.game_over:
            try:
                data = self.socket.recv(1024).decode('utf-8')
                if data:
                    buffer += data
                    while '\n' in buffer:
                        message_str, buffer = buffer.split('\n', 1)
                        if message_str:
                            try:
                                message_data = json.loads(message_str)
                                self.message_queue.put(message_data)
                            except json.JSONDecodeError as e:
                                logging.error(f"JSON decode error: {e}")
                else:
                    # Server closed connection
                    self.connected = False
            except socket.error as e:
                logging.error(f"Socket error: {e}")
                self.connected = False

    def receive_message(self, timeout=5):
        """
        Retrieve the next message from the queue.
        :param timeout: Time in seconds to wait for a message.
        :return: The message dictionary or None if timeout occurs.
        """
        try:
            return self.message_queue.get(timeout=timeout)
        except queue.Empty:
            logging.error("No message received within the timeout period.")
            return None

    def handle_move_ack(self, data):
        status = data.get('status')
        if status == 'success':
            self.game_state = data.get('game_state')
            next_player = data.get('next_player')
            winner = data.get('winner')
            self.display_game_board()
            if winner:
                if winner == 'draw':
                    print("The game ended in a draw.")
                elif winner == self.username:
                    print("Congratulations, you won!")
                else:
                    print(f"{winner} has won the game.")
                self.game_over = True
            else:
                print(f"It's {next_player}'s turn.")
                self.my_turn = (next_player == self.username)
        else:
            print(f"Move failed: {data.get('message')}")
            # Allow the player to retry
            self.my_turn = True

    def handle_quit_ack(self, data):
        print(data.get('message'))
        self.game_over = True

    def handle_error(self, data):
        error_code = data.get('code')
        message = data.get('message')
        print(f"Error from server [{error_code}]: {message}")

    def handle_join_ack(self, data):
        status = data.get('status')
        if status == 'success':
            self.game_id = data.get('game_id')
            self.player_symbol = data.get('player_symbol')
            print(f"Game started! You are '{self.player_symbol}'.")
            if self.player_symbol == 'X':
                self.my_turn = True
            else:
                self.my_turn = False
        elif status == 'waiting':
            print(data.get('message'))
        else:
            print("Failed to join game.")

    def handle_chat_broadcast(self, data):
        username = data.get('username')
        message = data.get('message')
        print(f"{username}: {message}")

    def display_game_board(self):
        print("\nCurrent Game Board:")
        for row in self.game_state:
            print(' | '.join(cell or ' ' for cell in row))
            print('---------')
        print()

    def play_game(self):
        while not self.game_over:
            if self.my_turn:
                command = input("Enter your move (row,col), 'chat', or 'quit': ")
                if command.lower() == 'quit':
                    self.send_quit()
                    self.game_over = True
                elif command.lower() == 'chat':
                    message_text = input("Enter your message: ")
                    self.send_chat(message_text)
                else:
                    try:
                        position = [int(x.strip()) for x in command.split(',')]
                        if len(position) != 2 or not all(0 <= x <= 2 for x in position):
                            raise ValueError
                        self.send_move(position)
                    except ValueError:
                        print("Invalid input. Please enter row and column as numbers between 0 and 2, separated by a comma.")
                    # Wait for server response before allowing another move
                    self.my_turn = False
            else:
                time.sleep(0.1)  # Small delay to prevent busy waiting

def main():
    parser = argparse.ArgumentParser(description="Tic-Tac-Toe Client")
    parser.add_argument('--host', default='127.0.0.1', help='Server host')
    parser.add_argument('--port', type=int, default=65432, help='Server port')
    parser.add_argument('--username', default='Player', help='Your username')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    client = Client(host=args.host, port=args.port, username=args.username)
    if client.connect():
        try:
            client.play_game()
        except KeyboardInterrupt:
            client.send_quit()
        finally:
            client.disconnect()
    else:
        print("Failed to connect to the server.")

if __name__ == '__main__':
    main()
