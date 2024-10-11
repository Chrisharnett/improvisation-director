from util.timeStamp import timeStamp
from util.Dynamo.userTableClient import UserTableClient
from util.Dynamo.connections import getDynamoDbConnection

class Performer:
    def __init__(self, websocket, userId=None, screenName=None, instrument=None):
        self.__dynamoDb = getDynamoDbConnection()
        self.__table = UserTableClient(self.__dynamoDb)
        self.__websocket = websocket
        self.__userId = userId
        self.__screenName = screenName
        self.__instrument = instrument
        self.__currentPrompts = {}
        self.__feedbackLog = {}
        self.__promptHistory = []
        self.__registeredUser = False
        self.__roomCreator = False
        self.__personality = None

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

    @property
    def currentPrompts(self):
        return self.__currentPrompts

    @currentPrompts.setter
    def currentPrompts(self, currentPrompts):
        self.__currentPrompts = currentPrompts

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

    def addPrompt(self, newPrompt, elapsedTime):
        for promptTitle, prompt in newPrompt.items():
            if prompt:
                self.__currentPrompts[promptTitle] = {
                    'prompt': prompt,
                    'timeStamp': elapsedTime
                }
                print(f'{self.screenName} - {promptTitle} - {prompt}')

    def logPrompt(self, prompt, elapsedTime, reaction=None):
        currentTime = int(elapsedTime)
        logPrompt = {
            'promptTitle': list(prompt.keys())[0],
            'prompt': list(prompt.values())[0],
            'timeStamp': currentTime,
            'reaction': reaction,
            'userId': self.__userId
        }
        self.__promptHistory.append(logPrompt)

    def addAndLogPrompt(self, prompt, elapsedTime):
        self.addPrompt(prompt, elapsedTime)
        self.logPrompt(prompt, elapsedTime)

    def logFeedback(self, type, question, response):
        if type not in self.__feedbackLog:
            self.__feedbackLog[type] = []
        self.__feedbackLog[type].append({
            'question': question,
            'response': response
        })

    def updateDynamo(self):
        self.__table.putItem({
            'sub': self.__userId,
            'screenName': self.__screenName,
            'instrument': self.__instrument
        })

    # def likePrompt(self, prompt, promptTitle, reaction=None):
    #     self.logPrompt({promptTitle: prompt}, reaction)

    def updateUserData(self, message):
        self.__userId = message.get('userId', self.__userId)
        self.__instrument = message.get('instrument', self.__instrument)
        self.__screenName = message.get('screenName', self.__screenName)

    def resetPerformer(self):
        self.__currentPrompts = {}
        self.__promptHistory = []
        self.__feedbackLog = {}


