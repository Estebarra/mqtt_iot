import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import paho.mqtt.client as paho
from paho import mqtt
import json
import threading
import time
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import logging
from collections import deque
import traceback

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Streamlit page config
st.set_page_config(
    page_title="Tablero de Monitoreo",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

class MQTTHandler:
    def __init__(self):
        self.client = None
        # Thread-safe data storage
        self.memory_data = deque(maxlen=100)
        self.cpu_data = deque(maxlen=100)
        self.messages = deque(maxlen=50)
        self.connected = False
        self.connection_errors = []
        self.data_lock = threading.Lock()
        self.setup_client()
    
    def setup_client(self):
        # MQTT callbacks
        def on_connect(client, userdata, flags, rc, properties=None):
            if rc == 0:
                self.connected = True
                logger.info("Connected to MQTT broker")
                
                # Subscribe to topics
                client.subscribe("monitoring/memory", qos=1)
                client.subscribe("monitoring/cpu", qos=1) 
                client.subscribe("monitoring/messages", qos=1)
                logger.info("Subscribed to monitoring topics")
            else:
                self.connected = False
                error_msg = f"Failed to connect to MQTT broker: {rc}"
                logger.error(error_msg)
                self.connection_errors.append(f"{datetime.now()}: {error_msg}")
        
        def on_message(client, userdata, msg):
            try:
                topic = msg.topic
                payload = json.loads(msg.payload.decode())
                timestamp = datetime.fromtimestamp(payload.get('timestamp', time.time()))
                
                logger.info(f"Received message on {topic}: {payload}")
                
                # Use thread-safe operations
                with self.data_lock:
                    if topic == "monitoring/memory":
                        # Check if required fields exist
                        if 'system_memory' in payload:
                            data_point = {
                                'timestamp': timestamp,
                                'sensor_id': payload.get('sensor_id', 'unknown'),
                                'memory_percent': float(payload.get('system_memory', 0))
                            }
                            self.memory_data.append(data_point)
                            logger.info(f"Added memory data point: {data_point}")
                        else:
                            logger.warning(f"Missing 'system_memory' field in payload: {payload}")
                            
                    elif topic == "monitoring/cpu":
                        if 'cpu_percent' in payload:
                            data_point = {
                                'timestamp': timestamp,
                                'sensor_id': payload.get('sensor_id', 'unknown'),
                                'cpu_percent': float(payload.get('cpu_percent', 0))
                            }
                            self.cpu_data.append(data_point)
                            logger.info(f"Added CPU data point: {data_point}")
                        else:
                            logger.warning(f"Missing 'cpu_percent' field in payload: {payload}")
                            
                    elif topic == "monitoring/messages":
                        message_data = {
                            'timestamp': timestamp,
                            'messenger_id': payload.get('messenger_id', 'unknown'),
                            'message': payload.get('message', 'No message')
                        }
                        self.messages.append(message_data)
                        logger.info(f"Added message: {message_data}")
                        
            except json.JSONDecodeError as e:
                error_msg = f"JSON decode error: {e}, payload: {msg.payload}"
                logger.error(error_msg)
                self.connection_errors.append(f"{datetime.now()}: {error_msg}")
            except Exception as e:
                error_msg = f"Error processing message: {e}, traceback: {traceback.format_exc()}"
                logger.error(error_msg)
                self.connection_errors.append(f"{datetime.now()}: {error_msg}")
        
        def on_disconnect(client, userdata, rc):
            self.connected = False
            if rc != 0:
                error_msg = f"Unexpected MQTT disconnection: {rc}"
                logger.warning(error_msg)
                self.connection_errors.append(f"{datetime.now()}: {error_msg}")
        
        # Create MQTT client
        self.client = paho.Client(
            client_id="streamlit_dashboard", 
            userdata=None, 
            protocol=paho.MQTTv5
        )
        
        # Set callbacks
        self.client.on_connect = on_connect
        self.client.on_message = on_message
        self.client.on_disconnect = on_disconnect
        
        # Configure TLS and credentials
        try:
            self.client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)
            username = os.getenv("MQTT_USERNAME")
            password = os.getenv("MQTT_PASSWORD")
            
            if not username or not password:
                error_msg = "MQTT credentials not found in environment variables"
                logger.error(error_msg)
                self.connection_errors.append(f"{datetime.now()}: {error_msg}")
            else:
                self.client.username_pw_set(username, password)
                
        except Exception as e:
            error_msg = f"Error setting up MQTT client: {e}"
            logger.error(error_msg)
            self.connection_errors.append(f"{datetime.now()}: {error_msg}")
    
    def connect(self):
        try:
            mqtt_url = os.getenv("MQTT_CLUSTER_URL")
            if not mqtt_url:
                error_msg = "MQTT_CLUSTER_URL not found in environment variables"
                logger.error(error_msg)
                self.connection_errors.append(f"{datetime.now()}: {error_msg}")
                return False
                
            self.client.connect(mqtt_url, 8883, 60)
            self.client.loop_start()
            return True
        except Exception as e:
            error_msg = f"Failed to connect to MQTT: {e}"
            logger.error(error_msg)
            self.connection_errors.append(f"{datetime.now()}: {error_msg}")
            return False
    
    def get_data(self):
        """Thread-safe method to get current data"""
        with self.data_lock:
            return {
                'memory_data': list(self.memory_data),
                'cpu_data': list(self.cpu_data), 
                'messages': list(self.messages),
                'connected': self.connected,
                'errors': list(self.connection_errors[-10:])  # Last 10 errors
            }
    
    def disconnect(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()

# Initialize session state for MQTT handler
if 'mqtt_handler' not in st.session_state:
    st.session_state.mqtt_handler = MQTTHandler()
    if st.session_state.mqtt_handler.connect():
        logger.info("MQTT handler initialized and connected")
    else:
        logger.error("Failed to initialize MQTT connection")

# Helper functions
def create_gauge_chart(value, title, max_value=100, color_threshold=80):
    """Create a gauge chart for metrics"""
    try:
        color = "green" if value < color_threshold else "orange" if value < 90 else "red"
        
        fig = go.Figure(go.Indicator(
            mode = "gauge+number+delta",
            value = value,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': title},
            delta = {'reference': color_threshold},
            gauge = {
                'axis': {'range': [None, max_value]},
                'bar': {'color': color},
                'steps': [
                    {'range': [0, color_threshold], 'color': "lightgray"},
                    {'range': [color_threshold, 90], 'color': "gray"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 90
                }
            }
        ))
        
        fig.update_layout(height=300)
        return fig
    except Exception as e:
        logger.error(f"Error creating gauge chart: {e}")
        # Return a simple figure with error message
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error creating chart: {str(e)}", 
            xref="paper", yref="paper", 
            x=0.5, y=0.5, showarrow=False
        )
        return fig

def create_time_series_chart(data, y_column, title, color):
    """Create time series chart"""
    try:
        if not data:
            fig = go.Figure()
            fig.add_annotation(
                text="No data available", 
                xref="paper", yref="paper", 
                x=0.5, y=0.5, showarrow=False
            )
            fig.update_layout(title=title, height=400)
            return fig
        
        df = pd.DataFrame(data)
        
        # Ensure the column exists
        if y_column not in df.columns:
            fig = go.Figure()
            fig.add_annotation(
                text=f"Column '{y_column}' not found in data", 
                xref="paper", yref="paper", 
                x=0.5, y=0.5, showarrow=False
            )
            fig.update_layout(title=title, height=400)
            return fig
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['timestamp'],
            y=df[y_column],
            mode='lines+markers',
            name=title,
            line=dict(color=color, width=2),
            marker=dict(size=4)
        ))
        
        fig.update_layout(
            title=title,
            xaxis_title="Time",
            yaxis_title="Percentage (%)",
            height=400,
            showlegend=False
        )
        
        return fig
    except Exception as e:
        logger.error(f"Error creating time series chart: {e}")
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error creating chart: {str(e)}", 
            xref="paper", yref="paper", 
            x=0.5, y=0.5, showarrow=False
        )
        fig.update_layout(title=title, height=400)
        return fig

# Main app
def main():
    st.title("📊 Tablero de monitoreo")
    st.markdown("---")
    
    try:
        # Get current data from MQTT handler
        mqtt_data = st.session_state.mqtt_handler.get_data()
        memory_data = mqtt_data['memory_data']
        cpu_data = mqtt_data['cpu_data']
        messages = mqtt_data['messages']
        mqtt_connected = mqtt_data['connected']
        connection_errors = mqtt_data['errors']
        
        # Enhanced debug information
        with st.expander("🔧 Debug", expanded=False):
            st.write(f"**Lecturas de memoria:** {len(memory_data)}")
            st.write(f"**Lecturas de CPU:** {len(cpu_data)}")
            st.write(f"**Mensajes:** {len(messages)}")
            st.write(f"**MQTT Conectado:** {mqtt_connected}")
            
            if memory_data:
                st.write("**Última información de memoria:**", memory_data[-1])
            if cpu_data:
                st.write("**última información de CPU:**", cpu_data[-1])
                
            if connection_errors:
                st.error("**Recent Errors:**")
                for error in connection_errors:
                    st.text(error)
        
    except Exception as e:
        st.error(f"Error getting MQTT data: {e}")
        st.code(traceback.format_exc())
        memory_data = []
        cpu_data = []
        messages = []
        mqtt_connected = False
    
    # Sidebar
    with st.sidebar:
        st.header("📡 Estado de la Conexión")
        if mqtt_connected:
            st.success("🟢 MQTT Conectado")
        else:
            st.error("🔴 MQTT Desconectado")
            if st.button("Reconectar"):
                if st.session_state.mqtt_handler.connect():
                    st.success("Reconexión exitosa!")
                else:
                    st.error("Reconexión fallida!")
                st.rerun()
        
        st.header("⚙️ Configuración")
        auto_refresh = st.checkbox("Actualización automática", value=False)  # Changed default to False
        refresh_interval = st.slider("Intervalo de actualización (segundos)", 1, 10, 5)
        
        # Manual refresh button
        if st.button("🔄 Actualizar ahora"):
            st.rerun()
    
    # Main dashboard
    col1, col2 = st.columns(2)
    
    # Current metrics
    current_memory = memory_data[-1]['memory_percent'] if memory_data else 0
    current_cpu = cpu_data[-1]['cpu_percent'] if cpu_data else 0
    
    with col1:
        st.subheader("💾 Uso de Memoria")
        fig_memory_gauge = create_gauge_chart(current_memory, "% Memoria", color_threshold=75)
        st.plotly_chart(fig_memory_gauge, use_container_width=True)
    
    with col2:
        st.subheader("⚡ Uso de CPU") 
        fig_cpu_gauge = create_gauge_chart(current_cpu, "% CPU", color_threshold=70)
        st.plotly_chart(fig_cpu_gauge, use_container_width=True)
    
    # Time series charts
    col3, col4 = st.columns(2)
    
    with col3:
        st.subheader("📈 Historial de uso de memoria")
        fig_memory_time = create_time_series_chart(
            memory_data, 
            'memory_percent', 
            'Uso de memoria a través del tiempo',
            '#FF6B6B'
        )
        st.plotly_chart(fig_memory_time, use_container_width=True)
    
    with col4:
        st.subheader("📈 Historial de uso de CPU")
        fig_cpu_time = create_time_series_chart(
            cpu_data, 
            'cpu_percent', 
            'Uso de CPU a través del tiempo', 
            '#4ECDC4'
        )
        st.plotly_chart(fig_cpu_time, use_container_width=True)
    
    # Messages section
    st.subheader("💬 Mensajes recientes")
    
    if messages:
        messages_df = pd.DataFrame(messages)
        messages_df['timestamp'] = pd.to_datetime(messages_df['timestamp'])
        messages_df = messages_df.sort_values('timestamp', ascending=False)
        
        # Display messages in a nice format
        for _, message in messages_df.head(10).iterrows():
            with st.container():
                col_time, col_id, col_msg = st.columns([2, 2, 6])
                with col_time:
                    st.caption(message['timestamp'].strftime("%H:%M:%S"))
                with col_id:
                    st.caption(f"ID: {message['messenger_id']}")
                with col_msg:
                    st.write(message['message'])
                st.divider()
    else:
        st.info("No se han recibido mensajes.")
    
    # Statistics
    st.subheader("📊 Estadísticas")
    
    col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
    
    with col_stat1:
        avg_memory = sum(d['memory_percent'] for d in memory_data) / len(memory_data) if memory_data else 0
        st.metric("% Memoria promedio", f"{avg_memory:.1f}")
    
    with col_stat2:
        avg_cpu = sum(d['cpu_percent'] for d in cpu_data) / len(cpu_data) if cpu_data else 0
        st.metric("% CPU promedio", f"{avg_cpu:.1f}")
    
    with col_stat3:
        st.metric("Lecturas de memoria", len(memory_data))
    
    with col_stat4:
        st.metric("Lecturas de CPU", len(cpu_data))
    
    # Auto refresh at the end to avoid blocking
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()

if __name__ == "__main__":
    main()