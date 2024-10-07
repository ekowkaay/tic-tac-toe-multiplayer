import unittest
import threading
import time
import logging
from client import Client
from server import Server
import socket
import json

class TestServerClientCommunication(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start the server
        cls.server = Server(host='127.0.0.1', port=65432, max_workers=20)
        cls.server_thread = threading.Thread(target=cls.server.start)
        cls.server_thread.daemon = True
        cls.server_thread.start()
        time.sleep(1)

    @classmethod
    def tearDownClass(cls):
        # Stop the server
        cls.server.stop()
        cls.server_thread.join()

    def test_multiple_clients(self):
        num_clients = 5
        threads = []

        def client_task(client_id):
            client = Client(host='127.0.0.1', port=65432)
            connected = client.connect()
            self.assertTrue(connected, f"Client {client_id} failed to connect")
            client.send_message(f"Hello from client {client_id}")
            client.disconnect()

        for i in range(num_clients):
            t = threading.Thread(target=client_task, args=(i,))
            t.start()
            threads.append(t)
            time.sleep(0.1) 

        for t in threads:
            t.join()

    def test_message_exchange(self):
        client = Client(host='127.0.0.1', port=65432)
        connected = client.connect()
        self.assertTrue(connected, "Client failed to connect")
        test_message = "Test Message"
        response = client.send_message(test_message)
        self.assertEqual(response, f"Echo: {test_message}", "Response does not match expected echo")
        client.disconnect()

    def test_connection_failure(self):
        client = Client(host='127.0.0.1', port=9999)
        connected = client.connect()
        self.assertFalse(connected, "Client should not connect to an incorrect port")

    def test_invalid_message(self):
        client = Client(host='127.0.0.1', port=65432)
        connected = client.connect()
        self.assertTrue(connected, "Client failed to connect")

        try:
            client.client_socket.sendall(b"This is not JSON")
            response = client.client_socket.recv(1024).decode('utf-8')
            data = json.loads(response)
            self.assertEqual(data['type'], 'error', "Server should respond with an error for invalid JSON")
        except json.JSONDecodeError:
            self.fail("Server response is not valid JSON")
        except Exception as e:
            self.fail(f"Test failed with exception: {e}")
        finally:
            client.disconnect()

    def test_client_disconnection(self):
        client = Client(host='127.0.0.1', port=65432)
        connected = client.connect()
        self.assertTrue(connected, "Client failed to connect")

        client.client_socket.close()
        time.sleep(1)

        self.assertTrue(self.server.is_running, "Server should still be running after client disconnection")

    def test_server_under_load(self):
        num_clients = 50
        threads = []

        def client_task(client_id):
            client = Client(host='127.0.0.1', port=65432)
            if client.connect():
                client.send_message(f"Load Test Message {client_id}")
                client.disconnect()

        for i in range(num_clients):
            t = threading.Thread(target=client_task, args=(i,))
            t.start()
            threads.append(t)
            time.sleep(0.01) 

        for t in threads:
            t.join()

        self.assertTrue(self.server.is_running, "Server should still be running after load test")

if __name__ == '__main__':
    logging.basicConfig(level=logging.ERROR)
    unittest.main()
