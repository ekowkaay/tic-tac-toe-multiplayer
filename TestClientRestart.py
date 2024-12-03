import unittest
from unittest.mock import patch, MagicMock
from client import Client

class TestClientRestart(unittest.TestCase):
    def setUp(self):
        self.client = Client(host='127.0.0.1', port=65432, username='TestUser')
        self.client.socket = MagicMock()
        self.client.root = MagicMock()  # Mock the Tkinter root to avoid GUI issues

    @patch('client.messagebox.showinfo')
    @patch('client.messagebox.askquestion', return_value='yes')
    def test_client_restart(self, mock_askquestion, mock_showinfo):
        # Simulate joining the game
        join_ack = {
            'type': 'join_ack',
            'data': {
                'status': 'success',
                'game_id': 'test-game-id',
                'player_symbol': 'X',
                'uuid': 'player-uuid'
            }
        }
        self.client.process_message(join_ack)

        # Simulate moves to complete the initial game
        move_ack = {
            'type': 'move_ack',
            'data': {
                'status': 'success',
                'game_state': [['X', '', ''], ['', '', ''], ['', '', '']],
                'next_player_uuid': 'opponent-uuid',
                'winner': None
            }
        }
        self.client.process_message(move_ack)

        move_ack['data']['game_state'] = [['X', '', ''], ['O', '', ''], ['', '', '']]
        self.client.process_message(move_ack)

        move_ack['data']['game_state'] = [['X', 'X', ''], ['O', '', ''], ['', '', '']]
        self.client.process_message(move_ack)

        move_ack['data']['game_state'] = [['X', 'X', ''], ['O', 'O', ''], ['', '', '']]
        self.client.process_message(move_ack)

        move_ack['data']['game_state'] = [['X', 'X', 'X'], ['O', 'O', ''], ['', '', '']]
        move_ack['data']['winner'] = 'TestUser'
        self.client.process_message(move_ack)

        # Simulate game over and prompt for new game
        game_over = {
            'type': 'game_over',
            'data': {
                'winner': 'TestUser'
            }
        }
        self.client.process_message(game_over)

        # Simulate new game request
        new_game = {
            'type': 'new_game',
            'data': {
                'status': 'success',
                'game_state': [['', '', ''], ['', '', ''], ['', '', '']],
                'next_player_uuid': 'player-uuid',
                'player_symbol': 'O',
                'next_player_username': 'TestUser'
            }
        }
        self.client.process_message(new_game)

        # Verify the game has been reset
        self.assertEqual(self.client.game_state, [['', '', ''], ['', '', ''], ['', '', '']])
        self.assertFalse(self.client.game_over)
        self.assertEqual(self.client.player_symbol, 'O')

        # Simulate moves to complete the restarted game
        move_ack['data']['game_state'] = [['O', '', ''], ['', '', ''], ['', '', '']]
        move_ack['data']['next_player_uuid'] = 'opponent-uuid'
        move_ack['data']['winner'] = None
        self.client.process_message(move_ack)

        move_ack['data']['game_state'] = [['O', '', ''], ['X', '', ''], ['', '', '']]
        self.client.process_message(move_ack)

        move_ack['data']['game_state'] = [['O', 'O', ''], ['X', '', ''], ['', '', '']]
        self.client.process_message(move_ack)

        move_ack['data']['game_state'] = [['O', 'O', ''], ['X', 'X', ''], ['', '', '']]
        self.client.process_message(move_ack)

        move_ack['data']['game_state'] = [['O', 'O', 'O'], ['X', 'X', ''], ['', '', '']]
        move_ack['data']['winner'] = 'TestUser'
        self.client.process_message(move_ack)

        # Verify the outcome of the restarted game
        self.assertEqual(self.client.game_state, [['O', 'O', 'O'], ['X', 'X', ''], ['', '', '']])
        self.assertTrue(self.client.game_over)
        #self.assertEqual(self.client.winner, 'TestUser')

if __name__ == '__main__':
    unittest.main()