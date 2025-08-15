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

from db_operations import (
    initialize_database,
    create_game,
    get_open_games,
    get_active_games_for_player,
    join_game,
    get_game_by_id,
    update_game_board,
    end_game
)
from modules.Games.tic_tac_toe import TicTacToeGame, handle_tic_tac_toe_steps, handle_tic_tac_toe_command
from utils import update_user_state, get_user_state

class TestTicTacToe(unittest.TestCase):

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
            f.write('bbs_menu_items = B,M,C,X\n')
            f.write('utilities_menu_items = S,F,W,X\n')
            f.write('games_menu_items = T,C,X\n')

        with open('fortunes.txt', 'w') as f:
            f.write('test fortune\n')

        initialize_database()
        self.game_instance = TicTacToeGame()
        self.initial_board_json = json.dumps(self.game_instance.get_initial_board())

    def tearDown(self):
        self.get_db_connection_patcher.stop()
        self.conn.close()
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_win_game(self):
        board = ["X", "X", "X", " ", " ", " ", " ", " ", " "]
        self.assertEqual(self.game_instance.check_winner(board), "X")

    def test_draw_game(self):
        board = ["X", "O", "X", "X", "O", "X", "O", "X", "O"]
        self.assertEqual(self.game_instance.check_winner(board), "draw")

    @patch('modules.Games.game_logic_driver.send_message')
    @patch('modules.Games.tic_tac_toe.send_message')
    def test_continue_game_flow(self, mock_ttt_send, mock_driver_send):
        mock_interface = MagicMock()
        p1_num = 111
        p2_num = 222
        mock_interface.nodes = {
            '!p1': {'num': p1_num, 'user': {'shortName': 'P1'}},
            '!p2': {'num': p2_num, 'user': {'shortName': 'P2'}},
        }
        with patch('utils.get_node_id_from_num', side_effect=lambda num, iface: {p1_num: '!p1', p2_num: '!p2'}.get(num)):
            game_id = create_game(self.game_instance.game_type, str(p1_num), self.initial_board_json)
            join_game(game_id, str(p2_num))
            update_game_board(game_id, self.initial_board_json, str(p1_num))

            handle_tic_tac_toe_command(p1_num, mock_interface)
            self.assertIn("[C]ONTINUE an active game", mock_ttt_send.call_args[0][0])

            state_p1 = get_user_state(p1_num)
            handle_tic_tac_toe_steps(p1_num, "c", state_p1['step'], state_p1, mock_interface)
            self.assertIn(f"ID: {game_id}, Opponent: P2", mock_ttt_send.call_args[0][0])

            state_p1 = get_user_state(p1_num)
            handle_tic_tac_toe_steps(p1_num, str(game_id), state_p1['step'], state_p1, mock_interface)
            self.assertEqual(mock_driver_send.call_count, 1)
            self.assertIn("It's your turn (X)", mock_driver_send.call_args[0][0])

    @patch('modules.Games.game_logic_driver.send_message')
    @patch('modules.Games.tic_tac_toe.send_message')
    def test_remote_game_flow(self, mock_ttt_send, mock_driver_send):
        mock_interface = MagicMock()
        p1_num = 111
        p2_num = 222
        mock_interface.nodes = {
            '!p1': {'num': p1_num, 'user': {'shortName': 'P1'}},
            '!p2': {'num': p2_num, 'user': {'shortName': 'P2'}},
        }

        with patch('utils.get_node_id_from_num', side_effect=lambda num, iface: {p1_num: '!p1', p2_num: '!p2'}.get(num)):
            # P1 starts
            handle_tic_tac_toe_command(p1_num, mock_interface)
            state_p1 = get_user_state(p1_num)
            handle_tic_tac_toe_steps(p1_num, 'n', state_p1['step'], state_p1, mock_interface) # New game
            self.assertEqual(mock_driver_send.call_count, 1)
            game_id = get_open_games('tic_tac_toe')[0][0]

            # P2 joins
            handle_tic_tac_toe_command(p2_num, mock_interface)
            state_p2 = get_user_state(p2_num)
            handle_tic_tac_toe_steps(p2_num, str(game_id), state_p2['step'], state_p2, mock_interface) # Join by ID
            self.assertEqual(mock_driver_send.call_count, 2)

            # P1 makes a move
            state_p1 = get_user_state(p1_num)
            handle_tic_tac_toe_steps(p1_num, "5", state_p1['step'], state_p1, mock_interface)
            self.assertEqual(mock_driver_send.call_count, 4)
            self.assertIn("has made a move. It's your turn", mock_driver_send.call_args_list[-2][0][0])
            self.assertIn("Move made. Waiting for opponent", mock_driver_send.call_args_list[-1][0][0])


if __name__ == '__main__':
    unittest.main()
