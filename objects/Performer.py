from util.Dynamo.userTableClient import UserTableClient
from util.Dynamo.connections import getDynamoDbConnection
from objects.Personalities import PerformerPersonality
from datetime import datetime
from decimal import Decimal

class Performer:
    def __init__(self, websocket, userId=None, screenName=None, instrument=None):
        self.__dynamoDb = getDynamoDbConnection()
        self.__table = UserTableClient(self.__dynamoDb)
        self.__websocket = websocket
        self.__userId = userId
        self.__screenName = screenName
        self.__instrument = instrument
        self.__feedbackLog = {}
        self.__promptHistory = []
        self.__registeredUser = False
        self.__roomCreator = False
        self.__personality = PerformerPersonality()
        self.__currentRoom = None

    @property
    def websocket(self):
        return self.__websocket

    @websocket.setter
    def websocket(self, websocket):
        self.__websocket = websocket

    @property
    def userId(self):
        return self.__userId

    @userId.setter
    def userId(self, userId):
        self.__userId = userId

    @property
    def screenName(self):
        return self.__screenName

    @screenName.setter
    def screenName(self, screenName):
        self.__screenName = screenName

    @property
    def instrument(self):
        return self.__instrument

    @instrument.setter
    def instrument(self, instrument):
        self.__instrument = instrument

    # @property
    # def currentPrompts(self):
    #     return self.__currentPrompts
    #
    # @currentPrompts.setter
    # def currentPrompts(self, currentPrompts):
    #     self.__currentPrompts = currentPrompts

    # @property
    # def performerPrompts(self):
    #     return self.__performerPrompts
    #
    # @property
    # def currentPrompt(self):
    #     return self.__performerPrompts[-1]
    #
    # @currentPrompt.setter
    # def currentPrompt(self, prompt):
    #     self.__performerPrompts[datetime.now().isoformat()] = {prompt}

    @property
    def promptHistory(self):
        return self.__promptHistory

    @promptHistory.setter
    def promptHistory(self, promptHistory):
        self.__promptHistory = promptHistory

    @property
    def feedbackLog(self):
        return self.__feedbackLog

    @property
    def registeredUser(self):
        return self.__registeredUser

    @registeredUser.setter
    def registeredUser(self, registeredUser):
        self.__registeredUser = registeredUser

    @property
    def roomCreator(self):
        return self.__roomCreator

    @roomCreator.setter
    def roomCreator(self, roomCreator):
        self.__roomCreator = roomCreator

    @property
    def personality(self):
        return self.__personality

    @personality.setter
    def personality(self, personality):
        self.__personality = personality
        self.updateDynamo()

    @property
    def currentRoom(self):
        return self.__currentRoom

    @currentRoom.setter
    def currentRoom(self, currentRoom):
        self.__currentRoom = currentRoom

    #
    # def addAndLogPrompt(self, prompt, elapsedTime):
    #     self.addPrompt(prompt, elapsedTime)
    #     self.logPrompt(prompt, elapsedTime)
    #     return

    def logFeedback(self, type, question, response, options=None):
        if type not in self.__feedbackLog:
            self.__feedbackLog[type] = []
        self.__feedbackLog[type].append({
            'question': question,
            'options': options,
            'response': response
        })
        return

    def feedbackString(self):
        feedbackString = ""
        for feedbackType in self.__feedbackLog:
            for i, log in enumerate(self.__feedbackLog[feedbackType]):
                question = log.get('question')
                options = log.get('options', "Not applicable")
                response = log.get('response')
                feedbackString += f"{i}. Question: {question}; Options: {options}; Response: {response}"
        return feedbackString

    def performerString(self):
        description = f"{self.screenName} (userId: {self.userId}). They play {self.instrument}.  "
        if self.__personality:
            description += f"Their personality is: {self.__personality.personalityString()}. "
        return description

    def updateDynamo(self):
        # personality = self.personality.toDict()
        personality = self.personality.toDecimalDict()
        # personality["attributes"] = {k: Decimal(str(v)) for k, v in personality["attributes"].items()}
        self.__table.putItem({
            'sub': self.__userId,
            'screenName': self.__screenName,
            'instrument': self.__instrument,
            'personality': personality,
        })

    def updateUserData(self, message):
        self.userId = message.get('userId', self.userId)
        self.instrument = message.get('instrument', self.instrument)
        self.screenName = message.get('screenName', self.screenName)
        self.promptHistory = message.get('promptHistory', self.promptHistory)
        self.registeredUser = message.get('registeredUser', self.registeredUser)
        self.roomCreator = message.get('roomCreator', self.roomCreator)
        updatedPersonality = message.get('personality', None)
        if updatedPersonality:
            self.personality.updatePersonality(updatedPersonality)

        return

    def resetPerformer(self):
        self.__currentPrompts = {}
        self.__promptHistory = []
        self.__feedbackLog = {}

    @property
    def playerProfile(self):
        userId = self.userId
        screenName = self.screenName
        instrument = self.instrument
        personality = self.personality.toDict()
        return {'userId': userId,
                'screenName': screenName,
                'instrument': instrument,
                'personality': personality,}

    def updatePlayerProfile(self, playerProfileData):
        for key, value in playerProfileData.items():
            if key != "personality":
                if hasattr(self, key) and value is not None:
                    setattr(self, key, value)
            else:
                self.personality.updatePersonality(value)


    def toDict(self):
        return ({
            'screenName': self.screenName or '',
            'instrument': self.instrument or '',
            'userId': self.userId,
            'registeredUser': self.registeredUser,
            'roomCreator': self.roomCreator,
            'personality': self.personality.toDict()
            # 'personality': self.personality.toDict()
        })


