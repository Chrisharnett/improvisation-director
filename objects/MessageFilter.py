from objects.Room import Room
from util.Dynamo.logTableClient import LogTableClient
from util.Dynamo.connections import getDynamoDbConnection
from util.Dynamo.userTableClient import UserTableClient
from util.JWTVerify import verify_jwt
import jwt
from jwt import ExpiredSignatureError, InvalidTokenError


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

    def updateRoom(self, newRoom):
        """Update the current room and its broadcastHandler and queryConnector."""
        self.__currentRoom = newRoom
        self.__broadcastHandler = newRoom.broadcastMessage
        newRoom.LLMQueryCreator = self.__query

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
        userId = currentPlayer.get('userId')
        if not self.currentClient.userId:
            self.currentClient.userId = userId
        playerData = self.handleGetUserData(userId)
        updatedData = {key: playerData[key] for key in ['screenName', 'instrument', 'personality'] if
                       key in playerData}
        self.currentClient.updatePlayerProfile(updatedData)
        return {
            'action': 'playerProfileData',
            'currentPlayer': self.currentClient.playerProfile(),
            'clients': [self.currentClient]}

    async def handleUpdateProfile(self, message):
        currentPlayer = message.get('currentPlayer')
        updatedData = {key: currentPlayer[key] for key in ['screenName', 'instrument', 'personality'] if key in currentPlayer}
        self.currentClient.updatePlayerProfile(updatedData)
        self.handleUpdateDynamo()
        return {
            'action': 'playerProfileData',
            'currentPlayer': self.currentClient.playerProfile(),
            'clients': [self.__currentClient],}

    async def handleChat(self, message):
        chatResponse = self.__query.chatTest(message.get('message'))
        return {
            'action': 'chat',
            'message': chatResponse,
            'clients': [self.__currentClient],
        }

    async def handleGetStarted(self, message):
        # print(f"user {websocketId} in room {self.__currentRoomName.roomName}")
        welcomeMessage = self.__currentRoom.sayHello()
        return {'action': 'welcome',
                'gameStatus': 'welcome',
                'roomName': self.__currentRoomName,
                'message': welcomeMessage,
                'clients': [self.__currentClient]}

    def handleGetUserData(self, sub):
        try:
            dynamoDb = getDynamoDbConnection()
            table = UserTableClient(dynamoDb)
            response = table.getItem({'sub': sub})
            return response['Item']
        except Exception as e:
            print(e)

    def handleUpdateDynamo(self):
        try:
            dynamoDb = getDynamoDbConnection()
            table = UserTableClient(dynamoDb)
            response = table.putItem({
                'sub': self.currentClient.userId,
                'screenName': self.currentClient.screenName,
                'instrument': self.currentClient.instrument,
                'personality': self.currentClient.personality,
            })
            return response
        except Exception as e:
            print(e)

    # Handler for 'registration' action
    async def handleRegistration(self, message):
        currentPlayer = message.get('currentPlayer')
        userId = currentPlayer.get('userId')
        registeredUser = currentPlayer.get('registeredUser')
        roomCreator = currentPlayer.get('roomCreator')
        if roomCreator:
            self.currentClient.roomCreator = True

        if registeredUser:
            self.currentClient.registeredUser = True
            userData = self.handleGetUserData(userId)
            if userData:
                currentPlayer['instrument'] = currentPlayer.get('instrument') or userData.get('instrument')
                currentPlayer['screenName'] = currentPlayer.get('screenName') or userData.get('screenName')

        if not currentPlayer.get('screenName'):
            return self.requestNewScreenName(userId)

        if not currentPlayer.get('instrument'):
            return self.requestNewInstrument(userId, currentPlayer['screenName'])

        self.__currentClient.userId = userId
        self.__currentClient.screenName = currentPlayer['screenName']
        self.__currentClient.instrument = currentPlayer['instrument']

        if registeredUser:
            self.handleUpdateDynamo()

        return await self.handleRoomRegistration(message)

    def requestNewScreenName(self, userId):
        return {
            'action': 'registration',
            'clients': [self.__currentClient],
            'userId': [userId],
            'message': self.__query.whatsYourName(),
            'responseRequired': True,
            'responseAction': 'newScreenName'
        }

    def requestNewInstrument(self, userId, screenName):
        return {
            'action': 'registration',
            'clients': [self.__currentClient],
            'userId': [userId],
            'message': self.__query.whatsYourInstrument(screenName),
            'responseRequired': True,
            'responseAction': 'newInstrument'
        }

    async def handleRoomRegistration(self, message):
        currentPlayer = message.get('currentPlayer')
        roomNameToJoin = message.get('roomName')
        if currentPlayer.get('roomCreator'):
            # Create a new room
            self.__currentRoom = Room(LLMQueryCreator=self.__query, broadcastHandler=self.__broadcastHandler)
            self.__currentRoomName = self.__currentRoom.roomName
            self.__currentRooms[self.__currentRoomName] = self.__currentRoom
            self.currentClient.roomCreator = True
        else:
            # Join an existing room
            if not self.__currentRoomName or self.__currentRoomName == 'lobby':
                return {
                    'action': 'registration',
                    'userId': [self.__currentClient.userId],
                    'clients': [self.__currentClient],
                    'message': 'Enter the room you would like to join.',
                    'responseRequired': "joinRoom",
                    'responseAction': 'joinRoom'
                }
            self.__currentRoom = self.__currentRooms.get(roomNameToJoin.lower())

        # Add player to the room and update game state
        await self.__currentRoom.addPlayerToRoom(self.__currentClient)
        self.removePlayerFromLobby()

        response = self.__currentRoom.prepareGameStateResponse('newPlayer')

        # Step 7: Handle performance mode if applicable
        if message.get('performanceMode') and self.currentClient.roomCreator:
            self.__currentRoom.performanceMode = True

        if self.__currentRoom.performanceMode:
            return await self.handleStartPerformance()

        # Provide feedback question if game is waiting to start
        if self.__currentRoom.gameStatus == "Waiting To Start":
            response['feedbackQuestion'] = self.__currentRoom.getLobbyFeedback([self.__currentClient])
        elif self.__currentRoom.gameStatus == "Theme selection":
            return self.__currentRoom.prepareGameStateResponse('newCentralTheme')
        return response

    async def handleStartPerformance(self, message=None):
        self.__currentRoom.updatePerformerPersonalities()
        self.__currentRoom.determineLLMPersonality()
        if not self.__currentRoom.themeApproved:
            self.__currentRoom.gameStatus = 'Theme Selection'
            centralTheme = self.__currentRoom.getCentralTheme()
            response = self.__currentRoom.prepareGameStateResponse('newCentralTheme')
            return response
        else:
            return self.initializePerformance()

    async def handleCentralThemeResponse(self, message):
        playerReaction = message.get('playerReaction')
        self.__currentRoom.addThemeReaction(self.currentClient, playerReaction)
        progress = len(self.currentRoom.themeReactions)
        if len(self.currentRoom.performers) >= progress:
            newTheme = self.currentRoom.refineTheme()
            if self.currentRoom.themeConsensus():
                return await self.initializePerformance()
            self.currentRoom.clearThemeReactions()
            return self.__currentRoom.prepareGameStateResponse('newCentralTheme')
        return {'action': 'Waiting for theme response.',
                'progress': progress}

    async def initializePerformance(self):
        await self.__currentRoom.initializeGameState()
        response = self.__currentRoom.prepareGameStateResponse('newGameState')
        return response

    async def handlePerformerLobbyFeedbackResponse(self, message):
        feedbackQuestion = message.get('feedbackQuestion').get('question')
        feedbackOptions = message.get('feedbackQuestion').get('options')
        feedbackResponse = message.get('response')
        self.__currentClient.logFeedback('performerLobbyFeedbackResponse', feedbackQuestion, feedbackResponse, feedbackOptions)
        response = {
            'feedbackQuestion': self.__currentRoom.getLobbyFeedback([self.__currentClient]),
        }
        response.update(self.__currentRoom.prepareGameStateResponse())
        return response

    async def handleReactToPrompt(self, message):
        prompt = message.get('prompt')
        promptTitle = message.get('promptTitle')
        reaction = message.get('reaction')
        await self.__currentRoom.promptReaction(self.__currentClient, prompt, promptTitle, reaction)
        response=self.__currentRoom.prepareGameStateResponse('newGameState')
        return response

    async def handleEndSong(self, message):
        await self.__currentRoom.endSong()
        self.__currentRoom.gameStatus = message.get('action')
        return self.__currentRoom.prepareGameStateResponse(action='endSong')

    async def handlePerformanceComplete(self, message):
        self.__currentRoom.logEnding()
        if self.currentRoom.performanceMode:
            return self.completePerformance()

        response = self.__currentRoom.getPostPerformancePerformerFeedback(self.__currentRoom.performers)
        response['gameStatus'] = 'debrief'
        response['action'] = 'debrief'
        return response

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
            return self.completePerformance()

        return {
            'action': 'finalSummaryPending',
            'message': 'Just waiting on other players. ',
            'roomName': self.__currentRoomName
        }

    def completePerformance(self):
        self.__currentRoom.summarizePerformance()
        self.dumpGameLog(self.__currentRoom.gameLog)
        return {
            'action': 'finalSummary',
            'gameStatus': 'finalSummary',
            'summary': self.__currentRoom.summary,
            'roomName': self.__currentRoomName
        }

    async def handleDefault(self, message):
        return

    def removePlayerFromLobby(self):
        performers = self.__currentRooms['lobby'].performers
        for client in performers:
            if client.userId == self.__currentClient.userId:
                performers.remove(client)
                break

    def dumpGameLog(self, log):
        dynamoDb = getDynamoDbConnection()
        table = LogTableClient(dynamoDb)
        table.putItem(log)

    async def handlePlayAgain(self, message):
        await self.__currentRoom.startNewSong()
        centralTheme = self.__currentRoom.getCentralTheme()
        response = self.__currentRoom.prepareGameStateResponse('newCentralTheme')
        return response

    async def handleAnnounceStartPerformance(self, message):
        announcement = self.__query.announceStart(self.__currentRoom)
        return  {'action': 'announcement',
                'roomName': self.__currentRoomName,
                'message': {'announcement': announcement},
                 'disableTimer': True}

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

