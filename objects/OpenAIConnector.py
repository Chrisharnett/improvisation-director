from openai import OpenAI
from util.awsSecretRetrieval import getAISecret
import json
import time

class OpenAIConnector:
    def __init__(self):
        oaKey, oaProject = getAISecret()
        self.client = OpenAI(api_key=oaKey)

    def getResponseFromLLM(self, prompt):
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-3.5-turbo",
            )
            content = chat_completion.choices[0].message.content.strip()
            return content
        except Exception as e:
            print(f"Error in LLM response: {e}")
            raise e

    def getSinglePerformerPrompt(self, prompt, max_retries=3, backoff_factor=2):
        attempt = 0

        while attempt < max_retries:
            try:
                # Make the LLM API call
                chatCompletion = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    functions=[
                        {
                            "name": "get_performer_prompt",
                            "description": "Generate a single performerPrompt for the specified user in the gameState.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "performerPrompts": {
                                            "type": "string",
                                            "description": 'The prompt for the user. ',
                                        }
                                    },
                                "required": ["performerPrompt"],
                                "additionalProperties": False
                            }

                        }
                    ],
                    function_call={"name": "get_performer_prompt"}
                )

                # Parse the response from the LLM
                # response = chatCompletion['choices'][0]['message']['function_call']['arguments']
                # Access the first choice from the response using dot notation
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

    def getGroupPrompt(self, prompt, max_retries=3, backoff_factor=2):
        attempt = 0

        while attempt < max_retries:
            try:
                # Make the LLM API call
                chatCompletion = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
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

                # Parse the response from the LLM
                # response = chatCompletion['choices'][0]['message']['function_call']['arguments']
                # Access the first choice from the response using dot notation
                choice = chatCompletion.choices[0]

                # Access the function call and its arguments
                function_call = choice.message.function_call

                arguments = function_call.arguments

                promptsData = json.loads(arguments)

                # Check if 'prompts' exists in the response
                if "groupPrompt" not in promptsData:
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

    def getPrompts(self, prompt, title, max_retries=3, backoff_factor=2):
        attempt = 0

        while attempt < max_retries:
            try:
                # Make the LLM API call
                chatCompletion = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    functions=[
                        {
                            "name": "get_prompts",
                            "description": "Generate a set of prompts for each userId in the gameState.",
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
                    raise KeyError("'prompts' key not found in LLM response.")

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
        try:
            chat_completion = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
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

if __name__ == "__main__":
    connector = OpenAIConnector()
    response = connector.getResponseFromLLM("Hello, how are you?")
    print(response)
