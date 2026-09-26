import builtins
orig_open = builtins.open

def safe_open(file, mode="r", *args, **kwargs):
    if "w" in mode and "b" not in mode and "encoding" not in kwargs:
        kwargs["encoding"] = "utf-8"
    return orig_open(file, mode, *args, **kwargs)

builtins.open = safe_open

from kaggle.api.kaggle_api_extended import KaggleApi
api = KaggleApi()
api.authenticate()

print("Pulling output...")
outfiles, token = api.kernels_output("anshulsingh45/idahr-anpr-pipeline", path="kaggle_output", quiet=False)
print("Files downloaded:", outfiles)
