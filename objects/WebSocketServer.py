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
from util.awsSecretRetrieval import origins

class WebSocketServer:
    def __init__(self):
        self.connectedClients = {}
        self.currentRooms = {}
        self.pingInterval = 20
        self.previousSessions = {}

    async def handleConnection(self, websocket, path):
        origin = websocket.request_headers.get("Origin")
        allowedOrigins = origins()
        if origin not in allowedOrigins:
            await websocket.close(code=4000, reason="Origin not allowed")
            return
        # currentClient = None
        websocketId = str(websocket.id)
        currentClient = Performer(websocket)

        queryCreator = LLMQueryCreator()
        roomName = "lobby"
        room = self.currentRooms.get(roomName) or Room(LLMQueryCreator=queryCreator, roomName=roomName)
        await room.addPlayerToRoom(currentClient)
        self.currentRooms[roomName] = room
        print(f"🔄 New connection assigned to the lobby.")

        self.connectedClients[websocketId] = currentClient
        filter = MessageFilter(currentClient, self.currentRooms, self.currentRooms['lobby'].LLMQueryCreator)

        try:
            # if websocketId not in self.connectedClients:
            #     # Send a welcome message immediately upon connection
            #     queryCreator = LLMQueryCreator()
            #     roomName = "lobby"  # Assign the client to the lobby by default
            #     room = self.currentRooms.get(roomName) or Room(LLMQueryCreator=queryCreator, roomName=roomName)
            #     await room.addPlayerToRoom(currentClient)
            #     self.currentRooms[roomName] = room

            # Now we wait for any incoming messages from the client
            async for message in websocket:
                if message:
                    currentRoom=None
                    try:
                        incomingMessage = json.loads(message)
                        print(f"Incoming Message: {incomingMessage.get('action')}")
                        currentPlayer = incomingMessage.get('currentPlayer', None)
                        roomName = incomingMessage.get("roomName", "lobby")
                        action = incomingMessage.get('action')
                        currentRoom = self.currentRooms.get(roomName)
                        if not currentRoom and action != "rejoinRoom":
                            response =  {
                                'action': 'invalid room name',
                                'userId': [currentClient.userId],
                                'clients': [currentClient],
                                'message': "Enter the room you would like to join.",
                                'responseRequired': "joinRoom",
                                'responseAction': 'joinRoom'
                            }
                            await self.currentRooms['lobby'].handleResponse(response)

                        if currentPlayer == 'audience':
                            print(f"Audience message received")
                            response = await filter.handleMessage(incomingMessage, currentRoom)
                            await currentRoom.handleResponse(response)
                        if action == "rejoinRoom":
                            userId = currentPlayer.get('userId', None)
                            previousRoomName = self.previousSessions.get(userId)
                            print(f"Rejoin Room: {currentPlayer.get('screenName', 'AUDIENCE')}")
                            if previousRoomName and previousRoomName in self.currentRooms:
                                room = self.currentRooms[previousRoomName]
                                await room.playerRejoinRoom(currentClient, currentPlayer)
                                print(f"✅ Reconnected to room: {previousRoomName}")
                                response = room.prepareGameStateResponse("rejoinRoom")
                                await room.handleResponse(response)
                        else:
                            screenName = currentPlayer.get('screenName') if currentPlayer else websocketId
                            print(f"{screenName}. MESSAGE: {incomingMessage}")
                            if currentPlayer:
                                userId = currentPlayer.get('userId')
                                if userId:
                                    currentClient.userId = userId
                            if currentRoom:
                                response = await filter.handleMessage(incomingMessage, currentRoom)
                                currentGameState = response.get('gameState')
                                if currentGameState:
                                    newRoomName = currentGameState.get('roomName')
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
                    except Exception as e:
                        traceback.print_exc()
                        response = currentRoom.prepareGameStateResponse('error')
                        await currentRoom.broadcastMessage(response)
                        continue

        except websockets.ConnectionClosedOK:
            print(f"Client {websocketId if currentClient else 'unknown'} disconnected normally (going away).")
        except websockets.ConnectionClosedError as e:
            print(f"Client {websocketId if currentClient else 'unknown'} disconnected unexpectedly: {str(e)}")
        except Exception as e:
            traceback.print_exc()
        finally:
            if currentClient:
                self.handleDisconnection(currentClient)

    # async def sendPeriodicGameState(self, client):
    #     try:
    #         while True:
    #             await asyncio.sleep(self.pingInterval)
    #             currentRoom = client.currentRoom
    #             if currentRoom and (len(currentRoom.performers) > 0) and currentRoom.improvisation:
    #                 response = currentRoom.prepareGameStateResponse('heartbeat')
    #                 await currentRoom.broadcastMessage(response)
    #     except websockets.ConnectionClosed:
    #         print(f"WebSocket {client.websocket.id} closed during periodic gameState updates.")

    def handleDisconnection(self, client):
        for room in self.currentRooms.values():
            if room.roomName != "lobby":
                userId = client.userId
                if client in room.performers:
                    # ✅ Store user's last known room before removing them
                    self.previousSessions[userId] = room.roomName
                    room.leaveRoom(client)

        websocketId = str(client.websocket.id)
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
