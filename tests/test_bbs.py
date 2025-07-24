import unittest
from unittest.mock import MagicMock, patch
import os
import sys
import configparser
import sqlite3
import tempfile
import shutil
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
        self.conn = sqlite3.connect(':memory:')
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

        self.get_node_short_name_patcher = patch('utils.get_node_short_name')
        self.mock_get_node_short_name = self.get_node_short_name_patcher.start()
        self.mock_get_node_short_name.return_value = 'MOCK'

        self.get_node_info_patcher = patch('utils.get_node_info')
        self.mock_get_node_info = self.get_node_info_patcher.start()
        self.mock_get_node_info.return_value = [{'num': 2, 'shortName': 'MOCK2', 'longName': 'Mock Node 2'}]

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
        state = self.message_processing.process_message(sender_id, 'help', self.interface)
        self.mock_send_message.assert_called_with(unittest.mock.ANY, sender_id, self.interface)
        # Check that the main menu is displayed
        call_args, _ = self.mock_send_message.call_args
        self.assertIn("TC² BBS", call_args[0])
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
        self.mock_send_message.assert_any_call(unittest.mock.ANY, 2, self.interface)
        # Get the last call
        last_call = self.mock_send_message.call_args_list[-2]
        call_args, _ = last_call
        self.assertIn("Mail has been posted", call_args[0])

    def test_read_and_delete_mail(self):
        sender_id = 1
        recipient_id = 2
        self.mock_get_node_id.return_value = '!another_mock_node_id'

        db_operations.add_mail('!a_mock_node_id', 'MOCK', '!another_mock_node_id', 'Test Subject', 'Test Content', [], self.interface)

        # Start the mail reading process
        state = self.message_processing.process_message(recipient_id, 'help', self.interface)
        state = self.message_processing.process_message(recipient_id, 'b', self.interface)
        state = self.message_processing.process_message(recipient_id, 'm', self.interface)
        state = self.message_processing.process_message(recipient_id, 'r', self.interface)
        # Select mail to read
        state = self.message_processing.process_message(recipient_id, '1', self.interface)

        # Check that the mail is displayed
        self.mock_send_message.assert_any_call(unittest.mock.ANY, recipient_id, self.interface)
        # Get the last call
        last_call = self.mock_send_message.call_args_list[-2]
        call_args, _ = last_call
        self.assertIn("Test Content", call_args[0])

        # Delete the mail
        state = self.message_processing.process_message(recipient_id, 'd', self.interface)
        self.mock_send_message.assert_any_call(unittest.mock.ANY, recipient_id, self.interface)
        # Get the last call
        last_call = self.mock_send_message.call_args_list[-1]
        call_args, _ = last_call
        self.assertIn("deleted", call_args[0])

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

    def test_tic_tac_toe_win(self):
        with patch('modules.Games.tic_tac_toe.send_message') as mock_send_message:
            sender_id = 1
            self.mock_get_node_id.return_value = '!a_mock_node_id'
            # Go to the games menu
            state = self.message_processing.process_message(sender_id, 'help', self.interface)
            state = self.message_processing.process_message(sender_id, 'g', self.interface)
            state = self.message_processing.process_message(sender_id, 't', self.interface)
            state = self.message_processing.process_message(sender_id, '1', self.interface) # pvp

            # Simulate a game where X wins
            self.message_processing.process_message(sender_id, '1', self.interface)
            self.message_processing.process_message(sender_id, '4', self.interface)
            self.message_processing.process_message(sender_id, '2', self.interface)
            self.message_processing.process_message(sender_id, '5', self.interface)
            self.message_processing.process_message(sender_id, '3', self.interface)

            # Check that the win message is displayed
            mock_send_message.assert_any_call(unittest.mock.ANY, sender_id, self.interface)
            last_call = mock_send_message.call_args_list[-1]
            call_args, _ = last_call
            self.assertIn("Congratulations! X wins!", call_args[0])


if __name__ == '__main__':
    unittest.main()
