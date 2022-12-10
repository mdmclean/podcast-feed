# podcast-feed

Run `gcloud auth application-default login`

# Deploy
`gcloud run deploy podcast-feed --source .` from repo root 

Ideas 
* summarizer? https://github.com/miso-belica/sumy
* clip intros https://cloud.google.com/text-to-speech/docs/libraries
* give clips broad categories - science, philosophy, etc.
* deploy to web https://cloud.google.com/run/docs/quickstarts/build-and-deploy/deploy-python-service
* can I move the speech-to-text to my compute environment https://towardsdatascience.com/transcribe-audio-files-with-openais-whisper-e973ae348aa7 

GOTCHA
- the remote dev containers features die silently if the remote VM is out of memory 
