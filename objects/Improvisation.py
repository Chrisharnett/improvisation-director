from util.timeStamp import timeStamp
from datetime import datetime
import asyncio
import random

class Improvisation:
    def __init__(self, LLMQueryCreator=None, centralTheme=None, startTime=None):
        self.__LLMQueryCreator = LLMQueryCreator
        self.__gameStatus = 'Waiting To Start'
        self.__gameLog = {}
        self.__summary = None
        self.__startTime = startTime
        self.__centralTheme = centralTheme

    @property
    def LLMQueryCreator(self):
        return self.__LLMQueryCreator

    @LLMQueryCreator.setter
    def LLMQueryCreator(self, LLMQueryCreator):
        self.__LLMQueryCreator = LLMQueryCreator

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
    def centralTheme(self):
        return self.__centralTheme

    @centralTheme.setter
    def centralTheme(self, centralTheme):
        self.__centralTheme = centralTheme

    def assignNewPrompts(self, newPrompts, performers):
        for userId, prompt in newPrompts.items():
            for performer in performers:
                if userId == performer.userId:
                    performer.addAndLogPrompt(prompt, self.getCurrentPerformanceTime())

    def gameStateString(self, performers):
        string = ""
        if self.__centralTheme:
            string += f"The central theme of this improvisation is {self.__centralTheme}. "
        string += self.getPerformerStrings(performers)
        promptString = self.getSortedPromptString(performers)
        if promptString:
            string += f"Here's the sequence of prompts and reactions so far. {promptString}"
        return string

    def getCentralTheme(self):
        self.__centralTheme = self.LLMQueryCreator.getCentralTheme(self)
        return self.__centralTheme

    def getCurrentPerformanceTime(self):
        if self.__startTime:
            start = datetime.fromisoformat(self.__startTime)
            currentTime = datetime.now()
            elapsed = currentTime - start
            return round(elapsed.total_seconds(), 2)
        else:
            return 'Start time not set.'

    async def getPerformerPrompts(self, groupPrompt, room):
        performerPrompts = self.LLMQueryCreator.createPerformerPrompts(self, groupPrompt)
        for userId in performerPrompts.keys():
            for performer in room.performers:
                if performer.userId == userId:
                    performer.addAndLogPrompt(performerPrompts[userId], self.getCurrentPerformanceTime())
                    performer.addAndLogPrompt(groupPrompt, self.getCurrentPerformanceTime())
                    if 'endPrompt' in groupPrompt:
                        if performer.currentPrompts.get('groupPrompt'):
                            del performer.currentPrompts['groupPrompt']
        if 'endPrompt' not in groupPrompt:
            await self.schedulePromptUpdate('performerPrompt', room)
        return

    @staticmethod
    def getSortedPromptList(performers):
        prompts = []
        for performer in performers:
            for prompt in performer.promptHistory:
                prompts.append(prompt)
        return sorted(prompts, key=lambda x: x['timeStamp'])

    def getSortedPromptString(self, performers):
        sortedPrompts = self.getSortedPromptList(performers)
        string = ""
        for i, prompt in enumerate(sortedPrompts):
            timestamp = prompt.get('timeStamp')
            promptTitle = prompt.get('promptTitle')
            currentPrompt = prompt.get('prompt')
            reaction = prompt.get('reaction')
            userId = prompt.get('userId')
            string += f"Prompt {i+1}. Seconds elapsed: {timestamp} . Title: {promptTitle}"
            if promptTitle == "performerPrompt" or reaction:
                string += f"User: {userId}. "
            string += f"Prompt:  {currentPrompt}. "
            string += f"Performer reaction: {reaction}. " if reaction else ""
        return string or None

    @staticmethod
    def getPerformerStrings(performers):
        performersString = "This performance features the following performers. "
        for performer in performers:
            performersString += performer.performerString()
        return performersString

    async def initializeGameState(self, room):
        self.setStartTime()
        groupPrompt = self.LLMQueryCreator.getFirstPrompt(self)
        await self.getPerformerPrompts(groupPrompt, room.performers)
        self.gameStatus = "improvise"
        await self.schedulePromptUpdate('groupPrompt', room)

    def refineTheme(self):
        newTheme = self.LLMQueryCreator.getNewTheme(self)
        self.__centralTheme = newTheme
        return self.centralTheme

    def setStartTime(self):
        if not self.__startTime:
            self.__startTime = timeStamp()
            return 0
        else:
            return 'Start time already set.'

    async def schedulePromptUpdate(self, promptTitle, room):
        try:
            interval = int(self.LLMQueryCreator.getIntervalLength(self.gameStateString(room.performers), promptTitle))
            # if interval > 120:
            #     interval = random.randint(45, 300)
        except ValueError:
            interval = random.randint(45, 300)
        if promptTitle in room.__scheduledTasks:
            existingTask = room.__scheduledTasks[promptTitle]
            if not existingTask.done():
                existingTask.cancel()
            try:
                await existingTask
            except asyncio.CancelledError:
                pass
            except Exception as e:
                print(f'Error: {e}')
        if promptTitle:
            room.__scheduledTasks[promptTitle] = asyncio.create_task(self.updatePrompt(interval, promptTitle, room))

    async def updatePrompt(self, interval, promptTitle, room):
        print(f'update {promptTitle} in {interval} seconds')
        await asyncio.sleep(interval)
        if 'endSong' != self.gameStatus:
            newPrompts = await self.LLMQueryCreator.getUpdatedPrompts(self, promptTitle)
            if 'groupPrompt' in newPrompts:
                await self.getPerformerPrompts(newPrompts, room)
            else:
                self.assignNewPrompts(newPrompts, room.performers)
            response = room.prepareGameStateResponse('newGameState')
            await room.handleResponse(response)
            if len(room.__performers) > 0:
                await self.schedulePromptUpdate(promptTitle, room)
            else:
                print(f"No active connections in room '{room.roomName}'. Stopping prompt updates.")