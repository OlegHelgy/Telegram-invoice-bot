from openai import OpenAI

from config import OPENAI_API_KEY


client = OpenAI(api_key=OPENAI_API_KEY)

print("OpenAI client created successfully")

def ask_gpt(text: str) -> str:
    response = client.responses.create(
        model="gpt-5",
        input=text
    )

    return response.output_text
