import asyncio
import json
from util.timeStamp import timeStamp

class Room:
    def __init__(self, LLMQueryCreator=None, roomName=None, broadcastHandler=None):
        self.__LLMQueryCreator = LLMQueryCreator
        if roomName == None:
            self.__roomName = self.__LLMQueryCreator.generateRoomName()
        else:
            self.__roomName = roomName
        self.__performers = []
        self.__scheduledTasks = {}
        self.__broadcastHandler = broadcastHandler
        self.__gameLog = {}
        self.__summary = None
        self.__songCount = 0
        self.__gameStatus = 'Waiting To Start'

    @property
    def LLMQueryCreator(self):
        return self.__LLMQueryCreator

    @LLMQueryCreator.setter
    def LLMQueryCreator(self, LLMQueryCreator):
        self.__LLMQueryCreator = LLMQueryCreator

    @property
    def songCount(self):
        return self.__songCount

    @songCount.setter
    def songCount(self, count):
        self.__songCount = count

    @property
    def gameStatus(self):
        return self.__gameStatus

    @gameStatus.setter
    def gameStatus(self, status):
        self.__gameStatus = status

    @property
    def roomName(self):
        return self.__roomName

    @property
    def performers(self):
        return self.__performers

    @property
    def scheduledTasks(self):
        return self.__scheduledTasks

    @property
    def broadcastHandler(self):
        return self.__broadcastHandler

    @property
    def gameLog(self):
        return self.__gameLog

    @property
    def summary(self):
        return self.__summary

    async def addPlayerToRoom(self, performer):
        self.__performers.append(performer)
        if self.gameStatus == "improvise":
            newCurrentPrompts = self.LLMQueryCreator.getNewCurrentPrompt(self)
            newHAndMPrompts = self.LLMQueryCreator.getNewHarmonyAndMeterPrompt(self)
            for userId, newPromptData in newCurrentPrompts.items():
                if newPromptData:
                    self.updatePrompts(userId, newPromptData)
                    await self.schedulePromptUpdate('currentPrompt')
            for userId, newPromptData in newHAndMPrompts.items():
                if newPromptData:
                    self.updatePrompts(userId, newPromptData)
                    await self.schedulePromptUpdate('harmonyAndMeterPrompt')

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

    async def broadcastMessage(self, message, newPrompts=None):
        if self.__performers:
            await asyncio.gather(*[performer.websocket.send(json.dumps(message)) for performer in self.__performers])
            print(f"Broadcasted message to room {self.__roomName}")
        if newPrompts:
            for userId, currentPrompts in newPrompts.items():
                for promptTitle, prompt in currentPrompts.items():
                    print(f"{self.__roomName}, {userId}, {promptTitle}: {prompt}")

    async def sendMessageToUser(self, message, client):
        response = message.copy()
        response.pop('clients', None)
        if client in self.__performers:
            await client.websocket.send(json.dumps(response))
            print(f"Sent message to user {client.userId or 'Unnamed Client'} in room {self.__roomName}")

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
            })
        return gameStateJSON

    def gameStateString(self):
        gameState = self.prepareGameStateResponse()
        for performer in self.__performers:
            for p in gameState.get("gameState")['performers']:
                if performer.userId == p.get('userId'):
                    p['promptHistory'] = performer.promptHistory
                    p['feedbackLog'] = performer.feedbackLog
        return json.dumps(gameState)

    def prepareGameStateResponse(self, action=None):
        return {
            'gameState': self.prepareGameStatePerformers(),
            'gameStatus': self.__gameStatus,
            'roomName': self.__roomName,
            'action': action
        }

    async def initializeGameState(self):
        feedback = []
        for performer in self.__performers:
            feedback.append({performer.userId: performer.feedbackLog})
        self.LLMQueryCreator.getStartingPerformerPrompts(self)
        self.__gameStatus = "improvise"
        await self.schedulePromptUpdate('currentPrompt')
        await self.schedulePromptUpdate('harmonyAndMeterPrompt')

    def assignNewPrompts(self, newPrompts):
        for userId, prompt in newPrompts.items():
            for performer in self.__performers:
                if userId == performer.userId:
                    performer.addAndLogPrompt(prompt)

    def updatePrompts(self, userId, newPrompt):
        for performer in self.__performers:
            if userId == performer.userId:
                for title, prompt in newPrompt.items():
                    if prompt:
                        performer.addAndLogPrompt({title: prompt})

    async def promptReaction(self, currentClient, currentPrompt, currentPromptTitle, reaction):
        for performer in self.__performers:
            if performer.userId == currentClient.userId:
                for prompt in performer.promptHistory:
                    if prompt.get('prompt') == currentPrompt:
                        prompt['playerReaction'] = reaction
        if reaction == 'reject':
            newPrompts = self.LLMQueryCreator.replaceRejectedPrompts(self, currentPrompt, currentPromptTitle)
            for userId, newPromptData in newPrompts.items():
                if newPromptData:
                    self.updatePrompts(userId, newPromptData)
            await self.schedulePromptUpdate(currentPromptTitle)
        if reaction == 'like':
            currentClient.likePrompt(currentPrompt, currentPromptTitle)

    async def schedulePromptUpdate(self, promptTitle):
        try:
            interval = int(self.LLMQueryCreator.getIntervalLength(self.gameStateString(), promptTitle))
        except ValueError:
            interval = 60

        if promptTitle in self.__scheduledTasks:
            existingTask = self.__scheduledTasks[promptTitle]
            if not existingTask.done():
                existingTask.cancel()
            try:
                await existingTask
            except asyncio.CancelledError:
                pass
            except Exception as e:
                print(f'Error: {e}')

        if promptTitle == 'currentPrompt':
            self.__scheduledTasks[promptTitle] = asyncio.create_task(self.updateCurrentPrompt(interval))
        elif promptTitle == 'harmonyAndMeterPrompt':
            self.__scheduledTasks[promptTitle] = asyncio.create_task(self.updateHarmonyAndMeterPrompt(interval))

    async def updatePrompt(self, interval, promptTitle):
        print(f'update {promptTitle} in {interval} seconds')
        await asyncio.sleep(interval)
        newPrompts = self.LLMQueryCreator.getPrompts(self.gameStateString())
        self.assignNewPrompts(newPrompts)
        response = self.prepareGameStateResponse('newGameState')
        await self.broadcastMessage(response, newPrompts)
        if len(self.__performers) > 0:
            await self.schedulePromptUpdate('currentPrompt')
        else:
            print(f"No active connections in room '{self.__roomName}'. Stopping prompt updates.")

    async def updateCurrentPrompt(self, interval):
        print(f'update current prompt in {interval} seconds')
        await asyncio.sleep(interval)
        newPrompts = self.LLMQueryCreator.getNewCurrentPrompt(self)
        self.assignNewPrompts(newPrompts)
        response = self.prepareGameStateResponse('newGameState')
        await self.broadcastMessage(response, newPrompts)
        if len(self.__performers) > 0:
            await self.schedulePromptUpdate('currentPrompt')
        else:
            print(f"No active connections in room '{self.__roomName}'. Stopping prompt updates.")

    async def updateHarmonyAndMeterPrompt(self, interval):
        print(f'update harmony and meter prompt in {interval} seconds')
        await asyncio.sleep(interval)
        newPrompts = self.LLMQueryCreator.getNewHarmonyAndMeterPrompt(self.gameStateString())
        self.assignNewPrompts(newPrompts)
        response = self.prepareGameStateResponse('newGameState')
        await self.broadcastMessage(response, newPrompts)
        if len(self.__performers) > 0:
            await self.schedulePromptUpdate('harmonyAndMeterPrompt')
        else:
            print(f"No active connections in room '{self.__roomName}'. Stopping prompt updates.")

    def getLobbyFeedback(self, currentPerformers):
        feedbackType = 'performerLobby'
        questions = []
        for performer in currentPerformers:
            questions.append({
                'userId': performer.userId,
                'question': self.LLMQueryCreator.gettingToKnowYou()
            })
        return {'feedbackType': feedbackType,
                 'questions': questions}

    def getPostPerformancePerformerFeedback(self, currentPerformers):
        self.__gameStatus = 'debrief'
        feedbackType = 'postPerformancePerformerFeedback'
        questions = []
        for performer in currentPerformers:
            questions.append({
                'userId': performer.userId,
                'question': self.LLMQueryCreator.postPerformancePerformerFeedback(
                    self.gameStateString(),
                    performer.feedbackLog.get('postPerformancePerformerFeedbackResponse') or [],
                    performer.userId
                )
            })
        return self.completeFeedbackResponse(questions, feedbackType, 'postPerformancePerformerFeedbackResponse')

    def completeFeedbackResponse(self, questions, feedbackType, responseRequired=None):
        return {'roomName': self.__roomName,
                'feedbackQuestion': {'feedbackType': feedbackType,
                                     'questions': questions},
                'responseRequired': responseRequired
                }

    def getClosingTimeSummary(self):
        self.__summary = self.LLMQueryCreator.closingSummary(self.gameStateString())
        self.createGameLog()
        return

    def logEnding(self):
        self.__gameLog['endingTimestamp'] = timeStamp()

    def createGameLog(self):
        promptLog = []
        performers = []
        for performer in self.__performers:
            performers.append({
                'userId': performer.userId,
                'instrument': performer.instrument,
                'feedbackResponses': performer.feedbackLog
            })
            promptLog.extend(performer.promptHistory)

        sortedLog = sorted(promptLog, key=lambda x: x['timeStamp'])

        self.__gameLog['roomName'] = f"{self.__roomName}-{self.__songCount}"
        self.__gameLog['performers'] = performers
        self.__gameLog['promptLog'] = sortedLog
        self.__gameLog['summary'] = self.__summary

    async def startNewSong(self):
        for performer in self.__performers:
            performer.resetPerformer()
        self.gameStatus = "improvise"
        self.songCount += 1
        self.LLMQueryCreator.refreshPerformanceLogs()
        await self.initializeGameState()