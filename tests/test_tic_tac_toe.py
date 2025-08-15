import unittest
import sqlite3
import json
import os
import sys
import tempfile
import shutil
from unittest.mock import patch, MagicMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db_operations import initialize_database, create_game, get_open_games, get_game_by_id, update_game_board, end_game, join_game
from modules.Games.tic_tac_toe import TicTacToeGame, handle_tic_tac_toe_steps, handle_tic_tac_toe_command
from utils import update_user_state, get_user_state

class TestTicTacToe(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        self.db_path = 'test_bulletins.db'
        self.conn = sqlite3.connect(self.db_path)
        self.get_db_connection_patcher = patch('db_operations.get_db_connection', return_value=self.conn)
        self.mock_get_db_connection = self.get_db_connection_patcher.start()

        with open('config.ini', 'w') as f:
            f.write('[menu]\nmain_menu_items = G,X\ngames_menu_items = T,C,X\n')
        with open('fortunes.txt', 'w') as f:
            f.write('test fortune\n')

        initialize_database()
        self.game_instance = TicTacToeGame()

    def tearDown(self):
        self.get_db_connection_patcher.stop()
        self.conn.close()
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    @patch('modules.Games.game_logic_driver.send_message')
    @patch('modules.Games.tic_tac_toe.send_message')
    def test_remote_game_flow(self, mock_ttt_send, mock_driver_send):
        mock_interface = MagicMock()
        p1_num, p2_num = 111, 222
        mock_interface.nodes = {
            '!p1': {'num': p1_num, 'user': {'shortName': 'P1'}},
            '!p2': {'num': p2_num, 'user': {'shortName': 'P2'}},
        }

        with patch('utils.get_node_id_from_num', side_effect=lambda num, iface: {p1_num: '!p1', p2_num: '!p2'}.get(num)):
            # P1 starts a new game and makes the first move
            handle_tic_tac_toe_command(p1_num, mock_interface)
            state_p1 = get_user_state(p1_num)
            handle_tic_tac_toe_steps(p1_num, 'n', state_p1['step'], state_p1, mock_interface)
            state_p1 = get_user_state(p1_num)
            handle_tic_tac_toe_steps(p1_num, '5', state_p1['step'], state_p1, mock_interface)
            game_id = get_open_games('tic_tac_toe')[0][0]

            # P2 joins
            handle_tic_tac_toe_command(p2_num, mock_interface)
            state_p2 = get_user_state(p2_num)
            handle_tic_tac_toe_steps(p2_num, str(game_id), state_p2['step'], state_p2, mock_interface)
            self.assertEqual(mock_driver_send.call_count, 2)

            # P2 makes a move
            state_p2 = get_user_state(p2_num)
            handle_tic_tac_toe_steps(p2_num, "1", state_p2['step'], state_p2, mock_interface)
            self.assertEqual(mock_driver_send.call_count, 4)

    @patch('modules.Games.game_logic_driver.send_message')
    @patch('modules.Games.tic_tac_toe.send_message')
    def test_continue_game_flow(self, mock_ttt_send, mock_driver_send):
        mock_interface = MagicMock()
        p1_num, p2_num = 111, 222
        mock_interface.nodes = {
            '!p1': {'num': p1_num, 'user': {'shortName': 'P1'}},
            '!p2': {'num': p2_num, 'user': {'shortName': 'P2'}},
        }
        with patch('utils.get_node_id_from_num', side_effect=lambda num, iface: {p1_num: '!p1', p2_num: '!p2'}.get(num)):
            # Create a game where it's P1's turn
            board = self.game_instance.get_initial_board()
            board[4] = 'O' # P2's move
            game_id = create_game(self.game_instance.game_type, str(p1_num), json.dumps(board))
            join_game(game_id, str(p2_num))
            update_game_board(game_id, json.dumps(board), str(p1_num))

            # P1 goes to the menu and chooses to continue
            handle_tic_tac_toe_command(p1_num, mock_interface)
            self.assertIn("Continue your game", mock_ttt_send.call_args[0][0])

            state_p1 = get_user_state(p1_num)
            handle_tic_tac_toe_steps(p1_num, str(game_id), state_p1['step'], state_p1, mock_interface)

            self.assertEqual(mock_driver_send.call_count, 1)
            self.assertIn("It's your turn (X)", mock_driver_send.call_args[0][0])

if __name__ == '__main__':
    unittest.main()
