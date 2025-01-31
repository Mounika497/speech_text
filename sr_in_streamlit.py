import streamlit as st
import websockets
import asyncio
import base64
import json
from configure import auth_key
import pyaudio
import threading

if 'text' not in st.session_state:
    st.session_state['text'] = 'Listening...'
    st.session_state['run'] = False

# Audio stream parameters
FRAMES_PER_BUFFER = 3200
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
p = pyaudio.PyAudio()

# Starts recording
stream = p.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    
    input=True,
    frames_per_buffer=FRAMES_PER_BUFFER
)

def start_listening():
    st.session_state['run'] = True

def stop_listening():
    st.session_state['run'] = False

st.title('Get real-time transcription')

start, stop = st.columns(2)
start.button('Start listening', on_click=start_listening)
stop.button('Stop listening', on_click=stop_listening)

URL = "wss://api.assemblyai.com/v2/realtime/ws?sample_rate=16000"

# Function to create a new thread for the WebSocket
def start_asyncio_thread():
    loop = asyncio.new_event_loop()
    threading.Thread(target=lambda: loop.run_until_complete(send_receive(loop)), daemon=True).start()

async def send_receive(loop):
    print(f'Connecting to WebSocket at URL {URL}')
    async with websockets.connect(
        URL,
        extra_headers=(("Authorization", auth_key),),
        ping_interval=5,
        ping_timeout=20
    ) as _ws:
        print("SessionBegins: Awaiting initial connection")
        session_begins = await _ws.recv()
        print("SessionBegins:", session_begins)  # Debugging step

        if "SessionBegins" not in session_begins:
            print("Error: Could not establish session.")
            return

        print("Sending audio data...")

        async def send():
            while st.session_state['run']:
                try:
                    # Capture audio data from the microphone
                    data = stream.read(FRAMES_PER_BUFFER)
                    print(f"Audio data captured: {len(data)} bytes")

                    # Base64 encode the audio data for transmission
                    data_encoded = base64.b64encode(data).decode("utf-8")
                    json_data = json.dumps({"audio_data": data_encoded})
                    await _ws.send(json_data)
                except websockets.exceptions.ConnectionClosedError as e:
                    print(f"WebSocket connection closed: {e}")
                    break
                except Exception as e:
                    print(f"Error sending audio data: {e}")
                await asyncio.sleep(0.01)

        async def receive():
            while st.session_state['run']:
                try:
                    result_str = await _ws.recv()
                    print(f"Received WebSocket message: {result_str}")  # Debugging step

                    response = json.loads(result_str)

                    # Debugging: Print all keys of the received message
                    print(f"Received response keys: {response.keys()}")

                    # Check for 'text' field and display if available
                    if 'text' in response:
                        result = response['text']
                        print(f"Text received: {result}")
                        if response.get('message_type') == 'FinalTranscript':
                            st.session_state['text'] = result
                            st.markdown(st.session_state['text'])

                    # Optionally, handle interim transcripts for live updates
                    if 'text' in response and response.get('message_type') == 'InterimTranscript':
                        print(f"Interim text: {response['text']}")
                        st.session_state['text'] = response['text']
                        st.markdown(st.session_state['text'])

                except websockets.exceptions.ConnectionClosedError as e:
                    print(f"WebSocket connection closed: {e}")
                    break
                except Exception as e:
                    print(f"Error receiving data: {e}")
                await asyncio.sleep(0.01)

        send_task = asyncio.create_task(send())
        receive_task = asyncio.create_task(receive())
        await asyncio.gather(send_task, receive_task)

# Trigger the WebSocket connection if listening
if st.session_state['run']:
    start_asyncio_thread()
