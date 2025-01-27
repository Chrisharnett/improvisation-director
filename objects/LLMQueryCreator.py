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
    def openAIConnector(self):
        return self.__openAIConnector

    @property
    def personality(self):
        return self.__personality

    @personality.setter
    def personality(self, personality):
        self.__personality = personality

    def systemContext(self):
        context = self.promptScripts['systemContext']
        return context

    def gettingToKnowYou(self):
        prompt = self.promptScripts['gettingToKnowYou']
        return self.openAIConnector.userOptionFeedback(prompt)

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
            f"\n {name} PERSONALITY UPDATE \n"
            f"{self.attributeChangesString(oldPersonality, newPersonality)}\n"
            f"'{oldPersonality.description}'\n'{newPersonality.description}\n\n'"
        )
        print(changeSummary)

    def createYourPersonality(self, room):
        prompt = self.promptScripts['createYourPersonality']
        return self.fineTuneYourPersonality(room, prompt)

    def fineTuneYourPersonality(self, room, prompt):
        oldPersonality = deepcopy(self.personality)
        context = self.systemContext() + room.currentImprovisation.currentPerformerContext()
        newPersonality = self.openAIConnector.getPersonality(prompt, self.personality, 'llm', context)
        self.printPersonalityChanges('llm', oldPersonality, self.personality)
        return newPersonality

    def centralThemeFineTunePerformerPersonality(self, room, performer, response):
        prompt = (f"The performer has responded to a suggested central theme for the improvisation. "
                  f"Performer with userId {performer.userId} {response.get('reaction')} the theme {room.currentImprovisation.centralTheme}. ")
        suggestion = response.get('suggestion')
        if suggestion:
            prompt += f'They suggested {suggestion}. '
        prompt += f"Based on the response given by the performer, please revise their personality description and attributes appropriately."
        return self.fineTunePerformerPersonality(performer, prompt, room)

    def promptReactionFineTunePersonalities(self, performer, response, room):
        prompt = response + f" Based on the response given by the performer, please revise their personality description and attributes appropriately."
        performerPersonality = self.fineTunePerformerPersonality(performer, prompt, room)
        llmPrompt = response + f" Based on the response given by the performer, please revise the LLM's personality description and attributes appropriately."
        llmPersonality = self.fineTuneYourPersonality(room, llmPrompt)
        return

    def fineTunePerformerPersonality(self, performer, prompt, room=None):
        oldPersonality = deepcopy(performer.personality)
        context = self.systemContext()
        if room:
            context += room.currentImprovisation.currentPerformerContext()
        newPersonality = self.openAIConnector.getPersonality(prompt, performer.personality, 'performer', context)
        self.printPersonalityChanges('performer', oldPersonality, self.personality)
        return newPersonality

    def nextSongPersonality(self, room):
        prompt = f"Performers are ready for another improvisation. Create a new improvDirector personality to lead this improvisation." \
                 f" This personality must be unique from the following personalities. " \
                 f"{room.pastLLMPersonalities()} ." \
                 f"Include a personality description and attributes as described. "
        return self.fineTuneYourPersonality(room, prompt)

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

    def updatePerformerPersonality(self, performer, feedbackString):
        prompt = "Provide a revised performer personality, including a description and attributes, based on the following feedback. "
        prompt += feedbackString if feedbackString else ""
        return self.fineTunePerformerPersonality(performer, prompt)

    def getPerformerIds(self, improvisation):
        performerIds = f"Include performerPrompts for performers with userId: "
        for performer in improvisation.performers:
            performerIds += f'{performer.userId}, '
        return performerIds

    def initiatePerformance(self, room):
        improvisation = room.currentImprovisation
        context = self.systemContext() + improvisation.currentSystemContext()
        prompt = f"Create the starting prompts for this performance. {self.getPerformerIds(improvisation)}"
        return self.openAIConnector.createPrompts(prompt, improvisation, context)

    def provideNewPrompts(self, room):
        improvisation = room.currentImprovisation
        context = self.systemContext() + improvisation.currentSystemContext()
        prompt = improvisation.currentPromptContext()
        endPrompt = prompt + \
                    'Is it time to end this performance? Respond with only yes or no.'
        endSong = self.openAIConnector.getResponseFromLLM(endPrompt, context)
        if 'yes' == endSong:
            return self.concludePerformance(room)
        prompt += f" What should happen next? " \
                  f"Create new group and performer prompts to describe how the improvisation should develop." \
                  f" {self.getPerformerIds(improvisation)}"
        return self.openAIConnector.createPrompts(prompt, improvisation, context)

    def concludePerformance(self, room):
        improvisation = room.currentImprovisation
        context = self.systemContext() + improvisation.currentSystemContext()
        prompt = improvisation.currentPromptContext()
        prompt += f"Create the final prompts to resolve this performance. {self.getPerformerIds(improvisation)}"
        improvisation.finalPrompt = True
        room.cancelAllTasks()
        return self.openAIConnector.createPrompts(prompt, improvisation, context)

    def groupMoveOn(self, room):
        improvisation = room.currentImprovisation
        context = self.systemContext() + improvisation.currentSystemContext()
        prompt = improvisation.currentPromptContext()
        prompt += f"Performers have decided it is time to move on from this prompt. Create the next group and performer Prompts. "
        return self.openAIConnector.createPrompts(prompt, improvisation, context)

    def groupRejectPrompt(self, room):
        improvisation = room.currentImprovisation
        context = self.systemContext() + improvisation.currentSystemContext()
        prompt = improvisation.currentPromptContext()
        prompt += "Performers have rejected this groupPrompt. " \
                  "Create new, contrasting, group and performer Prompts. " \
                  "Change the direction of the music."
        return self.openAIConnector.createPrompts(prompt, improvisation, context)

    def nextPerformerPrompt(self, room, performer):
        improvisation = room.currentImprovisation
        context = self.systemContext() + improvisation.currentSystemContext()
        prompt = improvisation.currentPromptContext()
        prompt += f"What should performer with userId {performer.userId} do next? " \
                  f"Provide them with their next performerPrompt.  "
        newPrompt = self.openAIConnector.createPerformerPrompt(prompt, improvisation, performer, context)
        newPrompt['userId'] = performer.userId
        return newPrompt

    def performerMoveOn(self, room, performer):
        improvisation = room.currentImprovisation
        context = self.systemContext() + improvisation.currentSystemContext()
        prompt = improvisation.currentPromptContext()
        prompt += f"Performer with userId {performer.userId} wants to move on from their current performerPrompt. " \
                  f"Provide them with their next performerPrompt.  "
        newPrompt =  self.openAIConnector.createPerformerPrompt(prompt, improvisation, performer, context)
        newPrompt['userId'] = performer.userId
        return newPrompt

    def performerRejectPrompt(self, room, performer):
        improvisation = room.currentImprovisation
        context = self.systemContext() + improvisation.currentSystemContext()
        prompt = improvisation.currentPromptContext()
        prompt += f"Performers with userId {performer.userId} has rejected their performerPrompt. " \
                  "Create a new, different, performerPrompt for them. " \
                  "Change the direction of the music. "
        newPrompt = self.openAIConnector.createPerformerPrompt(prompt, improvisation, performer, context)
        newPrompt['userId'] = performer.userId
        return newPrompt

    def generateRoomName(self):
        roomNames = {roomName.split('-')[0] for roomName in self.currentRoomNames}
        currentRoomNamesStr = ', '.join(roomNames)
        prompt = self.promptScripts['generateRoomName']
        prompt += f'The word cannot be in {currentRoomNamesStr}. '
        return self.openAIConnector.getResponseFromLLM(prompt)

    def closingSummary(self, room):
        prompt = self.promptScripts['closingSummary']
        prompt += room.currentImprovisation.currentPromptContext()
        return self.openAIConnector.getResponseFromLLM(prompt, self.systemContext())

    def getWelcomeMessage(self):
        return self.openAIConnector.getResponseFromLLM(self.promptScripts['wellHelloThere'])

    def getPastThemes(self, room):
        pastThemes = ""
        for i, improvisation in enumerate(room.improvisations):
            pastThemes += f"Theme {i + 1}: {improvisation.centralTheme}"
        return (f"This performance has already explored these themes.  {pastThemes}."
                f"The new theme must try something new.")

    def getCentralTheme(self, room):
        prompt = self.promptScripts['getCentralTheme']
        context = self.systemContext() + room.currentImprovisation.currentSystemContext()
        if room.songCount > 1:
            prompt += self.getPastThemes(room)
        return self.openAIConnector.getResponseFromLLM(prompt, context)

    def getNewTheme(self, room, centralTheme):
        themePrompt = f'Performers have responded to the suggested central theme of "{centralTheme}"'
        themePrompt += f'The performers responses: {room.themeResponseString()}'
        personalityPrompt = themePrompt + 'Revise the current LLM personality to accomodate the performers response.'
        newPersonality = self.openAIConnector.getPersonality(personalityPrompt, self.personality, 'llm',
                                                             systemContext=self.systemContext())
        if room.songCount > 1:
            themePrompt += self.getPastThemes(room)
        themePrompt += self.promptScripts['tryNewCentralTheme']
        return self.openAIConnector.getResponseFromLLM(themePrompt, self.systemContext())

    def announceStart(self, room):
        return "Just getting things ready. One Moment. "

    def aboutMe(self):
        prompt = self.promptScripts['aboutMe']
        return self.openAIConnector.getResponseFromLLM(prompt)