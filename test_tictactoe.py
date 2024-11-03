import unittest
import threading
import time
import logging
from client import Client
from server import Server
import socket

class TestTicTacToeGame(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start the server
        cls.server = Server(host='127.0.0.1', port=65432, max_workers=10)
        cls.server_thread = threading.Thread(target=cls.server.start)
        cls.server_thread.daemon = True
        cls.server_thread.start()
        time.sleep(1)  # Give the server a moment to start

    @classmethod
    def tearDownClass(cls):
        # Stop the server
        cls.server.stop()
        cls.server_thread.join()

    def test_client_connection_and_join(self):
        # Test that clients can connect and join the game
        client1 = Client(host='127.0.0.1', port=65432, username='Player1')
        client2 = Client(host='127.0.0.1', port=65432, username='Player2')

        self.assertTrue(client1.connect())
        self.assertTrue(client2.connect())

        # Wait for both clients to join the game
        time.sleep(1)

        self.assertIsNotNone(client1.game_id, "Client1 did not receive game_id")
        self.assertIsNotNone(client2.game_id, "Client2 did not receive game_id")
        self.assertEqual(client1.game_id, client2.game_id, "Clients are not in the same game")

        client1.disconnect()
        client2.disconnect()

    def test_valid_moves(self):
        # Test that clients can make valid moves
        client1 = Client(host='127.0.0.1', port=65432, username='Player1')
        client2 = Client(host='127.0.0.1', port=65432, username='Player2')

        client1.connect()
        client2.connect()
        time.sleep(1)

        # Simulate gameplay
        moves = [
            (client1, [0, 0]),
            (client2, [1, 1]),
            (client1, [0, 1]),
            (client2, [1, 2]),
            (client1, [0, 2])  # This move leads to a win for client1
        ]

        for client, position in moves:
            client.send_move(position)
            time.sleep(0.5)

        # Wait for server to process moves
        time.sleep(1)

        # Check if client1 is the winner
        self.assertTrue(client1.game_over, "Client1 game should be over")
        self.assertTrue(client2.game_over, "Client2 game should be over")
        self.assertEqual(client1.winner, client1.username, "Client1 should be the winner")
        self.assertEqual(client2.winner, client1.username, "Client2 should recognize Client1 as the winner")

        client1.disconnect()
        client2.disconnect()

    def test_invalid_moves(self):
        # Test that invalid moves are handled properly
        client1 = Client(host='127.0.0.1', port=65432, username='Player1')
        client2 = Client(host='127.0.0.1', port=65432, username='Player2')

        client1.connect()
        client2.connect()
        time.sleep(1)

        # Client1 makes a valid move
        client1.send_move([0, 0])
        time.sleep(0.5)

        # Client1 tries to move again (out of turn)
        client1.send_move([0, 1])
        time.sleep(0.5)

        # Verify that an error was received
        self.assertTrue(client1.last_error is not None, "Client1 should receive an error for moving out of turn")
        self.assertEqual(client1.last_error_code, 'not_your_turn', "Error code should be 'not_your_turn'")

        # Client2 makes a valid move
        client2.send_move([0, 0])  # Occupied cell
        time.sleep(0.5)

        # Verify that an error was received
        self.assertTrue(client2.last_error is not None, "Client2 should receive an error for moving on occupied cell")
        self.assertEqual(client2.last_error_code, 'invalid_move', "Error code should be 'invalid_move'")

        # Client2 makes a valid move
        client2.send_move([1, 1])
        time.sleep(0.5)

        client1.disconnect()
        client2.disconnect()

    def test_game_draw(self):
        # Test a game that results in a draw
        client1 = Client(host='127.0.0.1', port=65432, username='Player1')
        client2 = Client(host='127.0.0.1', port=65432, username='Player2')

        client1.connect()
        client2.connect()
        time.sleep(1)

        # Simulate gameplay leading to a draw
        moves = [
            (client1, [0, 0]),
            (client2, [0, 1]),
            (client1, [0, 2]),
            (client2, [1, 0]),
            (client1, [1, 2]),
            (client2, [1, 1]),
            (client1, [2, 1]),
            (client2, [2, 0]),
            (client1, [2, 2])
        ]

        for client, position in moves:
            client.send_move(position)
            time.sleep(0.5)

        # Wait for server to process moves
        time.sleep(1)

        # Check for draw
        self.assertTrue(client1.game_over, "Client1 game should be over")
        self.assertTrue(client2.game_over, "Client2 game should be over")
        self.assertEqual(client1.winner, 'draw', "Game should result in a draw")
        self.assertEqual(client2.winner, 'draw', "Game should result in a draw")

        client1.disconnect()
        client2.disconnect()

    def test_chat_messages(self):
        # Test chat functionality
        client1 = Client(host='127.0.0.1', port=65432, username='Player1')
        client2 = Client(host='127.0.0.1', port=65432, username='Player2')

        client1.connect()
        client2.connect()
        time.sleep(1)

        # Client1 sends a chat message
        client1.send_chat("Hello Player2!")
        time.sleep(0.5)

        # Verify that Client2 received the chat message
        self.assertIn("Hello Player2!", client2.chat_messages, "Client2 should receive chat message from Client1")

        client1.disconnect()
        client2.disconnect()

    def test_client_disconnection(self):
        # Test handling of client disconnection
        client1 = Client(host='127.0.0.1', port=65432, username='Player1')
        client2 = Client(host='127.0.0.1', port=65432, username='Player2')

        client1.connect()
        client2.connect()
        time.sleep(1)

        # Client1 disconnects
        client1.send_quit()
        time.sleep(1)

        # Verify that Client2 is notified
        self.assertTrue(client2.game_over, "Client2 should be notified of opponent's disconnection")

        client2.disconnect()

if __name__ == '__main__':
    # Set logging level to ERROR to reduce test output clutter
    logging.basicConfig(level=logging.ERROR)
    unittest.main()