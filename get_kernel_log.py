import sys
from kaggle.api.kaggle_api_extended import KaggleApi

api = KaggleApi()
api.authenticate()

# In KaggleApi, kernels_output calls:
# response = kaggle.kernels.kernel_client.get_kernel_output(...)
# and prints response.log
with api.build_kaggle_client() as kaggle:
    from kagglesdk.kernels.types.kernel_service_types import GetKernelOutputRequest
    req = GetKernelOutputRequest()
    req.user_name = "anshulsingh45"
    req.kernel_slug = "idahr-anpr-pipeline"
    res = kaggle.kernels.kernel_client.get_kernel_output(req)
    
    with open("kaggle_kernel_log.txt", "w", encoding="utf-8") as f:
        f.write(f"Status: {res.status}\n")
        f.write(f"Failure message: {res.failure_message}\n")
        f.write(f"Log:\n{res.log}\n")

print("Saved kaggle_kernel_log.txt successfully!")
