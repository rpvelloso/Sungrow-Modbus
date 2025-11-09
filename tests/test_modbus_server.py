from time import sleep
from SungrowModbusTcpClient.SungrowModbusTcpClient import (
    AsyncSungrowModbusTcpClient,
    SungrowModbusTcpClient,
    GET_KEY,
    PRIV_KEY,
    HEADER,
    SungrowCryptoInitRequest,
    SungrowModbusTCPWrapper,
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
    def __init__(self, host: str = "127.0.0.1", port: int = 5020, crypto: bool = False) -> None:
        """Initialize server context and identity."""
        self.storage: ModbusDeviceContext
        self.context: ModbusServerContext
        self.identity: ModbusDeviceIdentification
        self.holding_registers: ModbusSequentialDataBlock
        self.input_registers: ModbusSequentialDataBlock
        self._mb_server: ModbusTcpServer | None = None
        self.host: str = host
        self.port: int = port
        self.test_number = random.randint(1, 0xFFFE)
        self.crypto = crypto
        self._pub_key: bytes = bytes([0xaa, 0xbb] * 8)
        self.decoder = SungrowModbusTCPWrapper(priv_key=PRIV_KEY)
        self.decoder.set_pub_key(self._pub_key)
        self._handshake_done = False
        self.setup_server()

    def setup_server(self) -> None:
        """Run server setup."""
        self.holding_registers = ModbusSequentialDataBlock(0x00, [self.test_number] * 100)
        self.input_registers = ModbusSequentialDataBlock(0x00, [self.test_number+1] * 100)
        self.storage = ModbusDeviceContext(
            hr=self.holding_registers, ir=self.input_registers
        )
        # This is set by SungrowCryptoInitRequest.update_datastore()
        self.storage.store['handshake_signal'] = False
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
            custom_pdu=[SungrowCryptoInitRequest] if self.crypto else None,
            trace_packet=self.trace_packet,
        )
        await self._mb_server.serve_forever()

    async def stop(self) -> None:
        """Stop server."""
        if self._mb_server:
            await self._mb_server.shutdown()
            self._mb_server = None

    def trace_packet(self, sending: bool, data: bytes) -> bytes:

        if self.crypto and not self._handshake_done and self.storage.store['handshake_signal']:
            # Rising edge on the handshake. Enable encryption after this send.
            self._handshake_done = True
            return data

        if not self.crypto or not self._handshake_done:
            return data

        if sending:
            return self.decoder._send_cypher(data)
        else:
            return self.decoder._recv_cypher(data)


@pytest.fixture
def modbus_server_fixture():
    # This awkward mess is to avoid having to implement a synchronous
    # test modbus server, so we run the async version in a separate thread.
    modbus_server = AsyncModbusServer()
    server_ready = threading.Event()

    def run_server():
        loop = asyncio.new_event_loop()
        modbus_server._loop = loop  # Save loop for teardown
        asyncio.set_event_loop(loop)
        async def start_and_signal():
            server_ready.set()
            await modbus_server.run_async_server()
        loop.run_until_complete(start_and_signal())

    th = threading.Thread(target=run_server, daemon=True)
    th.start()
    server_ready.wait(timeout=5)  # Wait for server to be ready
    sleep(1)  # I don't know. Sleepy server?
    try:
        yield modbus_server
    finally:
        # Stop the server using the correct loop
        modbus_server._loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(modbus_server.stop(), loop=modbus_server._loop)
        )
        th.join(timeout=2)
    sleep(1)  # Let the server shut down properly


@pytest.fixture
def crypto_modbus_server_fixture():
    # This awkward mess is to avoid having to implement a synchronous
    # test modbus server, so we run the async version in a separate thread.
    modbus_server = AsyncModbusServer(crypto=True)
    server_ready = threading.Event()

    def run_server():
        loop = asyncio.new_event_loop()
        modbus_server._loop = loop  # Save loop for teardown
        asyncio.set_event_loop(loop)
        async def start_and_signal():
            server_ready.set()
            await modbus_server.run_async_server()
        loop.run_until_complete(start_and_signal())

    th = threading.Thread(target=run_server, daemon=True)
    th.start()
    server_ready.wait(timeout=5)  # Wait for server to be ready
    sleep(1)  # I don't know. Sleepy server?
    try:
        yield modbus_server
    finally:
        # Stop the server using the correct loop
        modbus_server._loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(modbus_server.stop(), loop=modbus_server._loop)
        )
        th.join(timeout=2)
    sleep(1)  # Let the server shut down properly


@pytest.mark.asyncio
async def test_async_no_crypto(modbus_server_fixture: AsyncModbusServer):
    modbus_client = AsyncSungrowModbusTcpClient(host="127.0.0.1", port=5020)
    await modbus_client.connect()
    result = await modbus_client.read_holding_registers(1, count=1, device_id=1)
    assert not result.isError()
    assert result.registers[0] == modbus_server_fixture.test_number
    # result = await modbus_client.read_input_registers(1, count=1, device_id=1)
    # assert not result.isError()
    # assert result.registers[0] == modbus_server_fixture.test_number + 1
    modbus_client.close()

@pytest.mark.asyncio
async def test_synchronous_no_crypto(modbus_server_fixture: AsyncModbusServer):

    modbus_client = SungrowModbusTcpClient(host="127.0.0.1", port=5020)
    assert modbus_client.connect()
    result = modbus_client.read_holding_registers(1, count=1, device_id=1)
    assert not result.isError()
    assert result.registers[0] == modbus_server_fixture.test_number
    # result = modbus_client.read_input_registers(1, count=1, device_id=1)
    # assert not result.isError()
    # assert result.registers[0] == modbus_server_fixture.test_number + 1
    modbus_client.close()

@pytest.mark.asyncio
async def test_async_crypto(crypto_modbus_server_fixture: AsyncModbusServer):

    modbus_client = AsyncSungrowModbusTcpClient(host="127.0.0.1", port=5020)
    await modbus_client.connect()
    result = await modbus_client.read_holding_registers(1, count=1, device_id=1)
    assert not result.isError()
    assert result.registers[0] == crypto_modbus_server_fixture.test_number
    # result = await modbus_client.read_input_registers(1, count=1, device_id=1)
    # assert not result.isError()
    # assert result.registers[0] == crypto_modbus_server_fixture.test_number + 1
    modbus_client.close()

@pytest.mark.asyncio
async def test_synchronous_crypto(crypto_modbus_server_fixture: AsyncModbusServer):

    modbus_client = SungrowModbusTcpClient(host="127.0.0.1", port=5020)
    assert modbus_client.connect()
    result = modbus_client.read_holding_registers(1, count=1, device_id=1)
    assert not result.isError()
    assert result.registers[0] == crypto_modbus_server_fixture.test_number
    # result = modbus_client.read_input_registers(1, count=1, device_id=1)
    # assert not result.isError()
    # assert result.registers[0] == crypto_modbus_server_fixture.test_number + 1
    modbus_client.close()
