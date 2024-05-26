# PeerStream
A video streaming and messaging network application. A course project for Computer Networks CS348.

Demo - https://drive.google.com/file/d/1jm953LuuoOqsXZkzscytyf-FOzPuoXFj/view?usp=sharing

## Problem Statement
Design and implement a socket programming system where a server manages client connections, maintains a dictionary mapping client names to public keys and facilitates secure communication and video streaming among clients. The system should allow clients to communicate with each other through the server securely, notify existing clients of new connections, and enable secure one-to-one communication by requesting public keys from the server for encryption. Additionally, the server should stream a video file requested by a client without actually saving the file at the client’s end.

# Setup

Install the requirements/dependencies (python 3.10).
``` 
pip install pycryptodome opencv-python
```

To start server and client 
```
python 210010015_server.py
python 210010015_client.py
```
For storing videos maintain a directory "video" in which video with diffrent resolutions are stored as "video_resolution.mp4". For example Video1_480p.mp4, dog_240p.mp4 etc.

# Interface

Server side terminal is only used for displaying connection messages.

Client can use the following actions.

| Action    | Description                                                                                                     |
|-----------|-----------------------------------------------------------------------------------------------------------------|
| LIST      | This command returns the video names along with their resolutions.                                              |
| PLAY      | This command requests the server to play the specified video file. If the file is present, client enters streaming mode and playback begins. |
| QUIT      | For closing the connection.                                                                                     |
| STOP      | For stopping the video if it is already streaming. Note that the video may not stop immediately.                |
| MESSAGE   | As the client enters the "MESSAGE" command, a list of client names is displayed. The client then types the client name in the terminal. 
|           | If the name is valid, the client is then requested to type a message (terminating by newline). |


# Functions

## Client

| Function Name          | Description                                                                                       |
|------------------------|---------------------------------------------------------------------------------------------------|
| modify_dict            | Maintains client side keys (dictionary).                                                          |
| receive_pickled_objects| Generator function used to parse pickle dumps and send dictionary.                                |
| process_message        | Gets message from 'receive_pickled_objects' function and processes them.                          |
| pick_action            | Used by client to choose valid and available action.                                              |
| pick_client            | Helps in picking a messaging client from list of available clients.                               |
| create_dump            | Creates pickle dumps file with added length value in the front. Every message from server to client follows this pattern.|
| simulate               | Main client function for receiving input commands and sending messages to server.                 |
| encode_message         | Message encryption.                                                                               |
| start_client           | It creates a send thread for sending messages after connection and calls handle_messages function.|
| set_encryption         | Sets up encryption using RSA algorithm.                                                           |

## Server 

| Function Name          | Description                                                                                |
|------------------------|--------------------------------------------------------------------------------------------|
| create_dump            | Creates pickle dumps file with added length value in the front.                            |
| parse_message          | Parses request dump files from the client and returns response dump files.                 |
| broadcast              | Handles broadcasting messages, actions like ADD, QUIT, and MESSAGE.                        |
| stream_data            | Handles streaming tasks including STREAMSTART, STREAMFRAME, and  STREAMEND.                |
| get_frames             | Fetches frames and other details for a video file.                                         |
| convert_to_video_files | Used to parse the "video" directory.                                                       |
| handle_client          | Thread function created for every client for handling requests.                            |
| start_server           | Main TCP listening socket, accepts new client requests, and creates a new thread for them. |


# Threads 
```
server
|--- main (accepts clients)
||-- client 1 (handle requests)
||-- client 2
||-- client 3
|| .
|| .
|| .

client
|--- main(sets name, key etc) -- converted to recv later 
||-- send (for sending messages)
```

# Demo

Follow the steps in given numerical order (on respective terminal) or watch the video 

### Terminal 1  
1 | python 210010015_server.py

### Terminal 2
2  | python 210010015_client.py   
3  | client1   
4  | LIST  
5  | MESSAGE    
15 |  QUIT  

### Terminal 3
6  | python 210010015_client.py  
7  | client2  
10 | MESSAGE  
11 | client1   
12 | Hi, I am client2  

### Terminal 4
8  | python 210010015_client.py  
9  | client3  
13 |  PLAY video.mp4  
14 |  STOP  

