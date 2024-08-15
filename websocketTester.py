import unittest
from unittest.mock import MagicMock, patch
from messageFilter import messageFilter

class TestMessageFilter(unittest.TestCase):

    def setUp(self):
        self.currentClient = MagicMock()
        self.currentRooms = {}
        self.currentRoomName = "testRoom"
        self.currentRooms[self.currentRoomName] = MagicMock()

    def test_create_room(self):
        message = {'action': 'createRoom'}
        response = messageFilter(message, self.currentClient, self.currentRooms)

        self.assertIn('roomName', response)
        self.assertIn(response['roomName'], self.currentRooms)
        self.assertEqual(response['action'], 'newPlayer')
        self.assertIn('feedbackQuestion', response)

    def test_join_room_success(self):
        self.currentRooms['existingRoom'] = MagicMock()
        message = {'action': 'joinRoom', 'roomName': 'existingRoom'}
        response = messageFilter(message, self.currentClient, self.currentRooms)

        self.assertEqual(response['action'], 'newPlayer')
        self.assertIn('feedbackQuestion', response)

    def test_join_room_failure(self):
        message = {'action': 'joinRoom', 'roomName': 'nonExistentRoom'}
        response = messageFilter(message, self.currentClient, self.currentRooms)

        self.assertEqual(response['action'], 'roomDoesNotExist')
        self.assertEqual(response['message'], 'roomDoesNotExist')

    def test_start_performance(self):
        message = {'action': 'startPerformance', 'roomName': self.currentRoomName}
        response = messageFilter(message, self.currentClient, self.currentRooms)

        self.currentRooms[self.currentRoomName].initializeGameState.assert_called_once()
        self.assertEqual(response['action'], 'newGameState')

    def test_end_performance(self):
        message = {'action': 'endPerformance', 'roomName': self.currentRoomName}
        response = messageFilter(message, self.currentClient, self.currentRooms)

        self.currentRooms[self.currentRoomName].logEnding.assert_called_once()
        self.assertTrue(self.currentRooms[self.currentRoomName].getPostPerformanceFeedback.called)

    def test_use_next_prompt(self):
        message = {'action': 'useNextPrompt', 'roomName': self.currentRoomName}
        response = messageFilter(message, self.currentClient, self.currentRooms)

        self.currentRooms[self.currentRoomName].useNextPrompt.assert_called_once_with(self.currentClient.userId)
        self.assertEqual(response['action'], 'newGameState')

    def test_ignore_prompt(self):
        message = {'action': 'ignorePrompt', 'roomName': self.currentRoomName}
        response = messageFilter(message, self.currentClient, self.currentRooms)

        self.currentRooms[self.currentRoomName].ignorePrompt.assert_called_once_with(self.currentClient.userId)
        self.assertEqual(response['action'], 'newGameState')

    def test_end_song(self):
        message = {'action': 'endSong', 'roomName': self.currentRoomName}
        response = messageFilter(message, self.currentClient, self.currentRooms)

        self.currentRooms[self.currentRoomName].createSongEnding.assert_called_once()
        self.assertEqual(response['action'], 'endSong')

    def test_performer_lobby_feedback_response(self):
        message = {
            'action': 'performerLobbyFeedbackResponse',
            'feedbackQuestion': 'testQuestion',
            'feedbackResponse': 'testResponse',
            'roomName': self.currentRoomName
        }
        response = messageFilter(message, self.currentClient, self.currentRooms)

        self.currentClient.logFeedback.assert_called_once_with('testQuestion', 'testResponse')
        self.assertEqual(response['feedbackQuestion']['feedbackType'], 'performerLobby')
        self.assertIn('question', response['feedbackQuestion'])
        self.assertIn(self.currentClient.userId, response['feedbackQuestion']['userId'])

if __name__ == "__main__":
    unittest.main()
