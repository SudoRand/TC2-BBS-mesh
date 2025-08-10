import unittest
import sqlite3
import json
import os
import sys
import tempfile
import shutil
from unittest.mock import patch
import configparser

# Add the parent directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db_operations import (
    initialize_database,
    create_tic_tac_toe_game,
    get_open_tic_tac_toe_games,
    join_tic_tac_toe_game,
    get_tic_tac_toe_game_by_id,
    update_tic_tac_toe_board,
    end_tic_tac_toe_game
)
from modules.Games.tic_tac_toe import check_winner, handle_tic_tac_toe_steps
from utils import update_user_state

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

        # Create a dummy config.ini
        with open('config.ini', 'w') as f:
            f.write('[menu]\n')
            f.write('main_menu_items = B,G,U,Q\n')
            f.write('bbs_menu_items = B,M,C,X\n')
            f.write('utilities_menu_items = S,F,W,X\n')
            f.write('games_menu_items = T,X\n')

        initialize_database()

    def tearDown(self):
        self.get_db_connection_patcher.stop()
        self.conn.close()
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_create_game(self):
        game_id = create_tic_tac_toe_game("player1")
        self.assertIsNotNone(game_id)
        games = get_open_tic_tac_toe_games()
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0][1], "player1")

    def test_join_game(self):
        game_id = create_tic_tac_toe_game("player1")
        games = get_open_tic_tac_toe_games()
        game_db_id = games[0][0]
        join_tic_tac_toe_game(game_db_id, "player2")
        game = get_tic_tac_toe_game_by_id(game_db_id)
        self.assertEqual(game[2], "player2")
        self.assertEqual(game[6], "in_progress")

    def test_make_move(self):
        game_id = create_tic_tac_toe_game("player1")
        games = get_open_tic_tac_toe_games()
        game_db_id = games[0][0]
        join_tic_tac_toe_game(game_db_id, "player2")

        board = json.loads(get_tic_tac_toe_game_by_id(game_db_id)[3])
        board[0] = "X"
        update_tic_tac_toe_board(game_db_id, json.dumps(board), "player2")

        game = get_tic_tac_toe_game_by_id(game_db_id)
        new_board = json.loads(game[3])
        self.assertEqual(new_board[0], "X")
        self.assertEqual(game[4], "player2")

    def test_win_game(self):
        game_id = create_tic_tac_toe_game("player1")
        games = get_open_tic_tac_toe_games()
        game_db_id = games[0][0]
        join_tic_tac_toe_game(game_db_id, "player2")

        board = ["X", "X", "X", " ", " ", " ", " ", " ", " "]
        self.assertEqual(check_winner(board), "X")

        end_tic_tac_toe_game(game_db_id, "player1")
        game = get_tic_tac_toe_game_by_id(game_db_id)
        self.assertEqual(game[5], "player1")
        self.assertEqual(game[6], "finished")

    def test_draw_game(self):
        game_id = create_tic_tac_toe_game("player1")
        games = get_open_tic_tac_toe_games()
        game_db_id = games[0][0]
        join_tic_tac_toe_game(game_db_id, "player2")

        board = ["X", "O", "X", "X", "O", "X", "O", "X", "O"]
        self.assertIsNone(check_winner(board))

        end_tic_tac_toe_game(game_db_id, "draw")
        game = get_tic_tac_toe_game_by_id(game_db_id)
        self.assertEqual(game[5], "draw")
        self.assertEqual(game[6], "finished")

    @patch('modules.Games.tic_tac_toe.send_message')
    def test_list_open_games_displays_short_name(self, mock_send_message):
        # 2. Setup mock interface and user states
        mock_interface = unittest.mock.MagicMock()
        player1_node_num = 12345
        player1_node_id = '!b827ebf575b0'
        player1_short_name = 'P1'

        mock_interface.nodes = {
            player1_node_id: {'num': player1_node_num, 'user': {'shortName': player1_short_name, 'longName': 'PlayerOne'}},
        }

        # 3. Create a game
        create_tic_tac_toe_game(str(player1_node_num))

        # 4. User requests to join a game
        player2_node_num = 54321
        player2_node_id = '!b827ebf575b1'
        update_user_state(player2_node_id, {'command': 'TIC_TAC_TOE', 'step': 10})
        state = {'command': 'TIC_TAC_TOE', 'step': 10}

        handle_tic_tac_toe_steps(player2_node_id, "2", 10, state, mock_interface)

        # 5. Assert the message contains the short name
        self.assertEqual(mock_send_message.call_count, 1)
        sent_message = mock_send_message.call_args[0][0]
        self.assertIn(f"Started by: {player1_short_name}", sent_message)
        self.assertNotIn(str(player1_node_num), sent_message)


if __name__ == '__main__':
    unittest.main()
