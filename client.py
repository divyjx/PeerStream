import socket
import threading
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from time import sleep
import pickle
import sys
import base64
import cv2

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 12346 if len(sys.argv) == 1 else int(sys.argv[1])
BUFFER_SIZE = 4096

COMMANDS = ["PLAY", "LIST", "QUIT", "MESSAGE", "STOP"]

is_streaming = False
done = False

# CLIENT SIDE DICTIONARY FOR STORING KEYS
client_keys = {}


def modify_dict(name, pubkey, is_quit=False):
    """
    Maintains client side keys (dictionary)
    """
    if is_quit and name in client_keys.keys():
        client_keys.pop(name)
        print(f"Client Disconnected - {name}")
    else:
        client_keys[name] = pubkey
        print(f"Client Added - {name}")


received_data = bytearray()
def receive_pickled_objects(client_socket):
    """
    Generator function used to parse pickle dumps and send dictionary
    """
    global received_data
    try:
        while True:
            data = client_socket.recv(BUFFER_SIZE)
            if not data:
                break

            received_data.extend(data)
            while len(received_data) > 4:
                obj_length = int.from_bytes(received_data[:4], byteorder="big")
                if len(received_data) < 4 + obj_length:
                    break

                pickled_obj = received_data[4 : 4 + obj_length]
                obj = pickle.loads(pickled_obj)
                received_data = received_data[4 + obj_length :]
                yield obj
    except ConnectionResetError:
        print("server disconnected")
        client_socket.close()
        exit(0)
    except Exception as e:
        # print(e)
        exit(0)


def process_message(client_socket, decoder):
    """
    Gets message from 'receive_pickled_objects' function and processes them 
    """
    global is_streaming
    # Metadata about streaming

    try:
        for obj in receive_pickled_objects(client_socket):
            messageType = obj["message"]
            entity = obj["entity"]
            payload = obj["payload"]
            if messageType == "QUIT":
                break
            elif messageType == "ADD":
                modify_dict(entity, payload)
            elif messageType == "POP":
                modify_dict(entity, "", is_quit=True)
            elif messageType == "LISTED":
                print("Available Videos:")
                for name, res in payload.items():
                    print(name, "resolutions", *res)

            elif messageType == "PLAYED":
                print(payload)
            elif messageType == "STOP":
                # print(payload)
                pass
            elif messageType == "MESSAGE":
                try:
                    decoded_payload = base64.b64decode(payload)
                    message = decoder.decrypt(decoded_payload)
                    print("Message From a Client:", message.decode())
                except Exception as e:
                    # print("\nDecoder Failed\n", e)
                    pass
            elif messageType == "SENT":
                print("Message status:", payload)
            elif messageType.startswith("STREAM"):
                if messageType.endswith("START"):
                    is_streaming = True
                    print("Streaming Starting ...")

                elif messageType.endswith("FRAME"):
                    cv2.imshow(
                        "VIDEO",
                        cv2.resize(payload, (1240, 720), interpolation=cv2.INTER_AREA),
                    )
                    cv2.waitKey(25) & 0xFF

                elif messageType.endswith("END"):
                    cv2.destroyAllWindows()
                    is_streaming = False
                    print("Streaming Ended :", payload)

    except KeyboardInterrupt:
        print("Closing Receiver")
        client_socket.close()
        exit(0)


def pick_action():
    """
    Used by client to choose valid and available action
    """
    message = input("Enter Command: \n").strip()
    if message == "":
        return "Invalid", None
    if is_streaming and message not in ["STOP", "QUIT"]:
        print("Streaming Mode Active: Valid Commands STOP or QUIT")
        return "Invalid", None
    command = message.split()[0]
    command = command.upper()
    if command in COMMANDS:
        if command == "PLAY" and len(message.split()) == 2:
            return command, message.split()[1]
        elif command != "PLAY":
            return command, None
    return "Invalid", None


def pick_client():
    """
    helps in picking a messaging client from list of available clients
    """
    print("Available clients:", *client_keys.keys())
    recv_client = input("Select Client :\n").strip().split()[0]
    if recv_client not in client_keys.keys():
        return 0, "0"
    else:
        return recv_client, client_keys[recv_client]


def create_dump(messageType, entity, payload):
    """
    Creates pickle dumps file with added length value in the front.
    Every message from server to client follows this pattern
    """ 
    if isinstance(payload, bytes):
        payload = base64.b64encode(payload).decode()
    data = {"message": messageType, "entity": entity, "payload": payload}
    pickled_data = pickle.dumps(data, pickle.HIGHEST_PROTOCOL)
    data_length = len(pickled_data)
    length_bytes = data_length.to_bytes(4, byteorder="big")
    return length_bytes + pickled_data


def simulate(client_socket: socket.socket):
    """
    main client function for reciving input commands and sending messages to server.
    """
    print("Available Actions", COMMANDS)
    while True:
        try:
            action, video = pick_action()
            message = ""
            if action == "QUIT":
                client_socket.sendall(create_dump("QUIT", client_name, ""))
                break
            elif action == "MESSAGE":
                if len(client_keys) == 0:
                    print("No one is Online")
                    continue
                else:
                    recv_client, recv_key = pick_client()
                    if recv_client == client_name:
                        print("Can't massage to self")
                        continue
                    elif recv_key != "0":
                        try:
                            message_data = input("Enter your message: \n")
                            message = create_dump(
                                "MESSAGE",
                                client_name,
                                encode_message(recv_client, message_data),
                            )
                        except Exception:
                            print("Client not available")
                            continue
                    else:
                        print("Client not available")
                        continue

            elif action == "LIST":
                message = create_dump("LIST", "", "")

            elif action == "PLAY":
                if is_streaming:
                    print("Already playing")
                    continue
                message = create_dump("PLAY", "", video)

            elif action == "STOP":
                message = create_dump("STOP", "", "")
            else:
                print("Invalid Action")
                print("Available Actions", COMMANDS)
                continue
            client_socket.sendall(message)

            sleep(1)
        except (KeyboardInterrupt, ConnectionResetError):
            break
    client_socket.close()
    print("Connection Closed")


def encode_message(client_name, data):
    """
    Message encryption
    """
    data = data.encode()
    client_key = client_keys[client_name]
    client_key_decoded = base64.b64decode(client_key.encode())
    encoder = PKCS1_OAEP.new(RSA.import_key(client_key_decoded))
    data = encoder.encrypt(data)
    return data


def start_client(host, port):
    """
    Name resolution in client side, genrating keys , and getting peers keys.
    It creates a send thread for sending messages after connection
    and calls handle_messages funtion 
    """
    global client_name
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((host, port))

    pub, decoder = set_encryption()

    while True:
        client_name = input("Enter your name: ").strip().split()[0]
        if client_name == "":
            print("Name must be non empty")
            continue
        message = create_dump("ADD", client_name, pub)
        client_socket.sendall(message)
        response = client_socket.recv(BUFFER_SIZE)

        length_bytes = response[:4]
        data_length = int.from_bytes(length_bytes, byteorder="big")
        pickled_data = pickle.loads(response[4 : 4 + data_length])
        if pickled_data["message"] == "ADDED":
            print(f"Accepted Name : {client_name}")
            global client_keys
            client_keys = pickled_data["payload"]
            if client_name in client_keys.keys():
                del client_keys[client_name]
            break
        else:
            print("Name already used")

    send_thread = threading.Thread(target=simulate, args=(client_socket,), daemon=True)
    send_thread.start()
    process_message(client_socket, decoder)
    send_thread.join()
    
    client_socket.close()


def set_encryption():
    key = RSA.generate(1024)
    private_key = key.export_key()
    public_key = key.publickey().export_key()
    decoder_cypher = PKCS1_OAEP.new(RSA.import_key(private_key))
    return public_key, decoder_cypher


if __name__ == "__main__":
    start_client(SERVER_HOST, SERVER_PORT)
