# test_tictactoe_game_state.py

import unittest
import subprocess
import time
import threading
from client import Client
import logging

class TestTicTacToeGameState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start the server process
        cls.server_process = subprocess.Popen(['python3', 'server.py'])
        time.sleep(1)  # Give the server time to start

    @classmethod
    def tearDownClass(cls):
        # Terminate the server process
        cls.server_process.terminate()
        cls.server_process.wait()

    def test_game_state_synchronization(self):
        # Set up logging for the test
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s')

        # Initialize clients
        client1 = Client(host='127.0.0.1', port=65432, username='Player1')
        client2 = Client(host='127.0.0.1', port=65432, username='Player2')

        # Flags to control the flow
        client1_turn = threading.Event()
        client2_turn = threading.Event()
        game_over = threading.Event()
        client1_ready = threading.Event()
        client2_ready = threading.Event()

        # Store game states for comparison
        client1_states = []
        client2_states = []

        # Client event handlers
        def client1_message_handler():
            while not game_over.is_set():
                message = client1.receive_message()
                if message:
                    self.handle_client_message(client1, message,
                                               client1_turn, client2_turn,
                                               game_over, client1_states, client1_ready)

        def client2_message_handler():
            while not game_over.is_set():
                message = client2.receive_message()
                if message:
                    self.handle_client_message(client2, message,
                                               client2_turn, client1_turn,
                                               game_over, client2_states, client2_ready)

        # Start clients and connect
        self.assertTrue(client1.connect(), "Client1 failed to connect.")
        self.assertTrue(client2.connect(), "Client2 failed to connect.")

        # Start listening threads
        client1_thread = threading.Thread(target=client1_message_handler)
        client2_thread = threading.Thread(target=client2_message_handler)
        client1_thread.start()
        client2_thread.start()

        try:
            # Wait for clients to be ready
            client1_ready.wait(timeout=5)
            client2_ready.wait(timeout=5)

            # Player1 starts first
            client1_turn.set()

            # Simulate game moves
            moves = [
                (client1, [0, 0]),  # Player1
                (client2, [1, 1]),  # Player2
                (client1, [0, 1]),  # Player1
                (client2, [1, 2]),  # Player2
                (client1, [0, 2])   # Player1 - Winning Move
            ]

            for client, position in moves:
                if client == client1:
                    client1_turn.wait(timeout=5)
                    if client1_turn.is_set():
                        client.send_move(position)
                        client1_turn.clear()
                elif client == client2:
                    client2_turn.wait(timeout=5)
                    if client2_turn.is_set():
                        client.send_move(position)
                        client2_turn.clear()

                # Wait for the other client's turn to complete
                time.sleep(0.5)

                # Check if the game is over
                if game_over.is_set():
                    break

            # Wait for game over
            game_over.wait(timeout=5)

            # Compare game states between clients
            self.assertEqual(client1_states[-1], client2_states[-1],
                             "Final game states should be equal.")

            # Verify that Player1 won
            final_state = client1_states[-1]
            self.assertEqual(final_state[0][0], 'X')
            self.assertEqual(final_state[0][1], 'X')
            self.assertEqual(final_state[0][2], 'X')

        finally:
            # Disconnect clients
            client1.disconnect()
            client2.disconnect()

            # Ensure threads are terminated
            client1_thread.join(timeout=1)
            client2_thread.join(timeout=1)

    def handle_client_message(self, client, message, own_turn_event,
                              other_turn_event, game_over_event, state_list, ready_event):
        message_type = message.get('type')
        data = message.get('data')

        if message_type == 'join_ack':
            self.handle_join_ack(client, data, ready_event)
        elif message_type == 'move_ack':
            self.handle_move_ack(client, data, own_turn_event, other_turn_event, game_over_event, state_list)
        elif message_type == 'error':
            self.handle_error(client, data, own_turn_event)
        elif message_type == 'chat_broadcast':
            self.handle_chat_broadcast(data)
        elif message_type == 'quit_ack':
            self.handle_quit_ack(data, game_over_event)
        else:
            logging.warning(f"Unknown message type: {message_type}")

    def handle_join_ack(self, client, data, ready_event):
        status = data.get('status')
        if status == 'success':
            client.game_id = data.get('game_id')
            client.player_symbol = data.get('player_symbol')
            logging.info(f"{client.username} joined game {client.game_id} as '{client.player_symbol}'")
            ready_event.set()
        elif status == 'waiting':
            logging.info(f"{client.username} is waiting for an opponent.")
            ready_event.set()  # Set the event even if waiting
        else:
            logging.error("Failed to join game.")

    def handle_move_ack(self, client, data, own_turn_event,
                        other_turn_event, game_over_event, state_list):
        status = data.get('status')
        if status == 'success':
            game_state = data.get('game_state')
            next_player = data.get('next_player')
            winner = data.get('winner')

            # Update client game state
            client.game_state = game_state
            state_list.append([row.copy() for row in game_state])  # Deep copy

            # Display game board
            self.display_game_board(game_state, client.username)

            if winner:
                if winner == 'draw':
                    logging.info("The game ended in a draw.")
                elif winner == client.username:
                    logging.info("Congratulations, you won!")
                else:
                    logging.info(f"{winner} has won the game.")
                game_over_event.set()
            else:
                # Set the appropriate turn event
                if next_player == client.username:
                    own_turn_event.set()
                else:
                    other_turn_event.set()
        else:
            logging.error(f"Move failed: {data.get('message')}")
            # Allow the player to retry
            own_turn_event.set()

    def handle_error(self, client, data, own_turn_event):
        error_code = data.get('code')
        message = data.get('message')
        logging.error(f"Error from server [{error_code}]: {message}")
        # Allow the client to retry or handle the error
        own_turn_event.set()

    def handle_chat_broadcast(self, data):
        username = data.get('username')
        message = data.get('message')
        logging.info(f"{username}: {message}")

    def handle_quit_ack(self, data, game_over_event):
        message = data.get('message')
        logging.info(message)
        game_over_event.set()

    def display_game_board(self, board, username):
        board_str = f"{username}'s View of the Game Board:\n"
        for row in board:
            board_str += ' | '.join(cell or ' ' for cell in row) + '\n'
            board_str += '---------\n'
        logging.info(board_str)

if __name__ == '__main__':
    unittest.main()
