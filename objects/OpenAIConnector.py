from openai import OpenAI
from util.awsSecretRetrieval import getAISecret
import json
import time
import traceback

class OpenAIConnector:
    def __init__(self):
        oaKey, oaProject, model = getAISecret()
        self.client = OpenAI(api_key=oaKey)
        self.model = model

    def promptIntervalContext(self):
        return ("All prompts must include a promptInterval. "
                "The promptInterval is an integer, representing the number of seconds the prompt remains active. "
                "PromptIntervals can be the same across different prompts but do not have to be. "
                "The groupPrompt interval must always be greater than or equal to the longest performerPrompt interval, "
                "as groupPrompts trigger the replacement of performerPrompts. "
                "PromptIntervals must be long enough for the player to reasonably implement the suggested prompt before it is replaced. "
                "Encourage variety in promptIntervals where appropriate.")

    def getResponseFromLLM(self, prompt, systemContext=None,):
        systemMessage = self.getSystemMessage(systemContext)
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": systemMessage},
                    {"role": "user", "content": prompt}],
                model=self.model,
            )
            content = chat_completion.choices[0].message.content.strip()
            return content
        except Exception as e:
            print(f"Error in LLM response: {e}")
            raise e

    def createPrompts(self, prompt, improvisation, systemContext=None, max_retries=3, backoff_factor=2):
        attempt = 0
        systemMessage = self.getSystemMessage(systemContext) + self.promptIntervalContext()
        systemMessage += (
            " When generating a response, ensure it matches the following structure exactly: "
            "{ 'groupPrompt': 'Prompt for all performers', "
            "'performerPrompts': [ { 'userId': 'string', 'performerPrompt': 'string', 'promptInterval': 'string' } ] }."
            )

        validUserIds = {performer.userId for performer in improvisation.performers}

        while attempt < max_retries:
            try:
                chatCompletion = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": systemMessage},
                        {"role": "user", "content": prompt}
                    ],
                    functions=[
                        {
                            "name": "get_group_and_performer_prompts",
                            "description": "Generate a group-level prompt and individual performer prompts.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "groupPrompt": {
                                        "type": "string",
                                        "description": "The overarching prompt for all performers."
                                    },
                                    "groupPromptInterval": {
                                        "type": "string",
                                        "description": "The length of time, in seconds, before this prompt should be replaced."
                                    },
                                    "performerPrompts": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "userId": {"type": "string"},
                                                "performerPrompt": {
                                                    "type": "string",
                                                    "description": "A performer-specific prompt for the performer with this userId."
                                                },
                                                "promptInterval": {
                                                    "type": "string",
                                                    "description": "The length of time, in seconds, before this prompt should be replaced."
                                                },

                                            },
                                            "required": ["userId", "performerPrompt"]
                                        }
                                    }
                                },
                                "required": ["groupPrompt", "groupPromptInterval", "performerPrompts"],
                                "additionalProperties": False
                            }
                        }
                    ],
                    function_call={"name": "get_group_and_performer_prompts"}
                )
                choice = chatCompletion.choices[0]
                function_call = choice.message.function_call
                arguments = function_call.arguments

                promptsData = json.loads(arguments)

                if "groupPrompt" not in promptsData or "performerPrompts" not in promptsData or len(promptsData['performerPrompts']) < 1 or "groupPromptInterval" not in promptsData:
                    raise KeyError("Required keys not found in LLM response.")

                # Validate userIds and ensure every user has a prompt
                providedUserIds = set()
                for performerPrompt in promptsData["performerPrompts"]:
                    userId = performerPrompt.get("userId")
                    if userId not in validUserIds:
                        raise ValueError(f"Invalid userId: {userId} in performerPrompts.")
                    providedUserIds.add(userId)

                # Ensure all validUserIds have a corresponding prompt
                missingUserIds = validUserIds - providedUserIds
                if missingUserIds:
                    raise ValueError(f"Missing prompts for userIds: {', '.join(missingUserIds)}.")

                # Return success response
                return promptsData

            except (KeyError, json.JSONDecodeError, ValueError) as e:
                print(f"Attempt {attempt + 1}/{max_retries} failed with error: {e}")
            except Exception as e:
                print(f"Unexpected error during attempt {attempt + 1}: {e}")

            # Increment the retry count
            attempt += 1

            # Handle max retries
            if attempt >= max_retries:
                print("Max retries reached. Exiting.")
                return {"error": "Failed to retrieve prompts after multiple attempts."}

            # Exponential backoff
            sleep_time = backoff_factor ** attempt
            print(f"Retrying in {sleep_time} seconds...")
            time.sleep(sleep_time)

    def createPerformerPrompt(self, prompt, improvisation, performer, systemContext=None, max_retries=3, backoff_factor=2):
        """
        Generate a single performer-specific prompt as a string and update the improvisation.

        Args:
            prompt (str): Specific instructions for generating the performer prompt.
            userId (str): The user ID of the performer for whom the prompt is generated.
            improvisation (object): An instance of the improvisation class with performers data.
            systemContext (str, optional): Additional system context to guide the LLM. Defaults to None.
            max_retries (int, optional): Maximum number of retries in case of failure. Defaults to 3.
            backoff_factor (int, optional): Exponential backoff factor for retries. Defaults to 2.

        Returns:
            str: The generated performer prompt.
        """
        attempt = 0
        systemMessage = self.getSystemMessage(systemContext) + self.promptIntervalContext()
        systemMessage += (
            " When generating a response, ensure it matches the following structure exactly: "
            "{ 'performerPrompt': 'string', }."
        )

        # Validate userId
        validUserIds = {performer.userId for performer in improvisation.performers}
        userId = performer.userId
        if userId not in validUserIds:
            raise ValueError(f"Invalid userId: {userId}")

        while attempt < max_retries:
            try:
                # Make a single LLM API call to generate the performer prompt
                chatCompletion = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": systemMessage},
                        {"role": "user", "content": prompt}
                    ],
                    functions=[
                        {
                            "name": "get_performer_prompt",
                            "description": "Generate a specific prompt for a performer.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "performerPrompt": {
                                        "type": "string",
                                        "description": "A performer-specific prompt for the performer."
                                    },
                                    "promptInterval": {
                                        "type": "string",
                                        "description": "The length of time, in seconds, before this prompt should be replaced."
                                    },

                                },
                                "required": ["performerPrompt", "promptInterval"],
                                "additionalProperties": False
                            }
                        }
                    ],
                    function_call={"name": "get_performer_prompt"}
                )

                # Parse the response from the LLM
                choice = chatCompletion.choices[0]
                function_call = choice.message.function_call
                arguments = function_call.arguments

                # Load the arguments as JSON
                promptData = json.loads(arguments)

                if "performerPrompt" not in promptData or "promptInterval" not in promptData:
                    raise KeyError("Required keys not found in LLM response.")

                # Return the generated performer prompt
                return promptData

            except (KeyError, json.JSONDecodeError, ValueError) as e:
                print(f"Attempt {attempt + 1}/{max_retries} failed with error: {e}")
            except Exception as e:
                print(f"Unexpected error during attempt {attempt + 1}: {e}")

            # Increment the retry count
            attempt += 1

            # Handle max retries
            if attempt >= max_retries:
                print("Max retries reached. Exiting.")
                return "Error: Failed to retrieve performer prompt after multiple attempts."

            # Exponential backoff
            sleep_time = backoff_factor ** attempt
            print(f"Retrying in {sleep_time} seconds...")
            time.sleep(sleep_time)

    def getPersonality(self, prompt, currentPersonality, personalityType, systemContext=None, max_retries=3,
                                backoff_factor=2):
        attempt = 0
        personalityContext = ("A personality describes the musical tendencies of a performer or the improvDirector LLM."
                              "The personality includes a description that is 10 words or less, and a set of personality attribute scores.")
        requiredAttributes = list(currentPersonality.attributes.keys())
        systemMessage = (
            f"{self.getSystemMessage()} {personalityContext}"
            f"This personality is for a {personalityType}. {currentPersonality.personalityAttributesContext()}"
        )

        if systemContext:
            systemMessage = systemContext + " " + systemMessage

        while attempt < max_retries:
            try:
                function_spec = {
                    "name": "create_or_update_personality",
                    "description": "Creation of personality description and attributes.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "description":{
                                "type": "string",
                                "description": "A textual description of the musical personality, of about 10 words.",
                            },
                            "attributes":{
                                "type": "array",
                                "description": "The personality attributes and their scores. ",
                                "items": {
                                    "name": {
                                    "type": "string",
                                    "description": "The name of the attribute."
                                    },
                                    "value": {
                                        "type": "number",
                                        "description": "Value for the attribute, ranging between -10 and 10."
                                    }
                                },
                            "required": ["attributeName", "value"]
                        }
                    }
                },
                "required": ["description", "attributes"],
                "additionalProperties": False
                }

                # Make the LLM API call with structured response
                chatCompletion = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": systemMessage},
                        {"role": "user", "content": prompt}
                    ],
                    functions=[function_spec],
                    function_call={"name": "create_or_update_personality"}
                )

                # Extract structured output
                structuredOutput = chatCompletion.choices[0].message.function_call.arguments
                if isinstance(structuredOutput, str):
                    structuredOutput = json.loads(structuredOutput)
                newDescription = structuredOutput.get('description')
                newAttributes = structuredOutput.get('attributes')
                attributeNames = [attribute['name'] for attribute in newAttributes]

                if newDescription and all(attribute in attributeNames for attribute in requiredAttributes):

                    attributes = {attribute['name']: attribute['value'] for attribute in newAttributes}
                    newPersonality = {'description': newDescription,
                                      'attributes': attributes}
                    currentPersonality.updatePersonality(newPersonality)
                    return currentPersonality

                # If some attributes are missing, raise an error to retry
                raise KeyError("One or more attributes are missing in the LLM response.")

            except (KeyError, json.JSONDecodeError) as e:
                # Handle known issues that might occur in the response format
                print(f"Attempt {attempt + 1}/{max_retries} failed with error: {e}")

            except Exception as e:
                print(f"Unexpected error during attempt {attempt + 1}: {e}")

            # Increment the retry count
            attempt += 1

            # If we've reached the max retries, raise the exception or return an error
            if attempt >= max_retries:
                print("Max retries reached. Exiting.")
                return {"error": "Failed to retrieve attributes score adjustments after multiple attempts."}

            # Exponential backoff: wait before retrying
            sleep_time = backoff_factor ** attempt
            print(f"Retrying in {sleep_time} seconds...")
            time.sleep(sleep_time)

    def userOptionFeedback(self, prompt):
        systemMessage = (f"{self.getSystemMessage()}"
                        "The performance has not started yet."
                         "You are collecting feedback from users to fine tune your style of musical leadership."
                         "When generating a response, ensure it matches the following structure exactly: "
                        "{'question': 'Which prompt do you prefer?', 'options': ['prompt1', 'prompt2']} "
                         "Only respond in this JSON format without additional text.")
        try:
            chat_completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": systemMessage},
                    {"role": "user", "content": prompt}],
                functions=[
                    {
                        "name": "get_user_feedback",
                        "description": "Generate a question with multiple options.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "question": {
                                    "type": "string",
                                    "description": "The question to be asked."
                                },
                                "options": {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                        "description": "A list of options."
                                    }
                                }
                            },
                            "required": ["question", "options"],
                            "additionalProperties": False
                        }
                    }
                ],
                function_call={"name": "get_user_feedback"}
            )

            structured_output = chat_completion.choices[0].message.function_call.arguments
            if isinstance(structured_output, str):
                structured_output = json.loads(structured_output)

            return {
                "question": structured_output.get("question"),
                "options": structured_output.get("options")
            }
        except Exception as e:
            print(f"Error in LLM response: {e}")
            raise e

    def getSystemMessage(self, systemContext=None):
        defaultMessage = ""
        return systemContext if systemContext else defaultMessage

if __name__ == "__main__":
    connector = OpenAIConnector()
    response = connector.getResponseFromLLM("Hello, how are you?")
    print(response)
