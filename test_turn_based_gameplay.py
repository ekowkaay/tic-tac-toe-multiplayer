# test_turn_based_gameplay.py

import unittest
import subprocess
import time
import threading
from client import Client
import logging

class TestTurnBasedGameplay(unittest.TestCase):
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

    def test_turn_enforcement_and_winning_conditions(self):
        # Set up logging for the test
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s')

        # Initialize clients
        client1 = Client(host='127.0.0.1', port=65432, username='Alice')
        client2 = Client(host='127.0.0.1', port=65432, username='Bob')

        # Events to manage synchronization
        client1_ready = threading.Event()
        client2_ready = threading.Event()
        game_over = threading.Event()

        # Store game states
        client1_states = []
        client2_states = []

        # Start clients and connect
        self.assertTrue(client1.connect(), "Client1 failed to connect.")
        self.assertTrue(client2.connect(), "Client2 failed to connect.")

        # Client message handlers
        def client1_message_handler():
            while not game_over.is_set():
                message = client1.receive_message()
                if message:
                    self.handle_client_message(client1, message, client1_ready, game_over, client1_states)

        def client2_message_handler():
            while not game_over.is_set():
                message = client2.receive_message()
                if message:
                    self.handle_client_message(client2, message, client2_ready, game_over, client2_states)

        # Start listening threads
        client1_thread = threading.Thread(target=client1_message_handler)
        client2_thread = threading.Thread(target=client2_message_handler)
        client1_thread.start()
        client2_thread.start()

        try:
            # Wait for both clients to be ready
            client1_ready.wait(timeout=5)
            client2_ready.wait(timeout=5)

            # Ensure that both clients have unique UUIDs
            self.assertIsNotNone(client1.player_uuid)
            self.assertIsNotNone(client2.player_uuid)
            self.assertNotEqual(client1.player_uuid, client2.player_uuid)

            # Determine symbol assignments
            if client1.player_symbol == 'X':
                current_client, other_client = client1, client2
            else:
                current_client, other_client = client2, client1

            # Simulate turns
            moves = [
                (current_client, [0, 0]),  # Current player (X) makes the first move
                (other_client, [1, 1]),    # Other player (O) makes their move
                (current_client, [0, 1]),  # X
                (other_client, [1, 2]),    # O
                (current_client, [0, 2])   # X - Winning Move
            ]

            for client, position in moves:
                # Attempt to make a move out of turn
                out_of_turn_client = other_client if client == current_client else current_client
                out_of_turn_client.send_move(position)

                # Send the correct move
                client.send_move(position)

                # Wait for the server to process moves
                time.sleep(0.5)

                # Check if game is over
                if client.game_over or other_client.game_over:
                    game_over.set()
                    break

            # Wait for game over
            game_over.wait(timeout=5)

            # Determine the winner
            winner_client = current_client if current_client.game_over and \
                             current_client.player_symbol == 'X' else other_client

            # Verify that the winner is the current_client with symbol 'X'
            self.assertTrue(winner_client.game_over, "Game should be over with a winner.")
            self.assertEqual(winner_client.game_state[0][0], 'X')
            self.assertEqual(winner_client.game_state[0][1], 'X')
            self.assertEqual(winner_client.game_state[0][2], 'X')
            self.assertEqual(winner_client.username, 'Alice' if client1.player_symbol == 'X' else 'Bob')

        finally:
            # Disconnect clients
            client1.disconnect()
            client2.disconnect()

            # Ensure threads are terminated
            client1_thread.join(timeout=1)
            client2_thread.join(timeout=1)

    def handle_client_message(self, client, message, ready_event, game_over_event, state_list):
        message_type = message.get('type')
        data = message.get('data')

        if message_type == 'join_ack':
            self.handle_join_ack(client, data, ready_event)
        elif message_type == 'move_ack':
            self.handle_move_ack(client, data, game_over_event, state_list)
        elif message_type == 'error':
            self.handle_error(client, data)
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
            client.player_uuid = data.get('uuid')
            logging.info(f"{client.username} joined game {client.game_id} as '{client.player_symbol}' with UUID {client.player_uuid}")
            ready_event.set()
        elif status == 'waiting':
            client.player_uuid = data.get('uuid')
            logging.info(f"{client.username} is waiting for an opponent.")
            ready_event.set()
        else:
            logging.error("Failed to join game.")

    def handle_move_ack(self, client, data, game_over_event, state_list):
        status = data.get('status')
        if status == 'success':
            game_state = data.get('game_state')
            next_player_uuid = data.get('next_player_uuid')
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
                    logging.info(f"Congratulations {client.username}, you won!")
                else:
                    logging.info(f"{winner} has won the game.")
                client.game_over = True
                game_over_event.set()
            else:
                # Update turn information
                client.my_turn = (next_player_uuid == client.player_uuid)
        else:
            logging.error(f"Move failed: {data.get('message')}")

    def handle_error(self, client, data):
        error_code = data.get('code')
        message = data.get('message')
        logging.error(f"Error from server [{error_code}]: {message}")

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
