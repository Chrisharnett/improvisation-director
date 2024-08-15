class PerformancePrompt:
    def __init__(self, promptTitle, prompt):
        self.__promptTitle = promptTitle
        self.__prompt = prompt

    @property
    def promptTitle(self):
        return self.__promptTitle

    @property
    def prompt(self):
        return self.__prompt

    @promptTitle.setter
    def promptTitle(self, promptTitle):
        self.__promptTitle = promptTitle

    @prompt.setter
    def prompt(self, prompt):
        self.__prompt = prompt
