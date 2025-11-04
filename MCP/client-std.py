import asyncio
import nest_asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

nest_asyncio.apply()


async def main():
    try:
        print("Starting client...")

        # Define server parameters
        server_params = StdioServerParameters(
            command="python",
            args=["server.py"],
        )
        print(f"Server params created: {server_params}")

        # Connect to the server
        print("Connecting to server...")
        async with stdio_client(server_params) as (read_stream, write_stream):
            print("Connected! Creating session...")

            async with ClientSession(read_stream, write_stream) as session:
                print("Session created! Initializing...")

                # Initialize the connection
                await session.initialize()
                print("Initialized successfully!")

                print("Calling get_unread_emails_tool...")
                unread_result = await session.call_tool(
                    "get_unread_emails_tool", arguments={}
                )
                print("Unread emails:", unread_result)

                import json

                try:
                    emails = json.loads(unread_result.content[0].text)
                    for email in emails:
                        print(email)  # Adjust this to match your actual output

                    print("Calling read_email_tool...")
                    result = await session.call_tool(
                        "read_email_tool", arguments={"email_id": emails["id"]}
                    )
                    print(f"Result received: {result}")
                    print(f"Email content: {result.content[0].text}")
                except (json.JSONDecodeError, KeyError, IndexError) as e:
                    print(f"Error parsing unread emails: {e}")
        print("Done!")

    except Exception as e:
        print(f"Error occurred: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
