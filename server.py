import socket
import threading


connected_clients = []

def connect_client(client_request):
    while True:
        try:
            message = client_request.recv(1024).decode('utf-8')
            if message:
                print(f"Received: {message}")
                broadcast(message, client_request)
        except:
            connected_clients.remove(client_request)
            client_request.close()
            break

def broadcast(message, current_socket):
    for client in connected_clients:
        if client != current_socket:
            client.send(message.encode('utf-8'))

## TO MAKE THE SERVER WITH PORT NO 
SERVER_NAME = 'localhost'
SERVER_PORT = 5777


## START LISTENING TO SERVER
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((SERVER_NAME, SERVER_PORT))
server.listen()

print(f"Server listening on {SERVER_NAME}:{SERVER_PORT}")

while True:
    client_request, client_address = server.accept()
    print(f"Connection from {client_address}")
    connected_clients.append(client_request)
    thread = threading.Thread(target=connect_client, args=(client_request,))
    thread.start()
