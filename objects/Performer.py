from util.timeStamp import timeStamp
import copy

class Performer:
    def __init__(self, websocket, userId = None, screenName = None, instrument = None):
        self.__websocket = websocket
        self.__userId = userId
        self.__screenName = screenName
        self.__instrument = instrument
        self.__currentPrompts = []
        self.__feedbackLog = {}
        self.__promptHistory = []

    @property
    def websocket(self):
        return self.__websocket

    @property
    def userId(self):
        return self.__userId

    @property
    def screenName(self):
        return self.__screenName

    @property
    def instrument(self):
        return self.__instrument

    @property
    def currentPrompts(self):
        return self.__currentPrompts

    @property
    def promptHistory(self):
        return self.__promptHistory

    @property
    def feedbackLog(self):
        return self.__feedbackLog

    @websocket.setter
    def websocket(self, websocket):
        self.__websocket = websocket

    @userId.setter
    def userId(self, userId):
        self.__userId = userId

    @screenName.setter
    def screenName(self, screenName):
        self.__screenName = screenName

    @instrument.setter
    def instrument(self, instrument):
        self.__instrument = instrument

    @currentPrompts.setter
    def currentPrompts(self, prompts):
        self.__currentPrompts = prompts

    def addPrompt(self, newPrompt):
        newPrompt['timeStamp'] = timeStamp()
        if not len(self.__currentPrompts) == 3:
            self.__currentPrompts.append(newPrompt)
        else:
            for currentPrompt in self.__currentPrompts:
                if currentPrompt.get('promptTitle')[0] == newPrompt.get('promptTitle')[0]:
                    currentPrompt['promptTitle'] = newPrompt.get('promptTitle')
                    currentPrompt['prompt'] = newPrompt.get('prompt')

    def logPrompt(self, prompt):
        logPrompt = copy.deepcopy(prompt)
        logPrompt['timeStamp'] = timeStamp()
        self.__promptHistory.append(logPrompt)

    def ignorePrompt(self, prompt):
        logPrompt = copy.deepcopy(prompt)
        logPrompt.get('promptTitle')[0] = 'playerIgnore'
        logPrompt['timeStamp'] = timeStamp()
        self.__promptHistory.append(logPrompt)

    def addAndLogPrompt(self, prompt):
        self.addPrompt(prompt)
        self.logPrompt(prompt)

    def logFeedback(self, type, question, response):
        if not self.__feedbackLog.get(type):
            self.__feedbackLog[type] = []
        self.__feedbackLog[type].append({'question': question,
                                   'response': response})
        print(f"Log: {self.__feedbackLog}")
        # self.__feedbackLog.append

    def updateUserData(self, message):
        self.__userId = message.get('userId')
        self.__instrument = message.get('instrument' or None)
        self.__screenName = message.get('screenName' or None)
