from objects.OpenAIConnector import OpenAIConnector
from util.Dynamo.promptTableClient import PromptTableClient
from util.Dynamo.logTableClient import LogTableClient
from util.Dynamo.connections import getDynamoDbConnection

class LLMQueryCreator:
    def __init__(self):
        self.__dynamoDb = getDynamoDbConnection()
        self.__table = PromptTableClient(self.__dynamoDb)
        self.__logTable = LogTableClient(self.__dynamoDb)
        self.__promptScripts = None  # Lazy loading
        self.__performanceLogs = None
        self.__currentRoomNames = None
        self.__openAIConnector = OpenAIConnector()

    @property
    def promptScripts(self):
        if self.__promptScripts is None:
            self.__promptScripts = self.__table.getAllPromptScripts()
        return self.__promptScripts

    @property
    def promptGuidelines(self):
        return self.promptScripts['promptGuidelines']

    @property
    def promptTitles(self):
        return self.promptScripts['promptTitles']

    @property
    def performanceLogs(self):
        if self.__performanceLogs is None:
            self.__performanceLogs = self.__logTable.getLogs()
        return self.__performanceLogs

    def refreshPerformanceLogs(self):
        self.__performanceLogs = self.__logTable.getLogs()

    @property
    def currentRoomNames(self):
        if self.__currentRoomNames is None:
            self.__currentRoomNames = list(self.performanceLogs.keys()) + ['lobby']
        return self.__currentRoomNames

    @property
    def context(self):
        return f" For context, here is a log of previous performances: {self.performanceLogs}. "

    @property
    def openAIConnector(self):
        return self.__openAIConnector

    def promptContext(self, room, feedback=None):
        prompt_context = f'Your general guidelines: {self.promptGuidelines} '
        prompt_context += f'Context from past performances: {self.context}'
        prompt_context += f'This gamestate describes the current improvisation. It contains user feedback, performer details and prompts, and their reactions. Current GameState: {room.gameStateString()}'
        if feedback:
            prompt_context += f"Here is player feedback. {feedback}. Let it influence the mood of the improvisation as you create prompts."
        return prompt_context

    def endSong(self, currentRoom):
        gameStateString = currentRoom.gameStateString()
        currentRoom.cancelAllTasks()
        prompt = self.promptGuidelines + self.context + self.promptScripts['endSong']
        prompt += f"Current gameState: {gameStateString}"
        endingPrompts = self.openAIConnector.getPrompts(prompt, 'endPrompt')
        editedPrompts = self.instrumentCheck(gameStateString, endingPrompts, 'endPrompt')
        for userId, prompts in editedPrompts.items():
            for performer in currentRoom.performers:
                if performer.userId == userId:
                    for promptTitle, prompt in prompts.items():
                        performer.addAndLogPrompt({promptTitle: prompt})
                        del performer.currentPrompts['groupPrompt']

    def postPerformancePerformerFeedback(self, gameStateString, feedbackLogs, userId):
        questionNumber = len(feedbackLogs) + 1
        prompt = self.promptScripts['postPerformancePerformerFeedback']
        prompt += f"Final gameState: {gameStateString}"
        prompt += f"Please create question {questionNumber} for userId {userId} "
        return self.openAIConnector.getResponseFromLLM(prompt)

    def gettingToKnowYou(self):
        prompt = self.promptGuidelines + self.promptScripts['gettingToKnowYou']
        return self.openAIConnector.userOptionFeedback(prompt)

    def getNewPrompt(self, currentRoom):
        promptTitle = 'currentPrompt'
        prompt = self.promptContext(currentRoom) + self.promptScripts['getNewPrompt']
        endPrompt = self.promptContext(currentRoom) + \
                    'Based on past performances and the current gameState, Do you think this performance is ready to end. Respond with only yes or no.'
        endSong = self.openAIConnector.getResponseFromLLM(endPrompt)
        if endSong == 'yes':
            return endSong(currentRoom)
        newPrompts = self.openAIConnector.getPrompts(prompt, promptTitle)
        return self.instrumentCheck(currentRoom.gameStateString, newPrompts, promptTitle)

    def getIntervalLength(self, gameStateString, promptTitle):
        prompt = self.promptGuidelines + self.context
        prompt += f"Current gameState: {gameStateString}"
        prompt += (
            f"Determine the time interval until the {promptTitle} in the gameState will be replaced. "
            "Use context from previous performances and the current gameState to calculate your response. "
            "Your response should be an integer representing the number of seconds until the specified prompt is replaced. "
            "Example responses include 5, 344, or 78. "
            "Provide only the number in digit format."
            # "It must be less than 5"
        )
        length =  self.openAIConnector.getResponseFromLLM(prompt)
        return length

    def getStartingPerformerPrompt(self, currentRoom):
        lobbyFeedback = []
        for performer in currentRoom.performers:
            feedback = performer.feedbackLog.get('performerLobbyFeedbackResponse')
            if feedback:
                lobbyFeedback.extend(feedback)

        prompt = self.promptContext(currentRoom, lobbyFeedback) + self.promptScripts['getStartingPrompts']
        currentPrompts = self.openAIConnector.getPrompts(prompt, 'currentPrompt')
        startingPrompts = self.instrumentCheck(currentRoom.gameStateString(), currentPrompts, 'currentPrompt')

        for userId, prompts in startingPrompts.items():
            for performer in currentRoom.performers:
                if performer.userId == userId:
                    for key, value in prompts.items():
                        performer.addAndLogPrompt({key: value})

    #####
    def getFirstPrompt(self, currentRoom,):
        prompt = self.promptContext(currentRoom) + self.promptScripts['getFirstGroupPrompt']
        groupPrompt = self.openAIConnector.getGroupPrompt(prompt)
        return groupPrompt

    #####
    def getPerformerPrompts(self, currentRoom, groupPrompt):
        prompt = self.promptContext(currentRoom) + self.promptScripts['getPerformerPrompts']
        prompt += f'The new groupPrompt is {groupPrompt}'
        if 'endPrompt' in groupPrompt:
            prompt += f'This is the final performerPrompt for the performance.'
        performerPrompts = self.openAIConnector.getPrompts(prompt, 'performerPrompt')
        return performerPrompts

    ####
    def updatePerformerPrompts(self, currentRoom, groupPrompt):
        prompt = self.promptContext(currentRoom) + self.promptScripts['updatePerformerPrompts']
        prompt += f'The new groupPrompt is {groupPrompt}'
        performerPrompts = self.openAIConnector.getPrompts(prompt, 'performerPrompt')
        return performerPrompts

    #####
    def getUpdatedPrompts(self,currentRoom, promptTitle):
        endPrompt = self.promptContext(currentRoom) + \
                    'Based on past performances and the current gameState, Do you think this performance is ready to end. Respond with only yes or no.'
        endSong = self.openAIConnector.getResponseFromLLM(endPrompt)
        if endSong == 'yes':
            return endSong(currentRoom)
        prompt = self.promptContext(currentRoom)
        if promptTitle =='groupPrompt':
            prompt += self.promptScripts['updateGroupPrompt']
            return self.openAIConnector.getGroupPrompt(prompt)
        if promptTitle == 'performerPrompt':
            prompt += self.promptScripts['getPerformerPrompts']
            prompt += f"The current groupPrompt is {currentRoom.performers[0].currentPrompts['groupPrompt'] or 'In the gameState'}"
            return self.openAIConnector.getPrompts(prompt, promptTitle)

    #####
    def rejectGroupPrompt(self, currentRoom):
        prompt = self.promptContext(currentRoom) + self.promptScripts['rejectGroupPrompt']
        return self.openAIConnector.getGroupPrompt(prompt)

    #####
    def rejectPerformerPrompt(self, currentClient, currentRoom, groupPrompt):
        prompt = self.promptContext(currentRoom) + self.promptScripts['rejectPerformerPrompt']
        prompt += f"Please create a new performerPrompt for the user with userId {currentClient.userId}." \
                  f"It should support the groupPrompt {groupPrompt}"
        return self.openAIConnector.getSinglePerformerPrompt(prompt)

    #####
    def endSong(self, currentRoom):
        gameStateString = currentRoom.gameStateString()
        currentRoom.cancelAllTasks()
        prompt = self.promptGuidelines + self.context + self.promptScripts['finalGroupPrompt']
        prompt += f"Current gameState: {gameStateString}"
        endingGroupPrompt = self.openAIConnector.getGroupPrompt(prompt)
        return {'endPrompt': endingGroupPrompt['groupPrompt']}

    #TODO: REMOVE
    def replaceRejectedPrompts(self, currentRoom, currentPrompt, currentPromptTitle):
        prompt = self.promptContext(currentRoom)
        prompt += f"Rejected PromptTitle: {currentPromptTitle}. Rejected prompt {currentPrompt}"
        prompt += self.promptScripts['replaceRejectedPrompt']
        if currentPromptTitle == 'harmonyAndMeterPrompt':
            prompt += self.promptScripts['getHarmonyAndMeterPrompt']
        newPrompts = self.openAIConnector.getPrompts(prompt, currentPromptTitle)
        editedPrompts = self.instrumentCheck(currentRoom, newPrompts, currentPromptTitle)
        return editedPrompts

    def instrumentCheck(self, gameState, newPrompts, promptTitle):
        prompt = self.promptGuidelines + self.context + self.promptScripts['instrumentCheck']
        prompt += f"Current gameState: {gameState}"
        prompt += f"New Prompts {newPrompts}"
        return self.openAIConnector.getPrompts(prompt, promptTitle)

    def generateRoomName(self):
        currentRoomNamesStr = ', '.join(self.currentRoomNames)
        prompt = self.promptScripts['generateRoomName']
        prompt += f'The word cannot be in {currentRoomNamesStr}. '
        return self.openAIConnector.getResponseFromLLM(prompt)

    def closingSummary(self, gameStateString):
        prompt = self.promptScripts['closingSummary']
        prompt += f"Final gameState: {gameStateString}"
        return self.openAIConnector.getResponseFromLLM(prompt)

    def getWelcomeMessage(self):
        return self.openAIConnector.getResponseFromLLM(self.promptScripts['wellHelloThere'])

    def whatsYourName(self):
        return self.openAIConnector.getResponseFromLLM(self.promptScripts['whatsYourName'])

    def whatsYourInstrument(self, name=None):
        prompt = 'You are the director of a group performing a musical improvisation.' \
                'You direct the group by providing prompts to inspire their performance ' \
                'and shape the overall structure, texture and mood of the improvisation.' \
                'A new musician has joined. '
        if name:
            prompt += f"Their name is {name}. "
        prompt += f"Ask the musician what instrument or instruments they will play."
        return self.openAIConnector.getResponseFromLLM(prompt)

    def whatsYourRoomName(self, name=None, instrument=None):
        prompt = 'You are the director of a group performing a musical improvisation.' \
                 'You direct the group by providing prompts to inspire their performance ' \
                 'and shape the overall structure, texture and mood of the improvisation.' \
                 'A new musician has joined. '
        if name:
            prompt += f"Their name is {name}. "
        if instrument:
            prompt += f"The instruments they have are: {instrument}. "
        prompt += f"Ask the musician the name of the room the would like to join. "
        return self.openAIConnector.getResponseFromLLM(prompt)

    def announceStart(self, room):
        prompt = "Announce the beginning of the improvisation" \
                 "described below."
        prompt += f"Gamestate: {room.gameStateString}"
        return self.openAIConnector.getResponseFromLLM(prompt)

    def aboutMe(self):
        prompt = self.promptGuidelines + self.promptScripts['aboutMe']
        return self.openAIConnector.getResponseFromLLM(prompt)