from google.cloud import storage

class BucketManager:
    def __init__(self, project_name, bucket_name):
        self.project_name = project_name
        self.bucket_name = bucket_name
        self.storage_client = storage.Client(project_name)
        self.bucket = self.storage_client.get_bucket(bucket_name)

    def get_blob(self, blob_name):
        return self.bucket.blob(blob_name)

    def get_bucket_name(self):
        return self.bucket_name
