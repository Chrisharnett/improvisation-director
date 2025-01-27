import asyncio
import json
from objects.Improvisation import Improvisation

class Room:
    def __init__(self, LLMQueryCreator=None, roomName=None, broadcastHandler=None):
        self.__LLMQueryCreator = LLMQueryCreator
        if roomName is None:
            self.__roomName = self.__LLMQueryCreator.generateRoomName()
        else:
            self.__roomName = roomName
        self.__performers = []
        self.__audience = []
        self.__scheduledTasks = {}
        self.__broadcastHandler = broadcastHandler
        self.__songCount = 0
        # self.__performanceMode = False
        self.__themeReactions = []
        self.__themeApproved = False
        self.__improvisations = [Improvisation(self.__performers, self.__LLMQueryCreator, room=self)]

    @property
    def LLMQueryCreator(self):
        return self.__LLMQueryCreator

    @LLMQueryCreator.setter
    def LLMQueryCreator(self, LLMQueryCreator):
        self.__LLMQueryCreator = LLMQueryCreator

    @property
    def roomName(self):
        return self.__roomName

    @property
    def performers(self):
        return self.__performers

    @property
    def audience(self):
        return self.__audience

    @property
    def scheduledTasks(self):
        return self.__scheduledTasks

    @property
    def broadcastHandler(self):
        return self.__broadcastHandler

    @property
    def themeApproved(self):
        return self.__themeApproved

    @themeApproved.setter
    def themeApproved(self, themeApproved):
        self.__themeApproved = themeApproved

    @property
    def themeReactions(self):
        return self.__themeReactions

    @themeReactions.setter
    def themeReactions(self, themeReactions):
        self.__themeReactions = themeReactions

    @property
    def improvisations(self):
        return self.__improvisations

    @improvisations.setter
    def improvisations(self, improvisations):
        self.__improvisations = improvisations

    @property
    def songCount(self):
        return len(self.__improvisations)

    @property
    def currentImprovisation(self):
        if self.__improvisations:
            return self.__improvisations[-1]
        return None

    def addImprovisation(self, centralTheme=None, startTime=None):
        improvisation = Improvisation(self.performers, self.__LLMQueryCreator, room=self, centralTheme=centralTheme, startTime=startTime, )
        self.__improvisations.append(improvisation)

    async def addPlayerToRoom(self, performer):
        self.__performers.append(performer)
        performer.currentRoom = self
        if self.currentImprovisation is not None and self.currentImprovisation.gameStatus == "improvise" and len(
                self.performers) > 0:
            # groupPrompt = await self.LLMQueryCreator.getUpdatedPrompts(self, 'groupPrompt')
            await self.currentImprovisation.adjustPrompts()
            return

    async def playerRejoinRoom(self, newClient, performer):
        newClient.updateUserData(performer)
        newClient.currentRoom = self
        if newClient not in self.performers:
            self.performers.append(newClient)
        userId = newClient.userId
        currentPrompt = self.currentImprovisation.getCurrentPerformerPrompt(userId).get('performerPrompt')
        currentGroupPrompt = self.currentImprovisation.currentPrompts.get('groupPrompt')
        await self.currentImprovisation.schedulePromptUpdate(currentPrompt, userId)
        await self.currentImprovisation.schedulePromptUpdate(currentGroupPrompt)
        return

    def addAudienceToRoom(self, client):
        client.currentRoom = self
        self.__audience.append(client)

    async def broadcastMessage(self, message):
        if self.__performers:
           await asyncio.gather(*[performer.websocket.send(json.dumps(message)) for performer in self.__performers])
        if self.__audience:
            await asyncio.gather(*[audienceMember.websocket.send(json.dumps(message)) for audienceMember in self.__audience])
        if message.get('action') != 'heartbeat':
            print(f"Broadcast {message.get('action')} to room {self.__roomName}")
        return

    async def concludePerformance(self):
        await self.currentImprovisation.concludePerformance()
        return

    def sayHello(self):
        return self.__LLMQueryCreator.getWelcomeMessage()

    def leaveRoom(self, performer):
        if performer in self.__performers:
            self.__performers.remove(performer)
        if not self.__performers:
            self.cancelAllTasks()

    def cancelAllTasks(self):
        for task in self.__scheduledTasks.values():
            task.cancel()

    async def sendMessageToUser(self, message, client):
        response = message.copy()
        response.pop('clients', None)
        if client in self.__performers:
            await client.websocket.send(json.dumps(response))
            detail = response.get('message')
            if not detail:
                detail = response.get('action')
            print(f"Send {detail}  to user {client.screenName or 'Unnamed Client'} in room {self.__roomName}")

    async def handleResponse(self, message):
        clientRecipients = message.get('clients')
        if clientRecipients:
            for c in clientRecipients:
                await self.sendMessageToUser(message, c)
        else:
            await self.broadcastMessage(message)

    def getClientConnections(self, connectedClients):
        userIds = [performer.userId for performer in self.__performers]
        return [client for client in connectedClients if client.userId in userIds]

    def prepareGameStatePerformers(self):
        gameStateJSON = {
            "performers": [],
        }
        for performer in self.__performers:
            gameStateJSON['performers'].append(performer.toDict())
        return gameStateJSON

    def prepareGameStateResponse(self, action=None):
        improvisation = self.currentImprovisation
        gameState = {'roomName': self.roomName}
        if improvisation:
            gameState.update({
                'gameStatus': improvisation.gameStatus,
                'centralTheme': improvisation.centralTheme,
                'prompts': improvisation.promptsDict(),
                })
        if self.currentImprovisation.finalPrompt:
            gameState['finalPrompt'] = self.currentImprovisation.finalPrompt
        gameState.update(self.prepareGameStatePerformers())
        response = {
            'gameState': gameState,
            'action': action
        }
        return response

    def determineLLMPersonality(self):
        self.LLMQueryCreator.initializeImprovDirectorPersonality(self)

    def updatePerformerPersonalities(self, feedback=None):
        for performer in self.__performers:
            self.LLMQueryCreator.updatePerformerPersonality(performer, feedback)
            performer.updateDynamo()

    def themeConsensus(self):
        vote = 0
        for response in self.__themeReactions:
            reaction = response.get('reaction')
            if reaction == "like":
                vote += 1
        if (len(self.performers) / 2) > vote:
            return False
        return True

    def themeResponseString(self):
        response = ""
        for i, reply in enumerate(self.__themeReactions):
            response += f"Performer {i+1}: {reply.get('reaction')}; {reply.get('suggestion')} "
        return response

    def addThemeReaction(self, performer, reaction, feedback=None):
        self.__themeReactions.append(reaction)
        self.LLMQueryCreator.centralThemeFineTunePerformerPersonality(self, performer, reaction)
        performer.updateDynamo()

    def clearThemeReactions(self):
        self.themeReactions = []

    async def promptReaction(self, currentClient, currentPrompt, currentPromptTitle, reaction):
        feedbackString = f"Performer {currentClient.userId} has reacted to this prompt. " \
                         f"{currentPromptTitle}: {currentPrompt}. " \
                         f"Their reaction is {reaction}"
        performerPersonality = self.LLMQueryCreator.promptReactionFineTunePersonalities(currentClient, feedbackString, self)
        await self.currentImprovisation.setPromptReaction(currentClient, reaction, currentPromptTitle)
        return


    def completeFeedbackResponse(self, questions, feedbackType, responseRequired=None):
        return {'feedbackQuestion': {'feedbackType': feedbackType,
                                     'questions': questions},
                'responseRequired': responseRequired,
                'action': 'debrief',
                'gameState': self.prepareGameStateResponse('debrief')
                }

    async def startNewImprovisation(self):
        self.LLMQueryCreator.nextSongPersonality(self)
        for performer in self.__performers:
            performer.resetPerformer()
        self.addImprovisation()
        self.__themeReactions = []
        self.__themeApproved = False
        self.LLMQueryCreator.refreshPerformanceLogs()
        return

    def pastLLMPersonalities(self):
        pastLLMs = ""
        for i, improvisation in enumerate(self.improvisations):
            pastLLMs += f"{i}. {improvisation.gameLog['llmPersonality']}"
        return pastLLMs
