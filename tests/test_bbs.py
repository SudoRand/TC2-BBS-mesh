import unittest
from unittest.mock import MagicMock, patch
import os
import sys
import configparser
import sqlite3
import tempfile
import shutil
import textwrap
import importlib
import logging

# Add the parent directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import update_user_state

class MockInterface:
    def __init__(self):
        self.nodes = {
            '!a_mock_node_id': {'num': 1, 'user': {'shortName': 'MOCK', 'longName': 'Mock Node'}},
            '!another_mock_node_id': {'num': 2, 'user': {'shortName': 'MOCK2', 'longName': 'Mock Node 2'}},
        }
        self.myInfo = MagicMock()
        self.myInfo.my_node_num = 1
        self.bbs_nodes = []
        self.allowed_nodes = []

    def sendText(self, text, destinationId, wantAck=True, wantResponse=False):
        # This is a mock implementation of the sendText method
        print(f"Sending text: '{text}' to destination: {destinationId}")
        return MagicMock()

    def close(self):
        pass

class TestBBS(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

        # Create a dummy config.ini file
        config = configparser.ConfigParser()
        config['menu'] = {
            'main_menu_items': 'Q,B,U,G,X',
            'bbs_menu_items': 'M,B,C,J,X',
            'utilities_menu_items': 'S,F,W,X',
            'games_menu_items': 'T,X'
        }
        with open('config.ini', 'w') as configfile:
            config.write(configfile)

        # Create a dummy fortunes.txt file
        with open('fortunes.txt', 'w') as f:
            f.write("This is a test fortune.\n")

        # Reload the command_handlers module to pick up the new config
        global command_handlers, message_processing, db_operations
        # Add the parent directory of the original cwd to the Python path
        sys.path.append(os.path.abspath(os.path.join(self.original_cwd)))
        import command_handlers
        import message_processing
        import db_operations
        self.message_processing = message_processing
        importlib.reload(command_handlers)
        importlib.reload(self.message_processing)
        importlib.reload(db_operations)

        update_user_state(1, None)
        update_user_state(2, None)


        # Set up a temporary database for testing
        self.db_path = 'test_bulletins.db'
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.get_db_connection_patcher = patch('db_operations.get_db_connection')
        self.mock_get_db_connection = self.get_db_connection_patcher.start()
        self.mock_get_db_connection.return_value = self.conn
        db_operations.initialize_database()

        # Create a mock interface object
        self.interface = MockInterface()

        # Patch the send_message function to prevent it from sending real messages
        self.send_message_patcher = patch('command_handlers.send_message')
        self.mock_send_message = self.send_message_patcher.start()

        self.get_node_id_patcher = patch('utils.get_node_id_from_num')
        self.mock_get_node_id = self.get_node_id_patcher.start()
        def get_node_id_side_effect(num, interface):
            if num == 1:
                return '!a_mock_node_id'
            if num == 2:
                return '!another_mock_node_id'
            return None
        self.mock_get_node_id.side_effect = get_node_id_side_effect

        self.get_node_short_name_patcher = patch('utils.get_node_short_name')
        self.mock_get_node_short_name = self.get_node_short_name_patcher.start()
        self.mock_get_node_short_name.return_value = 'MOCK'

        self.get_node_info_patcher = patch('utils.get_node_info')
        self.mock_get_node_info = self.get_node_info_patcher.start()
        self.mock_get_node_info.return_value = [{'num': 2, 'id': '!another_mock_node_id', 'shortName': 'MOCK2', 'longName': 'Mock Node 2'}]

        self.get_mail_content_patcher = patch('db_operations.get_mail_content')
        self.mock_get_mail_content = self.get_mail_content_patcher.start()
        self.mock_get_mail_content.return_value = ('MOCK', '2024-01-01', 'Test Subject', 'Test Content', '1234')

        self.get_bulletin_content_patcher = patch('db_operations.get_bulletin_content', side_effect=self.mock_get_bulletin_content)
        self.mock_get_bulletin_content_mock = self.get_bulletin_content_patcher.start()

        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


    def tearDown(self):
        # Stop the patcher
        self.send_message_patcher.stop()
        self.get_node_id_patcher.stop()
        self.get_node_short_name_patcher.stop()
        self.get_node_info_patcher.stop()
        self.get_db_connection_patcher.stop()
        self.get_mail_content_patcher.stop()
        self.get_bulletin_content_patcher.stop()

        # Close the database connection
        self.conn.close()

        # Change back to the original directory and remove the temporary directory
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_main_menu(self):
        sender_id = 1
        self.mock_get_node_id.return_value = '!a_mock_node_id'
        with patch('command_handlers.count_my_turn_games', return_value=0):
            state = self.message_processing.process_message(sender_id, 'help', self.interface)
        self.mock_send_message.assert_called_with(unittest.mock.ANY, sender_id, self.interface)
        # Check that the main menu is displayed
        call_args, _ = self.mock_send_message.call_args
        self.assertIn("TC² BBS", call_args[0])
        # Verify the entire menu block
        expected_menu = textwrap.dedent("""\
            💾TC² BBS💾 (✉️:0) 🕹️:0
            [Q]uick Commands
            [B]BS
            [U]tilities
            [G]ames
            E[X]IT
        """).strip()
        self.assertEqual(call_args[0].strip(), expected_menu)
        self.assertEqual(state['command'], 'MAIN_MENU')

    def test_quick_commands_menu(self):
        sender_id = 1
        self.mock_get_node_id.return_value = '!a_mock_node_id'
        state = self.message_processing.process_message(sender_id, 'help', self.interface)
        state = self.message_processing.process_message(sender_id, 'q', self.interface)
        self.mock_send_message.assert_called_with(unittest.mock.ANY, sender_id, self.interface)
        # Check that the quick commands menu is displayed
        call_args, _ = self.mock_send_message.call_args
        self.assertIn("QUICK COMMANDS", call_args[0])

    def test_bbs_menu(self):
        sender_id = 1
        self.mock_get_node_id.return_value = '!a_mock_node_id'
        state = self.message_processing.process_message(sender_id, 'help', self.interface)
        state = self.message_processing.process_message(sender_id, 'b', self.interface)
        self.mock_send_message.assert_called_with(unittest.mock.ANY, sender_id, self.interface)
        # Check that the BBS menu is displayed
        call_args, _ = self.mock_send_message.call_args
        self.assertIn("BBS Menu", call_args[0])
        self.assertEqual(state['menu'], 'bbs')

    def test_utilities_menu(self):
        sender_id = 1
        self.mock_get_node_id.return_value = '!a_mock_node_id'
        state = self.message_processing.process_message(sender_id, 'help', self.interface)
        state = self.message_processing.process_message(sender_id, 'u', self.interface)
        self.mock_send_message.assert_called_with(unittest.mock.ANY, sender_id, self.interface)
        # Check that the utilities menu is displayed
        call_args, _ = self.mock_send_message.call_args
        self.assertIn("Utilities Menu", call_args[0])
        self.assertEqual(state['menu'], 'utilities')

    def test_fortune(self):
        sender_id = 1
        self.mock_get_node_id.return_value = '!a_mock_node_id'
        state = self.message_processing.process_message(sender_id, 'help', self.interface)
        state = self.message_processing.process_message(sender_id, 'u', self.interface)
        state = self.message_processing.process_message(sender_id, 'f', self.interface)
        self.mock_send_message.assert_called_with(unittest.mock.ANY, sender_id, self.interface)
        # Check that the fortune is displayed
        call_args, _ = self.mock_send_message.call_args
        self.assertIn("This is a test fortune.", call_args[0])

    def test_send_mail(self):
        sender_id = 1
        self.mock_get_node_id.return_value = '!a_mock_node_id'
        # Start the mail sending process
        state = self.message_processing.process_message(sender_id, 'help', self.interface)
        state = self.message_processing.process_message(sender_id, 'b', self.interface)
        state = self.message_processing.process_message(sender_id, 'm', self.interface)
        state = self.message_processing.process_message(sender_id, 's', self.interface)
        # Enter recipient
        state = self.message_processing.process_message(sender_id, 'MOCK2', self.interface)
        # Enter subject
        state = self.message_processing.process_message(sender_id, 'Test Subject', self.interface)
        # Enter message
        state = self.message_processing.process_message(sender_id, 'This is a test message.', self.interface)
        # End message
        state = self.message_processing.process_message(sender_id, 'end', self.interface)

        # Check that the mail was sent
        self.mock_send_message.assert_any_call(unittest.mock.ANY, '!another_mock_node_id', self.interface)
        # Get the last call
        last_call = self.mock_send_message.call_args_list[-2]
        call_args, _ = last_call
        self.assertIn("Mail has been posted", call_args[0])

    def test_read_and_delete_mail(self):
        sender_id = '!a_mock_node_id'
        recipient_id = '!another_mock_node_id'
        recipient_num = 2

        db_operations.add_mail(sender_id, 'MOCK', recipient_id, 'Test Subject', 'Test Content', [], self.interface)

        # Start the mail reading process
        state = self.message_processing.process_message(recipient_num, 'help', self.interface)
        state = self.message_processing.process_message(recipient_num, 'b', self.interface)
        state = self.message_processing.process_message(recipient_num, 'm', self.interface)
        state = self.message_processing.process_message(recipient_num, 'r', self.interface)
        # Select mail to read
        state = self.message_processing.process_message(recipient_num, '1', self.interface)

        # Check that the mail is displayed
        self.mock_send_message.assert_any_call(unittest.mock.ANY, recipient_num, self.interface)
        # Get the second to last call
        last_call = self.mock_send_message.call_args_list[-2]
        call_args, _ = last_call
        self.assertIn("Test Content", call_args[0])

        # Delete the mail
        state = self.message_processing.process_message(recipient_num, 'd', self.interface)
        self.mock_send_message.assert_any_call(unittest.mock.ANY, recipient_num, self.interface)
        # Get the second to last call
        last_call = self.mock_send_message.call_args_list[-1]
        call_args, _ = last_call
        self.assertIn("deleted", call_args[0])

    def test_read_mail_invalid_input(self):
        sender_id = '!a_mock_node_id'
        recipient_id = '!another_mock_node_id'
        recipient_num = 2

        db_operations.add_mail(sender_id, 'MOCK', recipient_id, 'Test Subject', 'Test Content', [], self.interface)

        # Start the mail reading process
        state = self.message_processing.process_message(recipient_num, 'help', self.interface)
        state = self.message_processing.process_message(recipient_num, 'b', self.interface)
        state = self.message_processing.process_message(recipient_num, 'm', self.interface)
        state = self.message_processing.process_message(recipient_num, 'r', self.interface)

        # Send invalid input
        state = self.message_processing.process_message(recipient_num, 'invalid', self.interface)

        # Check that an error message is displayed
        self.mock_send_message.assert_any_call(unittest.mock.ANY, recipient_num, self.interface)
        last_call = self.mock_send_message.call_args_list[-1]
        call_args, _ = last_call
        self.assertIn("Invalid input. Please enter a message number, 'help', or 'x' to exit.", call_args[0])
        self.assertEqual(state['command'], 'MAIL')
        self.assertEqual(state['step'], 2)

    def test_read_mail_help_command(self):
        sender_id = '!a_mock_node_id'
        recipient_id = '!another_mock_node_id'
        recipient_num = 2

        db_operations.add_mail(sender_id, 'MOCK', recipient_id, 'Test Subject', 'Test Content', [], self.interface)

        # Start the mail reading process
        state = self.message_processing.process_message(recipient_num, 'help', self.interface)
        state = self.message_processing.process_message(recipient_num, 'b', self.interface)
        state = self.message_processing.process_message(recipient_num, 'm', self.interface)
        state = self.message_processing.process_message(recipient_num, 'r', self.interface)

        # Send 'help' command
        state = self.message_processing.process_message(recipient_num, 'help', self.interface)

        # Check that the help message is displayed (main menu)
        self.mock_send_message.assert_any_call(unittest.mock.ANY, recipient_num, self.interface)
        last_call = self.mock_send_message.call_args_list[-1]
        call_args, _ = last_call
        self.assertIn("💾TC² BBS💾", call_args[0])
        self.assertEqual(state['command'], 'MAIN_MENU')

    def test_read_mail_exit_command(self):
        sender_id = '!a_mock_node_id'
        recipient_id = '!another_mock_node_id'
        recipient_num = 2

        db_operations.add_mail(sender_id, 'MOCK', recipient_id, 'Test Subject', 'Test Content', [], self.interface)

        # Start the mail reading process
        state = self.message_processing.process_message(recipient_num, 'help', self.interface)
        state = self.message_processing.process_message(recipient_num, 'b', self.interface)
        state = self.message_processing.process_message(recipient_num, 'm', self.interface)
        state = self.message_processing.process_message(recipient_num, 'r', self.interface)

        # Send 'x' command
        state = self.message_processing.process_message(recipient_num, 'x', self.interface)

        # Check that the exit message is displayed and state is reset
        self.mock_send_message.assert_any_call(unittest.mock.ANY, recipient_num, self.interface)
        last_call = self.mock_send_message.call_args_list[-1]
        call_args, _ = last_call
        self.assertRegex(call_args[0], r"💾TC² BBS💾 \(✉️:\d+\) 🕹️:\d+\n")
        self.assertEqual(state, {'command': 'MAIN_MENU', 'step': 1})

    def _test_post_bulletin(self, board_char, board_name):
        sender_id = 1
        self.mock_get_node_id.return_value = '!a_mock_node_id'
        # Start the bulletin posting process
        state = self.message_processing.process_message(sender_id, 'help', self.interface)
        state = self.message_processing.process_message(sender_id, 'b', self.interface)
        state = self.message_processing.process_message(sender_id, 'b', self.interface)
        state = self.message_processing.process_message(sender_id, board_char, self.interface)
        state = self.message_processing.process_message(sender_id, 'p', self.interface)
        # Enter subject
        state = self.message_processing.process_message(sender_id, f'Test Subject for {board_name}', self.interface)
        # Enter message
        state = self.message_processing.process_message(sender_id, f'This is a test message for {board_name}.', self.interface)
        # End message
        state = self.message_processing.process_message(sender_id, 'end', self.interface)

        # Check that the bulletin was posted
        self.mock_send_message.assert_any_call(unittest.mock.ANY, sender_id, self.interface)
        # Get the last call
        last_call = self.mock_send_message.call_args_list[-2]
        call_args, _ = last_call
        self.assertIn("has been posted", call_args[0])

    def mock_get_bulletin_content(self, bulletin_id):
        c = self.conn.cursor()
        c.execute("SELECT sender_short_name, date, subject, content, unique_id FROM bulletins WHERE id = ?", (bulletin_id,))
        return c.fetchone()

    def _test_read_bulletin(self, board_char, board_name):
        sender_id = 1
        self.mock_get_node_id.return_value = '!a_mock_node_id'

        db_operations.add_bulletin(board_name, 'MOCK', f'Test Subject for {board_name}', f'This is a test message for {board_name}.', [], self.interface)

        # Start the bulletin reading process
        state = self.message_processing.process_message(sender_id, 'help', self.interface)
        state = self.message_processing.process_message(sender_id, 'b', self.interface)
        state = self.message_processing.process_message(sender_id, 'b', self.interface)
        state = self.message_processing.process_message(sender_id, board_char, self.interface)
        state = self.message_processing.process_message(sender_id, 'r', self.interface)
        # Select bulletin to read
        state = self.message_processing.process_message(sender_id, '1', self.interface)

        # Check that the bulletin is displayed
        self.mock_send_message.assert_any_call(unittest.mock.ANY, sender_id, self.interface)
        # Get the last call
        last_call = self.mock_send_message.call_args_list[-2]
        call_args, _ = last_call
        self.assertIn(f"This is a test message for {board_name}.", call_args[0])

    def test_general_bulletin(self):
        self._test_post_bulletin('g', 'General')
        self._test_read_bulletin('g', 'General')

    def test_info_bulletin(self):
        self._test_post_bulletin('i', 'Info')
        self._test_read_bulletin('i', 'Info')

    def test_news_bulletin(self):
        self._test_post_bulletin('n', 'News')
        self._test_read_bulletin('n', 'News')

    def test_urgent_bulletin(self):
        self._test_post_bulletin('u', 'Urgent')
        self._test_read_bulletin('u', 'Urgent')

    def test_channel_directory(self):
        sender_id = 1
        self.mock_get_node_id.return_value = '!a_mock_node_id'
        # Go to the channel directory
        state = self.message_processing.process_message(sender_id, 'help', self.interface)
        state = self.message_processing.process_message(sender_id, 'b', self.interface)
        state = self.message_processing.process_message(sender_id, 'c', self.interface)
        self.mock_send_message.assert_called_with(unittest.mock.ANY, sender_id, self.interface)
        # Check that the channel directory is displayed
        call_args, _ = self.mock_send_message.call_args
        self.assertIn("CHANNEL DIRECTORY", call_args[0])

    def test_post_channel(self):
        sender_id = 1
        self.mock_get_node_id.return_value = '!a_mock_node_id'
        # Start the channel posting process
        state = self.message_processing.process_message(sender_id, 'help', self.interface)
        state = self.message_processing.process_message(sender_id, 'b', self.interface)
        state = self.message_processing.process_message(sender_id, 'c', self.interface)
        state = self.message_processing.process_message(sender_id, 'p', self.interface)
        # Enter channel name
        state = self.message_processing.process_message(sender_id, 'Test Channel', self.interface)
        # Enter channel URL
        state = self.message_processing.process_message(sender_id, 'http://test.channel', self.interface)

        # Check that the channel was posted
        self.mock_send_message.assert_any_call(unittest.mock.ANY, sender_id, self.interface)
        # Get the last call
        last_call = self.mock_send_message.call_args_list[-2]
        call_args, _ = last_call
        self.assertIn("has been added", call_args[0])

    def test_stats_menu(self):
        sender_id = 1
        self.mock_get_node_id.return_value = '!a_mock_node_id'
        # Go to the stats menu
        state = self.message_processing.process_message(sender_id, 'help', self.interface)
        state = self.message_processing.process_message(sender_id, 'u', self.interface)
        state = self.message_processing.process_message(sender_id, 's', self.interface)
        self.mock_send_message.assert_called_with(unittest.mock.ANY, sender_id, self.interface)
        # Check that the stats menu is displayed
        call_args, _ = self.mock_send_message.call_args
        self.assertIn("Stats Menu", call_args[0])

    def test_node_stats(self):
        sender_id = 1
        self.mock_get_node_id.return_value = '!a_mock_node_id'
        # Go to the node stats
        state = self.message_processing.process_message(sender_id, 'help', self.interface)
        state = self.message_processing.process_message(sender_id, 'u', self.interface)
        state = self.message_processing.process_message(sender_id, 's', self.interface)
        state = self.message_processing.process_message(sender_id, 'n', self.interface)
        self.mock_send_message.assert_any_call(unittest.mock.ANY, sender_id, self.interface)
        # Check that the node stats are displayed
        call_args, _ = self.mock_send_message.call_args_list[-2]
        self.assertIn("Total nodes seen", call_args[0])

    def test_hardware_stats(self):
        sender_id = 1
        self.mock_get_node_id.return_value = '!a_mock_node_id'
        # Go to the hardware stats
        state = self.message_processing.process_message(sender_id, 'help', self.interface)
        state = self.message_processing.process_message(sender_id, 'u', self.interface)
        state = self.message_processing.process_message(sender_id, 's', self.interface)
        state = self.message_processing.process_message(sender_id, 'h', self.interface)
        self.mock_send_message.assert_any_call(unittest.mock.ANY, sender_id, self.interface)
        # Check that the hardware stats are displayed
        call_args, _ = self.mock_send_message.call_args_list[-2]
        self.assertIn("Hardware Models", call_args[0])

    def test_role_stats(self):
        sender_id = 1
        self.mock_get_node_id.return_value = '!a_mock_node_id'
        # Go to the role stats
        state = self.message_processing.process_message(sender_id, 'help', self.interface)
        state = self.message_processing.process_message(sender_id, 'u', self.interface)
        state = self.message_processing.process_message(sender_id, 's', self.interface)
        state = self.message_processing.process_message(sender_id, 'r', self.interface)
        self.mock_send_message.assert_any_call(unittest.mock.ANY, sender_id, self.interface)
        # Check that the role stats are displayed
        call_args, _ = self.mock_send_message.call_args_list[-2]
        self.assertIn("Roles", call_args[0])

    def test_wall_of_shame(self):
        sender_id = 1
        self.mock_get_node_id.return_value = '!a_mock_node_id'
        self.interface.nodes['!a_mock_node_id']['deviceMetrics'] = {'batteryLevel': 10}
        # Go to the wall of shame
        state = self.message_processing.process_message(sender_id, 'help', self.interface)
        state = self.message_processing.process_message(sender_id, 'u', self.interface)
        state = self.message_processing.process_message(sender_id, 'w', self.interface)
        self.mock_send_message.assert_called_with(unittest.mock.ANY, sender_id, self.interface)
        # Check that the wall of shame is displayed
        call_args, _ = self.mock_send_message.call_args
        self.assertIn("battery levels below 20%", call_args[0])

    # @patch('modules.Games.game_logic_driver.send_message')
    # @patch('modules.Games.tic_tac_toe.send_message')
    # def test_tic_tac_toe_win(self, mock_ttt_send, mock_driver_send):
    #     sender_id = 1
    #     self.mock_get_node_id.return_value = '!a_mock_node_id'
    #     # Go to the games menu
    #     state = self.message_processing.process_message(sender_id, 'g', self.interface)
    #     state = self.message_processing.process_message(sender_id, 't', self.interface)

    #     # Start a new game
    #     self.message_processing.process_message(sender_id, 'n', self.interface)

    #     # Make moves
    #     self.message_processing.process_message(sender_id, '1', self.interface) # P1 is X

    #     # Manually create a second player and join the game
    #     game_id = db_operations.get_open_games('tic_tac_toe')[0][0]
    #     db_operations.join_game(game_id, '2')

    #     self.message_processing.process_message(2, '2', self.interface) # P2 is O
    #     self.message_processing.process_message(sender_id, '4', self.interface)
    #     self.message_processing.process_message(2, '5', self.interface)
    #     self.message_processing.process_message(sender_id, '7', self.interface) # P1 wins

    #     # Check that the win message is displayed
    #     self.assertGreater(mock_driver_send.call_count, 0)
    #     last_call = mock_driver_send.call_args_list[-2][0][0]
    #     self.assertIn("Congratulations! You win!", last_call)

    # @patch('modules.Games.game_logic_driver.send_message')
    # @patch('modules.Games.tic_tac_toe.send_message')
    # def test_tic_tac_toe_remote_game(self, mock_ttt_send, mock_driver_send):
    #     user1_id = 1
    #     user2_id = 2

    #     def get_node_id_side_effect(num, interface):
    #         if num == user1_id:
    #             return '!a_mock_node_id'
    #         elif num == user2_id:
    #             return '!another_mock_node_id'
    #         return None
    #     self.mock_get_node_id.side_effect = get_node_id_side_effect

    #     # user1 starts a new game
    #     self.message_processing.process_message(user1_id, 'g', self.interface)
    #     self.message_processing.process_message(user1_id, 't', self.interface)
    #     self.message_processing.process_message(user1_id, 'n', self.interface)
    #     self.message_processing.process_message(user1_id, '1', self.interface)

    #     # user2 joins the game
    #     game_id = db_operations.get_open_games('tic_tac_toe')[0][0]
    #     self.message_processing.process_message(user2_id, 'g', self.interface)
    #     self.message_processing.process_message(user2_id, 't', self.interface)
    #     self.message_processing.process_message(user2_id, str(game_id), self.interface)

    #     # Simulate a game where user2 (O) wins
    #     self.message_processing.process_message(user2_id, '5', self.interface) # O takes center
    #     self.message_processing.process_message(user1_id, '3', self.interface) # X takes top-right
    #     self.message_processing.process_message(user2_id, '2', self.interface) # O takes top-center
    #     self.message_processing.process_message(user1_id, '7', self.interface) # X takes bottom-left
    #     self.message_processing.process_message(user2_id, '8', self.interface) # O wins with 2,5,8

    #     # Check that the win message is displayed for user2
    #     all_calls = mock_driver_send.call_args_list
    #     found_win_message = False
    #     for call in all_calls:
    #         if "Congratulations! You win!" in call[0][0] and call[0][1] == user2_id:
    #             found_win_message = True
    #             break
    #     self.assertTrue(found_win_message, "Win message not found for user2")

    def test_simulator_send_from_another_node(self):
        with patch('builtins.input', side_effect=['SIM2: help', EOFError]):
            import bbs_simulator
            importlib.reload(bbs_simulator)
            with patch('message_processing.process_message') as mock_process_message:
                with patch('argparse.ArgumentParser.parse_known_args', return_value=(MagicMock(no_log=True), [])):
                    bbs_simulator.main()
                expected_sender_num = 0xf1d5a926
                mock_process_message.assert_called_once_with(expected_sender_num, 'help', unittest.mock.ANY)

    def test_simulator_send_from_unknown_node(self):
        with patch('builtins.input', side_effect=['UNKN: help', EOFError]):
            with patch('argparse.ArgumentParser.parse_known_args', return_value=(MagicMock(no_log=True), [])):
                import bbs_simulator
                importlib.reload(bbs_simulator)
                with patch('message_processing.process_message') as mock_process_message:
                    with patch('builtins.print') as mock_print:
                        bbs_simulator.main()
                        mock_print.assert_any_call("\033[91mError: Unrecognized short name 'UNKN'.\033[0m")
                        mock_process_message.assert_not_called()

    def test_simulator_unprefixed_message(self):
        with patch('builtins.input', side_effect=['help', EOFError]):
            with patch('argparse.ArgumentParser.parse_known_args', return_value=(MagicMock(no_log=True), [])):
                import bbs_simulator
                importlib.reload(bbs_simulator)
                with patch('message_processing.process_message') as mock_process_message:
                    bbs_simulator.main()
                    # Check that the message was processed by the default sender
                    expected_sender_num = 0xf1d5a925
                    mock_process_message.assert_called_once_with(expected_sender_num, 'help', unittest.mock.ANY)

    def test_simulator_sticky_prompt(self):
        with patch('builtins.input', side_effect=['SIM2: help', 'help', EOFError]) as mock_input:
            with patch('argparse.ArgumentParser.parse_known_args', return_value=(MagicMock(no_log=True), [])):
                import bbs_simulator
                importlib.reload(bbs_simulator)
                with patch('message_processing.process_message') as mock_process_message:
                    bbs_simulator.main()

                    # Check prompts
                    self.assertEqual(mock_input.call_args_list[0].args[0], 'SIM: ')
                    self.assertEqual(mock_input.call_args_list[1].args[0], 'SIM2: ')

                    # Check that the second message was processed by the new sticky sender
                    self.assertEqual(mock_process_message.call_count, 2)
                    last_call = mock_process_message.call_args_list[1]
                    self.assertEqual(last_call.args[0], 0xf1d5a926) # SIM2's num
                    self.assertEqual(last_call.args[1], 'help')

    def test_simulator_startup_instructions(self):
        with patch('builtins.input', side_effect=EOFError):
            with patch('argparse.ArgumentParser.parse_known_args', return_value=(MagicMock(no_log=True), [])):
                import bbs_simulator
                importlib.reload(bbs_simulator)
                with patch('builtins.print') as mock_print:
                    bbs_simulator.main()
                    # Check that the startup instructions are printed
                    mock_print.assert_any_call("To send as a different node, prefix your message with 'NAME: ', e.g., 'SIM2: help'.")
                    mock_print.assert_any_call("Available nodes:")
                    mock_print.assert_any_call("- SIM (Simulator Node)")
                    mock_print.assert_any_call("- SIM2 (Second Node)")

    def test_main_menu_icons_and_items(self):
        sender_id = 1
        self.mock_get_node_id.return_value = '!a_mock_node_id'
        # Patch get_active_games, get_game_by_id, and get_mail in command_handlers
        with patch('command_handlers.get_active_games'), \
             patch('command_handlers.get_game_by_id'), \
             patch('command_handlers.get_mail') as mock_get_mail, \
             patch('command_handlers.count_my_turn_games') as mock_count_my_turn_games:
            # Simulate 3 mail messages
            mock_get_mail.return_value = [
                (1, 'MOCK2', 'Subject1', '2025-08-30', 'msgid1'),
                (2, 'MOCK2', 'Subject2', '2025-08-30', 'msgid2'),
                (3, 'MOCK2', 'Subject3', '2025-08-30', 'msgid3'),
            ]
            mock_count_my_turn_games.return_value = 2
            state = self.message_processing.process_message(sender_id, 'help', self.interface)
            self.mock_send_message.assert_called_with(unittest.mock.ANY, sender_id, self.interface)
            call_args, _ = self.mock_send_message.call_args
            menu_text = call_args[0]
            expected_menu = textwrap.dedent("""\
                💾TC² BBS💾 (✉️:3) 🕹️:2
                [Q]uick Commands
                [B]BS
                [U]tilities
                [G]ames
                E[X]IT
            """)
            self.assertEqual(menu_text.strip(), expected_menu.strip())
            self.assertEqual(state['command'], 'MAIN_MENU')

if __name__ == '__main__':
    unittest.main()
