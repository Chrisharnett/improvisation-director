from objects.OpenAIConnector import OpenAIConnector
from util.Dynamo.promptTableClient import PromptTableClient
from util.Dynamo.logTableClient import LogTableClient
from util.Dynamo.connections import getDynamoDbConnection

class LLMQueryCreator:
    def __init__(self):
        self.__dynamoDb = getDynamoDbConnection()
        self.__table = PromptTableClient(self.__dynamoDb)
        self.__logTable = LogTableClient(self.__dynamoDb)
        self.__promptScripts = None
        self.__performanceLogs = None
        self.__currentRoomNames = None
        self.__openAIConnector = OpenAIConnector()
        self.__personality = None

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

    def systemContext(self, room=None):
        context = "You are the director of this musical improvisation. "
        if self.__personality:
            context += f" {self.__personality}. "
        if room:
            context += "The performers in the room are :"
            for i, performer in enumerate(room.performers):
                context += f"Performer {i + 1}: {performer.performerString()} "
            context += "A player can only play one instrument at a time. "
        return context

    # TODO: MOVE TO PROMPTSCRIPTS
    def promptContext(self, room):
        prompt_context = f'You are the director of musical improvisations. ' \
                         f'The musicians depend on your prompts to direct their performance. ' \
                         f'A prompt encourages a change in the current performance.' \
                         f'The prompts you create must be 10 words or less. {room.gameStateString()}'
        return prompt_context

    def postPerformancePerformerFeedback(self, currentRoom, feedbackLogs, userId):
        questionNumber = len(feedbackLogs) + 1
        prompt = self.promptScripts['postPerformancePerformerFeedback'] + self.promptContext(currentRoom)
        prompt += f"Please create question {questionNumber} for userId {userId} "
        return self.openAIConnector.getResponseFromLLM(prompt, self.systemContext())

    # TODO: MOVE TO PROMPTSCRIPTS
    def gettingToKnowYou(self):
        prompt = ("Musical improvisers are ready to begin. Provide two contrasting musical prompts. "
                 "Provide prompts from contrasting musical personalities in the indicated format. "
                "Examples of musical personalities include directors who:"
                " prefer prompts in the style of Brian Eno's Oblique Strategies,"
                " or gives specific musical instructions, "
                "or focuses on changing the instrument combinations/textures, "
                "or prefer traditional music composition styles,"
                "or prefer popular music composition styles,"
                "or prefer innovative music composition styles." 
                  "Ask the player to choose their preferred option."
                  "Each options must include only the prompt, do not state the personality.")
        return self.openAIConnector.userOptionFeedback(prompt)

    # TODO: MOVE TO PROMPTSCRIPTS
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

    # TODO: MOVE TO PROMPTSCRIPTS
    def determineLLMPersonalityFromFeedback(self, feedback):
        feedbackText = ("This initial feedback indicates prompt preferences for a group of performers. " \
                        "Create a personality to describe the improvDirector's approach to this performance. " \
                        "The personality should describe the type of improvDirector that would best work with these performers. " \
                        "It should create a complete sentence structured like this: 'As improvDirector you <<musical style>> and focus on <<composition approach>>'." \
                        " Examples: 'As improvDirector you favor electronic textures and focus on adventurous, non-linear compositions.',"
                        "'As improvDirector, you favor switching instrumentation and focus on who is playing at a given moment. '"
                        " Feedback:\n")

        if feedback:
            for i, response in enumerate(feedback):
                question = response.get('question')
                optionList = question.get('options')
                options = ""
                if optionList:
                    for j, option in enumerate(optionList):
                        options += f"{j+1}. {option}"
                feedbackText += f"{i + 1}. Question: \'{question.get('question')}\" Options: \"{options}\" Preference: {response.get('response')})\n"
        else :
            feedbackText += "Performers did not provide feedback, choose a random personality. "
        newPersonality = self.openAIConnector.getResponseFromLLM(feedbackText, self.systemContext())
        self.__personality = newPersonality

    # TODO: MOVE TO PROMPTSCRIPTS
    def getPerformerPersonality(self, performer):
        # Explore creating specific attributes at a later time for ratings. i.e adventurous, technical skill, etc.
        prompt = (f"{performer.performerString()} "
                 f"This is feedback from a player of their preferred prompt choices. Feedback: {performer.feedbackString}. "
                  f"Create a personality to describe the musical and creative approach preferred by this performer. "
                  f"The description should be about 10 words long. It is meant to help the improvDirector tailor it's prompts to the user."
                  f"Do not invent facts."
                  f"Examples:"
                  f"'A guitar player who uses pedals to create spacey atmospheres and likes ambient music. "
                  f"'A harp player that specializes in atonal performance. The enjoy specific musical directions. "
                  f"'A woodwind player that switches between flute and saxophone. He likes electronic music and abstract prompts.")
        performerPersonality = self.openAIConnector.getResponseFromLLM(prompt)
        performer.personality = performerPersonality

    # TODO: MOVE TO PROMPTSCRIPTS
    def updatePerformerPersonality(self, performer):
        prompt = (f"{performer.performerString()}"
                  f"This performer has just completed a performance."
                  f"Analyze the performance and the feedback."
                  f"Notice the prompts the userId liked or rejected during the performance."
                  f"Note the following pre and post performance feedback. {performer.feedbackString()}"
                  f"Create an updated personality description for the performer based on this new data.")
        performerPersonality = self.openAIConnector.getResponseFromLLM(prompt)
        performer.personality = performerPersonality

    # TODO: MOVE TO PROMPTSCRIPTS
    def getFirstPrompt(self, currentRoom,):
        prompt = self.promptContext(currentRoom)
        prompt += "Your task is to generate a groupPrompt " \
                  "to initiate this performance. "  \
                  "Optionally include key and style or meter information. "
        groupPrompt = self.openAIConnector.getGroupPrompt(prompt, self.systemContext(currentRoom))
        return groupPrompt

    # TODO: MOVE TO PROMPTSCRIPTS
    def getPerformerPrompts(self, currentRoom, groupPrompt):
        prompt = self.promptContext(currentRoom)
        prompt += ("Review the current gameState and create new performerPrompts for each userId in the current performance. "
                   "The prompts should: Be personalized based on user preferences and performance details; "
                   "Align with the overall groupPrompt: "
                   "Encourage a change in the performance/music:"
                   "Build on past feedback, musical ideas, and advancing the improvisation;"
                   "Include specific instructions for performers' instruments and techniques;"
                   "Ensure all prompts are musically coherent with one another.")
        prompt += f'The new groupPrompt is {groupPrompt}'
        if 'endPrompt' in groupPrompt:
            prompt += f'This is the final performerPrompt for the performance.'
        performerPrompts = self.openAIConnector.getPrompts(prompt, 'performerPrompt', self.systemContext(currentRoom))
        return performerPrompts

    def updatePerformerPrompts(self, currentRoom, groupPrompt):
        prompt = self.promptContext(currentRoom) + self.promptScripts['updatePerformerPrompts']
        prompt += f'The new groupPrompt is {groupPrompt}'
        performerPrompts = self.openAIConnector.getPrompts(prompt, 'performerPrompt', self.systemContext(currentRoom))
        return performerPrompts

    def getUpdatedPrompts(self,currentRoom, promptTitle):
        endPrompt = self.promptContext(currentRoom) + \
                    'Based on past performances and the current gameState, Do you think this performance is ready to end. Respond with only yes or no.'
        endSong = self.openAIConnector.getResponseFromLLM(endPrompt, self.systemContext(currentRoom))
        if endSong == 'yes':
            return currentRoom.endSong()
        prompt = self.promptContext(currentRoom)
        if promptTitle =='groupPrompt':
            prompt += self.promptScripts['updateGroupPrompt']
            return self.openAIConnector.getGroupPrompt(prompt, self.systemContext(currentRoom))
        if promptTitle == 'performerPrompt':
            prompt += self.promptScripts['getPerformerPrompts']
            prompt += f"The current groupPrompt is {currentRoom.performers[0].currentPrompts['groupPrompt'] or 'In the gameState'}"
            return self.openAIConnector.getPrompts(prompt, promptTitle, self.systemContext(currentRoom))

    def rejectGroupPrompt(self, currentRoom):
        prompt = self.promptContext(currentRoom) + self.promptScripts['rejectGroupPrompt']
        return self.openAIConnector.getGroupPrompt(prompt, self.systemContext(currentRoom))

    def rejectPerformerPrompt(self, currentRoom, currentClient, groupPrompt):
        prompt = self.promptContext(currentRoom) + self.promptScripts['rejectPerformerPrompt']
        prompt += f"Please create a new performerPrompt for the user with userId {currentClient.userId}." \
                  f"It should support the following groupPrompt {groupPrompt}"
        return self.openAIConnector.getSinglePerformerPrompt(prompt, self.systemContext(currentRoom))

    def moveOnFromPerformerPrompt(self, currentRoom, currentClient, groupPrompt):
        prompt = self.promptContext(currentRoom)
        prompt += "The performer indicated would like a new performerPrompt."
        prompt += f"Please create a new performerPrompt for the user with userId {currentClient.userId}." \
                  f"It should support the following groupPrompt {groupPrompt}." \
                  f"Provide a new, different performerPrompt for this user."
        return self.openAIConnector.getSinglePerformerPrompt(prompt, self.systemContext(currentRoom))

    def getEndSongPrompt(self, currentRoom):
        currentRoom.cancelAllTasks()
        prompt = self.promptContext(currentRoom) + self.promptScripts['finalGroupPrompt']
        endingGroupPrompt = self.openAIConnector.getGroupPrompt(prompt, self.systemContext(currentRoom))
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
        script = "You are the ImprovDirector, designed to guide musicians through an improvised, musical experience. " \
                 "Briefly introduce yourself to this musician. Ask them their name."
        return self.openAIConnector.getResponseFromLLM(script)

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
        prompt = "You will start the improvisation and provide the initial prompts soon. " \
                 "Make a brief welcome announcement to get everyone's attention. " \
                 "Make them aware we are about to start."
        prompt += self.promptContext(room)
        return self.openAIConnector.getResponseFromLLM(prompt, self.systemContext(room))

    def aboutMe(self):
        prompt = self.promptScripts['aboutMe']
        return self.openAIConnector.getResponseFromLLM(prompt)