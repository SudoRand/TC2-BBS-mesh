import unittest
import sqlite3
import json
import os
import tempfile
import shutil
from unittest.mock import patch
from db_operations import (
    initialize_database,
    create_tic_tac_toe_game,
    get_open_tic_tac_toe_games,
    join_tic_tac_toe_game,
    get_tic_tac_toe_game_by_id,
    update_tic_tac_toe_board,
    end_tic_tac_toe_game
)
from modules.Games.tic_tac_toe import check_winner

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

if __name__ == '__main__':
    unittest.main()
