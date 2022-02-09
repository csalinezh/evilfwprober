import asyncio
import time

async def echo_timestamp(reader, writer):
    while True:
        data = await reader.readline()
        if not data.endswith(b'\n'):
            print("Client sent EOF")
            break

        wait_time = int(data)
        print(f"Will wait {wait_time} s")
        await asyncio.sleep(wait_time)

        ts = int(time.time() * 1000)
        writer.write(str(ts).encode() + b'\n')
        try:
            await writer.drain()
        except ConnectionResetError:
            print("Client disconnected abnormally")
            break
    writer.close()

async def main():
    server = await asyncio.start_server(echo_timestamp, host="127.0.0.1", port=7545)

    async with server:
        await server.serve_forever()

asyncio.run(main())