import os
import json
import asyncio
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from schemas import ConversationAgentOutput
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault('GOOGLE_API_KEY', os.environ.get('GEMINI_API_KEY', 'dummy'))

model_name = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')

agent = LlmAgent(
    name='shopping_consultant',
    model=model_name,
    instruction='Hello, return {"intent": "general_conversation", "response": "test"}',
    # output_schema=ConversationAgentOutput,
    output_key='agent_output',
)

session_service = InMemorySessionService()
runner = Runner(
    agent=agent,
    app_name='shopping-consultant',
    session_service=session_service,
)

async def main():
    await session_service.create_session(
        app_name='shopping-consultant',
        user_id='test',
        session_id='test',
    )

    user_content = types.Content(
        role='user',
        parts=[types.Part.from_text(text='test')]
    )

    try:
        async for event in runner.run_async(
            new_message=user_content,
            user_id='test',
            session_id='test',
        ):
            if event.is_final_response() and event.content and event.content.parts:
                print(event.content.parts[0].text)
        print('SUCCESS')
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(main())
