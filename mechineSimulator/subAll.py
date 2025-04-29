# Subscribe to all topics in pynng pubsub model
import pynng

# Create subscriber socket
sub = pynng.Sub0()

# Connect to publisher
sub.listen('tcp://127.0.0.1:5555')

# Subscribe to all topics by setting empty string subscription
sub.subscribe('motor|0|')


# Receive messages
while True:
    try:
        msg = sub.recv(block=False)
        print(f"Received: {msg.decode()}")
    except pynng.exceptions.TryAgain:
        pass
    except Exception as e:
        print(f"Error[any]: {e}")
        break
    except pynng.exceptions.ConnectionRefused as e:
        print(f"Error[ConnectionRefused]: {e}")
        break
        
sub.close()
exit(1)
