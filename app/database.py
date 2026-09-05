import os
from pymongo import MongoClient
from dotenv import load_dotenv
load_dotenv() 
# ---- Connection ----
client = MongoClient(os.getenv("MONGODB_URI"))
db = client["case_study"]
prompts_collection   = db["prompts"]
history_collection   = db["history"]
def seed_data():
    """Insert the default prompt if not present."""
    if prompts_collection.count_documents({}) == 0:
        prompts_collection.insert_one({"_id": "Education_Prompt","template": (
                "You are an expert in education domain. "
                "Answer the following: {{userinput}}"
            )
        })
