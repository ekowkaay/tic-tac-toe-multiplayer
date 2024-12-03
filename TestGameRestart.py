import unittest
from unittest.mock import Mock, patch
from server import Server, Game

class TestGameRestart(unittest.TestCase):
    def setUp(self):
        self.server = Server(host='127.0.0.1', port=65432, max_workers=1)
        self.game_id = 'test-game-id'
        self.game = Game(self.game_id, self.server)
        self.player1 = {'uuid': 'player1-uuid', 'username': 'Player1', 'symbol': 'X', 'socket': Mock()}
        self.player2 = {'uuid': 'player2-uuid', 'username': 'Player2', 'symbol': 'O', 'socket': Mock()}
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)

    def test_game_restart_and_completion(self):
        # Simulate moves to complete the initial game
        self.game.make_move(self.player1['uuid'], (0, 0))
        self.game.make_move(self.player2['uuid'], (1, 0))
        self.game.make_move(self.player1['uuid'], (0, 1))
        self.game.make_move(self.player2['uuid'], (1, 1))
        self.game.make_move(self.player1['uuid'], (0, 2))  # Player1 wins

        self.assertEqual(self.game.winner, self.player1)

        # Request a new game
        self.game.handle_new_game_request(self.player1['uuid'])
        self.game.handle_new_game_request(self.player2['uuid'])

        # Verify the game has been reset
        self.assertIsNone(self.game.winner)
        self.assertEqual(self.game.board, [['', '', ''], ['', '', ''], ['', '', '']])

        # Simulate moves to complete the new game
        self.game.make_move(self.player2['uuid'], (0, 0))
        self.game.make_move(self.player1['uuid'], (1, 0))
        self.game.make_move(self.player2['uuid'], (0, 1))
        self.game.make_move(self.player1['uuid'], (1, 1))
        self.game.make_move(self.player2['uuid'], (0, 2))  # Player2 wins

        self.assertEqual(self.game.winner, self.player2)

if __name__ == '__main__':
    unittest.main()
