class CutAndTransribeResult:
    def __init__(self, full_text_url, top_ngrams, mp3_url, image_url, mp3_size_bytes, reduced_text_url, summary_text_url, topic):
        self.full_text_url = full_text_url
        self.top_ngrams = top_ngrams
        self.mp3_url = mp3_url
        self.image_url = image_url
        self.mp3_size_bytes = mp3_size_bytes
        self.reduced_text_url = reduced_text_url
        self.summary_text_url = summary_text_url
        self.topic = topic
