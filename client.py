import socket
import logging
import argparse
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Client:
    def __init__(self, host='127.0.0.1', port=65432):
        self.server_address = (host, port)
        self.client_socket = None

    def connect(self):
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.settimeout(5)  # Set a timeout for blocking operations
            self.client_socket.connect(self.server_address)
            logging.info(f"Connected to server at {self.server_address}")
            return True
        except socket.timeout:
            logging.error("Connection timed out")
            return False
        except socket.error as e:
            logging.error(f"Socket error during connection: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error during connection: {e}")
            return False

    def send_message(self, message):
        try:
            if not message.strip():
                logging.warning("Empty message not sent")
                return
            msg = json.dumps({"type": "message", "content": message})
            self.client_socket.sendall(msg.encode('utf-8'))
            response = self.client_socket.recv(1024).decode('utf-8')
            try:
                data = json.loads(response)
                if 'type' in data and 'content' in data:
                    logging.info(f"Received response: {data['content']}")
                else:
                    logging.error("Invalid response format from server")
            except json.JSONDecodeError:
                logging.error("Invalid JSON response from server")
        except socket.timeout:
            logging.error("Socket timed out waiting for a response")
        except socket.error as e:
            logging.error(f"Socket error: {e}")
        except Exception as e:
            logging.error(f"Unexpected error: {e}")

    def disconnect(self):
        if self.client_socket:
            self.client_socket.close()
            logging.info("Disconnected from server")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TCP Client")
    parser.add_argument('--host', default='127.0.0.1', help='Server host')
    parser.add_argument('--port', type=int, default=65432, help='Server port')
    args = parser.parse_args()

    client = Client(host=args.host, port=args.port)
    if client.connect():
        try:
            while True:
                message = input("Enter message to send (or 'exit' to quit): ")
                if message.lower() == 'exit':
                    break
                client.send_message(message)
        except KeyboardInterrupt:
            logging.info("Client shutting down.")
        finally:
            client.disconnect()
    else:
        logging.error("Failed to connect to the server.")
