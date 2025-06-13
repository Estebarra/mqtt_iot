import time
import os
import psutil
import threading
import logging
import json
import paho.mqtt.client as paho

from paho import mqtt
from dotenv import load_dotenv

load_dotenv()

log_level = os.getenv("LOG_LEVEL", "INFO").upper()

sensor_id = os.getenv("SENSOR_ID")

logging.basicConfig(
    level=log_level,
    format=f'%(asctime)s - {sensor_id} - %(levelname)s - %(message)s'
)

def memory_monitor():

    publish_interval = int(os.getenv("PUBLISH_INTERVAL"))

    while True:
        system_memory = psutil.virtual_memory()

        logging.info(f"System RAM: {system_memory.percent:.1f}%")

        memory_data ={
            "timestamp": time.time(),
            "sensor_id": sensor_id,
            "system_memory": system_memory.percent
        }
        
        try:
            client.publish(
                "monitoring/memory", 
                payload=json.dumps(memory_data), 
                qos=1
            )
        except Exception as e:
            logging.error(f"Failed to publish memory data: {e}")
        
        time.sleep(publish_interval)

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
client = paho.Client(client_id=f"{sensor_id}_memory", userdata=None, protocol=paho.MQTTv5)
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

if __name__=="__main__":
    client.loop_start()

    try:
        logging.info(f"Starting memory monitoring")
        memory_monitor()

    except KeyboardInterrupt:
        logging.info("\nStopping memory monitor...")
    except Exception as e:
        logging.error(f"Error: {e}")
    finally:
        client.loop_stop()
        client.disconnect()
        logging.info("\nmemory sensor stopped")
