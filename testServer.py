import asyncio
import websockets
import ssl
from messageFilter import messageFilter
import json
import uuid
from objects.Performer import Performer
import traceback

connectedClients = []
currentRooms = {}

async def handle_connection(websocket, path):
    currentClient = Performer(websocket)
    connectedClients.append(currentClient)

    print("Connection")
    try:
        while True:
            incomingMessage = await websocket.recv()
            message = json.loads(incomingMessage)
            print(f"Received message from client: {message}")
            response = messageFilter(message, currentClient, currentRooms)

            roomName = response.get('roomName')
            userIds = response.get('userId')
            feedback = response.get('feedbackQuestion')

            if feedback:
                for question in feedback:
                    # feedbackResponse = {'roomName': roomName,
                    #                     'feedbackType': question.get('feedbackType'),
                    #                     'feedbackQuestion': question}
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


async def main():
    # ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    # ssl_context.load_cert_chain(certfile='CERT/cert.pem', keyfile='CERT/key.pem')

    async with websockets.serve(handle_connection, "0.0.0.0", 8765):

    # async with websockets.serve(handle_connection, "0.0.0.0", 8765, ssl=ssl_context):
    # async with websockets.serve(handle_connection, "localhost", 8765, ssl=ssl_context):

        print("")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
