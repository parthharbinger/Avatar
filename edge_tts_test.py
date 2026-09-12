import asyncio
import ssl
import aiohttp
import edge_tts

async def main():
    text = "Hello! This is a simple text to speech example."
    voice = "en-US-AriaNeural"

    # Disable SSL verification
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    connector = aiohttp.TCPConnector(ssl=ssl_context)

    async with aiohttp.ClientSession(connector=connector) as session:
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
        )

        # Inject custom session
        communicate.session = session

        await communicate.save("output.mp3")

asyncio.run(main())