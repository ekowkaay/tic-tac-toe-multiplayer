# Tic-Tac-Toe Multiplayer Game

## Overview
The goal of this project is to create a network-based multiplayer Tic-Tac-Toe game. The system will have a client-server architecture, in which player turns are managed by a central server that also broadcasts the game data to clients. The game will be played in turns by two players who will connect to the server as clients. Getting three marks (X or O) in a row, column, or diagonal is the aim of the game.

## How It Works
- The **server** handles player connections, game rules, and turn management.
- The **clients** connect to the server, make moves, and display the game board.

## Prerequisites
- Python 3.x

## Setup

### 1. Run the Server
Start the server by running:
```bash
python server.py
```
The server listens for two clients to connect and manages the game.

### 2. Run the Clients
On each client machine, run the client:
```bash
python client.py
```
Each client connects to the server, and the game begins once both clients are connected.

## How to Play
- Players take turns entering their move by specifying the row and column (e.g., `1 1` for the top-left corner).
- The game ends when one player gets three in a row, column, or diagonal, or if all spaces are filled (draw).

## Example
```bash
Player X, enter your move (row column): 1 1
Player O, enter your move (row column): 2 2
```

## TCP Client-Server Application
A simple TCP client-server application in Python that allows multiple clients to connect to a server concurrently, send messages, and receive responses.

### Server:

- Handles multiple client connections using threading.
- Implements a JSON-based communication protocol.
- Logs connection events and errors.

### Client:

- Connects to the server to send messages.
- Receives and displays responses from the server.
- Includes error handling for network issues.

### Installation
- Clone the Repository
```
git clone https://github.com/yourusername/tcp-client-server.git
```
### Install Dependencies
```
pip install -r requirements.txt
```
### Running the Server
```
python3 server.py --host <HOST> --port <PORT> --max-workers <MAX_WORKERS>
Example
python3 server.py --host 127.0.0.1 --port 65432 --max-workers 20
```
### Running the Client
```
python3 client.py --host <HOST> --port <PORT>
```

### Sending Messages
- Type a message and press Enter to send it to the server.
- The server will respond by echoing the message back with a prefix "Echo: ".
- Type exit to disconnect from the server.

### Testing
```
python3 test_multiple_clients.py
```
