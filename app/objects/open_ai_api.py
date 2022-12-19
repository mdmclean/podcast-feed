import openai

class OpenAIApi:

    def __init__(self):
        openai.api_key = ""

    def proccess_text (self, text_prompt:str, tokens:int):
        return openai.Completion.create(model="text-davinci-003", prompt=text_prompt, temperature=0, max_tokens=tokens)
        