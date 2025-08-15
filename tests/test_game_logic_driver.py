import unittest
import sqlite3
import json
import os
import sys
import tempfile
import shutil
from unittest.mock import patch, MagicMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db_operations import initialize_database, create_game, join_game, get_game_by_id
from modules.Games.game_interface import GameInterface
from modules.Games.game_logic_driver import GameLogicDriver

class MockGame(GameInterface):
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
        pos = int(move)
        board[pos] = player_symbol
        return board
    def check_winner(self, board):
        if "XX" in "".join(board): return "X"
        if "OO" in "".join(board): return "O"
        return None

class TestGameLogicDriver(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        self.patcher = patch('db_operations.get_db_connection', return_value=sqlite3.connect('test.db'))
        self.mock_db = self.patcher.start()
        initialize_database()

        self.mock_interface = MagicMock()
        self.p1_num, self.p1_id, self.p1_sn = 111, '!p1', 'P1'
        self.p2_num, self.p2_id, self.p2_sn = 222, '!p2', 'P2'
        self.mock_interface.nodes = {
            self.p1_id: {'num': self.p1_num, 'user': {'shortName': self.p1_sn}},
            self.p2_id: {'num': self.p2_num, 'user': {'shortName': self.p2_sn}},
        }
        with patch('utils.get_node_id_from_num', side_effect=lambda num, iface: {self.p1_num: self.p1_id, self.p2_num: self.p2_id}.get(num)):
            self.send_message_patcher = patch('modules.Games.game_logic_driver.send_message')
            self.mock_send_message = self.send_message_patcher.start()
            self.update_user_state_patcher = patch('modules.Games.game_logic_driver.update_user_state')
            self.mock_update_user_state = self.update_user_state_patcher.start()
            self.mock_game = MockGame()
            self.driver = GameLogicDriver(self.mock_game, self.mock_interface)

    def tearDown(self):
        self.patcher.stop()
        self.send_message_patcher.stop()
        self.update_user_state_patcher.stop()
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_create_game_with_first_move(self):
        board_after_move = ["X", " ", " ", " "]
        game_id = self.driver.create_game_with_first_move(self.p1_num, board_after_move)

        self.assertIsNotNone(game_id)
        db_game = get_game_by_id(game_id)
        self.assertEqual(db_game[1], 'mock_game')
        self.assertEqual(db_game[2], str(self.p1_num))
        self.assertIsNone(db_game[5])
        self.assertEqual(json.loads(db_game[4]), board_after_move)
        self.mock_send_message.assert_called_once()
        self.assertIn(f"Your game (ID: {game_id}) is now listed", self.mock_send_message.call_args[0][0])

    def test_join_game_by_id(self):
        game_id = create_game('mock_game', str(self.p1_num), json.dumps(["X", " ", " ", " "]))
        self.driver.join_game_by_id(self.p2_num, str(game_id))

        db_game = get_game_by_id(game_id)
        self.assertEqual(db_game[3], str(self.p2_num))
        self.assertEqual(db_game[5], str(self.p2_num))
        self.mock_send_message.assert_called_once()
        self.assertIn("It's your turn (O)", self.mock_send_message.call_args[0][0])

    def test_play_move_and_notify(self):
        game_id = create_game('mock_game', str(self.p1_num), json.dumps(["X", " ", " ", " "]))
        join_game(game_id, str(self.p2_num))

        state_p2 = {'game_id': game_id}
        self.driver.play_move(self.p2_num, "2", state_p2)

        self.assertEqual(self.mock_send_message.call_count, 2)
        notify_p1_call = self.mock_send_message.call_args_list[0]
        self.assertEqual(notify_p1_call[0][1], self.p1_num)
        self.assertIn("It's your turn (X)", notify_p1_call[0][0])

        db_game = get_game_by_id(game_id)
        self.assertEqual(db_game[5], str(self.p1_num))

if __name__ == '__main__':
    unittest.main()
