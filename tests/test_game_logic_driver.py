import unittest
import sqlite3
import json
import os
import sys
import tempfile
import shutil
from unittest.mock import patch, MagicMock

# Add the parent directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db_operations import initialize_database, get_db_connection, create_game, join_game, get_game_by_id
from modules.Games.game_interface import GameInterface
from modules.Games.game_logic_driver import GameLogicDriver
from utils import update_user_state

class MockGame(GameInterface):
    """A mock implementation of GameInterface for testing the driver."""
    @property
    def game_type(self):
        return 'mock_game'

    def get_initial_board(self):
        return [" "] * 4

    def render_board(self, board, player_x_name, player_o_name):
        return f"Board: {''.join(board)}"

    def get_instruction_board(self):
        return "Mock Instructions"

    def handle_move(self, board, move, player_symbol):
        try:
            pos = int(move)
            if board[pos] != " ":
                raise ValueError("Spot taken")
            board[pos] = player_symbol
            return board
        except (ValueError, IndexError):
            raise ValueError("Invalid Move")

    def check_winner(self, board):
        if "X" * 2 in "".join(board):
            return "X"
        if "O" * 2 in "".join(board):
            return "O"
        if " " not in board:
            return "draw"
        return None

class TestGameLogicDriver(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

        # Mock config.ini
        with open('config.ini', 'w') as f:
            f.write('[bbs]\n')
            f.write('node_short_name = ME\n')

        self.db_path = 'test_bulletins.db'
        self.conn = sqlite3.connect(self.db_path)
        self.get_db_connection_patcher = patch('db_operations.get_db_connection')
        self.mock_get_db_connection = self.get_db_connection_patcher.start()
        self.mock_get_db_connection.return_value = self.conn

        initialize_database()

        self.mock_interface = MagicMock()
        self.p1_num = 111
        self.p1_id = '!p1'
        self.p1_sn = 'P1'
        self.p2_num = 222
        self.p2_id = '!p2'
        self.p2_sn = 'P2'

        self.mock_interface.nodes = {
            self.p1_id: {'num': self.p1_num, 'user': {'shortName': self.p1_sn}},
            self.p2_id: {'num': self.p2_num, 'user': {'shortName': self.p2_sn}},
        }

        # Patch send_message and update_user_state from the driver's perspective
        self.send_message_patcher = patch('modules.Games.game_logic_driver.send_message')
        self.mock_send_message = self.send_message_patcher.start()

        self.update_user_state_patcher = patch('modules.Games.game_logic_driver.update_user_state')
        self.mock_update_user_state = self.update_user_state_patcher.start()

        self.mock_game = MockGame()
        self.driver = GameLogicDriver(self.mock_game, self.mock_interface)

    def tearDown(self):
        self.get_db_connection_patcher.stop()
        self.send_message_patcher.stop()
        self.update_user_state_patcher.stop()
        self.conn.close()
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_start_new_game(self):
        game_id = self.driver.start_new_game(self.p1_num)

        self.assertIsNotNone(game_id)
        db_game = get_game_by_id(game_id)
        self.assertEqual(db_game[1], 'mock_game')
        self.assertEqual(db_game[2], str(self.p1_num))

        self.mock_send_message.assert_called_once()
        message_sent = self.mock_send_message.call_args[0][0]
        self.assertIn(f"New game started. Game ID: {game_id}", message_sent)
        self.assertIn("Mock Instructions", message_sent)

    def test_join_game_by_id(self):
        game_id = create_game('mock_game', str(self.p1_num), json.dumps([" "]*4))

        returned_id = self.driver.join_game_by_id(self.p2_num, str(game_id))
        self.assertEqual(returned_id, game_id)

        db_game = get_game_by_id(game_id)
        self.assertEqual(db_game[3], str(self.p2_num)) # player_o
        self.assertEqual(db_game[5], str(self.p1_num)) # current_player should still be P1
        self.assertEqual(db_game[7], 'in_progress') # status

        self.mock_send_message.assert_called_once_with(
            f"You joined game {game_id}.\n\nMock Instructions\n\nBoard:     \nIt's your turn (O). Enter your move, or E[X]IT to pause.",
            self.p2_num,
            self.mock_interface
        )

    def test_play_move_and_notify(self):
        game_id = create_game('mock_game', str(self.p1_num), json.dumps([" "]*4))
        join_game(game_id, str(self.p2_num))

        # P1 makes a move
        state_p1 = {'game_id': game_id}
        self.driver.play_move(self.p1_num, "0", state_p1)

        # Assert P2 was notified correctly (second to last message)
        self.assertEqual(self.mock_send_message.call_count, 2)
        notify_p2_call = self.mock_send_message.call_args_list[0]
        self.assertEqual(notify_p2_call[0][1], self.p2_num)
        self.assertIn(f"{self.p1_sn} (X) has made a move.", notify_p2_call[0][0])
        self.assertIn("Board: X   ", notify_p2_call[0][0])
        self.assertIn("It's your turn (O).", notify_p2_call[0][0])

        # Assert P1 got confirmation (last message)
        confirm_p1_call = self.mock_send_message.call_args_list[1]
        self.assertEqual(confirm_p1_call[0][1], self.p1_num)
        self.assertIn(f"Move made. Waiting for opponent {self.p2_sn} (O).", confirm_p1_call[0][0])

        db_game = get_game_by_id(game_id)
        self.assertEqual(db_game[5], str(self.p2_num)) # current_player is now P2
        self.assertEqual(json.loads(db_game[4]), ["X", " ", " ", " "]) # board is updated

    def test_play_move_win_condition(self):
        # Setup a game where P1 can win
        game_id = create_game('mock_game', str(self.p1_num), json.dumps([" ", " ", " ", " "]))
        join_game(game_id, str(self.p2_num))

        state_p1 = {'game_id': game_id}
        state_p2 = {'game_id': game_id}

        # Move 1: P1 moves at 0. Board: ['X', ' ', ' ', ' ']
        self.driver.play_move(self.p1_num, "0", state_p1)
        self.assertEqual(self.mock_send_message.call_count, 2)

        # Move 2: P2 moves at 2. Board: ['X', ' ', 'O', ' ']
        self.driver.play_move(self.p2_num, "2", state_p2)
        self.assertEqual(self.mock_send_message.call_count, 4)

        # Move 3: P1 makes winning move at 1. Board: ['X', 'X', 'O', ' ']
        self.driver.play_move(self.p1_num, "1", state_p1)

        # Assert win messages were sent
        self.assertEqual(self.mock_send_message.call_count, 6)
        win_msg_p1 = self.mock_send_message.call_args_list[-2][0][0]
        lose_msg_p2 = self.mock_send_message.call_args_list[-1][0][0]

        self.assertIn("Congratulations! You win!", win_msg_p1)
        self.assertIn(f"Game over. {self.p1_sn} wins.", lose_msg_p2)

        # Assert user states were updated to go back to the menu
        self.assertEqual(self.mock_update_user_state.call_count, 2)
        self.mock_update_user_state.assert_any_call(self.p1_num, {'command': 'GAMES', 'step': 1})
        self.mock_update_user_state.assert_any_call(self.p2_num, {'command': 'GAMES', 'step': 1})

        db_game = get_game_by_id(game_id)
        self.assertEqual(db_game[7], 'finished') # status
        self.assertEqual(db_game[6], str(self.p1_num)) # winner

if __name__ == '__main__':
    unittest.main()
