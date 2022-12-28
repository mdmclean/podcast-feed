from objects.summarization_result import SummarizationResult

class SummarizationService:
    def __init__(self, open_ai_api):
        self.open_ai_api = open_ai_api

    def summarize(self, text:str):
        reduced_text = self.reduce_text(text)
        summary_text = self.get_clip_summary(reduced_text)
        topic = self.get_topic_from_text(reduced_text)

        return SummarizationResult(reduced_text, summary_text, topic)

    def reduce_text(self, text:str):
        chunks = [text[i:i+2000] for i in range(0, len(text), 2000)]
        general_prompt = " - Summarize the above discussion."

        new_text = ""

        for chunk in chunks:
            my_prompt = "'" + chunk + "'" + general_prompt
            response = self.open_ai_api.proccess_text(my_prompt, 200)
            new_text += "\n " + response.choices[0].text
            print (response.choices[0].text)

        return new_text

    def get_clip_summary(self, text:str):
        summary_prompt = "'" + text + "'" + " - Summarize the above discussion with as much detail as possible, without mentioning sponsors."
        summary = self.open_ai_api.proccess_text(summary_prompt, 500)
        return summary.choices[0].text

    def get_topic_from_text(self, text:str):
        prompt = "'" + text + "'" + " - Give this discussion a short category in the style of a book title."
        response = self.open_ai_api.proccess_text(prompt, 30)
        topic:str = response.choices[0].text
        topic = topic.replace("\n", "")
        topic = topic.replace('"', "")

        return topic