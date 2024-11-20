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

    def getSinglePerformerPrompt(self, prompt, systemContext=None, max_retries=3, backoff_factor=2):
        attempt = 0
        systemMessage = self.getSystemMessage(systemContext)
        systemMessage += (" When generating a response, ensure it matches the following structure exactly: "
                          "'performerPrompt': 'Prompt for the current performer'")
        while attempt < max_retries:
            try:
                # Make the LLM API call
                chatCompletion = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": systemMessage},
                        {"role": "user", "content": prompt}],
                    functions=[
                        {
                            "name": "get_performer_prompt",
                            "description": "Generate a single performerPrompt for the specified user in the gameState.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "performerPrompt": {
                                        "type": "string",
                                        "description": "The new performer prompt for the user."
                                    }
                                },
                                "required": ["performerPrompt"]
                            }
                        }
                    ],
                    function_call={"name": "get_performer_prompt"}
                )

                # Parse the response from the LLM
                choice = chatCompletion.choices[0]

                # Access the function call and its arguments
                function_call = choice.message.function_call

                arguments = function_call.arguments

                promptsData = json.loads(arguments)

                # Check if 'prompts' exists in the response
                if "performerPrompt" not in promptsData:
                    raise KeyError("'prompts' key not found in LLM response.")

                return promptsData

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
                return {"error": "Failed to retrieve prompts after multiple attempts."}

            # Exponential backoff: wait before retrying
            sleep_time = backoff_factor ** attempt
            print(f"Retrying in {sleep_time} seconds...")
            time.sleep(sleep_time)

    def getGroupPrompt(self, prompt, systemContext=None, max_retries=3, backoff_factor=2):
        attempt = 0
        systemMessage = self.getSystemMessage(systemContext)
        systemMessage += (" When generating a response, ensure it matches the following structure exactly: "
                          "'groupPrompts': 'Prompt for all performers'")
        while attempt < max_retries:
            try:
                # Make the LLM API call
                chatCompletion = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": systemMessage},
                        {"role": "user", "content": prompt}],
                    functions=[
                        {
                            "name": "get_group_prompt",
                            "description": "Generate a prompt for the group in the gameState.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "groupPrompt": {
                                            "type": "string",
                                            "description": 'The prompt for the group. ',
                                        }
                                    },
                                "required": ["groupPrompt"],
                                "additionalProperties": False
                            }

                        }
                    ],
                    function_call={"name": "get_group_prompt"}
                )


                choice = chatCompletion.choices[0]

                # Access the function call and its arguments
                function_call = choice.message.function_call

                arguments = function_call.arguments

                promptsData = json.loads(arguments)

                # Check if 'prompts' exists in the response
                if "groupPrompt" not in promptsData:
                    raise KeyError("GroupPrompt: 'prompts' key not found in LLM response.")

                return promptsData

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
                return {"error": "Failed to retrieve prompts after multiple attempts."}

            # Exponential backoff: wait before retrying
            sleep_time = backoff_factor ** attempt
            print(f"Retrying in {sleep_time} seconds...")
            time.sleep(sleep_time)

    def getPrompts(self, prompt, title, systemContext=None, max_retries=3, backoff_factor=2):
        attempt = 0
        systemMessage = self.getSystemMessage(systemContext)
        systemMessage += (" When generating a response, ensure it matches the following structure exactly: "
                          "'prompts': {'userId for user 1': 'Prompt for user 1', 'userId for user 2': 'prompt for user 2'}")
        while attempt < max_retries:
            try:
                # Make the LLM API call
                chatCompletion = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": systemMessage},
                        {"role": "user", "content": prompt}],
                    functions=[
                        {
                            "name": "get_prompts",
                            "description": "Generate a set of prompts for each userId in the performance.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "prompts": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "userId": {"type": "string", "format": "uuid"},
                                                "prompt": {"type": "string"}
                                            },
                                            "required": ["userId", "prompt", "promptTitle"]
                                        }
                                    }
                                },
                                "required": ["prompts"],
                                "additionalProperties": False
                            }
                        }
                    ],
                    function_call={"name": "get_prompts"}
                )

                # Parse the response from the LLM
                function_call = chatCompletion.choices[0].message.function_call
                arguments = function_call.arguments

                # Load the arguments as JSON
                promptsData = json.loads(arguments)

                # Check if 'prompts' exists in the response
                if "prompts" not in promptsData:
                    raise KeyError("PerformerPrompts: 'prompts' key not found in LLM response.")

                # Process the valid data
                result = {}
                for promptData in promptsData["prompts"]:
                    userId = promptData.get("userId")
                    prompt = promptData.get("prompt")
                    if userId not in result:
                        result[userId] = {title: prompt}

                return result

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
                return {"error": "Failed to retrieve prompts after multiple attempts."}

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

    def getInitialLLMPersonalityAttributes(self, prompt, currentPersonality=None, systemContext=None, max_retries=3, backoff_factor=2):
        attempt = 0

        systemMessage = (
            "The LLM personality attributes are: "
            "Creativity, Complexity, Energy, Interaction, Traditionality, Rhythmic Freedom, Tonal Prefence, Prompt Length, Adaptability, Abstractness. "
            "Provide scores in the range of 0 to 10 in the following JSON format: "
            "{'Creativity': 8, 'Complexity': 4, 'Energy': 6, 'Interaction': 9, 'Traditionality': 3, 'Prompt Length': 3, 'Adaptability': 7, 'Abstractness': 2}."
        )

        if systemContext:
            systemMessage += " " + systemContext

        while attempt < max_retries:
            try:
                function_spec = {
                    "name": "initial_llm_personality_attributes",
                    "description": "Generate initial scores for LLM personality attributes.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "Creativity": {"type": "number", "description": "Score between 0-10."},
                            "Complexity": {"type": "number", "description": "Score between 0-10."},
                            "Energy": {"type": "number", "description": "Score between 0-10."},
                            "Interaction": {"type": "number", "description": "Score between 0-10."},
                            "Traditionality": {"type": "number", "description": "Score between 0-10."},
                            "Rhythmic Freedom": {"type": "number", "description": "Score between 0-10."},
                            "Tonal Preference": {"type": "number", "description": "Score between 0-10."},
                            "Prompt Length": {"type": "number", "description": "Score between 0-10."},
                            "Adaptability": {"type": "number", "description": "Score between 0-10."},
                            "Abstractness": {"type": "number", "description": "Score between 0-10."}
                        },
                        "required": [
                            "Creativity", "Complexity", "Energy", "Interaction", "Traditionality",
                            "Rhythmic Freedom", "Tonal Preference", "Prompt Length", "Adaptability", "Abstractness"
                        ],
                        "additionalProperties": False
                    }
                }

                # Make the LLM API call with structured response
                chatCompletion = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": systemMessage},
                        {"role": "user", "content": prompt}
                    ],
                    functions=[function_spec],
                    function_call={"name": "initial_llm_personality_attributes"}
                )

                # Extract structured output
                structuredOutput = chatCompletion.choices[0].message.function_call.arguments
                if isinstance(structuredOutput, str):
                    structuredOutput = json.loads(structuredOutput)

                requiredAttributes = [
                    "Creativity", "Complexity", "Energy", "Interaction",
                    "Traditionality", "Rhythmic Freedom", "Tonal Preference", "Prompt Length", "Adaptability", "Abstractness"
                ]

                if all(attribute in structuredOutput for attribute in requiredAttributes):

                    if currentPersonality is None:
                        currentPersonality = {}
                    for attribute, score in structuredOutput.items():
                        currentPersonality.updateAttribute(attribute, score)
                    return currentPersonality

                # If some attributes are missing, raise an error to retry
                raise KeyError("One or more attributes are missing in the LLM response.")

            except (KeyError, json.JSONDecodeError) as e:
                # Handle known issues that might occur in the response format
                print(f"Attempt {attempt + 1}/{max_retries} failed with error: {e}")

            except Exception as e:
                print(f"Unexpected error during attempt {attempt + 1}: {e}")
                traceback.print_exc()

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

    def adjustPersonalityScores(self, prompt, currentPersonality, personalityType, systemContext=None, max_retries=3,
                                backoff_factor=2):
        attempt = 0

        # Define attributes and their system message based on personalityType
        if personalityType == "performer":
            requiredAttributes = [
                "Creativity", "Complexity", "Energy",
                "Interaction", "Traditionality", "Rhythmic Freedom",
                "Tonal Preference", "Adaptability", "Musical Knowledge"
            ]
        elif personalityType == "llm":
            requiredAttributes = [
                "Creativity", "Complexity", "Energy",
                "Interaction", "Traditionality", "Rhythmic Freedom",
                "Tonal Preference", "Prompt Length", "Adaptability",
                "Abstractness"
            ]
        else:
            raise ValueError(f"Unsupported personalityType: {personalityType}")

        systemMessage = (
            f"{self.getSystemMessage()} "
            f"Provide adjustments for each attribute in exactly the following structured format. The required attributes for a {personalityType} are "
        )

        for attribute in requiredAttributes:
            systemMessage += f'{attribute}, '
        systemMessage += '.'

        # Append system context if available
        if systemContext:
            systemMessage = systemContext + " " + systemMessage

        while attempt < max_retries:
            try:
                # Define the functions parameter to ensure structured output
                function_spec = {
                    "name": "adjust_personality_scores",
                    "description": "Generate adjustments for personality attributes.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            attribute: {
                                "type": "number",
                                "description": f"Adjustment value for {attribute}, ranging between -10 and 10."
                            } for attribute in requiredAttributes
                        },
                        "required": requiredAttributes,
                        "additionalProperties": False
                    }
                }

                # Make the LLM API call with structured response
                chatCompletion = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": systemMessage},
                        {"role": "user", "content": prompt}
                    ],
                    functions=[function_spec],
                    function_call={"name": "adjust_personality_scores"}
                )

                # Extract structured output
                structuredOutput = chatCompletion.choices[0].message.function_call.arguments
                if isinstance(structuredOutput, str):
                    structuredOutput = json.loads(structuredOutput)

                # Validate if the response contains all required attributes
                if all(attribute in structuredOutput for attribute in requiredAttributes):
                    # Apply incremental adjustments to the current scores
                    for attribute, adjustment in structuredOutput.items():
                        currentPersonality.incrementAttribute(attribute, adjustment)
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

    def getSystemMessage(self, systemContext=None):
        defaultMessage = ""
        return systemContext if systemContext else defaultMessage

if __name__ == "__main__":
    connector = OpenAIConnector()
    response = connector.getResponseFromLLM("Hello, how are you?")
    print(response)
