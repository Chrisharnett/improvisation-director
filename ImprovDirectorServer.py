import asyncio
import websockets
import ssl
from messageFilter import messageFilter
import json
import uuid
from objects.Performer import Performer
import traceback
from objects.Room import Room
from directorPrompts.directorPrompts import getWelcomeMessage
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

connectedClients = []
currentRooms = {}

 # Add a connected message from the server
async def handle_connection(websocket, path):
    currentClient = Performer(websocket)
    connectedClients.append(currentClient)
    joinLobby(currentClient)

    print("Connection")
    message = getWelcomeMessage()
    await broadcast_message(message, 'lobby')

    try:
        while True:
            incomingMessage = await websocket.recv()
            message = json.loads(incomingMessage)
            print(f"Received message from client: {message}")
            response = messageFilter(message, currentClient, currentRooms)

            roomName = response.get('roomName') or 'lobby'
            userIds = response.get('userId')
            feedback = response.get('feedbackQuestion')

            if feedback:
                for question in feedback:
                    await send_to_specific_users({'feedbackQuestion': question}, roomName, question.get('userId'))
                del response['feedbackQuestion']

            if userIds:
                await send_to_specific_users(response, roomName, userIds)
            else:
                await broadcast_message(response, roomName)

    except websockets.ConnectionClosed:
        handle_disconnection(currentClient)
        print("Connection closed")

    except Exception as e:
        print(f'Error: {str(e)}')
        traceback.print_exc()


def handle_disconnection(currentClient):
    for room in currentRooms:
        for performer in currentRooms[room].performers:
            if performer.userId == currentClient.userId:
                currentRooms[room].leaveRoom(currentClient)
    connectedClients.remove(currentClient)


async def broadcast_message(message, roomName):
    if roomName in currentRooms:
        clients = currentRooms[roomName].getClientConnections(connectedClients)
        if clients:
            await asyncio.gather(*[client.websocket.send(json.dumps(message)) for client in clients])
            print(f"Broadcasted message to room {roomName}")


async def send_to_specific_users(message, roomName, userIds):
    if not isinstance(userIds, list):
        userIds = [userIds]
    if roomName in currentRooms:
        clients = currentRooms[roomName].getClientConnections(connectedClients)
        for client in clients:
            if client.userId in userIds:
                await client.websocket.send(json.dumps(message))
                print(f"Sent message to user {client.userId} in room {roomName}")

def generateUserId():
    return str(uuid.uuid4())

def joinLobby(currentClient):
    if not currentRooms.get('lobby'):
        currentRooms['lobby'] = Room('lobby')
        currentRooms['lobby'].addPlayerToRoom(currentClient)
    else:
        currentRooms['lobby'].addPlayerToRoom(currentClient)

async def main():
    # ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    # ssl_context.load_cert_chain(certfile='CERT/cert.pem', keyfile='CERT/key.pem')

    async with websockets.serve(handle_connection, "0.0.0.0", 8765):
    # async with websockets.serve(handle_connection, "0.0.0.0", 8765, ssl=ssl_context):
    # async with websockets.serve(handle_connection, "localhost", 8765, ssl=ssl_context):

        print("WebSocket server started.")
    # print("WebSocket server started on wss://localhost:8765")

    # print("WebSocket server started on wss://localhost:8765")
        await asyncio.Future()

# Simple HTTP server for health checks
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

def run_http_server():
    server_address = ('', 80)  # Listen on port 80 for health checks
    httpd = HTTPServer(server_address, HealthCheckHandler)
    print("Health check HTTP server started on port 80")
    httpd.serve_forever()


if __name__ == "__main__":
    http_thread = threading.Thread(target=run_http_server)
    http_thread.start()

    asyncio.run(main())
