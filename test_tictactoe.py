import unittest
import subprocess
import time
import threading
from client import Client
import logging

class TestTicTacToe(unittest.TestCase):
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

    def test_game_play(self):
        # Set up logging for the test
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

        # Initialize clients
        client1 = Client(host='127.0.0.1', port=65432, username='Player1')
        client2 = Client(host='127.0.0.1', port=65432, username='Player2')

        # Flags to control the flow
        client1_turn = threading.Event()
        client2_turn = threading.Event()
        game_over = threading.Event()

        # Client event handlers
        def client1_message_handler():
            while not game_over.is_set():
                message = client1.receive_message()
                if message:
                    self.handle_client_message(client1, message, client1_turn, client2_turn, game_over)

        def client2_message_handler():
            while not game_over.is_set():
                message = client2.receive_message()
                if message:
                    self.handle_client_message(client2, message, client2_turn, client1_turn, game_over)

        # Start clients and connect
        self.assertTrue(client1.connect())
        self.assertTrue(client2.connect())

        # Start listening threads
        client1_thread = threading.Thread(target=client1_message_handler)
        client2_thread = threading.Thread(target=client2_message_handler)
        client1_thread.start()
        client2_thread.start()

        try:
            # Wait for the game to start
            time.sleep(1)

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
                    client1_turn.wait()
                    client1.send_move(position)
                    client1_turn.clear()
                elif client == client2:
                    client2_turn.wait()
                    client2.send_move(position)
                    client2_turn.clear()

                # Wait for the other client's turn to complete
                time.sleep(0.5)

                # Check if the game is over
                if game_over.is_set():
                    break

            # Wait for game over
            game_over.wait()

        finally:
            # Disconnect clients
            client1.disconnect()
            client2.disconnect()

            # Ensure threads are terminated
            client1_thread.join()
            client2_thread.join()

    def handle_client_message(self, client, message, own_turn_event, other_turn_event, game_over_event):
        message_type = message.get('type')
        data = message.get('data')

        if message_type == 'join_ack':
            status = data.get('status')
            if status == 'success':
                logging.info(f"{client.username} joined game {data.get('game_id')} as '{data.get('player_symbol')}'")
            elif status == 'waiting':
                logging.info(f"{client.username} is waiting for an opponent.")
        elif message_type == 'move_ack':
            status = data.get('status')
            if status == 'success':
                game_state = data.get('game_state')
                next_player = data.get('next_player')
                winner = data.get('winner')

                # Update client game state
                client.game_state = game_state

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
                # Allow the client to retry if desired
                own_turn_event.set()
        elif message_type == 'error':
            logging.error(f"Error from server [{data.get('code')}]: {data.get('message')}")
            # Decide how to handle the error
            # For this test, we'll set the turn event to allow retry
            own_turn_event.set()
        elif message_type == 'chat_broadcast':
            logging.info(f"{data.get('username')}: {data.get('message')}")
        elif message_type == 'quit_ack':
            logging.info(data.get('message'))
            game_over_event.set()

    def display_game_board(self, board, username):
        logging.info(f"{username}'s View of the Game Board:")
        for row in board:
            logging.info(' | '.join(cell or ' ' for cell in row))
            logging.info('---------')

if __name__ == '__main__':
    unittest.main()
