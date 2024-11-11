
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

### Server
- Handles multiple client connections using threading.
- Implements a JSON-based communication protocol.
- Logs connection events and errors.

### Client
- Connects to the server to send messages.
- Receives and displays responses from the server.
- Includes error handling for network issues.

### Installation
- Clone the Repository
```bash
git clone https://github.com/ekowkaay/tic-tac-toe-multiplayer.git
```

### Dependencies
This project uses only Python's standard library modules and does not require any external packages.

## Requirements File
The `requirements.txt` file is included to indicate that there are no external dependencies. It is empty because all the necessary modules are part of the Python standard library.

### Running the Server
```bash
python3 server.py --host <HOST> --port <PORT> --max-workers <MAX_WORKERS>
```
#### Example
```bash
python3 server.py --host 127.0.0.1 --port 65432 --max-workers 20
```

### Running the Client
```bash
python3 client.py --host <HOST> --port <PORT>
```
#### Example
```bash
python3 client.py --host 127.0.0.1 --port 65432
```

### Sending Messages
- Type a message and press Enter to send it to the server.
- The server will respond by echoing the message back with a prefix "Echo: ".
- Type `exit` to disconnect from the server.

### Testing
```bash
python3 test_multiple_clients.py
```

## Game Message Protocol Specification

### Message Format
All messages between the client and server are in JSON format. Each message consists of a "type" field indicating the message type and a "data" field containing message-specific information.

```json
{
    "type": "message_type",
    "data": {
        // message-specific data fields
    }
}
```
- `type`: (string) Indicates the type of the message (e.g., "join", "move", "chat", "quit", "error").
- `data`: (object) Contains message-specific data fields relevant to the message type.

### Message Types

1. **Join ("join")**
   - **Purpose**: Client requests to join a game.
   - **Client to Server Data Fields**:
     - `username`: (string) The player's username.
   - **Example**:
     ```json
     {
         "type": "join",
         "data": {
             "username": "Player1"
         }
     }
     ```
   - **Server Response: Join Acknowledgment ("join_ack")**
     - **Data Fields**:
       - `status`: (string) "success" if the game starts, "waiting" if waiting for an opponent.
       - `game_id`: (string) Unique game identifier (when status is "success").
       - `player_symbol`: (string) "X" or "O" (when status is "success").
       - `message`: (string) Informational message (when status is "waiting").
     - **Example (waiting)**:
       ```json
       {
           "type": "join_ack",
           "data": {
               "status": "waiting",
               "message": "Waiting for an opponent..."
           }
       }
       ```
     - **Example (success)**:
       ```json
       {
           "type": "join_ack",
           "data": {
               "status": "success",
               "game_id": "game12345",
               "player_symbol": "X"
           }
       }
       ```

2. **Move ("move")**
   - **Purpose**: Client makes a move on the game board.
   - **Client to Server Data Fields**:
     - `game_id`: (string) The game session identifier.
     - `position`: (list of integers) [row, column] indices of the move (0-based index).
   - **Example**:
     ```json
     {
         "type": "move",
         "data": {
             "game_id": "game12345",
             "position": [0, 1]
         }
     }
     ```
   - **Server Response: Move Acknowledgment ("move_ack")**
     - **Data Fields**:
       - `status`: (string) "success" or "failure".
       - `game_state`: (list of lists) The updated game board.
       - `next_player`: (string) Username of the next player.
       - `winner`: (string or null) Username of the winner, "draw" if the game is a draw, or null if the game is ongoing.
     - **Example**:
       ```json
       {
           "type": "move_ack",
           "data": {
               "status": "success",
               "game_state": [
                   ["X", "", "O"],
                   ["", "X", ""],
                   ["", "", ""]
               ],
               "next_player": "Player2",
               "winner": null
           }
       }
       ```

3. **Chat ("chat")**
   - **Purpose**: Client sends a chat message to the other player.
   - **Client to Server Data Fields**:
     - `game_id`: (string) The game session identifier.
     - `message`: (string) The chat message content.
   - **Example**:
     ```json
     {
         "type": "chat",
         "data": {
             "game_id": "game12345",
             "message": "Good luck!"
         }
     }
     ```
   - **Server Response: Chat Broadcast ("chat_broadcast")**
     - **Data Fields**:
       - `username`: (string) Sender's username.
       - `message`: (string) The chat message content.
     - **Example**:
       ```json
       {
           "type": "chat_broadcast",
           "data": {
               "username": "Player1",
               "message": "Good luck!"
           }
       }
       ```

4. **Quit ("quit")**
   - **Purpose**: Client requests to leave the game.
   - **Client to Server Data Fields**:
     - `game_id`: (string) The game session identifier.
   - **Example**:
     ```json
     {
         "type": "quit",
         "data": {
             "game_id": "game12345"
         }
     }
     ```
   - **Server Response: Quit Acknowledgment ("quit_ack")**
     - **Data Fields**:
       - `status`: (string) "success".
       - `message`: (string) Informational message.
     - **Example**:
       ```json
       {
           "type": "quit_ack",
           "data": {
               "status": "success",
               "message": "Player1 has left the game."
           }
       }
       ```

5. **Error ("error")**
   - **Purpose**: Server notifies the client of an error.
   - **Server to Client Data Fields**:
     - `code`: (string) Error code (e.g., "invalid_move", "not_your_turn", "unknown_type").
     - `message`: (string) Descriptive error message.
   - **Example**:
     ```json
     {
         "type": "error",
         "data": {
             "code": "invalid_move",
             "message": "Position already occupied."
         }
     }
     ```

6. **Start the server**
   ```bash
   python3 server.py --host 127.0.0.1 --port 65432 --max-workers 10
   ```
7. **Running Clients Manually:**
   ```bash
   python3 client.py --host 127.0.0.1 --port 65432 --username Player1
   ```

   ```bash
   python3 client.py --host 127.0.0.1 --port 65432 --username Player2
   ```
8. **Running the Test Script:**
    ```bash
    python3 test_tictactoe.py
    ```

## New Functionality

### Turn-Based Gameplay
- **Turn Management**: The server ensures that only the current player can make a move. If a player attempts to move out of turn, the server responds with an appropriate error message indicating that it is not their turn.
- **Simultaneous Moves Handling**: In cases where both players attempt to make a move simultaneously, the server processes moves in the order they are received, accepting the move from the player whose turn it is.
- **Game State Synchronization**: After each move, the server broadcasts the updated game state and the next player's turn to all connected clients. Clients update their local state to reflect the current game board.

### Game State Synchronization
- **Centralized Game State**: The server maintains the master game state and synchronizes it across all clients. Each time a player makes a valid move, the server updates the game state and broadcasts it to all connected clients, ensuring consistency.
- **Disconnection Handling**: The server tracks player connections. If a player disconnects mid-game, the server notifies the remaining player and closes the game gracefully.
- **Consistent Gameplay**: All players have a synchronized view of the game board, ensuring no discrepancies between client states.

### Client-Side Game Rendering
- **Real-Time Game Updates**: Clients dynamically render the game board based on updates received from the server. Each time the server broadcasts a new game state, the client redraws the board to reflect the latest moves.
- **Player Feedback**: The client provides clear messages to the player, such as indicating whose turn it is, notifying of any errors (e.g., "It is not your turn"), and displaying the game result (e.g., win, lose, or draw).
- **Game Progress Visualization**: The client displays the game board after each move, ensuring that players have a clear and consistent view of the current game state.

### Player Identification
- **Unique Identifiers**: Each player is assigned a unique identifier (UUID) upon connecting to the server, allowing the server to track players accurately throughout the game.
- **Usernames and Avatars**: Players can choose a username when connecting. If a username is not provided, the server assigns a default one. Players can also specify an avatar, adding a personal touch to their gameplay experience.

## How It Works
- The **server** handles player connections, game rules, turn management, and game state synchronization.
- The **clients** connect to the server, make moves, and render the game board based on server updates.

How to Play
Players take turns entering their move by specifying the row and column (e.g., 1,1 for the top-left corner).
The game ends when one player gets three in a row, column, or diagonal, or if all spaces are filled (draw).
```
Player X, enter your move (row,column): 1,1
Player O, enter your move (row,column): 2,2
```

Testing
To run the test scripts verifying the functionality:

```
python3 test_turn_based_gameplay.py
```

