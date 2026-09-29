import base64
import os

from openai import OpenAI

from config import OPENAI_API_KEY


client = OpenAI(api_key=OPENAI_API_KEY)

print("OpenAI client created successfully")


def ask_gpt_with_invoice(
    pdf_path: str,
    extracted_text: str,
    parser_result: dict,
    prompt: str,
) -> str:

    with open(pdf_path, "rb") as file:
        pdf_base64 = base64.b64encode(file.read()).decode("utf-8")

    response = client.responses.create(
        model="gpt-5-nano",
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_file",
                        "filename": "invoice.pdf",
                        "file_data": (
                            f"data:application/pdf;base64,{pdf_base64}"
                        ),
                    },
                    {
                        "type": "input_text",
                        "text": (
                            f"{prompt}\n\n"
                            "=== TEXT EXTRACTED BY PYPDF ===\n"
                            f"{extracted_text}\n\n"
                            "=== LOCAL PARSER RESULT ===\n"
                            f"{parser_result}\n"
                        ),
                    },
                ],
            }
        ],
    )

    return response.output_text