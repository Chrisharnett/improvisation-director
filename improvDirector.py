from objects.WebSocketServer import WebSocketServer, runHealthCheckServer
import threading
import asyncio

def main():
    healthCheckThread = threading.Thread(target=runHealthCheckServer)
    healthCheckThread.daemon = True
    healthCheckThread.start()

    server = WebSocketServer()
    asyncio.run(server.main())

if __name__ == "__main__":
    main()