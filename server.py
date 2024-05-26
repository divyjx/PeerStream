import socket
import threading
import pickle
import sys
import base64
import os
import cv2

MAX_CLIENTS = 5
SERVER_HOST = '127.0.0.1'
SERVER_PORT = 12346 if len(sys.argv) == 1 else int(sys.argv[1])
BUFFER_SIZE = 4096

Commands = ["ADD","PLAY","LIST","QUIT","MESSAGE","STOP"]

# SERVER SIDE DICTIONARY FOR STORING KEYS
client_keys = {}

video_files = {}
client_sockets = {}
client_streams = {}
client_messages = {}

def create_dump(messageType, entity, payload):
    """
    Creates pickle dumps file with added length value in the front.
    Every message from server to client follows this pattern
    """
    if isinstance(payload, bytes):
        payload = base64.b64encode(payload).decode()
    data = {
        "message": messageType,
        "entity": entity,
        "payload": payload
    }
    pickled_data = pickle.dumps(data, pickle.HIGHEST_PROTOCOL)
    data_length = len(pickled_data)
    length_bytes = data_length.to_bytes(4, byteorder='big')
    return length_bytes + pickled_data

def parse_message(pickle_dump, client_socket, clinet_name):
    """
    This Funtions parses request dump files from client and return response dump files 
    """
    length_bytes = pickle_dump[:4]
    data_length = int.from_bytes(length_bytes, byteorder='big')  
    pickled_data = pickle.loads(pickle_dump[4:4+data_length])

    is_add = False
    messageType = pickled_data['message']
    entity = pickled_data['entity']
    payload = pickled_data['payload']

    if messageType in Commands:
        if messageType == "ADD":
            """
            receives    - message, name
            returns     - "ADDED", name, client_keys 
                        | "NO", "", ""
            """
            name = entity
            key = payload
            if name in client_keys.keys():
                return create_dump("NO", "", ""), is_add
            else:
                broadcast(name, key, client_socket, name)
                is_add = True
                return create_dump("ADDED", name, client_keys), name
        
        elif messageType == "LIST":
            """
            receives    - "LIST"
            returns     - "LISTED", "", payload(video_files)
            """
            return create_dump("LISTED", "", video_files), is_add
        
        elif messageType == "PLAY":
            """
            receives    - "PLAY", "", video_name
            returns     - "STREAMSTART", "", "starting meta data"
                        | "STREAMFRAME", frame_number, frame
                        | "STREAMEND", "", "No Video" 
            """
            if payload in list(video_files.keys()):
                stream_data(clinet_name, payload, client_socket)
                return create_dump("STREAMEND", "", "Video Streaming Done"), is_add
            else:
                return create_dump("STREAMEND", "", "Video Not Available"), is_add

        elif messageType == "QUIT":
            """
            receives    - "QUIT", client_name, ""
            returns     - "QUIT", "", ""
            """
            broadcast(entity, "",client_socket, clinet_name, is_quit=True)
            return create_dump("QUIT", "", ""), is_add
        
        elif messageType == "MESSAGE":
            """
            receives    - "MESSAGE", reciever, message_text
            returns     - "SENT", "", server_response
            """
            if entity in client_keys.keys():
                data = create_dump("MESSAGE", entity, payload)
                broadcast(data, "", "", clinet_name, is_message = True)
                return create_dump("SENT", "", "Message Sent"), is_add
            return create_dump("SENT", "", "Client Not Available"), is_add 
        
        elif messageType == "STOP":
            """
            receives    - "STOP" 
            returns     - "STOP" , message
            """
            client_streams[clinet_name] = False
            return create_dump("STOP", "", "Not Streaming / Stopped Streaming"), is_add
        
    return create_dump("INVALID", "", ""), is_add


def broadcast(name, pubkey, client_socket:socket.socket, client_name, is_quit = False, is_message = False):
    """
    This funtion handle broadcasting messages, actions like ADD, QUIT, and MESSAGE
    """
    message = ""
    if is_quit:
            if name in client_keys.keys():
                del client_keys[name]
                del client_sockets[name]
                del client_streams[name]
                del client_messages[name]
                message = create_dump ("POP", name, "")
            else: 
                return
    elif is_message:
        message = name  
    else: 
        client_keys[name] = pubkey
        client_sockets[name] = client_socket
        client_streams[name] = False
        client_messages[name] = []
        message = create_dump("ADD", name, pubkey) 
    
    for bname, sock in client_sockets.items():
        """
        For streaming clients, add messages in broadcast list
        For others, send messages to their respective sockets
        """
        if bname!=client_name:
            if (client_streams[bname]):
                client_messages[bname].append(message)
                continue
            try:
                sock.sendall(message)
            except Exception as e:
                print("ERROR:", e)

def stream_data(client_name, video, client_socket:socket.socket):
    """
    Stream Data Tasks     
        STREAMSTART, metadata
        STREAMFAME, frame_no, frame
        (Optional) fetch message from socket - (STOP, other) 
        (Optional) send broadcast messages from message list 
        STREAMEND        
    """
    client_streams[client_name] = True
    resolutions = video_files[video]
    video = video.split('.')[0] # get name

    number_of_frames, frame_sizes = get_frames(video, resolutions)
    frames_per_res = number_of_frames // len(resolutions)

    # create streamstart
    client_socket.sendall(create_dump("STREAMSTART", "", [frames_per_res, frame_sizes]))

    done = False
    for i, resolution in enumerate(resolutions):
        curr_frames = 0
        video_file_path = f"video/{video}_{resolution}p.mp4"
        vid = cv2.VideoCapture(video_file_path)
        vid.set(1, i* frames_per_res)
        while curr_frames < frames_per_res:
            success, frame = vid.read() 
            if (not success):
                client_socket.sendall (create_dump("STREAMEND", "", "SERVER ERROR"))
                done = True
                break
            client_socket.sendall(create_dump("STREAMFRAME", curr_frames, frame))
            curr_frames += 1

            """
            Every 20th frame checks for clients messages 
            """
            if curr_frames%20 == 0:
                client_socket.settimeout(0.1)
                while True:
                    try:
                        data = client_socket.recv(BUFFER_SIZE)
                        if not data:
                            break
                        response, is_add= parse_message(data, client_socket, client_name)
                        client_socket.sendall(response)
                    except(KeyboardInterrupt, ConnectionResetError):
                        done = True
                        break
                    except socket.timeout:
                        break
                client_socket.settimeout(None)
                if not client_streams[client_name]:
                    done = True
            if done:
                break
        if done:
            break
    """
    Empty broadcast buffer before closing Stream
    """
    client_streams[client_name] = False
    for bmessage in client_messages[client_name]:
        client_socket.sendall(bmessage)
    client_messages[client_name].clear()
    return

def get_frames(video, resolutions):
    """
    fetches frames and other details for a video file
    """
    length = 0
    frame_lengths = []
    for resolution in resolutions:
        video_file_path = f"video/{video}_{resolution}p.mp4"
        cap = cv2.VideoCapture(video_file_path)
        property_id = int(cv2.CAP_PROP_FRAME_COUNT)
        length = int(cv2.VideoCapture.get(cap, property_id))
        status, frame = cap.read()
        frame_len = len(frame.reshape(-1))
        frame_lengths.append(frame_len)
    return length, frame_lengths
            
def convert_to_video_files(directory):
    """
    Used to parse "video" directory 
    """
    file_list = os.listdir(directory)
    video_files = {}
    for filename in file_list:
        base_name, ext = os.path.splitext(filename)  
        video_name, resolution = base_name.rsplit('_', 1)  
        resolution = resolution[:-1]
        resolution = int(resolution)
        video_files.setdefault(video_name + ext, []).append(resolution)
    
    for video_name in video_files:
        video_files[video_name] = sorted(video_files[video_name])
    return video_files

def handle_client(client_socket, client_address):
    """
    Thread function created for every client for handling requests
    """
    print(f"New connection from {client_address}")
    client_name = ""
    while True:
        try:
            data = client_socket.recv(BUFFER_SIZE)
            if not data:
                break
            response, is_add= parse_message(data, client_socket, client_name)
            if is_add:
                client_name+=is_add
            client_socket.sendall(response)
        except KeyboardInterrupt:
            break
        except ConnectionResetError:
            break
    print(f"Connection with {client_address} closed.")
    parse_message(create_dump("QUIT", client_name, ""), client_socket, client_name)
    client_socket.close()

def start_server(host, port):
    """
    Main TCP listening socket, accepts new client request and creates a new thread for them.
    """
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen(MAX_CLIENTS)
    global video_files
    video_files = convert_to_video_files("video")
    print(f"Server listening on {host}:{port}")

    while True:
        try: 
            client_socket, client_address = server_socket.accept()
            client_thread = threading.Thread(target=handle_client, args=(client_socket, client_address), daemon=True)
            client_thread.start()
        except KeyboardInterrupt:
            print("Closing Server")
            server_socket.close()
            exit(0)
if __name__ == "__main__":
    start_server(SERVER_HOST, SERVER_PORT)
