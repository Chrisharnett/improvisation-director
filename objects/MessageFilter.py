from objects.Room import Room
from util.Dynamo.logTableClient import LogTableClient
from util.Dynamo.connections import getDynamoDbConnection


class MessageFilter:
    def __init__(self, currentClient, currentRooms, queryCreator, broadcastHandler=None):
        self.__query = queryCreator
        self.__currentClient = currentClient
        self.__currentRooms = currentRooms
        self.__broadcastHandler = broadcastHandler
        self.__currentRoom = None
        self.__currentRoomName = None

    # Property for currentClient
    @property
    def currentClient(self):
        return self.__currentClient

    @currentClient.setter
    def currentClient(self, value):
        self.__currentClient = value

    # Property for currentRoom
    @property
    def currentRoom(self):
        return self.__currentRoom

    @currentRoom.setter
    def currentRoom(self, value):
        self.__currentRoom = value

    # Property for currentRoomName
    @property
    def currentRoomName(self):
        return self.__currentRoomName

    @currentRoomName.setter
    def currentRoomName(self, value):
        self.__currentRoomName = value

    # Property for broadcastHandler
    @property
    def broadcastHandler(self):
        return self.__broadcastHandler

    @broadcastHandler.setter
    def broadcastHandler(self, value):
        self.__broadcastHandler = value

    # Method to handle room changes
    def updateRoom(self, newRoom):
        """Update the current room and its broadcastHandler and queryConnector."""
        self.__currentRoom = newRoom
        self.__broadcastHandler = newRoom.broadcastMessage
        newRoom.LLMQueryCreator = self.__query

    # Main message handler, room is passed dynamically
    async def handleMessage(self, message, currentRoom):
        self.__currentRoomName = message.get('roomName') or 'lobby'
        self.updateRoom(currentRoom)


        action = message.get('action')
        if action:
            methodName = f"handle{action[0].upper()}{action[1:]}"  # Convert action to camelCase method name
            method = getattr(self, methodName, self.handleDefault)
            return await method(message)
        return

    # Handler for 'chat' action
    async def handleChat(self, message):
        chatResponse = self.__query.chatTest(message.get('message'))
        return {
            'action': 'chat',
            'message': chatResponse
        }

    # Handler for 'registration' action
    async def handleRegistration(self, message):
        screenName = message.get('screenName')
        instrument = message.get('instrument')
        userId = message.get('userId')

        if userId:
            self.__currentClient.userId = userId

        if not screenName:
            return {
                'action': 'registration',
                'clients': [self.__currentClient],
                'userId': [userId],
                'message': self.__query.whatsYourName(),
                'responseRequired': True,
                'responseAction': 'newScreenName'
            }

        self.__currentClient.screenName = screenName
        if not instrument and not self.__currentClient.instrument:
            return {
                'action': 'registration',
                'clients': [self.__currentClient],
                'userId': [userId],
                'message': self.__query.whatsYourInstrument(screenName),
                'responseRequired': True,
                'responseAction': 'newInstrument'
            }

        if instrument:
            self.currentClient.instrument = instrument

        if message.get('roomCreator'):
            self.__currentRoom = Room(LLMQueryCreator=self.__query, broadcastHandler=self.__broadcastHandler)
            self.__currentRoomName = self.__currentRoom.roomName
            self.__currentRooms[self.__currentRoomName] = self.__currentRoom
        else:
            if not self.__currentRoomName or self.__currentRoomName == 'lobby':
                return {
                    'action': 'registration',
                    'userId': [userId],
                    'clients': [self.__currentClient],
                    'message': 'Enter the room you would like to join.',
                    'responseRequired': True,
                    'responseAction': 'joinRoom'
                }
            currentRoom = self.__currentRooms.get(self.currentRoomName.lower())
            self.__currentRoom = currentRoom

        await self.__currentRoom.addPlayerToRoom(self.__currentClient)
        self.removePlayerFromLobby()
        response = self.__currentRoom.prepareGameStateResponse('newPlayer')

        if self.__currentRoom.gameStatus == "Waiting To Start":
            response['feedbackQuestion'] = self.__currentRoom.getLobbyFeedback([self.__currentClient])
        return response

    # Handler for 'startPerformance' action
    async def handleStartPerformance(self, message):
        await self.__currentRoom.initializeGameState()
        response = self.__currentRoom.prepareGameStateResponse('newGameState')
        return response

    # Handler for 'performerLobbyFeedbackResponse' action
    async def handlePerformerLobbyFeedbackResponse(self, message):
        feedbackQuestion = message.get('feedbackQuestion')
        feedbackResponse = message.get('response')
        self.__currentClient.logFeedback('performerLobbyFeedbackResponse', feedbackQuestion, feedbackResponse)
        response = {
            'feedbackQuestion': self.__currentRoom.getLobbyFeedback([self.__currentClient]),
            'roomName': self.__currentRoomName,
            'gameStatus': self.__currentRoom.gameStatus,
            'gameState': self.__currentRoom.prepareGameStatePerformers()
        }
        return response

    # Handler for 'reactToPrompt' action
    async def handleReactToPrompt(self, message):
        prompt = message.get('prompt')
        promptTitle = message.get('promptTitle')
        reaction = message.get('reaction')
        await self.__currentRoom.promptReaction(self.__currentClient, prompt, promptTitle, reaction)
        return self.__currentRoom.prepareGameStateResponse('newGameState')

    # Handler for 'endSong' action
    async def handleEndSong(self, message):
        self.__query.endSong(self.__currentRoom)
        response = self.__currentRoom.prepareGameStateResponse('endSong')
        return response

    # Handler for 'performanceComplete' action
    async def handlePerformanceComplete(self, message):
        self.__currentRoom.logEnding()
        response = self.__currentRoom.getPostPerformancePerformerFeedback(self.__currentRoom.performers)
        response['gameStatus'] = 'debrief'
        response['action'] = 'debrief'
        return response

    # Handler for 'postPerformancePerformerFeedbackResponse' action
    async def handlePostPerformancePerformerFeedbackResponse(self, message):
        question = message.get('question')
        response = message.get('response')
        self.__currentClient.logFeedback('postPerformancePerformerFeedbackResponse', question, response)
        if len(self.__currentClient.feedbackLog['postPerformancePerformerFeedbackResponse']) < 3:
            return self.__currentRoom.getPostPerformancePerformerFeedback([self.__currentClient])

        allPerformersComplete = all(
            len(performer.feedbackLog.get('postPerformancePerformerFeedbackResponse', [])) >= 3
            for performer in self.__currentRoom.performers
        )
        if allPerformersComplete:
            self.__currentRoom.getClosingTimeSummary()
            self.__currentRoom.createGameLog()
            self.dumpGameLog(self.__currentRoom.gameLog)
            return {
                'action': 'finalSummary',
                'gameStatus': 'finalSummary',
                'summary': self.__currentRoom.summary,
                'roomName': self.__currentRoomName
            }
        return {
            'action': 'finalSummaryPending',
            'message': 'Just waiting on other players. ',
            'roomName': self.__currentRoomName
        }

    async def handleDefault(self, message):
        return

    # Method to remove a player from the lobby
    def removePlayerFromLobby(self):
        performers = self.__currentRooms['lobby'].performers
        for client in performers:
            if client.userId == self.__currentClient.userId:
                performers.remove(client)
                break

    # Method to dump the game log
    def dumpGameLog(self, log):
        dynamoDb = getDynamoDbConnection()
        table = LogTableClient(dynamoDb)
        table.putItem(log)

    async def handlePlayAgain(self, message):
        await self.__currentRoom.startNewSong()
        return self.__currentRoom.prepareGameStateResponse('newGameState')
