import asyncio
import websockets
import json
from objects.Performer import Performer
from objects.Room import Room
from objects.MessageFilter import MessageFilter
import traceback
from objects.LLMQueryCreator import LLMQueryCreator
import http.server
import socketserver
import threading

class WebSocketServer:
    def __init__(self):
        self.connectedClients = {}
        self.currentRooms = {}
        self.pingInterval = 20
        self.pingTimeout = 0

    async def handleConnection(self, websocket, path):
        currentClient = None
        websocketId = str(websocket.id)  # Use websocket.id (UUID) as the identifier

        try:
            # Initialize the client immediately after the connection
            currentClient = Performer(websocket)

            if websocketId not in self.connectedClients:
                # Send a welcome message immediately upon connection
                queryCreator = LLMQueryCreator()
                roomName = "lobby"  # Assign the client to the lobby by default
                room = self.currentRooms.get(roomName) or Room(LLMQueryCreator=queryCreator, roomName=roomName)
                await room.addPlayerToRoom(currentClient)
                self.currentRooms[roomName] = room

                # Store the client in the connectedClients dictionary using websocket.id
                self.connectedClients[websocketId] = currentClient

                # print(f"Sent message to user {websocketId} in room {roomName}")
                # welcomeMessage = room.sayHello()
                # await room.sendMessageToUser({'action': 'welcome', 'message': welcomeMessage}, currentClient)

            filter = MessageFilter(currentClient, self.currentRooms, queryCreator)

            # Now we wait for any incoming messages from the client
            async for message in self.pingWebsocket(websocket):
                if message:
                    incomingMessage = json.loads(message)
                    print(f"Received message from {incomingMessage.get('currentPlayer').get('screenName') or websocketId}. MESSAGE: {incomingMessage}")
                    roomName = incomingMessage.get("roomName", "lobby")
                    currentRoom = self.currentRooms.get(roomName)
                    userId = incomingMessage.get('userId')
                    if userId:
                        currentClient.userId = userId
                    if currentRoom:
                        response = await filter.handleMessage(incomingMessage, currentRoom)
                        newRoomName = response.get('roomName')
                        if newRoomName:
                            currentRoom = self.currentRooms.get(newRoomName)
                        await currentRoom.handleResponse(response)
                    else:
                        await currentRoom.handleResponse({
                            'action': 'error',
                            'message': 'Room not found.',
                            'responseRequired': True,
                            'responseAction': 'joinRoom'
                        })

        except websockets.ConnectionClosedOK:
            print(f"Client {websocketId if currentClient else 'unknown'} disconnected normally (going away).")
        except websockets.ConnectionClosedError as e:
            print(f"Client {websocketId if currentClient else 'unknown'} disconnected unexpectedly: {str(e)}")
        except Exception as e:
            traceback.print_exc()
        finally:
            if currentClient:
                self.handleDisconnection(currentClient)

    async def pingWebsocket(self, websocket):
        try:
            while True:
                # pingMessage = json.dumps({'action': 'ping'})
                # await websocket.send(pingMessage)
                # await asyncio.sleep(self.pingInterval)
                try:
                    # incomingMessage = await asyncio.wait_for(websocket.recv(), timeout=self.pingTimeout)
                    incomingMessage = await websocket.recv()
                    data = json.loads(incomingMessage)

                    if data.get('action') == 'pong':
                        pass
                    else:
                        yield incomingMessage
                except asyncio.TimeoutError:
                    print(f"No pong received from client {websocket.id}, closing connection.")
                    raise websockets.ConnectionClosed(1001, "Ping timeout")
        except websockets.ConnectionClosed:
            yield None

    def handleDisconnection(self, client):
        # Use the websocket.id (UUID) to remove the client
        for room in self.currentRooms.values():
            room.leaveRoom(client)
        websocketId = str(client.websocket.id)  # Assuming client.websocket gives access to the WebSocket
        if websocketId in self.connectedClients:
            del self.connectedClients[websocketId]

    async def main(self):
        async with websockets.serve(self.handleConnection, "0.0.0.0", 8765):
            print("WebSocket server started.")
            await asyncio.Future()


class HealthCheckHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Respond with 200 OK
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Healthy")

def runHealthCheckServer():
    with socketserver.TCPServer(("", 8080), HealthCheckHandler) as httpd:
        print(f"Serving health check on port 8080")
        httpd.serve_forever()

if __name__ == "__main__":
    healthCheckThread = threading.Thread(target=runHealthCheckServer)
    healthCheckThread.daemon = True
    healthCheckThread.start()

    server = WebSocketServer()
    asyncio.run(server.main())
