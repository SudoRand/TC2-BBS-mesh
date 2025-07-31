import logging
import argparse
class SimulatorInterface:
    def __init__(self, node_id='!f1d5a925', short_name='SIM', long_name='Simulator'):
        self.myInfo = type('MyInfo', (), {'my_node_num': int(node_id.replace('!', '0x'), 16)})()
        self.nodes = {
            node_id: {
                'num': self.myInfo.my_node_num,
                'user': {'shortName': short_name, 'longName': long_name},
                'deviceMetrics': {'batteryLevel': 100},
            },
            # Add more nodes for the simulator
            '!f1d5a926': {
                'num': 0xf1d5a926,
                'user': {'shortName': 'NODE2', 'longName': 'Second Node'},
                'deviceMetrics': {'batteryLevel': 90},
            },
            '!f1d5a927': {
                'num': 0xf1d5a927,
                'user': {'shortName': 'NODE3', 'longName': 'Third Node'},
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
    parser.add_argument("--node-id", default='!f1d5a925', help="Node ID of the simulator")
    parser.add_argument("--short-name", default='SIM', help="Short name of the simulator node")
    parser.add_argument("--long-name", default='Simulator', help="Long name of the simulator node")
    parser.add_argument("--no-log", action="store_true", help="Suppress logging output")

    # This is a bit of a hack to allow the simulator to be launched from server.py
    # without parsing the server's command-line arguments.
    args, _ = parser.parse_known_args()


    if not args.no_log:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    from db_operations import initialize_database
    from message_processing import process_message

    initialize_database()

    interface = SimulatorInterface(node_id=args.node_id, short_name=args.short_name, long_name=args.long_name)

    print("BBS Simulator Started. Type 'help' for a list of commands.")

    while True:
        try:
            prompt = f"\033[93m{interface.nodes[args.node_id]['user']['longName']} ({interface.nodes[args.node_id]['user']['shortName']}): \033[0m"
            message = input(prompt)

            sender_num = interface.myInfo.my_node_num
            processed_message = message

            if message.startswith('@'):
                parts = message.split(':', 1)
                if len(parts) == 2:
                    from_node_short_name = parts[0][1:].strip()
                    actual_message = parts[1].strip()

                    sender_node_info = None
                    # Find the node by shortName
                    for node_id, node_info in interface.nodes.items():
                        if node_info['user']['shortName'].lower() == from_node_short_name.lower():
                            sender_node_info = node_info
                            break

                    if sender_node_info:
                        sender_num = sender_node_info['num']
                        processed_message = actual_message
                        # Optional: give feedback to the user
                        print(f"\033[95mSending as {sender_node_info['user']['longName']} ({sender_node_info['user']['shortName']})\033[0m")
                    else:
                        print(f"\033[91mError: Node '{from_node_short_name}' not found.\033[0m")
                        continue  # continue to next loop iteration, skipping process_message

            process_message(sender_num, processed_message, interface)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting simulator.")
            break

if __name__ == "__main__":
    main()
