import time
import os
import logging
import json
import paho.mqtt.client as paho
from datetime import datetime
from collections import defaultdict

from paho import mqtt
from dotenv import load_dotenv

load_dotenv()

log_level = os.getenv("LOG_LEVEL", "INFO")
subscriber_id = os.getenv("SUBSCRIBER_ID", "monitoring-subscriber-001")

logging.basicConfig(
    level=log_level,
    format=f'%(asctime)s - {subscriber_id} - %(levelname)s - %(message)s'
)

latest_readings = defaultdict(dict)
message_counts = defaultdict(int)

def process_memory_data(data):
    try:
        sensor_id = data.get('sensor_id', 'unknown')
        system_memory = data.get('system_memory', 0)
        timestamp = data.get('timestamp', time.time())
        
        latest_readings[sensor_id]['memory'] = {
            'system_memory_percent': system_memory,
            'timestamp': timestamp,
            'readable_time': datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        }
        
        message_counts['memory'] += 1
        
        logging.info(f"MEMORY | {sensor_id} | RAM: {system_memory:.1f}% | {latest_readings[sensor_id]['memory']['readable_time']}")
        
        return True
    except Exception as e:
        logging.error(f"Error processing memory data: {e}")
        return False

def process_cpu_data(data):
    try:
        sensor_id = data.get('sensor_id', 'unknown')
        cpu_percent = data.get('cpu_percent', 0)
        timestamp = data.get('timestamp', time.time())
        
        latest_readings[sensor_id]['cpu'] = {
            'cpu_percent': cpu_percent,
            'timestamp': timestamp,
            'readable_time': datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        }
        
        message_counts['cpu'] += 1
        
        logging.info(f"CPU | {sensor_id} | CPU usage: {cpu_percent:.1f}% | {latest_readings[sensor_id]['cpu']['readable_time']}")
        
        return True
    except Exception as e:
        logging.error(f"Error processing CPU data: {e}")
        return False

def print_summary():
    """Print a summary of all latest readings"""
    if not latest_readings:
        logging.info("SUMMARY | No data received yet")
        return
    
    logging.info("=" * 60)
    logging.info("MONITORING SUMMARY")
    logging.info(f"Total messages: Memory={message_counts['memory']}, CPU={message_counts['cpu']}")
    
    for sensor_id, readings in latest_readings.items():
        logging.info(f"Sensor: {sensor_id}")
        
        if 'memory' in readings:
            mem_data = readings['memory']
            logging.info(f"Memory: {mem_data['system_memory_percent']:.1f}% @ {mem_data['readable_time']}")
        
        if 'cpu' in readings:
            cpu_data = readings['cpu']
            logging.info(f"CPU: {cpu_data['cpu_percent']:.1f}% @ {cpu_data['readable_time']}")
    
    logging.info("=" * 60)

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logging.info(f"Connected to MQTT broker successfully")
        
        topics_to_subscribe = [
            ("monitoring/memory", 1),
            ("monitoring/cpu", 1),
        ]
        
        for topic, qos in topics_to_subscribe:
            result = client.subscribe(topic, qos)
            logging.info(f"Subscribed to {topic} with QoS {qos}")
    else:
        logging.error(f"Failed to connect to MQTT broker. Code: {rc}")

def on_subscribe(client, userdata, mid, granted_qos, properties=None):
    logging.info(f"Subscription confirmed - mid: {mid}, QoS: {granted_qos}")

def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            logging.error(f"Invalid JSON received from {topic}: {payload}")
            return
        
        if topic == "monitoring/memory":
            process_memory_data(data)
        elif topic == "monitoring/cpu":
            process_cpu_data(data)
        else:
            logging.info(f"Received from {topic}: {data}")
            
    except Exception as e:
        logging.error(f"Error processing message from {topic}: {e}")

def on_disconnect(client, userdata, rc):
    if rc != 0:
        logging.warning(f"Unexpected MQTT disconnection. Code: {rc}")
    else:
        logging.info("Disconnected from MQTT broker")

client = paho.Client(client_id=subscriber_id, userdata=None, protocol=paho.MQTTv5)
client.on_connect = on_connect
client.on_subscribe = on_subscribe
client.on_message = on_message
client.on_disconnect = on_disconnect

client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)
client.username_pw_set(os.getenv("MQTT_USERNAME"), os.getenv("MQTT_PASSWORD"))

client.connect(os.getenv("MQTT_CLUSTER_URL"), 8883)

def summary_reporter():
    summary_interval = int(os.getenv("SUMMARY_INTERVAL", "120"))
    
    while True:
        time.sleep(summary_interval)
        print_summary()

if __name__ == "__main__":
    client.loop_start()
    

    try:
        logging.info("MQTT Subscriber started - listening for sensor data...")
        summary_reporter()
        
    except KeyboardInterrupt:
        logging.info("\nStopping MQTT subscriber...")
    except Exception as e:
        logging.error(f"Error: {e}")
    finally:
        client.loop_stop()
        client.disconnect()
        print_summary()
        logging.info("\nMQTT subscriber stopped")