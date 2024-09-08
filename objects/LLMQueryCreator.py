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

    def promptContext(self, room, feedback=""):
        prompt_context = f'Your general guidelines: {self.promptGuidelines} '
        prompt_context += f'Context from past performances: {self.context}'
        prompt_context += f'Gamestate: {room.gameStateString()}'
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

    def postPerformancePerformerFeedback(self, gameStateString, feedbackLogs, userId):
        questionNumber = len(feedbackLogs) + 1
        prompt = self.promptScripts['postPerformanceFeedback']
        prompt += f"Final gameState: {gameStateString}"
        prompt += f"Please create question {questionNumber} for userId {userId} "
        return self.openAIConnector.getResponseFromLLM(prompt)

    def gettingToKnowYou(self):
        prompt = self.promptGuidelines + self.promptScripts['gettingToKnowYou']
        return self.openAIConnector.userOptionFeedback(prompt)

    def getNewCurrentPrompt(self, currentRoom):
        promptTitle = 'currentPrompt'
        prompt = self.promptContext(currentRoom) + self.promptScripts['getNewCurrentPrompt']
        endPrompt = self.promptContext(currentRoom) + \
                    'Based on past performances and the current gameState, Do you think this performance is ready to end. Respond with only yes or no.'
        endSong = self.openAIConnector.getResponseFromLLM(endPrompt)
        if endSong == 'yes':
            return endSong(currentRoom)
        newPrompts = self.openAIConnector.getPrompts(prompt, promptTitle)
        return self.instrumentCheck(currentRoom.gameStateString, newPrompts, promptTitle)

    def getNewHarmonyAndMeterPrompt(self, gameStateString):
        promptTitle = 'harmonyAndMeterPrompt'
        prompt = self.promptGuidelines + self.context + self.promptScripts['getNewHarmonyAndMeterPrompt']
        prompt += f"Current gameState: {gameStateString}"
        newPrompts = self.openAIConnector.getPrompts(prompt, promptTitle)
        return self.instrumentCheck(gameStateString, newPrompts, promptTitle)

    def getIntervalLength(self, gameStateString, promptTitle):
        prompt = self.promptGuidelines + self.context
        prompt += f"Current gameState: {gameStateString}"
        prompt += (
            f'Determine the time interval until you will be asked to replace the {promptTitle} in the Gamestate. '
            f'Use context from previous performances and the current gamestate to determine your response. '
            f'The response must be only an integer representing the number of seconds until the specified prompt is replaced. '
            f'Example responses are 5, 344, or 78. '
            f'Please provide only an integer as the answer.'
        )
        return self.openAIConnector.getResponseFromLLM(prompt)

    def getStartingPerformerPrompts(self, currentRoom):
        lobbyFeedback = []
        for performer in currentRoom.performers:
            feedback = performer.feedbackLog.get('performerLobbyFeedbackResponse')
            if feedback:
                lobbyFeedback.extend(feedback)

        prompt = self.promptContext(currentRoom, lobbyFeedback) + self.promptScripts['getStartingCurrentPrompts']
        currentPrompts = self.openAIConnector.getPrompts(prompt, 'currentPrompt')
        startingPrompts = self.instrumentCheck(currentRoom.gameStateString(), currentPrompts, 'currentPrompt')

        prompt = self.promptContext(currentRoom, lobbyFeedback) + self.promptScripts['getHarmonyAndMeterPrompt']
        harmonyAndMeterPrompts = self.openAIConnector.getPrompts(prompt, 'harmonyAndMeterPrompt')
        checkedPrompts = self.instrumentCheck(currentRoom.gameStateString(), harmonyAndMeterPrompts, 'harmonyAndMeterPrompt')

        for startingUserId, startingPromptData in startingPrompts.items():
            for userId, promptData in harmonyAndMeterPrompts.items():
                if startingUserId == userId:
                    startingPrompts[userId]['harmonyAndMeterPrompt'] = checkedPrompts[userId]['harmonyAndMeterPrompt']

        for userId, prompts in startingPrompts.items():
            for performer in currentRoom.performers:
                if performer.userId == userId:
                    for key, value in prompts.items():
                        performer.addAndLogPrompt({key: value})

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
        prompt = (
            'You are the director of a group performing a musical improvisation.'
            + 'You direct the group by providing prompts to inspire their performance '
            + 'and shape the overall structure, texture and mood of the improvisation.'
            + f"A musician has walked into the studio. Welcome them. "
            + f"Introduce yourself if you like, you can invent your own name. "
            + f"They have the option to join a performance or create a new performance, present that option to them."
        )
        return self.openAIConnector.getResponseFromLLM(prompt)

    def whatsYourName(self):
        prompt = 'You are the director of a group performing a musical improvisation.' \
                'You direct the group by providing prompts to inspire their performance ' \
                'and shape the overall structure, texture and mood of the improvisation.' \
                'A new musician has joined. '\
                "Ask the musician what  name you should use to identify them in the performance."
        return self.openAIConnector.getResponseFromLLM(prompt)

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
            prompt += "The instruments they have are: {instrument}. "
        prompt += f"Ask the musician the name of the room the would like to join. "
        return self.openAIConnector.getResponseFromLLM(prompt)