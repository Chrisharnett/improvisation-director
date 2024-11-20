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
        self.__performanceMode = False
        self.__themeReactions = []
        self.__themeApproved = False
        self.__improvisations = [Improvisation(self.__performers, self.__LLMQueryCreator)]

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
    def performanceMode(self):
        return self.__performanceMode

    @performanceMode.setter
    def performanceMode(self, boolean):
        self.__performanceMode = boolean

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
        improvisation = Improvisation(self.performers, self.__LLMQueryCreator, centralTheme, startTime)
        self.__improvisations.append(improvisation)

    async def addPlayerToRoom(self, performer):
        self.__performers.append(performer)
        performer.currentRoom = self
        if self.currentImprovisation is not None and self.currentImprovisation.gameStatus == "improvise" and len(
                self.performers) > 0:
            # groupPrompt = self.performers[0].currentPrompts['groupPrompt']
            groupPrompt = await self.LLMQueryCreator.getUpdatedPrompts(self, 'groupPrompt')
            await self.currentImprovisation.getPerformerPrompts(groupPrompt, self)
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
        finalGroupPrompt = self.LLMQueryCreator.getEndSongPrompt(self)
        await self.currentImprovisation.getPerformerPrompts(finalGroupPrompt, self)
        self.currentImprovisation.gameStatus = 'endSong'
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
            gameStateJSON['performers'].append({
                'screenName': performer.screenName or '',
                'instrument': performer.instrument or '',
                'userId': performer.userId,
                'currentPrompts': performer.currentPrompts,
                'registeredUser': performer.registeredUser,
                'roomCreator': performer.roomCreator,
                'personality': performer.personality.to_dict()
            })
        return gameStateJSON

    def prepareGameStateResponse(self, action=None):
        improvisation = self.currentImprovisation
        gameState = {'roomName': self.roomName}
        if improvisation:
            gameState.update({'gameStatus': improvisation.gameStatus, 'centralTheme': improvisation.centralTheme})
        gameState.update(self.prepareGameStatePerformers())
        response = {
            'gameState': gameState,
            'action': action
        }
        return response

    def determineLLMPersonality(self):
        feedback = ""
        for performer in self.__performers:
            if performer.feedbackLog:
                feedback += f"Performer {performer.userId}: {performer.feedbackString()}"
        self.LLMQueryCreator.initializeLLMPersonality(self.performers)

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
        self.LLMQueryCreator.updatePerformerPersonality(performer, feedback)
        performer.updateDynamo()

    def clearThemeReactions(self):
        self.themeReactions = []

    async def promptReaction(self, currentClient, currentPrompt, currentPromptTitle, reaction):
        currentClient.logPrompt(
            {currentPromptTitle: currentPrompt},
            self.currentImprovisation.getCurrentPerformanceTime(),
            reaction)
        feedbackString = f"Performer {currentClient.userId} has reacted to this prompt. " \
                         f"{currentPromptTitle}: {currentPrompt}. " \
                         f"Their reaction is {reaction}"
        self.LLMQueryCreator.updatePerformerPersonality(currentClient, feedbackString)
        self.LLMQueryCreator.adjustLLMPersonality(self.performers, feedbackString)
        if 'endSong' != self.currentImprovisation.gameStatus:
            match reaction:
                case 'moveOn':
                    await self.handleMoveOn(currentPromptTitle, currentClient)
                case 'reject':
                    await self.handleRejectedPrompts(currentClient, currentPromptTitle)
                case _:
                    return

    async def handleMoveOn(self, promptTitle, currentClient):
        match promptTitle:
            case 'groupPrompt':
                newGroupPrompt = await self.LLMQueryCreator.getUpdatedPrompts(self, promptTitle)
                if newGroupPrompt == 'endSong':
                    await self.concludePerformance()
                    return
                await self.currentImprovisation.getPerformerPrompts(newGroupPrompt, self)
                return

            case 'performerPrompt':
                if len(self.performers) > 0:
                    groupPrompt = self.performers[0].currentPrompts.get('groupPrompt')
                    if groupPrompt:
                        newUserPrompt  = self.LLMQueryCreator.moveOnFromPerformerPrompt(
                            self,
                            currentClient,
                            groupPrompt
                        )
                        currentClient.addAndLogPrompt(
                            newUserPrompt,
                            self.currentImprovisation.getCurrentPerformanceTime()
                        )

    async def handleRejectedPrompts(self, currentClient, promptTitle):
        match promptTitle:
            case 'groupPrompt':
                newGroupPrompt = await self.LLMQueryCreator.getUpdatedPrompts(self, promptTitle)
                await self.currentImprovisation.getPerformerPrompts(newGroupPrompt, self)
            case 'performerPrompt':
                if len(self.performers) > 0:
                    groupPrompt = self.performers[0].currentPrompts.get('groupPrompt')
                    if groupPrompt:
                        updatedPerformerPrompt = self.LLMQueryCreator.rejectPerformerPrompt(
                            self,
                            currentClient, groupPrompt
                        )
                        currentClient.addAndLogPrompt(
                            updatedPerformerPrompt,
                            self.currentImprovisation.getCurrentPerformanceTime()
                        )

    def getLobbyFeedback(self, currentPerformers):
        feedbackType = 'performerLobby'
        questions = {}
        for performer in currentPerformers:
            questions[performer.userId] = self.LLMQueryCreator.gettingToKnowYou()
        return {'feedbackType': feedbackType,
                 'questions': questions}

    def getPostPerformancePerformerFeedback(self, currentPerformers):
        self.currentImprovisation.gameStatus = 'debrief'
        feedbackType = 'postPerformancePerformerFeedback'
        questions = {}
        for performer in currentPerformers:
            questions[performer.userId] = self.LLMQueryCreator.postPerformancePerformerFeedback(
                    self,
                    performer.feedbackLog.get('postPerformancePerformerFeedbackResponse') or [],
                    performer.userId
                )
        response =  self.completeFeedbackResponse(questions, feedbackType, 'postPerformancePerformerFeedbackResponse')
        return response

    def completeFeedbackResponse(self, questions, feedbackType, responseRequired=None):
        return {'feedbackQuestion': {'feedbackType': feedbackType,
                                     'questions': questions},
                'responseRequired': responseRequired,
                'action': 'debrief',
                'gameState': self.prepareGameStateResponse('debrief')
                }

    async def startNewSong(self, performers):
        feedbackString = f"Here is a summary of all feedback from this performance. "
        for performer in self.performers:
            feedbackString += performer.feedbackString()
        self.LLMQueryCreator.adjustLLMPersonality(performers, feedbackString)
        self.LLMQueryCreator.getNewLLMPersonality(performers)
        for performer in self.__performers:
            performer.resetPerformer()
        self.addImprovisation()
        self.__themeReactions = []
        self.__themeApproved = False
        self.currentImprovisation.gameStatus = "newCentralTheme"
        self.LLMQueryCreator.refreshPerformanceLogs()
        return
