from directorPrompts.directorPrompts\
    import chatTest, \
    generateRoomName, \
    getStartingPrompt, \
    getHarmonyAndMeterPrompt, \
    getNextPrompt, \
    coordinatePrompt, \
    endSong, \
    postPerformancePerformerFeedback, \
    closingSummary
from objects.Performer import timeStamp

class Room:
    def __init__(self, roomName = generateRoomName()):
        self.__performers = []
        self.__roomName = roomName
        self.__logs = {}

    # Getters
    @property
    def performers(self):
        return self.__performers

    @property
    def roomName(self):
        return self.__roomName

    @performers.setter
    def performers(self, performers):
        self.__performers = performers

    @roomName.setter
    def roomName(self, roomName):
        self.__roomName = roomName

    def addPlayerToRoom(self, currentClient):
        self.__performers.append(currentClient)

    def leaveRoom(self, currentClient):
        # TODO: add logging of performers who leave the room.
        if currentClient in self.__performers:
            self.__performers.remove(currentClient)

    def getGameStateResponse(self):
        gameStateJSON = {
                         "performers": [],
                         }
        for performer in self.__performers:
            gameStateJSON['performers'].append({
                'screenName': performer.screenName or '',
                'instrument': performer.instrument or '',
                'userId': performer.userId,
                'currentPrompts': performer.currentPrompts,
                'promptHistory': performer.promptHistory
            })
        return gameStateJSON

    def gameStateString(self):
        return ', '.join(self.getGameStateResponse())

    def prepareGameStateResponse(self, action):
        return {
            'gameState': self.getGameStateResponse(),
            'roomName': self.__roomName,
            'action': action
            }

    def getClientConnections(self, connectedClients):
        userIds = [performer.userId for performer in self.__performers]
        return [client for client in connectedClients if client.userId in userIds]

    def initializeGameState(self):
        feedback = []
        for performer in self.__performers:
            feedback.append({performer.userId: performer.feedbackLog})
        startingPrompt = getStartingPrompt(feedback)
        for performer in self.__performers:
            coordinatedPrompt = coordinatePrompt(performer, self.gameStateString(), startingPrompt)
            newPrompt = {'promptTitle': ['currentPrompt'],
                'prompt': coordinatedPrompt
                 }
            performer.addAndLogPrompt(newPrompt)
        harmonyAndMeterPrompt = {
                'promptTitle': ['harmonyAndMeterPrompt'],
                'prompt': getHarmonyAndMeterPrompt(self.gameStateString()),
            }
        for performer in self.__performers:
            performer.addAndLogPrompt(harmonyAndMeterPrompt)
        for performer in self.__performers:
            nextPrompt = getNextPrompt(self, performer).split(',')
            performer.addAndLogPrompt({
                'promptTitle': ['nextPrompt', nextPrompt[0]],
                'prompt': nextPrompt[1],
            })

    def refreshNextPrompt(self):
        for performer in self.__performers:
            nextPrompt = getNextPrompt(self, performer).split(',')
            performer.addAndLogPrompt({
                'promptTitle': ['nextPrompt', nextPrompt[0]],
                'prompt': nextPrompt[1],
            })

    def useNextPrompt(self, userId):
        currentClient = next(player for player in self.__performers if userId == player.userId)
        nextPrompt = next(
            (prompt for prompt in currentClient.currentPrompts if prompt.get('promptTitle')[0] == 'nextPrompt'),
            None
        )
        if nextPrompt:
            for performer in self.__performers:
                promptToAdd = nextPrompt
                if nextPrompt.get('promptTitle') != 'harmonyAndMeterPrompt':
                    promptToAdd = coordinatePrompt(performer, self.gameStateString(), nextPrompt)
                performer.addAndLogPrompt(
                    {'promptTitle': ['currentPrompt'],
                     'prompt': promptToAdd
                     })
            self.refreshNextPrompt()

    def ignorePrompt(self, userId):
        currentClient = next(player for player in self.__performers if userId == player.userId)
        ignorePrompt = next(
            (prompt for prompt in currentClient.currentPrompts if prompt.get('promptTitle')[0] == 'nextPrompt'), None)
        if ignorePrompt:
            currentClient.ignorePrompt(ignorePrompt)
            self.refreshNextPrompt()

    def getPromptIndex(self, currentClient, promptTitle):
        for i, prompt in enumerate(currentClient.currentPrompts):
            if prompt.get('promptTitle')[0] == promptTitle:
                return i
        return -1

    def createSongEnding(self):
        endPrompt = endSong(self.gameStateString())
        for performer in self.__performers:
            finalPrompt = coordinatePrompt(performer, self.gameStateString(), endPrompt, True)
            performer.addAndLogPrompt(
                {'promptTitle': ['currentPrompt', 'endPrompt'],
                 'prompt': finalPrompt
                 })

    def logEnding(self):
        self.__logs['promptLog'] = []
        self.__logs['endingTimestamp'] = timeStamp()
        for performer in self.__performers:
            self.__logs["promptLog"].append({"userId": performer.userId,
                                          "promptLog": performer.promptHistory})

    def getPostPerformancePerformerFeedback(self):
        response = {'roomName': self.__roomName, 'feedbackQuestion': []}
        for performer in self.__performers:
            response['feedbackQuestion'].append({
                'userId': performer.userId,
                'feedbackType': 'postPerformancePerformerFeedback',
                'question': postPerformancePerformerFeedback(
                    self.gameStateString(),
                    performer.feedbackLog,
                    performer.userId
                )
            })
        return response

    def closingTimeSummary(self):
        return closingSummary(self.gameStateString())