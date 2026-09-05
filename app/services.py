import os
import asyncio
from datetime import datetime, timezone
from openai import OpenAI, AsyncOpenAI
from app.database import prompts_collection, history_collection

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def get_prompt_template(prompt_id):
    prompt_doc = prompts_collection.find_one({"_id": prompt_id})
    return prompt_doc["template"] if prompt_doc else None


def render_prompt(user_input, template):
    return template.replace("{{userinput}}", user_input)


def call_chatgpt(user_input, template):
    final_prompt = render_prompt(user_input, template)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": final_prompt}]
    )
    return response.choices[0].message.content


async def call_chatgpt_async(user_input, template, async_client):
    final_prompt = render_prompt(user_input, template)
    response = await async_client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": final_prompt}]
    )
    return response.choices[0].message.content


def save_to_history(user_input, rendered_prompt, response):
    history_collection.insert_one({
        "user_input": user_input,
        "prompt": rendered_prompt,
        "response": response,
        "timestamp": datetime.now(timezone.utc)
    })


async def process_bulk(user_inputs, template):
    # AsyncOpenAI client is created inside the event loop that will use it;
    # a module-level one would be shared across different request loops.
    async_client = AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
    )

    async def run_one(item):
        rendered_prompt = render_prompt(item, template)
        response = await call_chatgpt_async(item, template, async_client)
        # PyMongo is synchronous; to_thread keeps its writes off the event loop
        await asyncio.to_thread(save_to_history, item, rendered_prompt, response)
        return response

    # gather returns results in argument order even if calls finish out of order;
    # return_exceptions=True keeps one failed item from sinking the whole batch
    return await asyncio.gather(
        *(run_one(u) for u in user_inputs),
        return_exceptions=True,
    )
