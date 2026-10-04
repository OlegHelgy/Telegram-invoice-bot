import base64

from openai import OpenAI

from config import OPENAI_API_KEY


client = OpenAI(api_key=OPENAI_API_KEY)


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
                            "=== ТЕКСТ, ВИТЯГНУТИЙ PYPDF ===\n"
                            f"{extracted_text}\n\n"
                            "=== РЕЗУЛЬТАТ ЛОКАЛЬНОГО PARSER ===\n"
                            f"{parser_result}\n"
                        ),
                    },
                ],
            }
        ],
    )

    return response.output_text


def ask_gpt_for_random_fact(
    prompt: str,
    image_path: str,
) -> str:

    with open(image_path, "rb") as file:
        image_base64 = base64.b64encode(
            file.read()
        ).decode("utf-8")

    response = client.responses.create(
        model="gpt-5-nano",
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": prompt,
                    },
                    {
                        "type": "input_image",
                        "image_url": (
                            "data:image/png;base64,"
                            f"{image_base64}"
                        ),
                    },
                ],
            }
        ],
    )

    return response.output_text

def ask_gpt(prompt: str) -> str:
    response = client.responses.create(
        model="gpt-5-nano",
        input=prompt,
    )

    return response.output_text
