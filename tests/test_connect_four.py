import unittest
import sqlite3
import json
import os
import sys
import tempfile
import shutil
from unittest.mock import patch, MagicMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db_operations import initialize_database, create_game, get_open_games, get_game_by_id
from modules.Games.connect_four import ConnectFourGame, handle_connect_four_steps, handle_connect_four_command
from utils import update_user_state, get_user_state

class TestConnectFour(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        self.db_path = 'test_bulletins.db'
        self.conn = sqlite3.connect(self.db_path)
        self.get_db_connection_patcher = patch('db_operations.get_db_connection')
        self.mock_get_db_connection = self.get_db_connection_patcher.start()
        self.mock_get_db_connection.return_value = self.conn

        with open('config.ini', 'w') as f:
            f.write('[menu]\n')
            f.write('main_menu_items = B,G,U,Q,X\n')
            f.write('bbs_menu_items = M,B,C,J,X\n')
            f.write('utilities_menu_items = S,F,W,X\n')
            f.write('games_menu_items = T,C,X\n')
        with open('fortunes.txt', 'w') as f:
            f.write('test fortune\n')

        initialize_database()
        self.game_instance = ConnectFourGame()
        self.initial_board_json = json.dumps(self.game_instance.get_initial_board())

    def tearDown(self):
        self.get_db_connection_patcher.stop()
        self.conn.close()
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_handle_move(self):
        board = self.game_instance.get_initial_board()
        board = self.game_instance.handle_move(board, "3", "X")
        self.assertEqual(board[0][2], "X")
        board = self.game_instance.handle_move(board, "3", "O")
        self.assertEqual(board[1][2], "O")

    def test_win_horizontal(self):
        board = self.game_instance.get_initial_board()
        board[0][1] = board[0][2] = board[0][3] = board[0][4] = "X"
        self.assertEqual(self.game_instance.check_winner(board), "X")

    def test_win_vertical(self):
        board = self.game_instance.get_initial_board()
        board[0][2] = board[1][2] = board[2][2] = board[3][2] = "O"
        self.assertEqual(self.game_instance.check_winner(board), "O")

    def test_win_diagonal(self):
        board = self.game_instance.get_initial_board()
        board[0][0] = board[1][1] = board[2][2] = board[3][3] = "X"
        self.assertEqual(self.game_instance.check_winner(board), "X")

    def test_draw_game(self):
        board = [
            ['X', 'X', 'O', 'O', 'X', 'X', 'O'],
            ['O', 'O', 'X', 'X', 'O', 'O', 'X'],
            ['X', 'X', 'O', 'O', 'X', 'X', 'O'],
            ['O', 'O', 'X', 'X', 'O', 'O', 'X'],
            ['X', 'X', 'O', 'O', 'X', 'X', 'O'],
            ['O', 'O', 'X', 'X', 'O', 'O', 'X']
        ]
        self.assertEqual(self.game_instance.check_winner(board), "draw")

    @patch('modules.Games.game_logic_driver.send_message')
    @patch('modules.Games.connect_four.send_message')
    def test_remote_game_flow(self, mock_c4_send, mock_driver_send):
        mock_interface = MagicMock()
        p1_num = 111
        p2_num = 222
        mock_interface.nodes = {
            '!p1': {'num': p1_num, 'user': {'shortName': 'P1'}},
            '!p2': {'num': p2_num, 'user': {'shortName': 'P2'}},
        }

        with patch('utils.get_node_id_from_num', side_effect=lambda num, iface: {p1_num: '!p1', p2_num: '!p2'}.get(num)):
            # P1 starts a new game
            handle_connect_four_command(p1_num, mock_interface)
            state_p1 = get_user_state(p1_num)
            handle_connect_four_steps(p1_num, 'n', state_p1['step'], state_p1, mock_interface) # New game
            self.assertEqual(mock_driver_send.call_count, 1)
            game_id = get_open_games('connect_four')[0][0]

            # P2 joins the game by ID
            handle_connect_four_command(p2_num, mock_interface)
            state_p2 = get_user_state(p2_num)
            handle_connect_four_steps(p2_num, str(game_id), state_p2['step'], state_p2, mock_interface) # Join by ID
            self.assertEqual(mock_driver_send.call_count, 2)

            # P1 makes a move
            state_p1 = get_user_state(p1_num)
            handle_connect_four_steps(p1_num, '4', state_p1['step'], state_p1, mock_interface)
            self.assertEqual(mock_driver_send.call_count, 4)
            self.assertIn("has made a move. It's your turn", mock_driver_send.call_args_list[-2][0][0])
            self.assertIn("Move made. Waiting for opponent", mock_driver_send.call_args_list[-1][0][0])

if __name__ == '__main__':
    unittest.main()
