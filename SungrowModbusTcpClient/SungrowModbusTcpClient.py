from pymodbus.client import (
    ModbusTcpClient,
    AsyncModbusTcpClient,
)
from pymodbus.pdu.register_message import ReadInputRegistersResponse
from pymodbus.datastore import ModbusDeviceContext
from pymodbus.exceptions import ModbusIOException
from pymodbus.pdu import ModbusPDU
from Cryptodome.Cipher import AES
from pymodbus.logging import Log
from collections.abc import Callable

PRIV_KEY = b"Grow#0*2Sun68CbE"
NO_CRYPTO1 = b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
NO_CRYPTO2 = b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
GET_KEY = b"\x68\x68\x00\x00\x00\x06\xf7\x04\x0a\xe7\x00\x08"
HEADER = bytes([0x68, 0x68])


class SungrowModbusTcpClient(ModbusTcpClient):
    def __init__(self, priv_key=PRIV_KEY, **kwargs):
        # Remove the caller's trace_packet function, if any.
        callers_trace_packet = kwargs.pop("trace_packet", None)
        self._sg_crypto = SungrowModbusCryptoManager(
            priv_key=priv_key, trace_packet=callers_trace_packet
        )
        # Insert our own trace_packet function.
        kwargs["trace_packet"] = self._sg_crypto.trace_packet
        super().__init__(**kwargs)
        self._connected = False

    def connect(self) -> bool:
        Log.debug("*** SungrowModbusTcpClient *** connect")
        if self._connected:
            return True

        self._connected = super().connect()
        if not self._connected:
            return self._connected

        request = SungrowCryptoInitRequest()
        # Register the custom handshake PDU
        self.register(SungrowCryptoInitResponse)
        try:
            # Send and receive the handshake request/response,
            # extracting the public key from the response.
            response = self.execute(no_response_expected=False, request=request)
            if (
                isinstance(response, SungrowCryptoInitResponse)
                and response.pub_key is not None
            ):
                self._sg_crypto.set_pub_key(response.pub_key)
                self._connected = True
                return True
        except ModbusIOException:  # pragma: no cover
            Log.info("*** SungrowModbusTcpClient *** Server doesn't support Sungrow handshake")
        finally:
            # Re-register the normal 0x04 Read Input Registers PDU
            self.register(ReadInputRegistersResponse)

        return self._connected

    def close(self):
        Log.debug("*** SungrowModbusTcpClient *** close")
        super().close()
        self._sg_crypto.reset()
        self._connected = False


class AsyncSungrowModbusTcpClient(AsyncModbusTcpClient):
    def __init__(self, priv_key=PRIV_KEY, **kwargs):
        # Remove the caller's trace_packet function, if any.
        callers_trace_packet = kwargs.pop("trace_packet", None)
        self._sg_crypto = SungrowModbusCryptoManager(
            priv_key=priv_key, trace_packet=callers_trace_packet
        )
        # Insert our own trace_packet function.
        kwargs["trace_packet"] = self._sg_crypto.trace_packet
        super().__init__(**kwargs)

    async def connect(self):
        Log.debug("*** AsyncSungrowModbusTcpClient *** connect")

        result = await super().connect()
        if not result:
            return result

        request = SungrowCryptoInitRequest()
        # Register the custom handshake PDU
        self.register(SungrowCryptoInitResponse)
        try:
            # Send and receive the handshake request/response,
            # extracting the public key from the response.
            response = await self.execute(no_response_expected=False, request=request)
            if (
                isinstance(response, SungrowCryptoInitResponse)
                and response.pub_key is not None
            ):
                self._sg_crypto.set_pub_key(response.pub_key)
        except ModbusIOException:  # pragma: no cover
            Log.info("*** AsyncSungrowModbusTcpClient *** Server doesn't support Sungrow handshake")
        finally:
            # Re-register the normal 0x04 Read Input Registers PDU
            self.register(ReadInputRegistersResponse)

        return result

    def close(self):
        Log.debug("*** AsyncSungrowModbusTcpClient *** close")
        super().close()
        self._sg_crypto.reset()


class SungrowCryptoException(ModbusIOException):
    """Exception for Sungrow Crypto errors."""

    pass


class SungrowCryptoInitPDU(ModbusPDU):
    function_code = 0x04

    # The transaction needs to be immutable for these classes
    @property
    def transaction_id(self) -> int:
        return 0x6868

    @transaction_id.setter
    def transaction_id(self, value: int) -> None:
        pass

    @property
    def device_id(self) -> int:
        return 0xF7

    @device_id.setter
    def device_id(self, value: int) -> None:
        pass


class SungrowCryptoInitRequest(SungrowCryptoInitPDU):
    rtu_frame_size = 6

    def __init__(self, values=None, dev_id: int = 0xF7, transaction=0x6868):
        super().__init__(dev_id=dev_id, transaction_id=transaction)
        self.key_request: bytes | None = None

    def encode(self):
        return GET_KEY[8:]

    def decode(self, data: bytes):
        self.key_request = data

    async def update_datastore(self, context: ModbusDeviceContext) -> ModbusPDU:
        # This is a mild crime, but it's only used in the tests, so...
        context.store["handshake_signal"] = True
        return SungrowCryptoInitResponse()


class SungrowCryptoInitResponse(SungrowCryptoInitPDU):
    rtu_frame_size = 17

    def __init__(self, values=None, dev_id: int = 0xF7, transaction=0x6868):
        super().__init__(dev_id=dev_id, transaction_id=transaction)
        # This response is used by the Sungrow inverter simulator in the tests.
        # This demo pubkey is not used in production clients.
        self._demo_pub_key: bytes = bytes([0xAA, 0xBB] * 8)
        self.pub_key: bytes | None = None

    def encode(self):
        return bytes([0x00]) + self._demo_pub_key

    def decode(self, data: bytes):
        if len(data) != 17:
            raise SungrowCryptoException("Invalid SungrowCryptoInitResponse length")
        possible_pub_key = data[1:]
        if (possible_pub_key == NO_CRYPTO1) or (possible_pub_key == NO_CRYPTO2):
            self.pub_key = None
            return
        self.pub_key = possible_pub_key
        print("Received Sungrow public key:", self.pub_key.hex())


class SungrowModbusCryptoManager:
    """
    This class handles the cryptographic decoding/encoding the Sungrow
    Modbus TCP comms. It provides a `trace_packet` function that can be
    passed to the ModbusTcpClient/AsyncModbusTcpClient to intercept the
    raw bytes being sent/received, and perform the necessary encryption/
    decryption.
    The `trace_packet` function will pass through bytes as-is until the
    crypto handshake has taken place, and the inverter's public key has been
    set using the `set_pub_key` method. After that, it will encrypt outgoing
    packets and decrypt incoming packets automatically.
    """

    def __init__(
        self,
        priv_key=PRIV_KEY,
        trace_packet: Callable[[bool, bytes], bytes] | None = None,
    ):
        # Save the caller's trace_packet function, if present.
        self._caller_trace_packet: Callable[[bool, bytes], bytes] | None = trace_packet
        self._priv_key = priv_key
        self.reset()
        self._pub_key: bytes | None = None
        self._crypto_enabled: bool = False
        self._transactionID: bytes = bytes([0x00, 0x00])

    def set_pub_key(self, pub_key: bytes):
        self._pub_key = pub_key
        self._setup()

    def reset(self):
        Log.debug("*** AsyncSungrowModbusTcpClient *** reset")
        self._crypto_enabled = False
        self._fifo = bytes()
        self._key = None

    def _setup(self):
        Log.debug("*** AsyncSungrowModbusTcpClient *** setup pub_key {}", self._pub_key)
        self._key = bytes(a ^ b for (a, b) in zip(self._pub_key, self._priv_key))
        self._aes_ecb = AES.new(self._key, AES.MODE_ECB)
        self._crypto_enabled = True

    def _send_cypher(self, request: bytes) -> bytes:
        length = len(request)
        padding = 16 - (length % 16)
        self._transactionID = request[:2]
        request = HEADER + bytes(request[2:]) + bytes([0xFF] * padding)
        crypto_header = bytes([1, 0, length, padding])
        return crypto_header + self._aes_ecb.encrypt(request)

    def _recv_cypher(self, data: bytes) -> bytes:
        self._fifo = self._fifo + data
        output = bytes()
        while len(self._fifo) >= 4:
            packet_len = int(self._fifo[2])
            padding = int(self._fifo[3])
            length = packet_len + padding + 4
            if len(self._fifo) >= length:
                encrypted_packet = self._fifo[4:length]
                self._fifo = self._fifo[length:]
                packet = self._aes_ecb.decrypt(encrypted_packet)
                packet = self._transactionID + packet[2:]
                output += packet
            else:
                break
        return output

    def trace_packet(self, sending: bool, data: bytes) -> bytes:
        """
        This function is called when sending or receiving bytes on the network.
        It handles encryption/decryption as needed, and calls the original
        trace_packet function provided by the caller, if any.
        """
        if sending:
            if self._caller_trace_packet:
                data = self._caller_trace_packet(sending, data)
            if self._crypto_enabled:
                data = self._send_cypher(data)
        else:
            # Receiving
            if self._crypto_enabled:
                data = self._recv_cypher(data)
            if self._caller_trace_packet:
                self._caller_trace_packet(sending, data)
        return data
