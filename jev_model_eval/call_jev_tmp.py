import json

from jev_news.jev_client import LiveJevClient
from jev_model_eval.check_api import read_key

state = {
    "news": (
        "ExampleCo raised its quarterly amount of products made "
        "from $8 billion to $10 billion."
    )
}

questions = {
    "product_increase": {
        "type": "noul",
        "instructions": (
            "Does the supplied news explicitly report "
            "an increase in the company's revenue guidance?"
        ),
    }
}

client = LiveJevClient(api_key=read_key(), max_calls=1)

result = client.evaluate(state, questions)

print(json.dumps(result, indent=2))