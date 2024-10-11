import asyncio
import json
from util.timeStamp import timeStamp
from datetime import datetime

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
        self.__performanceMode = False
        self.__startTime = None

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

    @property
    def performanceMode(self):
        return self.__performanceMode

    @performanceMode.setter
    def performanceMode(self, boolean):
        self.__performanceMode = boolean

    @property
    def startTime(self):
        return self.__startTime


    def setStartTime(self):
        if not self.__startTime:
            self.__startTime = timeStamp()
            return 0
        else:
            return 'Start time already set.'

    def getCurrentPerformanceTime(self):
        if self.__startTime:
            start = datetime.fromisoformat(self.__startTime)
            currentTime = datetime.now()
            elapsed = currentTime - start
            return round(elapsed.total_seconds(), 2)
        else:
            return 'Start time not set.'

    async def addPlayerToRoom(self, performer):
        self.__performers.append(performer)
        if self.gameStatus == "improvise":
            if len(self.performers) > 0:
                groupPrompt = self.performers[0].currentPrompts['groupPrompt']
                self.LLMQueryCreator.getPerformerPrompts(self, groupPrompt)

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
        return

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
                'registeredUser': performer.registeredUser,
                'roomCreator': performer.roomCreator
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

    def determinePersonality(self):
        feedback = []
        for performer in self.__performers:
            feedback.extend(performer.feedbackLog.get('performerLobbyFeedbackResponse'))
        self.LLMQueryCreator.determinePersonalityFromFeedback(feedback)

    async def initializeGameState(self):
        if not self.__LLMQueryCreator.personality:
            self.determinePersonality()
        self.setStartTime()

        groupPrompt = self.LLMQueryCreator.getFirstPrompt(self)
        await self.getPerformerPrompts(groupPrompt)

        self.gameStatus = "improvise"
        await self.schedulePromptUpdate('groupPrompt')
        await self.schedulePromptUpdate('performerPrompt')

    async def getPerformerPrompts(self, groupPrompt):
        performerPrompts = (self.LLMQueryCreator.getPerformerPrompts(self, groupPrompt))
        # betterPrompts = self.LLMQueryCreator.instrumentCheck(self.gameStateString, performerPrompts, 'performerPrompt')

        for userId in performerPrompts.keys():
            for performer in self.performers:
                if performer.userId == userId:
                    performer.addAndLogPrompt(performerPrompts[userId], self.getCurrentPerformanceTime())
                    performer.addAndLogPrompt(groupPrompt, self.getCurrentPerformanceTime())
                    if 'endPrompt' in groupPrompt:
                        del performer.currentPrompts['groupPrompt']

        await self.schedulePromptUpdate('performerPrompt')

    #####
    def assignNewPrompts(self, newPrompts):
        for userId, prompt in newPrompts.items():
            for performer in self.__performers:
                if userId == performer.userId:
                    performer.addAndLogPrompt(prompt, self.getCurrentPerformanceTime())

    def updatePrompts(self, userId, newPrompt):
        for performer in self.__performers:
            if userId == performer.userId:
                for title, prompt in newPrompt.items():
                    if prompt:
                        performer.addAndLogPrompt({title: prompt}, self.getCurrentPerformanceTime())

    async def promptReaction(self, currentClient, currentPrompt, currentPromptTitle, reaction):
        currentClient.logPrompt({currentPromptTitle: currentPrompt}, self.getCurrentPerformanceTime(), reaction)
        match reaction:
            case 'moveOn':
                await self.handleMoveOn(currentPrompt, currentPromptTitle, currentClient)
            case 'reject':
                await self.handleRejectedPrompts(currentClient, currentPrompt, currentPromptTitle)
            case _:
                await self.handleMoveOn(currentPrompt, currentPromptTitle, currentClient)

    async def handleMoveOn(self, prompt, promptTitle, currentClient):
        match promptTitle:
            case 'groupPrompt':
                newGroupPrompt = self.LLMQueryCreator.getUpdatedPrompts(self, promptTitle)
                await self.getPerformerPrompts(newGroupPrompt)
                await self.schedulePromptUpdate(promptTitle)
            case 'performerPrompt':
                if len(self.performers) > 0:
                    groupPrompt = self.performers[0].currentPrompts.get('groupPrompt')
                    if groupPrompt:
                        newUserPrompt  = self.LLMQueryCreator.moveOnFromPerformerPrompt(self, currentClient, groupPrompt)
                        currentClient.addAndLogPrompt(newUserPrompt, self.getCurrentPerformanceTime())

    async def handleRejectedPrompts(self, currentClient, prompt, promptTitle):
        match promptTitle:
            case 'groupPrompt':
                newGroupPrompt = self.LLMQueryCreator.rejectGroupPrompt(self)
                await self.getPerformerPrompts(newGroupPrompt)
                await self.schedulePromptUpdate(promptTitle)
            case 'performerPrompt':
                if len(self.performers) > 0:
                    groupPrompt = self.performers[0].currentPrompts.get('groupPrompt')
                    if groupPrompt:
                        updatedPerformerPrompt = self.LLMQueryCreator.rejectPerformerPrompt(self, currentClient, groupPrompt)
                        currentClient.addAndLogPrompt(updatedPerformerPrompt, self.getCurrentPerformanceTime())

    async def schedulePromptUpdate(self, promptTitle):
        try:
            interval = int(self.LLMQueryCreator.getIntervalLength(self.gameStateString(), promptTitle))
            if interval > 60:
                interval = 30
        except ValueError:
            interval = 30
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
        if promptTitle:
            self.__scheduledTasks[promptTitle] = asyncio.create_task(self.updatePrompt(interval, promptTitle))

    async def updatePrompt(self, interval, promptTitle):
        print(f'update {promptTitle} in {interval} seconds')
        await asyncio.sleep(interval)
        newPrompts = self.LLMQueryCreator.getUpdatedPrompts(self, promptTitle)
        if 'groupPrompt' in newPrompts:
            await self.getPerformerPrompts(newPrompts)
        else:
            self.assignNewPrompts(newPrompts)
        response = self.prepareGameStateResponse('newGameState')
        await self.broadcastMessage(response, newPrompts)
        if len(self.__performers) > 0:
            await self.schedulePromptUpdate(promptTitle)
        else:
            print(f"No active connections in room '{self.__roomName}'. Stopping prompt updates.")

    async def endSong(self):
        finalGroupPrompt = self.LLMQueryCreator.getEndSongPrompt(self)
        await self.getPerformerPrompts(finalGroupPrompt)

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
                    self,
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

    def summarizePerformance(self):
        self.getClosingTimeSummary()
        self.createGameLog()
