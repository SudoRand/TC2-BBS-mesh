import logging
import argparse
import re
class SimulatorInterface:
    def __init__(self):
        self.send_delay = 0
        node_id='!f1d5a925'
        self.myInfo = type('MyInfo', (), {'my_node_num': int(node_id.replace('!', '0x'), 16)})()
        self.nodes = {
            '!f1d5a925': {
                'num': self.myInfo.my_node_num,
                'user': {'shortName': 'SIM', 'longName': 'Simulator Node'},
                'deviceMetrics': {'batteryLevel': 100},
            },
            '!f1d5a926': {
                'num': 0xf1d5a926,
                'user': {'shortName': 'SIM2', 'longName': 'Second Node'},
                'deviceMetrics': {'batteryLevel': 90},
            },
            '!f1d5a927': {
                'num': 0xf1d5a927,
                'user': {'shortName': 'SIM3', 'longName': 'Third Node'},
                'deviceMetrics': {'batteryLevel': 80},
            }
        }
        self.bbs_nodes = []
        self.allowed_nodes = []

    def sendText(self, text, destinationId=None, wantAck=False, wantResponse=False):
        print(f"\033[96mBBS: {text}\033[0m")
        return type('Packet', (), {'id': 'simulator_packet'})()

    def close(self):
        pass

def main():
    parser = argparse.ArgumentParser(description="BBS Simulator")
    parser.add_argument("--no-log", action="store_true", help="Suppress logging output")
    args, _ = parser.parse_known_args()

    if not args.no_log:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    from db_operations import initialize_database
    from message_processing import process_message

    initialize_database()

    interface = SimulatorInterface()

    print("BBS Simulator Started. Type 'help' for a list of commands.")
    print("To send as a different node, prefix your message with 'NAME: ', e.g., 'SIM2: help'.")
    print("Available nodes:")
    for node in interface.nodes.values():
        print(f"- {node['user']['shortName']} ({node['user']['longName']})")

    last_sender_short_name = 'SIM'

    while True:
        try:
            # Find the node info for the last sender to create the prompt
            last_sender_node_info = None
            for node_id, node_info in interface.nodes.items():
                if node_info['user']['shortName'].lower() == last_sender_short_name.lower():
                    last_sender_node_info = node_info
                    break

            short_name = last_sender_node_info['user']['shortName']
            prompt_str = f"{short_name}: "
            message = input(prompt_str)

            # Use regex to match "short_name: message" format
            match = re.match(r'^(\S{1,4}):\s(.*)', message)
            if match:
                # Prefix found, attempt to switch sender
                from_node_short_name, actual_message = match.groups()
                sender_node_info = None
                for node_id, node_info in interface.nodes.items():
                    if node_info['user']['shortName'].lower() == from_node_short_name.lower():
                        sender_node_info = node_info
                        break

                if not sender_node_info:
                    print(f"\033[91mError: Unrecognized short name '{from_node_short_name}'.\033[0m")
                    continue # Don't process message, but keep last sender

                # Sender is valid, process message and update sticky sender
                sender_num = sender_node_info['num']
                processed_message = actual_message
                last_sender_short_name = sender_node_info['user']['shortName']

            else:
                # No prefix, use the last active sender
                sender_num = last_sender_node_info['num']
                processed_message = message

            process_message(sender_num, processed_message, interface)

        except (KeyboardInterrupt, EOFError):
            print("\nExiting simulator.")
            break

if __name__ == "__main__":
    main()
