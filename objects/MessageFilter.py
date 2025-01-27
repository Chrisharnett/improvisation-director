from objects.Room import Room
from util.Dynamo.logTableClient import LogTableClient
from util.Dynamo.connections import getDynamoDbConnection
from util.Dynamo.userTableClient import UserTableClient
from util.JWTVerify import verify_jwt
import traceback
import jwt

class MessageFilter:
    AUTHENTICATED_ACTIONS = {
        'updateProfile',
        'registration',
        'getCurrentPlayer',
        'getStarted',
        'performerLobbyFeedbackResponse',
        'centralThemeResponse',
        'postPerformancePerformerFeedbackResponse',
        'playAgain',
        'announceStartPerformance',
        'startPerformance',
        'performanceComplete',
        'endSong',
        'reactToPrompt'
    }

    def __init__(self, currentClient, currentRooms, queryCreator, broadcastHandler=None):
        self.__query = queryCreator
        self.__currentClient = currentClient
        self.__currentRooms = currentRooms
        self.__broadcastHandler = broadcastHandler
        self.__currentRoom = None
        self.__currentRoomName = None

    @property
    def currentClient(self):
        return self.__currentClient

    @currentClient.setter
    def currentClient(self, value):
        self.__currentClient = value

    @property
    def currentRooms(self):
        return self.__currentRooms

    @currentRooms.setter
    def currentRooms(self, currentRooms):
        self.currentRooms = currentRooms

    @property
    def currentRoom(self):
        return self.__currentRoom

    @currentRoom.setter
    def currentRoom(self, value):
        self.__currentRoom = value

    @property
    def currentRoomName(self):
        return self.__currentRoomName

    @currentRoomName.setter
    def currentRoomName(self, value):
        self.__currentRoomName = value

    @property
    def broadcastHandler(self):
        return self.__broadcastHandler

    @broadcastHandler.setter
    def broadcastHandler(self, value):
        self.__broadcastHandler = value

    async def handlePlayAgain(self, message=None):
        await self.currentRoom.startNewImprovisation()
        return await self.handleStartPerformance()

    async def handleAnnounceStartPerformance(self, message):
        announcement = self.__query.announceStart(self.__currentRoom)
        return {'action': 'announcement',
                'roomName': self.__currentRoomName,
                'message': {'announcement': announcement},
                'disableTimer': True}

    async def handleMessage(self, message, currentRoom):
        self.__currentRoomName = message.get('roomName') or 'lobby'
        self.updateRoom(currentRoom)

        is_authenticated, auth_response = await self.verifyAuthentication(message)
        if not is_authenticated:
            return auth_response

        action = message.get('action')
        if action:
            methodName = f"handle{action[0].upper()}{action[1:]}"
            method = getattr(self, methodName, self.handleDefault)
            return await method(message)
        return

    async def handleObserveRoom(self, message):
        roomName = message.get('roomName')
        self.__currentRoom.addAudienceToRoom(self.__currentClient)
        self.removePlayerFromLobby()
        return self.__currentRoom.prepareGameStateResponse(action='newObserver')

    async def handleAboutMe(self, message):
        aboutMe = self.__query.aboutMe()
        return {
            'action': 'aboutMe',
            'message': aboutMe,
            'clients': [self.currentClient]
        }

    async def handleGetCurrentPlayer(self, message):
        currentPlayer = message.get('currentPlayer')
        if currentPlayer:
            userId = currentPlayer.get('userId')
            if not self.currentClient.userId:
                self.currentClient.userId = userId
            playerData = self.handleGetUserData(userId)
            updatedData = {key: playerData[key] for key in ['screenName', 'instrument', 'personality'] if
                           key in playerData}
            self.currentClient.updatePlayerProfile(updatedData)
            return {
                'action': 'playerProfileData',
                'currentPlayer': self.currentClient.playerProfile,
                'clients': [self.currentClient]}

    async def handleUpdateProfile(self, message):
        currentPlayer = message.get('currentPlayer')
        updatedData = {key: currentPlayer[key] for key in
                       ['screenName', 'instrument', 'personality']
                       if key in currentPlayer}
        self.currentClient.updatePlayerProfile(updatedData)
        self.currentClient.updateDynamo()
        return {
            'action': 'playerProfileData',
            'currentPlayer': self.currentClient.playerProfile,
            'clients': [self.__currentClient],}

    async def handleChat(self, message):
        chatResponse = self.__query.chatTest(message.get('message'))
        return {
            'action': 'chat',
            'message': chatResponse,
            'clients': [self.__currentClient],
        }

    async def handleGetStarted(self, message):
        welcomeMessage = self.__currentRoom.sayHello()
        return {'action': 'welcome',
                'gameStatus': 'welcome',
                'responseRequired': False,
                'roomName': self.__currentRoomName,
                'message': welcomeMessage,
                'clients': [self.__currentClient]}

    def handleGetUserData(self, sub):
        try:
            dynamoDb = getDynamoDbConnection()
            table = UserTableClient(dynamoDb)
            response = table.getItem({'sub': sub})
            userData = response['Item']
            personality = userData.get('personality')
            attributes = personality.get('attributes', None)
            if personality and attributes:
                attributeValuesToFloat = {key: float(value) for key, value in attributes.items()}
                userData['personality']['attributes'] = attributeValuesToFloat
            return userData
        except Exception as e:
            traceback.print_exc()

    # Handler for 'registration' action
    async def handleRegistration(self, message):
        currentPlayer = message.get('currentPlayer')
        userId = currentPlayer.get('userId')
        registeredUser = currentPlayer.get('registeredUser')
        roomCreator = currentPlayer.get('roomCreator')
        instrument = currentPlayer.get('instrument')
        screenName = currentPlayer.get('screenName')
        if roomCreator:
            self.currentClient.roomCreator = True

        if registeredUser:
            self.currentClient.registeredUser = True
            userData = self.handleGetUserData(userId)
            if userData:
                currentPlayer['instrument'] = instrument or userData.get('instrument')
                currentPlayer['screenName'] = screenName or userData.get('screenName')
                personality = userData.get('personality')
                self.currentClient.userId = userId
                self.currentClient.screenName = currentPlayer['screenName']
                self.currentClient.instrument = currentPlayer['instrument']
                self.currentClient.personality.updatePersonality(personality)

            if not currentPlayer.get('screenName') or not currentPlayer.get('instrument'):
                return self.requestNewPlayerData()
            self.currentClient.updateDynamo()

        response = await self.handleRoomRegistration(message)
        return response

    async def handleRoomRegistration(self, message):
        currentPlayer = message.get('currentPlayer')
        roomNameToJoin = message.get('roomName')
        if currentPlayer.get('roomCreator'):
            # Create a new room
            self.currentRoom = Room(LLMQueryCreator=self.__query, broadcastHandler=self.__broadcastHandler)
            self.currentRoomName = self.currentRoom.roomName
            self.__currentRooms[self.currentRoomName] = self.currentRoom
            self.currentClient.roomCreator = True
        else:
            # Join an existing room
            if not self.currentRoomName or self.currentRoomName == 'lobby':
                return {
                    'action': 'registration',
                    'userId': [self.__currentClient.userId],
                    'clients': [self.__currentClient],
                    'message': 'Enter the room you would like to join.',
                    'responseRequired': "joinRoom",
                    'responseAction': 'joinRoom'
                }
            self.currentRoom = self.__currentRooms.get(roomNameToJoin.lower())

        # Add player to the room and update game state
        await self.currentRoom.addPlayerToRoom(self.__currentClient)
        self.removePlayerFromLobby()

        response = self.currentRoom.prepareGameStateResponse('newPlayer')

        if self.currentRoom.currentImprovisation.gameStatus == 'registration':
            self.currentRoom.currentImprovisation.gameStatus = "Theme Selection"

        if self.currentRoom.currentImprovisation.gameStatus == "Theme Selection":
            self.currentRoom.currentImprovisation.initializeImprovDirectorPersonality()
            self.currentRoom.currentImprovisation.getCentralTheme(self.currentRoom)
            response = self.currentRoom.prepareGameStateResponse('newCentralTheme')
        return response

    async def handleStartPerformance(self, message=None):
        improv = self.currentRoom.currentImprovisation
        if not self.currentRoom.themeApproved:
            improv.gameStatus = 'Theme Selection'
            if not self.currentRoom.currentImprovisation.centralTheme:
                centralTheme = improv.getCentralTheme(self.currentRoom)
            response = self.currentRoom.prepareGameStateResponse('newCentralTheme')
            return response
        else:
            return self.initializePerformance()

    async def handleCentralThemeResponse(self, message):
        improv = self.__currentRoom.currentImprovisation
        playerReaction = message.get('playerReaction')
        centralTheme = message.get('centralTheme')
        suggestion = playerReaction.get('suggestion')
        reaction = playerReaction.get('reaction')
        feedback = f"The suggested central theme is {centralTheme}. "
        feedback += f"The performer {reaction} the central Theme."
        if suggestion:
            feedback += f"The performer suggests: {suggestion}. "
        self.currentRoom.addThemeReaction(self.currentClient, playerReaction, feedback)
        progress = len(self.currentRoom.themeReactions)
        if len(self.currentRoom.performers) == progress:
            newTheme = improv.refineTheme(self.__currentRoom)
            if self.currentRoom.themeConsensus():
                return await self.initializePerformance()
            self.currentRoom.clearThemeReactions()
            return self.currentRoom.prepareGameStateResponse('newCentralTheme')
        return {'action': 'Waiting for theme response.',
                'progress': progress}

    async def initializePerformance(self):
        await self.currentRoom.currentImprovisation.initializeGameState()
        response = self.currentRoom.prepareGameStateResponse('newGameState')
        return response

    def handleRequestGameState(self, message):
        for room in self.currentRooms:
            if self.currentClient in room.performers:
                return room.prepareGameStateResponse('improvise')

    async def handleEndSong(self, message):
        await self.currentRoom.concludePerformance()
        return self.currentRoom.prepareGameStateResponse(action='endSong')

    async def handlePerformanceComplete(self, message):
        self.currentRoom.currentImprovisation.logEnding()
        improv = self.currentRoom.currentImprovisation
        improv.summarizePerformance(self.currentRoom)
        self.dumpGameLog(improv.gameLog)
        return await self.handlePlayAgain()

    async def handleReactToPrompt(self, message):
        prompt = message.get('prompt')
        promptTitle = message.get('promptTitle')
        reaction = message.get('reaction')
        await self.currentRoom.promptReaction(self.currentClient, prompt, promptTitle, reaction)
        response = self.currentRoom.prepareGameStateResponse('newGameState')
        return response

    async def handleDefault(self, message):
        return

    def removePlayerFromLobby(self):
        performers = self.__currentRooms['lobby'].performers
        for client in performers:
            if client.userId == self.__currentClient.userId:
                performers.remove(client)
                break

    def requestNewPlayerData(self):
        return (
            {
                'action': 'getNewPlayerData',
                'clients': [self.currentClient],
                'currentPlayer': self.currentClient.playerProfile,
                'responseRequired': 'getNewPlayerData',
                'responseAction': 'updatePlayerProfile'
            }
        )

    def dumpGameLog(self, log):
        dynamoDb = getDynamoDbConnection()
        table = LogTableClient(dynamoDb)
        table.putItem(log)

    def updateRoom(self, newRoom):
        """Update the current room and its broadcastHandler and queryConnector."""
        self.__currentRoom = newRoom
        self.__broadcastHandler = newRoom.broadcastMessage
        newRoom.LLMQueryCreator = self.__query

    async def verifyAuthentication(self, message):
        action = message.get('action')
        token = message.get('token')

        if action in self.AUTHENTICATED_ACTIONS:
            if not token:
                return False, {
                    'action': 'error',
                    'errorMessage': 'Authentication required for this action.',
                    'responseRequired': "",
                    'clients': [self.__currentClient],
                }

            try:
                decoded_token = verify_jwt(token)

            except jwt.ExpiredSignatureError:
            # Handle specific case of expired token
                return False, {
                    'action': 'error',
                    'errorMessage': 'Token has expired. Access denied.',
                    'responseRequired': "",
                    'clients': [self.__currentClient],
                }
            except jwt.InvalidTokenError as e:
                # Handle specific case of invalid token
                print("Token verification error:", str(e))
                return False, {
                    'action': 'error',
                    'errorMessage': 'Invalid token. Access denied.',
                    'responseRequired': "",
                    'clients': [self.__currentClient],
                }

            except ValueError as e:
                # Handle general token verification errors, like missing claims
                return False, {
                    'action': 'error',
                    'errorMessage': str(e),
                    'responseRequired': "",
                    'clients': [self.__currentClient],
                }

            except Exception as e:
                # Fallback for unexpected errors, with more specific information
                return False, {
                    'action': 'error',
                    'errorMessage': f'Unexpected error occurred: {str(e)}. Access denied.',
                    'responseRequired': "",
                    'clients': [self.__currentClient],
                }

        return True, None

