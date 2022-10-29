import random
import uuid

def pseudo_random_uuid(seed):
    random.seed(seed)
    return uuid.UUID(bytes=bytes(random.getrandbits(8) for _ in range(16)), version=4)
