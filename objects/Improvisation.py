from util.timeStamp import timeStamp
from objects.Prompt import Prompt
from datetime import datetime
import asyncio
import random

class Improvisation:
    def __init__(self, performers, LLMQueryCreator, room = None, centralTheme=None, startTime=None):
        self.__performers = performers
        self.__LLMQueryCreator = LLMQueryCreator
        self.__room = room
        self.__gameStatus = 'registration'
        self.__gameLog = {}
        self.__summary = None
        self.__startTime = startTime
        self.__prompts = []
        self.__centralTheme = centralTheme
        self.__finalPrompt = False

    @property
    def performers(self):
        return self.__performers

    @performers.setter
    def performers(self, performers):
        self.__performers = performers

    @property
    def LLMQueryCreator(self):
        return self.__LLMQueryCreator

    @LLMQueryCreator.setter
    def LLMQueryCreator(self, LLMQueryCreator):
        self.__LLMQueryCreator = LLMQueryCreator

    @property
    def room(self):
        return self.__room

    @room.setter
    def room(self, room):
        self.__room = room

    @property
    def gameStatus(self):
        return self.__gameStatus

    @gameStatus.setter
    def gameStatus(self, gameStatus):
        self.__gameStatus = gameStatus

    @property
    def gameLog(self):
        return self.__gameLog

    @gameLog.setter
    def gameLog(self, gameLog):
        self.__gameLog = gameLog

    @property
    def summary(self):
        return self.__summary

    @summary.setter
    def summary(self, summary):
        self.__summary = summary

    @property
    def startTime(self):
        return self.__startTime

    @startTime.setter
    def startTime(self, startTime):
        self.__startTime = startTime

    @property
    def prompts(self):
        return self.__prompts

    @prompts.setter
    def prompts(self, groupPrompt):
        self.__prompts = groupPrompt

    @property
    def currentPrompts(self):
        currentPrompt = self.__prompts[-1]
        currentGroupPrompt = currentPrompt.get('groupPrompt')
        currentPerformerPrompts = currentPrompt.get('performerPrompts')
        performerPrompts = []
        for performer in self.performers:
            currentPrompt = next(prompt for prompt in reversed(currentPerformerPrompts) if prompt.get('userId') == performer.userId)
            if currentPrompt:
                performerPrompts.append(currentPrompt)
        return {
            'groupPrompt': currentGroupPrompt,
            'performerPrompts': currentPerformerPrompts
        }

    @property
    def finalPrompt(self):
        return self.__finalPrompt

    @finalPrompt.setter
    def finalPrompt(self, finalPrompt):
        self.__finalPrompt = finalPrompt

    @property
    def centralTheme(self):
        return self.__centralTheme

    @centralTheme.setter
    def centralTheme(self, centralTheme):
        self.__centralTheme = centralTheme

    async def setPromptReaction(self, currentClient, reaction, currentPromptTitle):
        if currentPromptTitle == 'groupPrompt':
            self.currentPrompts[reaction] = [{
                'userId': currentClient.userId,
                'reaction': reaction
            }]
            if 'moveOn' == reaction and 'endSong' != self.gameStatus:
                newPrompts = self.LLMQueryCreator.groupMoveOn(self.room)
                await self.setCurrentPrompts(newPrompts)
            elif 'reject' == reaction and 'endSong' != self.gameStatus:
                newPrompts = self.LLMQueryCreator.groupRejectPrompt(self.room)
                await self.setCurrentPrompts(newPrompts)
            return
        else:
            performerPrompt = next(prompt for prompt in self.currentPrompts.get('performerPrompts') if prompt.get('userId') == currentClient.userId )
            performerPrompt['reaction'] = reaction
            if 'moveOn' == reaction and 'endSong' != self.gameStatus:
                newPrompts = self.LLMQueryCreator.performerMoveOn(self.room, currentClient)
                await self.addPerformerPrompts([newPrompts])
            elif 'reject' == reaction and 'endSong' != self.gameStatus:
                newPrompts = self.LLMQueryCreator.performerRejectPrompt(self.room, currentClient)
                await self.addPerformerPrompts([newPrompts])
            return

    async def setCurrentPrompts(self, currentPrompts):
        newGroupPrompt = currentPrompts.get('groupPrompt')
        interval = currentPrompts.get('groupPromptInterval')
        # interval = 100
        performerPrompts = currentPrompts.get('performerPrompts')
        groupPrompt = Prompt('groupPrompt', newGroupPrompt, interval)
        timestamp = self.getCurrentPerformanceTime()
        currentPrompts = {
            'groupPrompt': groupPrompt,
            'timestamp': timestamp,
            'performerPrompts': []
        }
        if not self.finalPrompt:
            await self.schedulePromptUpdate(groupPrompt)
        print(f"Group Prompt: {groupPrompt}")
        for prompt in performerPrompts:
            interval = prompt.get('promptInterval')
            # interval = 5
            performerPrompt =  Prompt('performerPrompt', prompt.get('performerPrompt'), interval)
            userId = prompt.get('userId')
            currentPrompts['performerPrompts'].append({
                "userId": userId,
                "timestamp": timestamp,
                "performerPrompt": performerPrompt
            })
            if not self.finalPrompt:
                await self.schedulePromptUpdate(performerPrompt, userId)
            print(f"{userId}: {performerPrompt}")
        self.prompts.append(currentPrompts)

    def getPerformerById(self, userId):
        return next(performer for performer in self.performers if performer.userId == userId)

    async def addPerformerPrompts(self, performerPrompts):
        for newPrompt in performerPrompts:
            userId = newPrompt.get('userId')
            prompt = Prompt('performerPrompt', newPrompt.get('performerPrompt'), newPrompt.get('promptInterval'))
            self.currentPrompts['performerPrompts'].append(
                {
                    'userId': userId,
                    'timeStamp': self.getCurrentPerformanceTime(),
                    'performerPrompt': prompt
                })
            print(f"{userId}: {prompt}")
            await self.schedulePromptUpdate(prompt, userId)
        return

    def createGameLog(self, room):
        performers = []
        for performer in self.performers:
            performers.append({
                'userId': performer.userId,
                'instrument': performer.instrument,
                'personality': performer.personality.toDecimalDict()
            })
        self.__gameLog['roomName'] = f"{room.roomName}-{room.songCount}"
        self.__gameLog['performers'] = performers
        self.__gameLog['promptLog'] = self.promptsDict()
        # self.__gameLog['llmPersonality'] = self.__LLMQueryCreator.personality.to_decimalDict()
        self.__gameLog['llmPersonality'] = self.__LLMQueryCreator.personality.personalityString()
        self.__gameLog['centralTheme'] = self.__centralTheme
        self.__gameLog['summary'] = self.__summary

    def currentState(self):
        return {
            'llmPersonality': self.LLMQueryCreator,
            'centralTheme': self.centralTheme,
            'performers': self.performers,
            'prompts': self.prompts
        }

    def currentSystemContext(self):
        context = ""
        if self.LLMQueryCreator.personality:
            context += f"Your musical personality is:  {self.LLMQueryCreator.personality.personalityString()}. "
        if self.performers:
            context += "On stage, ready to performer we have :"
            for i, performer in enumerate(self.performers):
                context += f"{i + 1}: {performer.performerString()} "
            context += "A player can only play one instrument at a time. "
        if self.centralTheme:
            context += f"The central theme for this improvisation is {self.centralTheme}."
        return context

    def currentPromptContext(self):
        if not self.prompts:
            return "The performance has not started, there are no prompts yet."
        context = "Here are the prompts so far in the performance. "
        promptCount = 1
        for prompt in self.prompts:
            time = prompt.get('timestamp')
            gPrompt = prompt.get('groupPrompt').prompt
            context += f'{promptCount}. Time: {time}. Prompt: {gPrompt} .'
            promptCount += 1
            pPromptCount = 1
            for pPrompt in prompt.get('performerPrompts'):
                time = pPrompt.get('timestamp')
                prompt = pPrompt.get('performerPrompt').prompt
                userId = pPrompt.get('userId')
                context += f'{pPromptCount}. Time: {time}. UserId: {userId}. Prompt: {prompt}'
                pPromptCount += 1
        return context

    def getCurrentPerformerPrompt(self, userId):
        if not self.prompts:
            return None
        lastPrompt = self.prompts[-1]
        for performerPrompt in reversed(lastPrompt.get("performerPrompts", [])):
            if performerPrompt.get("userId") == userId:
                return performerPrompt
        return None

    def gameStateString(self):
        string = ""
        if self.__centralTheme:
            string += f"The central theme of this improvisation is {self.__centralTheme}. "
        string += self.currentPerformerContext()
        promptString = self.getSortedPromptString()
        if promptString:
            string += f"Here's the sequence of prompts and reactions so far. {promptString}"
        return string

    def getCentralTheme(self, room):
        self.__centralTheme = self.LLMQueryCreator.getCentralTheme(room)
        return self.__centralTheme

    def getClosingTimeSummary(self, room):
        self.__summary = self.LLMQueryCreator.closingSummary(room)

    def getCurrentPerformanceTime(self):
        if self.__startTime:
            start = datetime.fromisoformat(self.__startTime)
            currentTime = datetime.now()
            elapsed = currentTime - start
            return round(elapsed.total_seconds(), 2)
        else:
            return 'Start time not set.'

    def currentPerformerContext(self):
        performersString = "This performance features the following performers. "
        for performer in self.performers:
            performersString += performer.performerString()
        return performersString

    def initializeImprovDirectorPersonality(self):
        return self.LLMQueryCreator.createYourPersonality(self.room)

    async def initializeGameState(self):
        self.setStartTime()
        await self.setCurrentPrompts(self.LLMQueryCreator.initiatePerformance(self.room))
        self.gameStatus = "improvise"
        return

    async def concludePerformance(self):
        await self.setCurrentPrompts(self.LLMQueryCreator.concludePerformance(self.room))
        self.room.cancelAllTasks()
        self.gameStatus = 'endSong'
        self.finalPrompt = True
        return

    def logEnding(self):
        self.__gameLog['endingTimestamp'] = timeStamp()

    def refineTheme(self, room):
        newTheme = self.LLMQueryCreator.getNewTheme(room, self.centralTheme)
        self.centralTheme = newTheme
        return self.centralTheme

    def setStartTime(self):
        if not self.__startTime:
            self.__startTime = timeStamp()
            return 0
        else:
            return 'Start time already set.'

    async def schedulePromptUpdate(self, prompt, userId=None):
        taskId = prompt.promptTitle
        if userId:
            taskId += userId
        if taskId in self.room.scheduledTasks:
            existingTask = self.room.scheduledTasks[taskId]
            if not existingTask.done():
                existingTask.cancel()
            try:
                await existingTask
            except asyncio.CancelledError:
                pass
            except Exception as e:
                print(f'Error: {e}')
        if taskId:
            self.room.scheduledTasks[taskId] = asyncio.create_task(self.updatePrompt(prompt, userId))

    def summarizePerformance(self, room):
        self.getClosingTimeSummary(room)
        self.createGameLog(room)

    async def updatePrompt(self, prompt, userId):
        promptTitle = prompt.promptTitle
        interval = prompt.promptInterval
        # interval = 5
        print(f'update {promptTitle} in {interval} seconds')
        await asyncio.sleep(int(interval))
        if 'endSong' != self.gameStatus:
            if not userId:
                newPrompts = self.LLMQueryCreator.provideNewPrompts(self.room)
                await self.setCurrentPrompts(newPrompts)
            else:
                currentPerformer = next(performer for performer in self.performers if performer.userId == userId)
                newPrompt = self.LLMQueryCreator.nextPerformerPrompt(self.room, currentPerformer)
                await self.addPerformerPrompts([newPrompt])
            response = self.room.prepareGameStateResponse('newGameState')
            await self.room.handleResponse(response)

    async def adjustPrompts(self):
        newPrompts = self.LLMQueryCreator.provideNewPrompts(self.room)
        await self.setCurrentPrompts(newPrompts)
        return

    def promptsDict(self):
        prompts = []
        for prompt in self.prompts:
            promptToAdd = {'groupPrompt': prompt.get('groupPrompt').toDict(),
                           'performerPrompts': []}
            for pr in prompt.get('performerPrompts'):

                promptToAdd['performerPrompts'].append(pr.get('performerPrompt').toDict(pr.get('userId')))
            prompts.append(promptToAdd)
        return prompts