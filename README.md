# Sungrow-Modbus
### TCP Client for Sungrow Devices with AES128 ECB encryption

### Class based on pymodbus.ModbusTcpClient, completely interchangeable, just replace ModbusTcpClient() with SungrowModbusTcpClient()

### Home Assistant Custom Component - tested with HASS docker v2025.8.3 and Sungrow SG4K inverter

- ALL the component code was ripped from the modbus custom component dev repository ```https://github.com/pymodbus-dev/homeassistant_modbus```. Unused code was removed.

- Copy the folder ```sungrowmodbus``` into your custom_components folder and add the integration to configuration.yaml. Example config provided for SG4K inverter in ```sungrow_sg4k.yaml``` 

- For standalone use (outside home assistant): copy the ```sungrow.py``` file into your project and import the class ```AsyncSungrowModbusTcpClient```. It is a decorator on top of the async modbus TCP client (```AsyncModbusTcpClient```) that handles encryption transparently.
