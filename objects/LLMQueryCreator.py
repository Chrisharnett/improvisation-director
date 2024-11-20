from objects.OpenAIConnector import OpenAIConnector
from util.Dynamo.promptTableClient import PromptTableClient
from util.Dynamo.logTableClient import LogTableClient
from util.Dynamo.connections import getDynamoDbConnection
from objects.Personalities import LLMPersonality
from copy import deepcopy

class LLMQueryCreator:
    def __init__(self):
        self.__dynamoDb = getDynamoDbConnection()
        self.__table = PromptTableClient(self.__dynamoDb)
        self.__logTable = LogTableClient(self.__dynamoDb)
        self.__promptScripts = None
        self.__performanceLogs = None
        self.__currentRoomNames = None
        self.__openAIConnector = OpenAIConnector()
        self.__personality = LLMPersonality()
        self.__centralTheme = None

    @property
    def promptScripts(self):
        if self.__promptScripts is None:
            self.__promptScripts = self.__table.getAllPromptScripts()
        return self.__promptScripts

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

    @property
    def personality(self):
        return self.__personality

    @personality.setter
    def personality(self, personality):
        self.__personality = personality

    def systemContext(self, performers=None, centralTheme=None):
        context = "You are the director of this musical improvisation. "
        if self.__personality:
            context += f"Your musical personality is:  {self.__personality.personalityString()}. "
        if performers:
            context += "On stage, ready to performer we have :"
            for i, performer in enumerate(performers):
                context += f"{i + 1}: {performer.performerString()} "
            context += "A player can only play one instrument at a time. "
        if centralTheme:
            context += f"The central theme for this improvisation is {centralTheme}"
        f'The musicians depend on your prompts to direct and inspire their performance. ' \
        f'A prompt initiates change in the current performance.' \
        f'The prompts you create must be 5-8 words. '
        return context

    def promptContext(self, room):
        prompt_context = room.currentImprovisation.gameStateString()
        return prompt_context

    def postPerformancePerformerFeedback(self, currentRoom, feedbackLogs, userId):
        questionNumber = len(feedbackLogs) + 1
        prompt = self.promptScripts['postPerformancePerformerFeedback'] + self.promptContext(currentRoom)
        prompt += f"Please create question {questionNumber} for userId {userId} "
        return self.openAIConnector.getResponseFromLLM(prompt, self.systemContext())

    def gettingToKnowYou(self):
        prompt = self.promptScripts['gettingToKnowYou']
        return self.openAIConnector.userOptionFeedback(prompt)

    def getIntervalLength(self, gameStateString, promptTitle):
        prompt = f"Current gameState: {gameStateString}"
        prompt += (
            f"Determine the time interval until the {promptTitle} in the gameState will be replaced. "
            "Use context from previous performances and the current gameState to calculate your response. "
            "Your response should be an integer representing the number of seconds until the specified prompt is replaced. "
            "Example responses include 5, 344, or 78. "
            "Provide only the number in digit format."
        )
        length =  self.openAIConnector.getResponseFromLLM(prompt)
        return length

    def attributeChangesString(self, oldPersonality, newPersonality):
        changes = []
        for attr, old_value in oldPersonality.attributes.items():
            new_value = newPersonality.attributes.get(attr, None)
            if new_value is not None:
                changes.append(f"{attr}: ({old_value}) -> ({new_value})")
            else:
                changes.append(f"{attr}: ({old_value}) -> (Not updated)")
        return ", ".join(changes)

    def printPersonalityChanges(self, name, oldPersonality, newPersonality):
        changeSummary = (
            f"{name}"
            f"{self.attributeChangesString(oldPersonality, newPersonality)}\n"
            f"'{oldPersonality.description}'\n'{newPersonality.description}'"
        )
        print(changeSummary)

    # def determineLLMPersonalityFromFeedback(self, feedback=None, performers=None):
    #     prompt = "Create a personality to describe the LLM that will direct this improvisation. " + self.promptScripts['determineLLMPersonality']
    #     oldPersonality = deepcopy(self.personality)
    #     if feedback:
    #         prompt += f'Feedback: {feedback} .'
    #     newPersonality = self.openAIConnector.getResponseFromLLM(prompt, self.systemContext(performers=performers))
    #     self.personality.description = newPersonality
    #     self.printPersonalityChanges('llm', oldPersonality, self.personality)

    def initializeLLMPersonality(self, performers):
        prompt = "Based on the performers in this improvisation, suggest values for the llm personality attributes in this improvisation. " \
                 "The values should attempt to work with the performers in this performance, " \
                 "with perhaps one or 2 values different to create interest. "
        oldPersonality = deepcopy(self.personality)
        personality = self.openAIConnector.getInitialLLMPersonalityAttributes(prompt, self.personality, self.systemContext(performers))
        prompt = "Based on the performers in the improvisation and the initial attribute scores in the LLM, " + self.promptScripts['determineLLMPersonality']
        newPersonality = self.openAIConnector.getResponseFromLLM((prompt), self.systemContext(performers))
        self.personality.description = newPersonality
        self.printPersonalityChanges('llm', oldPersonality, self.personality)
        return

    def adjustLLMPersonality(self, performers, feedbackString):
        oldPersonality = deepcopy(self.personality)
        prompt = f"{feedbackString}. Based on the feedback given, revise the personality that describes this llm to better lead this improvisation."
        self.openAIConnector.adjustPersonalityScores(prompt, self.personality, "llm", self.systemContext(performers=performers))
        newPersonality = self.openAIConnector.getResponseFromLLM((prompt + self.promptScripts['determineLLMPersonality']), self.systemContext(performers=performers))
        self.personality.description = newPersonality
        self.printPersonalityChanges('llm', oldPersonality, self.personality)
        return

    def getNewLLMPersonality(self, performers):
        prompt=f"Create a different, contrasting, personality to guide the next performance. "
        originalContext = self.systemContext(performers)
        originalPersonality = deepcopy(self.personality)
        self.openAIConnector.adjustPersonalityScores(prompt, originalPersonality, "llm", originalContext)
        prompt = f"These are the attributes of the next musical director {self.personality.attributeString()}. " \
                 f"Create a description of this new personality. {self.promptScripts['determineLLMPersonality']}"
        newPersonality = self.openAIConnector.getResponseFromLLM(prompt, originalContext)
        self.personality.description = newPersonality
        self.printPersonalityChanges('llm', originalPersonality, self.personality)
        return

    def processPerformerFeedback(self, performer, centralTheme=None, feedback=False, themeResponse=None):
        prompt = f"{performer.performerString()} "
        if feedback:
            prompt += f"This is feedback from this player of their preferred prompt choices. Feedback: {performer.feedbackString}. "
        if centralTheme and themeResponse:
            prompt += f"The suggested central theme is {centralTheme}. "
            reaction = themeResponse.get('reaction')
            prompt += f"The performer {reaction} the central Theme."
            suggestion = themeResponse.get('suggestion')
            if suggestion:
                prompt += f"The performer has this suggestion for the theme. {suggestion}. "
        return prompt

    def getPerformerPersonality(self, performer, feedbackString):
        oldPersonality = deepcopy(performer.personality)
        self.updatePerformerAttributes(performer, feedbackString)
        prompt = self.processPerformerFeedback(performer, feedbackString)
        prompt += self.promptScripts['getPerformerPersonality']
        performerPersonality = self.openAIConnector.getResponseFromLLM(prompt, self.systemContext())
        performer.personality.description = performerPersonality
        self.printPersonalityChanges(performer.screenName, oldPersonality, performer.personality)

        return performerPersonality

    def updatePerformerPersonality(self, performer, feedbackString):
        oldPersonality = deepcopy(performer.personality)
        self.updatePerformerAttributes(performer, feedbackString)
        # prompt = self.processPerformerFeedback(performer, centralTheme, feedback, themeResponse)
        prompt = feedbackString if feedbackString else ""
        prompt += self.promptScripts['updatePerformerPersonality']
        performerPersonality = self.openAIConnector.getResponseFromLLM(prompt, self.systemContext())
        performer.personality.description = performerPersonality
        self.printPersonalityChanges(performer.screenName, oldPersonality, performer.personality)
        return performerPersonality

    def updatePerformerAttributes(self, performer, feedbackString):
        # prompt = self.processPerformerFeedback(performer, centralTheme, feedback, themeResponse)
        systemContext = performer.personality.personalityAttributesContext()
        prompt = f"Current performers values: {feedbackString}. Based on the performer responses given and the current attribute scores," \
                "suggest adjustments for each performer attributes attribute"
        context = self.systemContext() + performer.personality.personalityAttributesContext()
        adjustedScores = self.openAIConnector.adjustPersonalityScores(prompt, performer.personality, 'performer', context)

    def postPerformanceUpdatePerformerPersonality(self, performer):
        prompt = (f"{performer.performerString()}"
                  f"This performer has just completed a performance."
                  f"Analyze the performance and the feedback."
                  f"Notice the prompts the userId liked or rejected during the performance."
                  f"Note the following pre and post performance feedback. {performer.feedbackString()}"
                  f"Create an updated personality description for the performer based on this new data.")
        self.updatePerformerAttributes(performer, performer.feedbackString())
        performerPersonality = self.openAIConnector.getResponseFromLLM(prompt)
        performer.personality.description = performerPersonality

    def getFirstPrompt(self, currentRoom,):
        prompt = self.promptContext(currentRoom)
        prompt += self.promptScripts['getFirstPrompt']
        groupPrompt = self.openAIConnector.getGroupPrompt(prompt, self.systemContext(currentRoom.performers))
        return groupPrompt

    def createPerformerPrompts(self, currentRoom, groupPrompt):
        prompt = self.promptContext(currentRoom)
        prompt += self.promptScripts['getPerformerPrompts']
        prompt += f'The new groupPrompt is {groupPrompt}'
        possibleEndPrompt = groupPrompt.get('endPrompt')
        if possibleEndPrompt:
            prompt += f'This is the final performerPrompt for the performance.'
        performerPrompts = self.openAIConnector.getPrompts(prompt, 'performerPrompt', self.systemContext(currentRoom.performers))
        return performerPrompts

    def updatePerformerPrompts(self, currentRoom, groupPrompt):
        prompt = self.promptContext(currentRoom) + self.promptScripts['updatePerformerPrompts']
        prompt += f'The new groupPrompt is {groupPrompt}'
        performerPrompts = self.openAIConnector.getPrompts(prompt, 'performerPrompt', self.systemContext(currentRoom.performers))
        return performerPrompts

    async def getUpdatedPrompts(self,currentRoom, promptTitle):
        endPrompt = self.promptContext(currentRoom) + \
                    'Based on past performances and the current gameState, Do you think this performance is ready to end. Respond with only yes or no.'
        endSong = self.openAIConnector.getResponseFromLLM(endPrompt, self.systemContext(currentRoom.performers))
        if endSong == 'yes':
            return 'endSong'
        prompt = self.promptContext(currentRoom)
        if promptTitle =='groupPrompt':
            prompt += self.promptScripts['updateGroupPrompt']
            return self.openAIConnector.getGroupPrompt(prompt, self.systemContext(currentRoom.performers))
        if promptTitle == 'performerPrompt':
            prompt += self.promptScripts['getPerformerPrompts']
            prompt += f"The current groupPrompt is {currentRoom.performers[0].currentPrompts['groupPrompt'] or 'In the gameState'}"
            return self.openAIConnector.getPrompts(prompt, promptTitle, self.systemContext(currentRoom.performers))

    def rejectGroupPrompt(self, currentRoom):
        prompt = self.promptContext(currentRoom) + self.promptScripts['rejectGroupPrompt']
        return self.openAIConnector.getGroupPrompt(prompt, self.systemContext(currentRoom.performers))

    def rejectPerformerPrompt(self, currentRoom, currentClient, groupPrompt):
        prompt = self.promptContext(currentRoom) + self.promptScripts['rejectPerformerPrompt']
        prompt += f"Please create a new performerPrompt for the user with userId {currentClient.userId}." \
                  f"It should support the following groupPrompt {groupPrompt}"
        return self.openAIConnector.getSinglePerformerPrompt(prompt, self.systemContext(currentRoom.performers))

    def moveOnFromPerformerPrompt(self, currentRoom, currentClient, groupPrompt):
        prompt = self.promptContext(currentRoom)
        prompt += "The performer indicated would like a new performerPrompt."
        prompt += f"Please create a new performerPrompt for the user with userId {currentClient.userId}." \
                  f"It should support the following groupPrompt {groupPrompt}." \
                  f"Provide a new, different performerPrompt for this user."
        return self.openAIConnector.getSinglePerformerPrompt(prompt, self.systemContext(currentRoom.performers))

    def getEndSongPrompt(self, currentRoom):
        currentRoom.cancelAllTasks()
        prompt = self.promptContext(currentRoom) + self.promptScripts['finalGroupPrompt']
        endingGroupPrompt = self.openAIConnector.getGroupPrompt(prompt, self.systemContext(currentRoom.performers))
        return {'endPrompt': endingGroupPrompt['groupPrompt']}

    def generateRoomName(self):
        roomNames = {roomName.split('-')[0] for roomName in self.currentRoomNames}
        currentRoomNamesStr = ', '.join(roomNames)
        prompt = self.promptScripts['generateRoomName']
        prompt += f'The word cannot be in {currentRoomNamesStr}. '
        return self.openAIConnector.getResponseFromLLM(prompt)

    def closingSummary(self, currentRoom):
        prompt = self.promptScripts['closingSummary']
        prompt += self.promptContext(currentRoom)
        return self.openAIConnector.getResponseFromLLM(prompt, self.systemContext())

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

    def getPastThemes(self, room):
        pastThemes = ""
        for i, improvisation in enumerate(room.improvisations):
            pastThemes += f"Theme {i + 1}: {improvisation.centralTheme}"
        return (f"This performance has already explored these themes. "
                f"The new theme must try something new. {pastThemes}.")

    def getCentralTheme(self, room):
            prompt = self.promptScripts['getCentralTheme']
            if room.songCount > 1:
                prompt += self.getPastThemes(room)
            return self.openAIConnector.getResponseFromLLM(prompt, self.systemContext(room.performers))

    def getNewTheme(self, room, centralTheme):
        prompt = f'Performers have responded to the suggested central theme of "{centralTheme}"'
        prompt += f'The performers responses: {room.themeResponseString()}'
        newPersonality = self.adjustLLMPersonality(room.performers, prompt)
        if room.songCount > 1:
            prompt += self.getPastThemes(room)
        prompt += self.promptScripts['tryNewCentralTheme']
        return self.openAIConnector.getResponseFromLLM(prompt, self.systemContext(room.performers, centralTheme))

    def announceStart(self, room):
        prompt = "You will start the improvisation and provide the initial prompts soon. " \
                 "Make a brief welcome announcement to get everyone's attention. " \
                 "Make them aware we are about to start."
        prompt += self.promptContext(room)
        # return self.openAIConnector.getResponseFromLLM(prompt, self.systemContext(room))
        return "Just getting things ready. One Moment. "

    def aboutMe(self):
        prompt = self.promptScripts['aboutMe']
        return self.openAIConnector.getResponseFromLLM(prompt)