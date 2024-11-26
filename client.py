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
    """
    A Tic-Tac-Toe client that connects to a server, handles game logic,
    and provides a GUI for user interaction.
    """

    def __init__(self, host='127.0.0.1', port=65432, username=None, avatar=None):
        """
        Initializes the client with server details and user information.
        Sets up the initial game state and GUI.
        """
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
        """
        Sets up the GUI components including the game board, status label,
        and action buttons.
        """
        # Frame for displaying status information
        self.info_frame = tk.Frame(self.root)
        self.info_frame.pack(pady=10)

        self.status_label = tk.Label(self.info_frame, text="Connecting to server...", font=("Arial", 14))
        self.status_label.pack()

        # Frame for the game board buttons
        self.board_frame = tk.Frame(self.root)
        self.board_frame.pack()

        # Create a 3x3 grid of buttons for the Tic-Tac-Toe board
        self.buttons = [[None for _ in range(3)] for _ in range(3)]
        for row in range(3):
            for col in range(3):
                btn = tk.Button(
                    self.board_frame,
                    text='',
                    font=("Arial", 24),
                    width=5,
                    height=2,
                    command=lambda r=row, c=col: self.on_cell_click(r, c)
                )
                btn.grid(row=row, column=col)
                self.buttons[row][col] = btn

        # Frame for action buttons like Chat and Quit
        self.action_frame = tk.Frame(self.root)
        self.action_frame.pack(pady=10)

        self.chat_button = tk.Button(
            self.action_frame,
            text="Chat",
            command=self.open_chat_window,
            state='disabled'
        )
        self.chat_button.pack(side='left', padx=5)

        self.quit_button = tk.Button(
            self.action_frame,
            text="Quit",
            command=self.quit_game,
            state='disabled'
        )
        self.quit_button.pack(side='left', padx=5)

    def on_cell_click(self, row, col):
        """
        Handles the event when a cell on the game board is clicked.
        Sends the move to the server if it's the player's turn and the cell is empty.
        """
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

        # Send the move to the server
        self.send_move([row, col])
        self.my_turn = False  # Prevent multiple rapid clicks
        logging.debug(f"Move sent for cell ({row}, {col}). Waiting for opponent.")

    def open_chat_window(self):
        """
        Opens the chat window for sending and receiving messages.
        Ensures only one chat window is open at a time.
        """
        if not hasattr(self, 'chat_window') or not self.chat_window.winfo_exists():
            self.chat_window = tk.Toplevel(self.root)
            self.chat_window.title("Chat")
            self.chat_window.resizable(False, False)

            # Text area to display chat messages
            self.chat_text = tk.Text(self.chat_window, state='disabled', width=40, height=15, wrap='word')
            self.chat_text.pack(pady=5, padx=5)

            # Entry field to type chat messages
            self.chat_entry = tk.Entry(self.chat_window, width=30)
            self.chat_entry.pack(side='left', padx=5, pady=5)
            self.chat_entry.bind("<Return>", lambda event: self.send_chat())

            # Button to send chat messages
            self.send_chat_button = tk.Button(self.chat_window, text="Send", command=self.send_chat)
            self.send_chat_button.pack(side='left', padx=5, pady=5)

    def send_chat(self):
        """
        Sends a chat message to the server.
        """
        message_text = self.chat_entry.get().strip()
        if message_text:
            message = {
                "type": "chat",
                "data": {
                    "game_id": self.game_id,
                    "message": message_text,
                    "uuid": self.player_uuid
                }
            }
            self.send_message(message)
            self.chat_entry.delete(0, tk.END)
            logging.debug(f"Sent chat message: {message_text}")

    def quit_game(self):
        """
        Handles quitting the game by sending a quit message to the server
        and closing the GUI.
        """
        if self.game_id and self.player_uuid:
            self.send_quit()
        self.connected = False  # Ensure the receiver thread exits
        self.disconnect()
        self.root.destroy()

    def connect(self):
        """
        Attempts to connect to the server. If successful, starts the receiver thread
        and sends a join request.
        """
        try:
            self.socket.connect(self.server_address)
            logging.info(f"Connected to server at {self.server_address}")
            self.connected = True

            # Start the receiver thread to handle incoming messages
            threading.Thread(target=self.receive_messages, daemon=True).start()

            # Send a join request to the server
            self.send_join_request()
            return True
        except socket.error as e:
            logging.error(f"Connection error: {e}")
            messagebox.showerror("Connection Error", f"Failed to connect to server: {e}")
            return False

    def disconnect(self):
        """
        Disconnects from the server gracefully by closing the socket.
        """
        if self.connected:
            try:
                self.socket.close()
                logging.info("Disconnected from server")
            except Exception as e:
                logging.error(f"Error closing socket: {e}")
            finally:
                self.connected = False

    def send_message(self, message):
        """
        Sends a JSON-formatted message to the server.
        """
        try:
            serialized_message = json.dumps(message) + '\n'
            self.socket.sendall(serialized_message.encode('utf-8'))
            logging.debug(f"Sent: {message}")
        except socket.error as e:
            logging.error(f"Send error: {e}")
            self.connected = False
            messagebox.showerror("Connection Error", f"Failed to send message: {e}")

    def send_join_request(self):
        """
        Sends a join request to the server with the player's username and avatar.
        """
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
        """
        Sends the player's move to the server.
        :param position: A list containing the row and column indices.
        """
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
        """
        Sends a quit message to the server indicating the player is leaving the game.
        """
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
        """
        Continuously listens for incoming messages from the server.
        Decodes JSON messages and places them into the message queue.
        """
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
        Retrieves the next message from the queue.
        :param timeout: Time in seconds to wait for a message.
        :return: The message dictionary or None if timeout occurs.
        """
        try:
            return self.message_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def handle_join_ack(self, data):
        """
        Processes the join acknowledgment from the server.
        Sets up game parameters based on the server response.
        """
        logging.debug(f"Received join_ack: {data}")
        status = data.get('status')

        if status == 'success':
            self.game_id = data.get('game_id')
            self.player_symbol = data.get('player_symbol')
            self.player_uuid = data.get('uuid')
            self.update_status(f"Game started! You are '{self.player_symbol}'.")
            logging.info(f"Joined game {self.game_id} as '{self.player_symbol}' with UUID {self.player_uuid}.")

            # Determine if it's the player's turn based on their symbol
            if self.player_symbol == 'X':
                self.my_turn = True
                self.update_status("Your turn.")
                logging.debug("It's your turn.")
            else:
                self.my_turn = False
                self.update_status("Waiting for opponent's move.")
                logging.debug("Waiting for opponent's turn.")

            # Enable action buttons
            self.chat_button.config(state='normal')
            self.quit_button.config(state='normal')

        elif status == 'waiting':
            self.player_uuid = data.get('uuid')
            self.update_status("Waiting for an opponent...")
            logging.info(f"{self.username} is waiting for an opponent.")

        else:
            self.update_status("Failed to join game.")
            logging.warning(f"Failed to join game: {data}")

    def handle_move_ack(self, data):
        """
        Processes the move acknowledgment from the server.
        Updates the game state and GUI accordingly.
        """
        logging.debug(f"Received move_ack: {data}")
        status = data.get('status')

        if status == 'success':
            self.game_state = data.get('game_state')
            next_player_uuid = data.get('next_player_uuid')
            winner = data.get('winner')

            self.render_game_board()

            if winner:
                # Handle game over scenarios
                if winner == 'draw':
                    self.update_status("The game ended in a draw.")
                elif winner == self.username:
                    self.update_status("Congratulations, you won!")
                else:
                    self.update_status(f"{winner} has won the game.")
                self.game_over = True
            else:
                # Determine whose turn is next
                if next_player_uuid == self.player_uuid:
                    self.my_turn = True
                    self.update_status("Your turn.")
                    logging.debug("It's your turn.")
                else:
                    self.my_turn = False
                    self.update_status("Waiting for opponent's move.")
                    logging.debug("Waiting for opponent's turn.")
        else:
            # Handle move errors
            error_message = data.get('message', 'Move failed.')
            messagebox.showerror("Move Error", error_message)
            logging.error(f"Move error: {error_message}")
            error_code = data.get('code')

            # Allow the player to try again for specific error codes
            if error_code in ['invalid_move', 'invalid_position']:
                self.my_turn = True
                logging.debug("Allowing player to try again.")

    def handle_chat_broadcast(self, data):
        """
        Displays chat messages received from the server.
        """
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
        """
        Handles acknowledgment from the server when a player quits the game.
        """
        logging.debug(f"Received quit_ack: {data}")
        message = data.get('message')
        messagebox.showinfo("Game Info", message)
        self.game_over = True
        self.prompt_new_game(None, message)

    def handle_game_over(self, data):
        """
        Handles the game over message from the server, indicating the result.
        """
        logging.debug(f"Received game_over: {data}")
        winner = data.get('winner')

        if winner == 'draw':
            self.update_status("The game ended in a draw.")
        elif winner == self.username:
            self.update_status("Congratulations, you won!")
        else:
            self.update_status(f"{winner} has won the game.")

        self.game_over = True
        self.prompt_new_game(winner)

    def handle_new_game(self, data):
        """
        Handles the new_game message from the server to reset the game state.
        """
        logging.debug(f"Received new_game: {data}")
        status = data.get('status')
        game_state = data.get('game_state')
        next_player_uuid = data.get('next_player_uuid')
        next_player_username = data.get('next_player_username')

        if status != 'success' or game_state is None or next_player_uuid is None:
            logging.error("Invalid new_game data received.")
            return

        # Reset game state
        self.game_state = game_state
        self.game_over = False

        # Determine if it's the player's turn
        if next_player_uuid == self.player_uuid:
            self.my_turn = True
            self.update_status("Your turn.")
            logging.debug("It's your turn in the new game.")
        else:
            self.my_turn = False
            self.update_status("Waiting for opponent's move.")
            logging.debug("Waiting for opponent's turn in the new game.")

        # Render the cleared game board
        self.render_game_board()

        # Optionally, reset any other necessary variables or GUI elements
        logging.info("New game has been initialized.")

    def handle_error(self, data):
        """
        Handles error messages received from the server.
        Displays appropriate error dialogs to the user.
        """
        logging.debug(f"Received error: {data}")
        error_code = data.get('code')
        message = data.get('message')
        messagebox.showerror("Server Error", f"[{error_code}] {message}")
        logging.error(f"Server error [{error_code}]: {message}")

        # Allow the player to try again for specific error codes
        if error_code in ['invalid_move', 'invalid_position']:
            self.my_turn = True
            logging.debug("Allowing player to try again after error.")

    def handle_opponent_disconnected(self, data):
        """
        Handles scenarios where the opponent disconnects unexpectedly.
        """
        logging.debug(f"Received opponent_disconnected: {data}")
        message = data.get('message')
        self.update_status(message)
        messagebox.showinfo("Opponent Disconnected", message)
        self.game_over = True
        self.prompt_new_game(None, message)

    def prompt_new_game(self, winner=None, message=None):
        """
        Prompts the user to start a new game or quit after a game concludes.
        """
        if winner == 'draw':
            prompt_message = "The game ended in a draw."
        elif winner == self.username:
            prompt_message = "Congratulations, you won the game!"
        elif winner:
            prompt_message = f"{winner} has won the game."
        elif message:
            prompt_message = message
        else:
            prompt_message = "The game has ended."

        # Ask the user if they want to start a new game
        result = messagebox.askquestion("Game Over", f"{prompt_message}\nDo you want to start a new game?")
        if result == 'yes':
            self.send_new_game_request()
        else:
            self.quit_game()

    def send_new_game_request(self):
        """
        Sends a request to the server to start a new game.
        """
        message = {
            "type": "new_game_response",
            "data": {
                "game_id": self.game_id,
                "uuid": self.player_uuid,
                "response": "start"
            }
        }
        self.send_message(message)
        self.update_status("Sent request to start a new game. Waiting for opponent...")
        logging.debug(f"Sent new_game_response: {message}")

    def send_new_game_quit(self):
        """
        Sends a request to the server indicating the player does not want to start a new game.
        """
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
        """
        Continuously processes messages from the message queue and schedules
        their handling on the main GUI thread.
        """
        while self.connected:
            message = self.receive_message()
            if message:
                # Schedule the message processing on the main thread
                self.root.after(0, self.process_message, message)
            else:
                continue  # Continue waiting for messages

    def process_message(self, message):
        """
        Determines the type of message received and delegates handling
        to the appropriate method.
        """
        message_type = message.get('type')
        data = message.get('data')

        # Map message types to handler methods
        handlers = {
            'join_ack': self.handle_join_ack,
            'move_ack': self.handle_move_ack,
            'chat_broadcast': self.handle_chat_broadcast,
            'quit_ack': self.handle_quit_ack,
            'game_over': self.handle_game_over,
            'new_game': self.handle_new_game,
            'opponent_disconnected': self.handle_opponent_disconnected,
            'error': self.handle_error
        }

        handler = handlers.get(message_type)
        if handler:
            handler(data)
        else:
            logging.warning(f"Unknown message type: {message_type}")

    def update_status(self, message):
        """
        Updates the status label in the GUI with the provided message.
        """
        self.status_label.config(text=message)
        logging.debug(f"Status updated: {message}")

    def render_game_board(self):
        """
        Updates the game board GUI based on the current game state.
        Disables buttons for occupied cells or when the game is over.
        """
        for row in range(3):
            for col in range(3):
                cell_value = self.game_state[row][col]
                btn = self.buttons[row][col]
                btn.config(text=cell_value)

                # Disable the button if the cell is occupied or the game is over
                if cell_value or self.game_over:
                    btn.config(state='disabled')
                else:
                    btn.config(state='normal')

        # Optionally, reset any additional GUI elements or states
        logging.debug("Rendered game board.")

    def start_gui(self):
        """
        Starts the Tkinter main loop and sets up the window close protocol.
        """
        self.root.protocol("WM_DELETE_WINDOW", self.quit_game)
        self.root.mainloop()

    def run(self):
        """
        Starts the client by connecting to the server, handling incoming messages,
        and launching the GUI.
        """
        try:
            if self.connect():
                # Start a thread to handle incoming server messages
                threading.Thread(target=self.handle_server_message, daemon=True).start()
                self.start_gui()
        except Exception as e:
            logging.exception(f"An unexpected error occurred: {e}")
            messagebox.showerror("Error", f"An unexpected error occurred: {e}")
        finally:
            self.disconnect()

    def quit_game(self):
        """
        Ensures that the client quits gracefully by sending a quit message,
        disconnecting from the server, and closing the GUI.
        """
        if self.game_id and self.player_uuid:
            self.send_quit()
        self.connected = False  # Ensure that the message-handling loop exits
        self.disconnect()
        self.root.destroy()


def main():
    """
    Entry point of the client application. Parses command-line arguments,
    configures logging, and starts the client.
    """
    parser = argparse.ArgumentParser(description="Tic-Tac-Toe Client")
    parser.add_argument('-i', '--ip', type=str, required=True, help='Server IP address or DNS')
    parser.add_argument('-p', '--port', type=int, required=True, help='Server port')
    parser.add_argument('--username', help='Your username (optional)', default=None)
    parser.add_argument('--avatar', help='Your avatar (optional)', default=None)
    args = parser.parse_args()

    # Configure logging to write to a file and console with detailed debug information
    logging.basicConfig(
        level=logging.DEBUG,  # Set to DEBUG for more detailed logs
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("client.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Initialize and run the client
    client = Client(host=args.ip, port=args.port, username=args.username, avatar=args.avatar)
    client.run()


if __name__ == '__main__':
    main()
