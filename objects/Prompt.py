
class Prompt:
    def __init__(self, promptTitle, prompt, promptInterval = None):
        self.__promptTitle = promptTitle
        self.__prompt = prompt
        self.__promptInterval = promptInterval

    @property
    def promptTitle(self):
        return self.__promptTitle

    @promptTitle.setter
    def promptTitle(self, value):
        self.__promptTitle = value

    @property
    def prompt(self):
        return self.__prompt

    @prompt.setter
    def prompt(self, value):
        self.__prompt = value

    @property
    def promptInterval(self):
        if self.__promptInterval:
            return self.__promptInterval
        # default value of 60 seconds
        return 60

    @promptInterval.setter
    def promptInterval(self, promptInterval):
        self.__promptInterval = promptInterval

    def toDict(self, userId=None):
        promptDict = {
            "promptTitle": self.promptTitle,
            "prompt": self.prompt
        }
        if userId:
            promptDict['userId'] = userId
        return promptDict

    def __str__(self):
        return f"{self.prompt}"
