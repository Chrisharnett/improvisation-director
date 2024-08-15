from directorPrompts.directorPrompts\
    import chatTest, \
    generateRoomName, \
    gettingToKnowYou
from objects.Room import Room

def messageFilter(message, currentClient, currentRooms):
    currentRoomName = message.get('roomName') or 'lobby'
    action = message.get('action')
    match action:
        # Test match to connect with OpenAi API
        case 'chat':
            chatResponse = chatTest(message.get('message'))
            return {'action': 'chat',
                    'message': chatResponse}

        case 'createRoom':
            currentRoomName = generateRoomName(currentRooms.keys())
            currentRoom = Room(currentRoomName)
            currentRooms[currentRoomName] = currentRoom
            currentClient.updateUserData(message)
            currentRoom.addPlayerToRoom(currentClient)
            response = currentRoom.prepareGameStateResponse('newPlayer')
            response['roomName'] = currentRoomName
            includeFeedbackQuestionInResponse('performerLobby', currentClient.userId, response)
            return response

        case 'startPerformance':
            currentRooms[currentRoomName].initializeGameState()
            response = currentRooms[currentRoomName].prepareGameStateResponse('newGameState')
            return response

        case 'joinRoom':
            roomName = message.get('roomName')
            if roomName not in currentRooms:
                return {
                    'action': 'roomDoesNotExist',
                    'message': 'roomDoesNotExist'
                }
            currentClient.updateUserData(message)
            currentRooms[roomName].addPlayerToRoom(currentClient)
            response = currentRooms[roomName].prepareGameStateResponse('newPlayer')
            includeFeedbackQuestionInResponse('performerLobby', currentClient.userId, response)
            return response

        case 'performerLobbyFeedbackResponse':
            feedbackQuestion = message.get('feedbackQuestion')
            feedbackResponse = message.get('response')
            currentClient.logFeedback(message.get('action'), feedbackQuestion, feedbackResponse)
            return {'feedbackQuestion': [{
                'feedbackType': 'performerLobby',
                'question': gettingToKnowYou().split(','),
                'userId': [currentClient.userId]}],
                    'roomName': currentRoomName
                    }

        case 'useNextPrompt':
            currentRooms[currentRoomName].useNextPrompt(currentClient.userId)
            return currentRooms[currentRoomName].prepareGameStateResponse('newGameState')

        case 'ignorePrompt':
            currentRooms[currentRoomName].ignorePrompt(currentClient.userId)
            return currentRooms[currentRoomName].prepareGameStateResponse('newGameState')

        case 'endSong':
            currentRooms[currentRoomName].createSongEnding()
            response =  currentRooms[currentRoomName].prepareGameStateResponse('endSong')
            return response

        case 'performanceComplete':
            currentRooms[currentRoomName].logEnding()
            response = currentRooms[currentRoomName].getPostPerformancePerformerFeedback()
            return response

        case 'postPerformancePerformerFeedbackResponse':
            response = message.get('response')
            currentClient.logFeedback(action, message.get('feedbackQuestion'), response)
            if len(currentClient.feedbackLog[action]) <3:
                return currentRooms[currentRoomName].getPostPerformancePerformerFeedback()
            summary = currentRooms[currentRoomName].closingTimeSummary()
            return {'action': 'finalSummary',
                    'summary': summary,
                    'roomName': currentRoomName}

        case _:
            return

def includeFeedbackQuestionInResponse(feedbackType, userId, response = {}):
    match feedbackType:
        case 'performerLobby':
            response['feedbackQuestion'] = [{
                'userId': [userId],
                'feedbackType': feedbackType,
                'question': gettingToKnowYou().split(',')}]




