from directorPrompts.directorPrompts\
    import chatTest, \
    generateRoomName, \
    gettingToKnowYou
from objects.Room import Room
from util.Dynamo.logTableClient import LogTableClient
from util.Dynamo.connections import getDynamoDbConnection

def messageFilter(message, currentClient, currentRooms):
    currentRoomName = message.get('roomName') or 'lobby'
    action = message.get('action')
    currentRoom = currentRooms[currentRoomName]
    match action:
        # Test match to connect with OpenAi API
        case 'chat':
            chatResponse = chatTest(message.get('message'))
            return {'action': 'chat',
                    'message': chatResponse}

        case 'createRoom':
            currentRoomName = generateRoomName()
            currentRoom = Room(currentRoomName)
            currentRooms[currentRoomName] = currentRoom
            currentClient.updateUserData(message)
            currentRoom.addPlayerToRoom(currentClient)
            response = currentRoom.prepareGameStateResponse('newPlayer')
            response['roomName'] = currentRoomName
            includeFeedbackQuestionInResponse('performerLobby', currentClient.userId, response)
            return response

        case 'startPerformance':
            currentRoom.initializeGameState()
            response = currentRoom.prepareGameStateResponse('newGameState')
            return response

        case 'joinRoom':
            roomName = message.get('roomName')
            if roomName not in currentRooms:
                return {
                    'action': 'roomDoesNotExist',
                    'message': 'roomDoesNotExist'
                }
            currentClient.updateUserData(message)
            currentRoom.addPlayerToRoom(currentClient)
            response = currentRoom.prepareGameStateResponse('newPlayer')
            includeFeedbackQuestionInResponse('performerLobby', currentClient.userId, response)
            return response

        case 'performerLobbyFeedbackResponse':
            feedbackQuestion = message.get('feedbackQuestion')
            feedbackResponse = message.get('response')
            currentClient.logFeedback(action, feedbackQuestion, feedbackResponse)
            return {'feedbackQuestion': [{
                'feedbackType': 'performerLobby',
                'question': gettingToKnowYou().split(','),
                'userId': [currentClient.userId]}],
                    'roomName': currentRoomName
                    }

        case 'useNextPrompt':
            currentRoom.useNextPrompt(currentClient.userId)
            return currentRoom.prepareGameStateResponse('newGameState')

        case 'ignorePrompt':
            currentRoom.ignorePrompt(currentClient.userId)
            return currentRoom.prepareGameStateResponse('newGameState')

        case 'endSong':
            currentRoom.createSongEnding()
            response =  currentRoom.prepareGameStateResponse('endSong')
            return response

        case 'performanceComplete':
            currentRoom.logEnding()
            response = currentRoom.getPostPerformancePerformerFeedback()
            return response

        case 'postPerformancePerformerFeedbackResponse':
            response = message.get('response')
            currentClient.logFeedback(action, message.get('feedbackQuestion'), response)
            if len(currentClient.feedbackLog[action]) < 3:
                return currentRoom.getPostPerformancePerformerFeedback()
            allPerformersComplete = False
            for performer in currentRoom.performers:
                if len(performer.feedbackLog[action]) < 3:
                    break
                allPerformersComplete = True
            if allPerformersComplete:
                currentRoom.getClosingTimeSummary()
                currentRoom.createGameLog()
                dumpGameLog(currentRoom.gameLog)
                return {'action': 'finalSummary',
                        'summary': currentRoom.summary,
                        'roomName': currentRoomName}
            return  {'action': 'finalSummaryPending',
                    'roomName': currentRoomName}

        case _:
            return

def dumpGameLog(log):
    dynamoDb = getDynamoDbConnection()
    table = LogTableClient(dynamoDb)
    table.putItem(log)

def includeFeedbackQuestionInResponse(feedbackType, userId, response = {}):
    match feedbackType:
        case 'performerLobby':
            response['feedbackQuestion'] = [{
                'userId': [userId],
                'feedbackType': feedbackType,
                'question': gettingToKnowYou().split(',')}]




