from util.openAIConnector import getResponseFromLLM
from util.Dynamo.promptTableClient import PromptTableClient
from util.Dynamo.logTableClient import LogTableClient
from util.Dynamo.connections import getDynamoDbConnection

dynamoDb = getDynamoDbConnection()
table = PromptTableClient(dynamoDb)
logTable = LogTableClient(dynamoDb)
promptScripts = table.getAllPromptScripts()
promptGuidelines = promptScripts['promptGuidelines']
promptTitles = promptScripts['promptTitles']

performanceLogs = logTable.getLogs()
currentRoomNames = list(performanceLogs.keys())
currentRoomNames.append('lobby')
context = f" For context, here is a log of previous performances. {performanceLogs}. "

def endSong(gameStateString):
    context
    prompt = promptGuidelines + context + promptScripts['endSong']
    prompt += f"Current gameState: {gameStateString}"
    return getResponseFromLLM(prompt)

def postPerformancePerformerFeedback(gameStateString, feedbackLogs, userId):
    questionNumber = len(feedbackLogs) + 1
    prompt = promptScripts['postPerformanceFeedback']
    prompt += f"Final gameState: {gameStateString}"
    prompt += f"Please create question {questionNumber} for userId{userId} "
    return getResponseFromLLM(prompt)

def gettingToKnowYou():
    prompt = promptGuidelines + promptScripts['gettingToKnowYou']
    return getResponseFromLLM(prompt)

def getHarmonyAndMeterPrompt(gameStateString = None):
    prompt = promptGuidelines + context + promptScripts['getHarmonyAndMeterPrompt']
    if gameStateString:
        prompt += f"Current gameState: {gameStateString}"
    return getResponseFromLLM(prompt)

def getStartingPrompt(lobbyFeedback):
    prompt = promptGuidelines + context + promptScripts['getStartingPrompt']
    prompt += f"Here is the initial player feedback. {lobbyFeedback}. Let it influence the mood of the improvisation as you create prompts. "
    return getResponseFromLLM(prompt)

def getNextPrompt(room, currentClient):
    # currentPrompts = ""
    # for client in room.performers:
    #     if client.userId == currentClient.userId:
    #         currentPrompts = json.dumps(client.currentPrompts)
    prompt = promptGuidelines + context + promptScripts['getNextPrompt']
    prompt += f"Current gameState: {room.gameStateString()}"
    prompt += f"Current userId: {currentClient.userId}"
    prompt += f"Valid promptTitles:  {promptTitles}"
    result = getResponseFromLLM(prompt)
    return result

def coordinatePrompt(performer, gameStateString, draftPrompt, ending=False):
    prompt = promptGuidelines + context + promptScripts['coordinatePrompts']
    prompt += f"Prompt to add: {draftPrompt}"
    prompt += f"Current userId: {performer.userId}"
    prompt += f"Current gameState: {gameStateString}"
    if ending:
        prompt += "This prompt will be the final prompt for the performance."
    return getResponseFromLLM(prompt)

def generateRoomName():
    currentRoomNamesStr = ', '.join(currentRoomNames)
    prompt = promptScripts['generateRoomName']
    prompt += f'The word cannot be in {currentRoomNamesStr}, mystic, mystical. '
    return getResponseFromLLM(prompt)

def closingSummary(gameStateString):
    prompt = promptScripts['closingSummary']
    prompt += f"Final gameState: {gameStateString}"
    return getResponseFromLLM(prompt)

def chatTest(message):
    prompt = f"create a short response to the user message: {message}."
    return getResponseFromLLM(prompt)

def getWelcomeMessage():
    prompt = f"Someone has just walked into the room. Please provide a welcome message."
    return getResponseFromLLM(prompt)