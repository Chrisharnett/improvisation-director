from util.timeStamp import timeStamp
from datetime import datetime
import asyncio
import random

class Improvisation:
    def __init__(self, performers, LLMQueryCreator, centralTheme=None, startTime=None):
        self.__LLMQueryCreator = LLMQueryCreator
        self.__performers = performers
        self.__gameStatus = 'Waiting To Start'
        self.__gameLog = {}
        self.__summary = None
        self.__startTime = startTime
        self.__centralTheme = centralTheme

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

    def assignNewPrompts(self, newPrompts):
        for userId, prompt in newPrompts.items():
            for performer in self.performers:
                if userId == performer.userId:
                    performer.addAndLogPrompt(prompt, self.getCurrentPerformanceTime())

    def createGameLog(self, room):
        performers = []
        for performer in self.performers:
            if performer.registeredUser:
                self.LLMQueryCreator.postPerformanceUpdatePerformerPersonality(performer)
            performers.append({
                'userId': performer.userId,
                'instrument': performer.instrument,
                'personality': performer.personality.to_decimalDict()
            })

        self.__gameLog['roomName'] = f"{room.roomName}-{room.songCount}"
        self.__gameLog['performers'] = performers
        self.__gameLog['promptLog'] = self.getSortedPromptList()
        self.__gameLog['llmPersonality'] = self.__LLMQueryCreator.personality.to_decimalDict()
        self.__gameLog['centralTheme'] = self.__centralTheme
        self.__gameLog['summary'] = self.__summary

    # async def endSong(self):
    #     finalGroupPrompt = self.LLMQueryCreator.getEndSongPrompt(self)
    #     await self.getPerformerPrompts(finalGroupPrompt)
    #     self.gameStatus = 'endSong'
    #     # return finalGroupPrompt
    #     return

    def gameStateString(self):
        string = ""
        if self.__centralTheme:
            string += f"The central theme of this improvisation is {self.__centralTheme}. "
        string += self.getPerformerStrings()
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

    async def getPerformerPrompts(self, groupPrompt, room):
        performerPrompts = self.LLMQueryCreator.createPerformerPrompts(room, groupPrompt)
        for userId in performerPrompts.keys():
            for performer in self.performers:
                if performer.userId == userId:
                    performer.addAndLogPrompt(performerPrompts[userId], self.getCurrentPerformanceTime())
                    performer.addAndLogPrompt(groupPrompt, self.getCurrentPerformanceTime())
                    if 'endPrompt' in groupPrompt:
                        if performer.currentPrompts.get('groupPrompt'):
                            del performer.currentPrompts['groupPrompt']
        if 'endPrompt' not in groupPrompt:
            await self.schedulePromptUpdate('performerPrompt', room)
        return


    def getPerformerStrings(self):
        performersString = "This performance features the following performers. "
        for performer in self.performers:
            performersString += performer.performerString()
        return performersString

    def getSortedPromptList(self):
        prompts = []
        for performer in self.performers:
            for prompt in performer.promptHistory:
                prompts.append(prompt)
        return sorted(prompts, key=lambda x: x['timeStamp'])

    def getSortedPromptString(self):
        sortedPrompts = self.getSortedPromptList()
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

    async def initializeGameState(self, room):
        self.setStartTime()
        groupPrompt = self.LLMQueryCreator.getFirstPrompt(room)
        await self.getPerformerPrompts(groupPrompt, room)
        self.gameStatus = "improvise"
        await self.schedulePromptUpdate('groupPrompt', room)

    def logEnding(self):
        self.__gameLog['endingTimestamp'] = timeStamp()

    def refineTheme(self, room):
        newTheme = self.LLMQueryCreator.getNewTheme(room, self.centralTheme)
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
            interval = int(self.LLMQueryCreator.getIntervalLength(self.gameStateString(), promptTitle))
            # if interval > 120:
            #     interval = random.randint(45, 300)
        except ValueError:
            interval = random.randint(45, 300)
        if promptTitle in room.scheduledTasks:
            existingTask = room.scheduledTasks[promptTitle]
            if not existingTask.done():
                existingTask.cancel()
            try:
                await existingTask
            except asyncio.CancelledError:
                pass
            except Exception as e:
                print(f'Error: {e}')
        if promptTitle:
            room.scheduledTasks[promptTitle] = asyncio.create_task(self.updatePrompt(interval, promptTitle, room))

    def summarizePerformance(self, room):
        self.getClosingTimeSummary(room)
        self.createGameLog(room)

    async def updatePrompt(self, interval, promptTitle, room):
        print(f'update {promptTitle} in {interval} seconds')
        await asyncio.sleep(interval)
        if 'endSong' != self.gameStatus:
            newPrompts = await self.LLMQueryCreator.getUpdatedPrompts(room, promptTitle)
            if 'groupPrompt' in newPrompts:
                await self.getPerformerPrompts(newPrompts, room)
            else:
                self.assignNewPrompts(newPrompts)
            response = room.prepareGameStateResponse('newGameState')
            await room.handleResponse(response)
            if len(self.performers) > 0:
                await self.schedulePromptUpdate(promptTitle, room)
            else:
                print(f"No active connections in room '{room.roomName}'. Stopping prompt updates.")