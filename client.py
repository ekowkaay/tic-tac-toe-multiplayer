import socket

SERVER_HOST = 'localhost'
SERVER_PORT = 5777

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    client.connect((SERVER_HOST, SERVER_PORT))
    print(f"Connected to server {SERVER_HOST}:{SERVER_PORT}")
except socket.error as e:
    print(f"Error: {e}")


while True:
    message = input("Enter message: ")
    client.send(message.encode('utf-8'))
    response = client.recv(1024).decode('utf-8')
    print(f"Server: {response}")
