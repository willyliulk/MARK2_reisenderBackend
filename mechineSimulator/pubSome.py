import pynng
import time

# Create a pub socket
with pynng.Pub0() as pub:
    # Bind to an address
    pub.dial('tcp://127.0.0.1:5555')

    # Publish messages in a loop
    while True:
        # Create a message
        msg = b"Hello subscribers!"
        
        # Publish the message
        pub.send(msg)
        print(f"Published: {msg}")
        
        # Wait a bit before next publish
        time.sleep(1)
