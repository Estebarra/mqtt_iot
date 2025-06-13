import time
import os
import psutil
import threading
import logging
import json
import paho.mqtt.client as paho

from paho import mqtt
from dotenv import load_dotenv
from fastapi import FastAPI, Response, status
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager


load_dotenv()

log_level = os.getenv("LOG_LEVEL", "INFO").upper()

messenger_id = os.getenv("MESSENGER_ID")

logging.basicConfig(
    level=log_level,
    format=f'%(asctime)s - {messenger_id} - %(levelname)s - %(message)s'
)

# setting callbacks for different events to see if it works, print the message etc.
def on_connect(client, userdata, flags, rc, properties=None):
    logging.info(f"CONNACK received with code {rc}.")

# with this callback you can see if your publish was successful
def on_publish(client, userdata, mid, properties=None):
    logging.info("mid: " + str(mid))

# print which topic was subscribed to
def on_subscribe(client, userdata, mid, granted_qos, properties=None):
    logging.info("Subscribed: " + str(mid) + " " + str(granted_qos))

# print message, useful for checking if it was successful
def on_message(client, userdata, msg):
    logging.info(msg.topic + " " + str(msg.qos) + " " + str(msg.payload))

def on_disconnect(client, userdata, rc):
    if rc != 0:
        logging.warning(f"Unexpected MQTT disconnection. Code: {rc}")
    else:
        logging.info("Disconnected from MQTT broker")

# using MQTT version 5 here, for 3.1.1: MQTTv311, 3.1: MQTTv31
# userdata is user defined data of any type, updated by user_data_set()
# client_id is the given name of the client
client = paho.Client(client_id=f"{messenger_id}", userdata=None, protocol=paho.MQTTv5)
client.on_connect = on_connect

# enable TLS for secure connection
client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)
# set username and password
client.username_pw_set(os.getenv("MQTT_USERNAME"), os.getenv("MQTT_PASSWORD"))
# connect to HiveMQ Cloud on port 8883 (default for MQTT)
client.connect(os.getenv("MQTT_CLUSTER_URL"), 8883)

# setting callbacks, use separate functions like above for better visibility
client.on_subscribe = on_subscribe
client.on_message = on_message
client.on_publish = on_publish
client.on_disconnect = on_disconnect

class UserInput(BaseModel):
    message: str = Field(description="Message to be sent")

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        client.loop_start()
        logging.info(f"Starting messaging app")

        yield

    except KeyboardInterrupt:
        logging.info("\nStopping messaging app...")
    except Exception as e:
        logging.error(f"Error: {e}")
    finally:
        client.loop_stop()
        client.disconnect()
        logging.info("\nmessaging app stopped")

app = FastAPI(lifespan=lifespan)

@app.post("/")
async def publish_message(input: UserInput):
    message_data ={
            "timestamp": time.time(),
            "messenger_id": messenger_id,
            "message": input.message
        }
    try:
            client.publish(
                "monitoring/messages", 
                payload=json.dumps(message_data), 
                qos=1
            )
    except Exception as e:
        logging.error(f"Failed to publish memory data: {e}")

    return Response(status_code=status.HTTP_200_OK)

