from SungrowModbusTcpClient.SungrowModbusTcpClient import (
    AsyncSungrowModbusTcpClient,
    SungrowModbusTcpClient
)
import pytest
import pytest_asyncio
import random
import asyncio
import threading

from pymodbus import (
    ModbusDeviceIdentification,
)
from pymodbus.server import ModbusTcpServer
from pymodbus.constants import ExcCodes
from pymodbus.datastore import (
    ModbusDeviceContext,
    ModbusSequentialDataBlock,
    ModbusServerContext,
)

class AsyncModbusServer:
    """MODBUS server class."""
    def __init__(self, host: str = "0.0.0.0", port: int = 5020) -> None:
        """Initialize server context and identity."""
        self.storage: ModbusDeviceContext
        self.context: ModbusServerContext
        self.identity: ModbusDeviceIdentification
        self.holding_registers: ModbusSequentialDataBlock
        self.input_registers: ModbusSequentialDataBlock
        self._mb_server: ModbusTcpServer | None = None
        self.host: str = host
        self.port: int = port
        self.test_number = random.randint(1, 0xFFFF)
        self.setup_server()

    def setup_server(self) -> None:
        """Run server setup."""
        self.holding_registers = ModbusSequentialDataBlock(0x00, [self.test_number] * 100)
        self.input_registers = ModbusSequentialDataBlock(0x00, [0] * 100)
        self.storage = ModbusDeviceContext(
            hr=self.holding_registers, ir=self.input_registers
        )
        self.context = ModbusServerContext(devices=self.storage)

    async def set_holding_register(self, address: int, value: int) -> None:
        """Set holding register value."""
        self.holding_registers.setValues(address + 1, [value])

    async def get_holding_register(self, address: int) -> int:
        """Get holding register value."""
        result = self.holding_registers.getValues(address + 1, count=1)
        if type(result) is ExcCodes:
            raise ValueError(f"Error getting holding register at address {address}")
        if type(result) is list and len(result) > 0:
            return result[0]
        raise ValueError(f"Error getting holding register at address {address}")

    async def run_async_server(self) -> None:
        """Run server."""
        print(f"Starting MODBUS TCP server on {self.host}:{self.port}")
        address = (self.host, self.port)
        self._mb_server = ModbusTcpServer(
            context=self.context,  # Data storage
            address=address,  # listen address
        )
        await self._mb_server.serve_forever()

    async def stop(self) -> None:
        """Stop server."""
        if self._mb_server:
            await self._mb_server.shutdown()
            self._mb_server = None


@pytest_asyncio.fixture
async def async_modbus_fixture():
    modbus_server = AsyncModbusServer()
    server_task = asyncio.create_task(modbus_server.run_async_server())
    await asyncio.sleep(1)  # Give server time to start
    try:
        yield modbus_server
        await modbus_server.stop()
    finally:
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass


@pytest.fixture
def synchronous_async_mqtt_fixture():
    modbus_server = AsyncModbusServer()
    server_ready = threading.Event()

    def run_server():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        async def start_and_signal():
            server_ready.set()
            await modbus_server.run_async_server()
        loop.run_until_complete(start_and_signal())

    th = threading.Thread(target=run_server, daemon=True)
    th.start()
    server_ready.wait(timeout=5)  # Wait for server to be ready
    try:
        yield modbus_server
    finally:
        # Stop the server
        loop = asyncio.get_event_loop()
        loop.run_until_complete(modbus_server.stop())
        th.join(timeout=2)


@pytest.mark.asyncio
async def test_async_no_crypto(async_modbus_fixture: AsyncModbusServer):
    modbus_client = AsyncSungrowModbusTcpClient(host="localhost", port=5020)
    await modbus_client.connect()
    result = await modbus_client.read_holding_registers(1, count=1, device_id=1)
    assert not result.isError()
    assert result.registers[0] == async_modbus_fixture.test_number
    modbus_client.close()

@pytest.mark.asyncio
async def test_synchronous_no_crypto(synchronous_async_mqtt_fixture: AsyncModbusServer):

    modbus_client = SungrowModbusTcpClient(host="localhost", port=5020)
    assert modbus_client.connect()
    result = modbus_client.read_holding_registers(1, count=1, device_id=1)
    assert not result.isError()
    assert result.registers[0] == synchronous_async_mqtt_fixture.test_number
    modbus_client.close()