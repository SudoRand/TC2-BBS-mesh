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
            }
        }
        self.bbs_nodes = []
        self.allowed_nodes = []

    def sendText(self, text, destinationId=None, wantAck=False, wantResponse=False):
        print(f"BBS: {text}")
        return type('Packet', (), {'id': 'simulator_packet'})()

    def close(self):
        pass

def main():
    parser = argparse.ArgumentParser(description="BBS Simulator")
    parser.add_argument("--node-id", default='!f1d5a925', help="Node ID of the simulator")
    parser.add_argument("--short-name", default='SIM', help="Short name of the simulator node")
    parser.add_argument("--long-name", default='Simulator', help="Long name of the simulator node")

    # This is a bit of a hack to allow the simulator to be launched from server.py
    # without parsing the server's command-line arguments.
    args, _ = parser.parse_known_args()


    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    from db_operations import initialize_database
    from message_processing import process_message

    initialize_database()

    interface = SimulatorInterface(node_id=args.node_id, short_name=args.short_name, long_name=args.long_name)

    print("BBS Simulator Started. Type 'help' for a list of commands.")

    while True:
        try:
            message = input(f"{interface.nodes[args.node_id]['user']['longName']} ({interface.nodes[args.node_id]['user']['shortName']}): ")
            process_message(interface.myInfo.my_node_num, message, interface)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting simulator.")
            break

if __name__ == "__main__":
    main()
