from openai import OpenAI
# Remove dotenv for production deployment
# from dotenv import load_dotenv
import os
from util.awsSecretRetrieval import getAISecret

# load_dotenv()
oaKey, oaProject = getAISecret()

# Initialize the OpenAI client with the secret key
client = OpenAI(
    api_key=oaKey
)

def getResponseFromLLM(prompt):
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="gpt-3.5-turbo",
        )
        content = chat_completion.choices[0].message.content.strip()
        return content
    except Exception as e:
        print(f"Error in LLM response: {e}")
        raise e

def main():
    pass

if __name__ == "__main__":
    main()
