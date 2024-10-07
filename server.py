import socket
import threading
import logging
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Server:
    def __init__(self, host='127.0.0.1', port=65432, max_workers=10):
        self.server_address = (host, port)
        self.is_running = True
        self.max_workers = max_workers
        self.setup_server_socket()

    def setup_server_socket(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.server_socket.bind(self.server_address)
            self.server_socket.listen()
            logging.info(f"Server listening on {self.server_address[0]}:{self.server_address[1]}")
        except socket.error as e:
            logging.error(f"Socket error during server setup: {e}")
            self.server_socket.close()
            sys.exit(1)

    def handle_client(self, client_socket, address):
        thread_name = threading.current_thread().name
        logging.info(f"[{thread_name}] Connection established with {address}")
        client_socket.settimeout(300) 
        try:
            while True:
                message = client_socket.recv(1024).decode('utf-8')
                if not message:
                    break
                try:
                    data = json.loads(message)
                    if 'type' in data and 'content' in data:
                        logging.info(f"[{thread_name}] Received message from {address}: {data['content']}")
                        response = json.dumps({
                            "type": "response",
                            "content": f"Echo: {data['content']}"
                        })
                        client_socket.sendall(response.encode('utf-8'))
                    else:
                        logging.error(f"[{thread_name}] Invalid message format from {address}")
                except json.JSONDecodeError:
                    logging.error(f"[{thread_name}] Invalid JSON received from {address}")
                    error_response = json.dumps({
                        "type": "error",
                        "content": "Invalid JSON format"
                    })
                    client_socket.sendall(error_response.encode('utf-8'))
        except socket.timeout:
            logging.error(f"[{thread_name}] Socket timed out with {address}")
        except socket.error as e:
            logging.error(f"[{thread_name}] Socket error with {address}: {e}")
        except Exception as e:
            logging.error(f"[{thread_name}] Unexpected error with {address}: {e}")
        finally:
            client_socket.close()
            logging.info(f"[{thread_name}] Connection closed with {address}")

    def start(self):
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            while self.is_running:
                try:
                    client_socket, address = self.server_socket.accept()
                    executor.submit(self.handle_client, client_socket, address)
                except socket.timeout:
                    continue 
                except socket.error as e:
                    logging.error(f"Socket error during accept: {e}")
                    break
                except Exception as e:
                    logging.error(f"Unexpected error: {e}")
                    break

    def stop(self):
        self.is_running = False
        self.server_socket.close()
        logging.info("Server has been stopped.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TCP Server")
    parser.add_argument('--host', default='127.0.0.1', help='Server host')
    parser.add_argument('--port', type=int, default=65432, help='Server port')
    parser.add_argument('--max-workers', type=int, default=10, help='Maximum number of worker threads')
    args = parser.parse_args()

    server = Server(host=args.host, port=args.port, max_workers=args.max_workers)

    def signal_handler(sig, frame):
        logging.info("Server shutting down...")
        server.stop()
        sys.exit(0)

    import signal
    signal.signal(signal.SIGINT, signal_handler)

    server.start()
