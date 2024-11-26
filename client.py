# client.py

import socket
import threading
import argparse
import json
import logging
import sys
import time
import queue
import uuid
import tkinter as tk
from tkinter import messagebox


class Client:
    def __init__(self, host='127.0.0.1', port=65432, username=None, avatar=None):
        self.server_address = (host, port)
        self.username = username or f"Player_{uuid.uuid4().hex[:6]}"
        self.avatar = avatar or ""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connected = False
        self.game_id = None
        self.player_uuid = None
        self.player_symbol = None
        self.game_state = [['' for _ in range(3)] for _ in range(3)]
        self.my_turn = False
        self.game_over = False
        self.message_queue = queue.Queue()  # Queue to store incoming messages

        # Initialize Tkinter GUI
        self.root = tk.Tk()
        self.root.title(f"Tic-Tac-Toe - {self.username}")
        self.create_gui()

    def create_gui(self):
        # Create frames
        self.info_frame = tk.Frame(self.root)
        self.info_frame.pack(pady=10)

        self.status_label = tk.Label(self.info_frame, text="Connecting to server...", font=("Arial", 14))
        self.status_label.pack()

        self.board_frame = tk.Frame(self.root)
        self.board_frame.pack()

        # Create buttons for the board
        self.buttons = [[None for _ in range(3)] for _ in range(3)]
        for row in range(3):
            for col in range(3):
                btn = tk.Button(self.board_frame, text='', font=("Arial", 24), width=5, height=2,
                                command=lambda r=row, c=col: self.on_cell_click(r, c))
                btn.grid(row=row, column=col)
                self.buttons[row][col] = btn

        self.action_frame = tk.Frame(self.root)
        self.action_frame.pack(pady=10)

        self.chat_button = tk.Button(self.action_frame, text="Chat", command=self.open_chat_window, state='disabled')
        self.chat_button.pack(side='left', padx=5)

        self.quit_button = tk.Button(self.action_frame, text="Quit", command=self.quit_game, state='disabled')
        self.quit_button.pack(side='left', padx=5)

    def on_cell_click(self, row, col):
        logging.debug(f"Cell clicked at ({row}, {col})")
        if self.game_over:
            logging.debug("Game is over. Click ignored.")
            return
        if not self.my_turn:
            logging.debug("Not your turn. Click ignored.")
            return
        if self.game_state[row][col]:
            logging.debug(f"Cell ({row}, {col}) is already occupied.")
            messagebox.showwarning("Invalid Move", "Position already occupied.")
            return
        self.send_move([row, col])
        self.my_turn = False  # Prevent multiple rapid clicks
        logging.debug(f"Move sent for cell ({row}, {col}). Waiting for opponent.")

    def open_chat_window(self):
        if not hasattr(self, 'chat_window') or not self.chat_window.winfo_exists():
            self.chat_window = tk.Toplevel(self.root)
            self.chat_window.title("Chat")
            self.chat_text = tk.Text(self.chat_window, state='disabled', width=40, height=15)
            self.chat_text.pack(pady=5)

            self.chat_entry = tk.Entry(self.chat_window, width=30)
            self.chat_entry.pack(side='left', padx=5, pady=5)
            self.chat_entry.bind("<Return>", lambda event: self.send_chat())

            self.send_chat_button = tk.Button(self.chat_window, text="Send", command=self.send_chat)
            self.send_chat_button.pack(side='left', padx=5, pady=5)

    def send_chat(self):
        message_text = self.chat_entry.get().strip()
        if message_text:
            self.send_message({
                "type": "chat",
                "data": {
                    "game_id": self.game_id,
                    "message": message_text,
                    "uuid": self.player_uuid
                }
            })
            self.chat_entry.delete(0, tk.END)
            logging.debug(f"Sent chat message: {message_text}")

    def quit_game(self):
        if self.game_id and self.player_uuid:
            self.send_quit()
        self.root.destroy()

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
            messagebox.showerror("Connection Error", f"Failed to connect to server: {e}")
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
            logging.debug(f"Sent: {message}")
        except socket.error as e:
            logging.error(f"Send error: {e}")
            self.connected = False

    def send_join_request(self):
        message = {
            "type": "join",
            "data": {
                "username": self.username,
                "avatar": self.avatar
            }
        }
        self.send_message(message)
        logging.debug(f"Sent join request: {message}")

    def send_move(self, position):
        message = {
            "type": "move",
            "data": {
                "game_id": self.game_id,
                "position": position,
                "uuid": self.player_uuid
            }
        }
        self.send_message(message)
        logging.debug(f"Sent move message: {message}")

    def send_quit(self):
        message = {
            "type": "quit",
            "data": {
                "game_id": self.game_id,
                "uuid": self.player_uuid
            }
        }
        self.send_message(message)
        logging.debug(f"Sent quit message: {message}")

    def receive_messages(self):
        self.socket.settimeout(None)  # Disable socket timeout
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
                                logging.debug(f"Received message: {message_data}")
                            except json.JSONDecodeError as e:
                                logging.error(f"JSON decode error: {e}")
                else:
                    # Server closed connection
                    self.connected = False
                    self.root.after(0, lambda: messagebox.showerror("Disconnected", "Server closed the connection."))
                    logging.error("Server closed the connection.")
                    break
            except socket.error as e:
                logging.error(f"Socket error: {e}")
                self.connected = False
                self.root.after(0, lambda: messagebox.showerror("Connection Error", f"Socket error: {e}"))
                break

    def receive_message(self, timeout=None):
        """
        Retrieve the next message from the queue.
        :param timeout: Time in seconds to wait for a message.
        :return: The message dictionary or None if timeout occurs.
        """
        try:
            return self.message_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def handle_join_ack(self, data):
        logging.debug(f"Received join_ack: {data}")
        status = data.get('status')
        if status == 'success':
            self.game_id = data.get('game_id')
            self.player_symbol = data.get('player_symbol')
            self.player_uuid = data.get('uuid')
            self.update_status(f"Game started! You are '{self.player_symbol}'.")
            if self.player_symbol == 'X':
                self.my_turn = True
                self.update_status("Your turn.")
                logging.debug("It's your turn.")
            else:
                self.my_turn = False
                self.update_status("Waiting for opponent's move.")
                logging.debug("Waiting for opponent's turn.")
            self.chat_button.config(state='normal')
            self.quit_button.config(state='normal')
            logging.info(f"Joined game {self.game_id} as '{self.player_symbol}' with UUID {self.player_uuid}.")
        elif status == 'waiting':
            self.player_uuid = data.get('uuid')
            self.update_status("Waiting for an opponent...")
            logging.info(f"Client {self.username} is waiting for an opponent.")
        else:
            self.update_status("Failed to join game.")
            logging.warning(f"Failed to join game: {data}")

    def handle_move_ack(self, data):
        logging.debug(f"Received move_ack: {data}")
        status = data.get('status')
        if status == 'success':
            self.game_state = data.get('game_state')
            next_player_uuid = data.get('next_player_uuid')
            winner = data.get('winner')
            self.render_game_board()
            if winner:
                if winner == 'draw':
                    self.update_status("The game ended in a draw.")
                elif winner == self.username:
                    self.update_status("Congratulations, you won!")
                else:
                    self.update_status(f"{winner} has won the game.")
                self.game_over = True
                # Removed duplicate prompt
                # self.prompt_new_game(winner)
            else:
                if next_player_uuid == self.player_uuid:
                    self.my_turn = True
                    self.update_status("Your turn.")
                    logging.debug("It's your turn.")
                else:
                    self.my_turn = False
                    self.update_status("Waiting for opponent's move.")
                    logging.debug("Waiting for opponent's turn.")
        else:
            error_message = data.get('message', 'Move failed.')
            messagebox.showerror("Move Error", error_message)
            logging.error(f"Move error: {error_message}")
            error_code = data.get('code')
            if error_code in ['invalid_move', 'invalid_position']:
                self.my_turn = True  # Allow the player to try again
                logging.debug("Allowing player to try again.")

    def handle_chat_broadcast(self, data):
        logging.debug(f"Received chat_broadcast: {data}")
        username = data.get('username')
        message = data.get('message')
        if hasattr(self, 'chat_window') and self.chat_window.winfo_exists():
            timestamp = time.strftime('%H:%M:%S', time.localtime())
            self.chat_text.config(state='normal')
            self.chat_text.insert(tk.END, f"[{timestamp}] {username}: {message}\n")
            self.chat_text.config(state='disabled')
            self.chat_text.see(tk.END)
            logging.debug(f"Displayed chat message from {username}: {message}")

    def handle_quit_ack(self, data):
        logging.debug(f"Received quit_ack: {data}")
        message = data.get('message')
        messagebox.showinfo("Game Info", message)
        self.game_over = True
        self.prompt_new_game(None, message)

    def handle_game_over(self, data):
        logging.debug(f"Received game_over: {data}")
        winner = data.get('winner')
        game_id = data.get('game_id')
        if winner == 'draw':
            self.update_status("The game ended in a draw.")
        elif winner == self.username:
            self.update_status("Congratulations, you won!")
        else:
            self.update_status(f"{winner} has won the game.")
        self.game_over = True
        self.prompt_new_game(winner)

    def handle_new_game(self, data):
        logging.debug(f"Received new_game: {data}")
        status = data.get('status')
        game_state = data.get('game_state')
        next_player_username = data.get('next_player_username')

        self.game_state = game_state
        self.game_over = False

        # Set 'my_turn' based on 'next_player_username' instead of 'next_player_uuid'
        if next_player_username == self.username:
            self.my_turn = True
            self.update_status("Your turn.")
            logging.debug("It's your turn in the new game.")
        else:
            self.my_turn = False
            self.update_status("Waiting for opponent's move.")
            logging.debug("Waiting for opponent's turn in the new game.")

        self.render_game_board()

    def handle_error(self, data):
        logging.debug(f"Received error: {data}")
        error_code = data.get('code')
        message = data.get('message')
        messagebox.showerror("Server Error", f"[{error_code}] {message}")
        logging.error(f"Server error [{error_code}]: {message}")
        if error_code in ['invalid_move', 'invalid_position']:
            self.my_turn = True  # Allow the player to try again
            logging.debug("Allowing player to try again after error.")

    def handle_opponent_disconnected(self, data):
        logging.debug(f"Received opponent_disconnected: {data}")
        message = data.get('message')
        self.update_status(message)
        messagebox.showinfo("Opponent Disconnected", message)
        self.game_over = True
        # Optionally, prompt to start a new game or exit
        self.prompt_new_game(None, message)

    def prompt_new_game(self, winner=None, message=None):
        if winner == 'draw' or winner:
            if winner == 'draw':
                prompt_message = "The game ended in a draw."
            elif winner == self.username:
                prompt_message = "Congratulations, you won the game!"
            else:
                prompt_message = f"{winner} has won the game."
        elif message:
            prompt_message = message
        else:
            prompt_message = "The game has ended."

        result = messagebox.askquestion("Game Over", f"{prompt_message}\nDo you want to start a new game?")
        if result == 'yes':
            self.send_new_game_request()
        else:
            self.quit_game()

    def send_new_game_request(self):
        message = {
            "type": "new_game_response",
            "data": {
                "game_id": self.game_id,
                "uuid": self.player_uuid,
                "response": "start"
            }
        }
        self.send_message(message)
        self.update_status("Waiting for opponent's response to start a new game...")
        logging.debug(f"Sent new_game_response: {message}")

    def send_new_game_quit(self):
        message = {
            "type": "new_game_response",
            "data": {
                "game_id": self.game_id,
                "uuid": self.player_uuid,
                "response": "quit"
            }
        }
        self.send_message(message)
        logging.debug(f"Sent new_game_response to quit: {message}")
        self.quit_game()

    def handle_server_message(self):
        while self.connected:
            message = self.receive_message()
            if message:
                # Schedule the message processing on the main thread
                self.root.after(0, self.process_message, message)
            else:
                continue  # Continue waiting for messages

    def process_message(self, message):
        message_type = message.get('type')
        data = message.get('data')
        if message_type == 'join_ack':
            self.handle_join_ack(data)
        elif message_type == 'move_ack':
            self.handle_move_ack(data)
        elif message_type == 'chat_broadcast':
            self.handle_chat_broadcast(data)
        elif message_type == 'quit_ack':
            self.handle_quit_ack(data)
        elif message_type == 'game_over':
            self.handle_game_over(data)
        elif message_type == 'new_game':
            self.handle_new_game(data)
        elif message_type == 'opponent_disconnected':
            self.handle_opponent_disconnected(data)
        elif message_type == 'error':
            self.handle_error(data)
        else:
            logging.warning(f"Unknown message type: {message_type}")

    def update_status(self, message):
        self.status_label.config(text=message)
        logging.debug(f"Status updated: {message}")

    def render_game_board(self):
        for row in range(3):
            for col in range(3):
                cell_value = self.game_state[row][col]
                btn = self.buttons[row][col]
                btn.config(text=cell_value)
                if cell_value or self.game_over:
                    btn.config(state='disabled')
                else:
                    btn.config(state='normal')
        logging.debug("Rendered game board.")

    def start_gui(self):
        self.root.protocol("WM_DELETE_WINDOW", self.quit_game)
        self.root.mainloop()

    def run(self):
        try:
            if self.connect():
                threading.Thread(target=self.handle_server_message, daemon=True).start()
                self.start_gui()
        except Exception as e:
            logging.exception(f"An unexpected error occurred: {e}")
            messagebox.showerror("Error", f"An unexpected error occurred: {e}")
        finally:
            self.disconnect()

    def quit_game(self):
        if self.game_id and self.player_uuid:
            self.send_quit()
        self.connected = False  # Ensure that the message-handling loop exits
        self.disconnect()
        self.root.destroy()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Tic-Tac-Toe Client")
    parser.add_argument('--host', default='127.0.0.1', help='Server host')
    parser.add_argument('--port', type=int, default=65432, help='Server port')
    parser.add_argument('--username', help='Your username')
    parser.add_argument('--avatar', help='Your avatar (optional)')
    args = parser.parse_args()

    # Configure logging to write to a file and console
    logging.basicConfig(
        level=logging.DEBUG,  # Set to DEBUG for more detailed logs
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("client.log"),
            logging.StreamHandler()
        ]
    )

    client = Client(host=args.host, port=args.port, username=args.username, avatar=args.avatar)
    client.run()
