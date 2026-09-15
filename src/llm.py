from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic()


def ask_claude(prompt: str) -> str:
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=800,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )

    return response.content[0].text