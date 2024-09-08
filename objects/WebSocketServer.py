import asyncio
import websockets
import json
from objects.Performer import Performer
from objects.Room import Room
# from directorPrompts.directorPrompts import getWelcomeMessage
# from messageFilter import messageFilter
from objects.MessageFilter import MessageFilter
import traceback
from objects.LLMQueryCreator import LLMQueryCreator

class WebSocketServer:
    def __init__(self):
        self.__connectedClients = []
        self.__currentRooms = {}

    @property
    def connectedClients(self):
        return self.__connectedClients

    @property
    def currentRooms(self):
        return self.__currentRooms

    async def handleConnection(self, websocket, path):
        currentClient = Performer(websocket)
        self.__connectedClients.append(currentClient)
        queryCreator = LLMQueryCreator()
        lobbyRoom = self.__currentRooms.get('lobby') or Room(LLMQueryCreator=queryCreator, roomName='lobby')
        await lobbyRoom.addPlayerToRoom(currentClient)
        self.__currentRooms['lobby'] = lobbyRoom

        print("Connection")
        message = lobbyRoom.sayHello()
        await lobbyRoom.sendMessageToUser({'action': 'welcome', 'message': message}, currentClient)
        filter = MessageFilter(currentClient, self.__currentRooms, queryCreator)

        try:
            while True:
                incomingMessage = await websocket.recv()
                message = json.loads(incomingMessage)
                print(f"Received message from client: {message}")
                currentRoomName = message.get('roomName', 'lobby')
                if currentRoomName in self.__currentRooms or currentRoomName == 'lobby':
                    currentRoom = self.__currentRooms.get(currentRoomName)
                    response = await filter.handleMessage(message, currentRoom)
                    roomName = response.get('roomName')
                    if roomName:
                        currentRoomName = roomName
                        currentRoom = self.__currentRooms[currentRoomName]
                    await currentRoom.handleResponse(response)
                else:
                    await lobbyRoom.handleResponse({
                    'action': 'registration',
                    'userId': [currentClient.userId],
                    'clients': [currentClient],
                    'errorMessage': {'Registration Error': 'That room is not open. Log in to create a room or try again. '},
                    'message': 'Enter the room you would like to join.',
                    'responseRequired': True,
                    'responseAction': 'joinRoom'
                })
        except websockets.ConnectionClosed:
            self.handleDisconnection(currentClient)
            print("Connection closed")
        except Exception as e:
            print(f'Error: {str(e)}')
            traceback.print_exc()

    def handleDisconnection(self, client):
        for room in self.__currentRooms.values():
            room.leaveRoom(client)
        if client in self.__connectedClients:
            self.__connectedClients.remove(client)

    async def broadcastMessage(self, message, roomName):
        room = self.__currentRooms.get(roomName)
        if room:
            await room.broadcastMessage(message)

    async def main(self):
        async with websockets.serve(self.handleConnection, "0.0.0.0", 8765):
            print("WebSocket server started.")
            await asyncio.Future()


if __name__ == "__main__":
    server = WebSocketServer()
    asyncio.run(server.main())
